from io import BytesIO
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from auth import logout_button
from config import DEFAULTS
from core import *
from github_reports import list_reports, load_report, save_report


def render_planning() -> None:
    logout_button('tedarik_logout')
    # UI
    # ------------------------------------------------------------
    st.title("YR Logistics Dashboard")

    st.write(
        "Supply girişlerini, APO çıkış forecastini ve ürün tipi dosyasını yükleyerek "
        "haftalık Ekol stok, palet, ADR palet ve tır hesabını oluşturabilirsiniz."
    )

    with st.sidebar:
        st.header("Dosyalar")

        supply_file = st.file_uploader("Supply dosyası", type=["xlsx", "xlsm"])
        apo_file = st.file_uploader("APO Forecast dosyası", type=["xlsx", "xlsm"])
        mapping_file = st.file_uploader("Ürün Tipi + Kampanya + ADR dosyası", type=["xlsx", "xlsm"])
        ekol_file = st.file_uploader("Ekol Depo Data Dosyası", type=["xlsx", "xlsm"])

        st.header("Palet Parametreleri")
        ana_palet_ici = st.number_input("Ana Ürün Palet İçi", min_value=1, value=2400, step=50)
        mini_palet_ici = st.number_input("Mini Sample Palet İçi", min_value=1, value=15000, step=100)
        adr_palet_ici = st.number_input("ADR Palet İçi", min_value=1, value=5540, step=10)

        sarf_palet = st.number_input("Haftalık Sarf Palet", min_value=0.0, value=250.0, step=0.5)
        tir_kapasitesi = st.number_input("1 Tır Kaç Palet?", min_value=1, value=40, step=1)

        st.header("Depo Kapasite Parametreleri")
        depo_kapasitesi = st.number_input("Depo Maksimum Palet Kapasitesi", min_value=1.0, value=1100.0, step=100.0)
        takip_esigi = st.number_input("Takip Eşiği (%)", min_value=0.0, max_value=100.0, value=85.0, step=1.0)
        kritik_esigi = st.number_input("Kritik Eşiği (%)", min_value=0.0, max_value=100.0, value=99.0, step=1.0)

        st.header("Başlangıç Stok")
        initial_ana = st.number_input("Başlangıç Ana Ürün Stok", value=0, step=1000)
        initial_mini = st.number_input("Başlangıç Mini Sample Stok", value=0, step=1000)
        initial_adr = st.number_input("Başlangıç ADR Stok", value=0, step=1000)

        calculate = st.button("Raporu Hesapla", type="primary")


    pallet_map = {
        "Ana Ürün": ana_palet_ici,
        "Mini Sample": mini_palet_ici,
        "ADR": adr_palet_ici,
    }

    initial_stock_map = {
        "Ana Ürün": initial_ana,
        "Mini Sample": initial_mini,
        "ADR": initial_adr,
    }

    mevcut_ana_palet = initial_ana / ana_palet_ici if ana_palet_ici else 0
    mevcut_mini_palet = initial_mini / mini_palet_ici if mini_palet_ici else 0
    mevcut_adr_palet = initial_adr / adr_palet_ici if adr_palet_ici else 0
    mevcut_total_palet = mevcut_ana_palet + mevcut_mini_palet + sarf_palet - mevcut_adr_palet


    if calculate:
        if not supply_file or not apo_file or not mapping_file:
            st.error("Lütfen Supply, APO Forecast ve Ürün Tipi dosyalarının üçünü de yükleyin.")
            st.stop()

        with st.spinner("Dosyalar okunuyor ve rapor hazırlanıyor..."):
            type_map, adr_codes, campaign_df, sheet_info = read_mapping_file(mapping_file)

            supply_long = read_supply_file(supply_file)
            apo_long = read_apo_file(apo_file)

            supply_long = add_product_type(supply_long, type_map, adr_codes)
            apo_long = add_product_type(apo_long, type_map, adr_codes)

            # Kontrol için kategori bazlı adet / kod sayısı
            supply_check_base = supply_long.copy()
            supply_check_adr = supply_long[supply_long["is_adr"]].copy()
            supply_check_adr["report_type"] = "ADR"
            supply_check_all = pd.concat([supply_check_base, supply_check_adr], ignore_index=True)

            apo_check_base = apo_long.copy()
            apo_check_adr = apo_long[apo_long["is_adr"]].copy()
            apo_check_adr["report_type"] = "ADR"
            apo_check_all = pd.concat([apo_check_base, apo_check_adr], ignore_index=True)

            supply_category_check = (
                supply_check_all
                .groupby("report_type")
                .agg(
                    supply_total_qty=("inbound_qty", "sum"),
                    supply_product_count=("product_code", "nunique")
                )
                .reset_index()
            )

            apo_category_check = (
                apo_check_all
                .groupby("report_type")
                .agg(
                    apo_total_qty=("outbound_qty", "sum"),
                    apo_product_count=("product_code", "nunique")
                )
                .reset_index()
            )

            category_check = pd.merge(
                supply_category_check,
                apo_category_check,
                on="report_type",
                how="outer"
            ).fillna(0)

            # Ana/Mini hesapları: ADR ürünler Ana Ürün içinde kalır.
            inbound_base = (
                supply_long
                .groupby(["week_start", "report_type"], as_index=False)["inbound_qty"]
                .sum()
            )

            outbound_base = (
                apo_long
                .groupby(["week_start", "report_type"], as_index=False)["outbound_qty"]
                .sum()
            )

            # ADR ayrıca gösterilir: Ana Ürün içinden düşülmez, sadece ek satır olarak hesaplanır.
            inbound_adr = (
                supply_long[supply_long["is_adr"]]
                .groupby("week_start", as_index=False)["inbound_qty"]
                .sum()
            )
            inbound_adr["report_type"] = "ADR"

            outbound_adr = (
                apo_long[apo_long["is_adr"]]
                .groupby("week_start", as_index=False)["outbound_qty"]
                .sum()
            )
            outbound_adr["report_type"] = "ADR"

            inbound = pd.concat([inbound_base, inbound_adr], ignore_index=True)
            outbound = pd.concat([outbound_base, outbound_adr], ignore_index=True)

            movement = pd.merge(
                inbound,
                outbound,
                on=["week_start", "report_type"],
                how="outer"
            ).fillna(0)

            # Aylık giriş / çıkış toplamları
            monthly_summary = movement.copy()
            monthly_summary["week_start"] = pd.to_datetime(monthly_summary["week_start"].astype(str), errors="coerce")
            monthly_summary["month"] = monthly_summary["week_start"].dt.strftime("%Y-%m")
            monthly_summary = (
                monthly_summary
                .groupby(["month", "report_type"], as_index=False)[["inbound_qty", "outbound_qty"]]
                .sum()
            )

            monthly_summary = monthly_summary.pivot_table(
                index="month",
                columns="report_type",
                values=["inbound_qty", "outbound_qty"],
                aggfunc="sum",
                fill_value=0
            )

            monthly_summary.columns = [f"{metric}_{rtype}" for metric, rtype in monthly_summary.columns]
            monthly_summary = monthly_summary.reset_index()

            monthly_report = pd.DataFrame()
            monthly_report["Ay"] = monthly_summary["month"]

            for col in [
                "inbound_qty_Ana Ürün", "outbound_qty_Ana Ürün",
                "inbound_qty_Mini Sample", "outbound_qty_Mini Sample",
                "inbound_qty_ADR", "outbound_qty_ADR"
            ]:
                if col not in monthly_summary.columns:
                    monthly_summary[col] = 0

            monthly_report["Ana Ürün Giriş"] = monthly_summary["inbound_qty_Ana Ürün"]
            monthly_report["Ana Ürün Çıkış"] = monthly_summary["outbound_qty_Ana Ürün"]
            monthly_report["Mini Sample Giriş"] = monthly_summary["inbound_qty_Mini Sample"]
            monthly_report["Mini Sample Çıkış"] = monthly_summary["outbound_qty_Mini Sample"]
            monthly_report["ADR Giriş"] = monthly_summary["inbound_qty_ADR"]
            monthly_report["ADR Çıkış"] = monthly_summary["outbound_qty_ADR"]

            monthly_numeric_cols = monthly_report.select_dtypes(include=[np.number]).columns
            monthly_report[monthly_numeric_cols] = monthly_report[monthly_numeric_cols].round(0).astype(int)

            # Tüm haftalar x tüm tipler matrisi
            all_weeks = pd.DataFrame({"week_start": sorted(movement["week_start"].dropna().unique())})
            all_types = pd.DataFrame({"report_type": ["Ana Ürün", "Mini Sample", "ADR"]})
            grid = all_weeks.merge(all_types, how="cross")

            movement = grid.merge(movement, on=["week_start", "report_type"], how="left").fillna(0)
            movement = movement.sort_values(["report_type", "week_start"])

            # Kümülatif stok
            stock_rows = []
            for report_type, g in movement.groupby("report_type"):
                current_stock = initial_stock_map.get(report_type, 0)

                for _, row in g.sort_values("week_start").iterrows():
                    current_stock = current_stock + row["inbound_qty"] - row["outbound_qty"]

                    pallet_inner = pallet_map.get(report_type, ana_palet_ici)
                    pallet = safe_divide(current_stock, pallet_inner)

                    stock_rows.append({
                        "week_start": row["week_start"],
                        "report_type": report_type,
                        "inbound_qty": row["inbound_qty"],
                        "outbound_qty": row["outbound_qty"],
                        "stock_qty": current_stock,
                        "pallet_inner": pallet_inner,
                        "pallet": pallet,
                    })

            detail = pd.DataFrame(stock_rows)

            # Haftalık özet
            weekly = (
                detail
                .pivot_table(
                    index="week_start",
                    columns="report_type",
                    values=["inbound_qty", "outbound_qty", "stock_qty", "pallet"],
                    aggfunc="sum"
                )
            )

            weekly.columns = [f"{metric}_{rtype}" for metric, rtype in weekly.columns]
            weekly = weekly.reset_index()

            # Eksik kolonları oluştur
            needed_numeric_cols = [
                "inbound_qty_Ana Ürün", "outbound_qty_Ana Ürün", "stock_qty_Ana Ürün", "pallet_Ana Ürün",
                "inbound_qty_Mini Sample", "outbound_qty_Mini Sample", "stock_qty_Mini Sample", "pallet_Mini Sample",
                "inbound_qty_ADR", "outbound_qty_ADR", "stock_qty_ADR", "pallet_ADR",
            ]

            for col in needed_numeric_cols:
                if col not in weekly.columns:
                    weekly[col] = 0

            # Excel görünümüne yakın rapor
            report = pd.DataFrame()
            weekly["week_start"] = pd.to_datetime(weekly["week_start"].astype(str), errors="coerce")
            report["Hafta"] = weekly["week_start"].dt.strftime("%Y-W%U")
            report["Hafta Başlangıcı"] = weekly["week_start"].dt.strftime("%d.%m.%Y")
            report["Kampanya"] = weekly["week_start"].apply(lambda x: assign_campaign(x, campaign_df))

            report["Ana Ürün Giriş"] = weekly["inbound_qty_Ana Ürün"]
            report["Ana Ürün Çıkış"] = weekly["outbound_qty_Ana Ürün"]
            report["Ana Ürün Ekol Stok Seviyesi"] = weekly["stock_qty_Ana Ürün"]
            report["Ana Ürün Palet"] = weekly["pallet_Ana Ürün"]
            report["Ana Ürün Giriş Paleti"] = report["Ana Ürün Giriş"] / ana_palet_ici

            report["Mini Sample Giriş"] = weekly["inbound_qty_Mini Sample"]
            report["Mini Sample Çıkış"] = weekly["outbound_qty_Mini Sample"]
            report["Mini Sample Ekol Stok Seviyesi"] = weekly["stock_qty_Mini Sample"]
            report["Mini Sample Palet"] = weekly["pallet_Mini Sample"]
            report["Mini Sample Giriş Paleti"] = report["Mini Sample Giriş"] / mini_palet_ici

            report["ADR Giriş"] = weekly["inbound_qty_ADR"]
            report["ADR Çıkış"] = weekly["outbound_qty_ADR"]
            report["ADR Ekol Stok Seviyesi"] = weekly["stock_qty_ADR"]
            report["ADR Palet"] = weekly["pallet_ADR"]

            # ADR palet ayrı gösterilir ve final total paletten düşülür.
            report["Sarf Palet"] = sarf_palet
            report["ADR Düşülecek Palet"] = report["ADR Palet"]
            report["Total Palet"] = (
                report["Ana Ürün Palet"] +
                report["Mini Sample Palet"] +
                report["Sarf Palet"] -
                report["ADR Düşülecek Palet"]
            )

            # Tır sayısı hesabı: sadece o haftaki girişlerin Ana Ürün + Mini Sample giriş paleti üzerinden yapılır.
            report["Tır Sayısı"] = (
                report["Ana Ürün Giriş Paleti"] +
                report["Mini Sample Giriş Paleti"]
            ) / tir_kapasitesi

            # Depo kapasite kontrol alanları
            report["Kapasite Kullanım %"] = report["Total Palet"] / depo_kapasitesi * 100
            report["Kalan Kapasite Palet"] = depo_kapasitesi - report["Total Palet"]
            report["Haftalık Palet Değişimi"] = report["Total Palet"].diff().fillna(0)

            def capacity_status(value):
                if value >= 100:
                    return "Kapasite Aşımı"
                if value >= kritik_esigi:
                    return "Kritik"
                if value >= takip_esigi:
                    return "Takip"
                return "Güvenli"

            report["Kapasite Durumu"] = report["Kapasite Kullanım %"].apply(capacity_status)

            report["Palet Trend"] = np.where(
                report["Haftalık Palet Değişimi"] > 0,
                "Artış",
                np.where(report["Haftalık Palet Değişimi"] < 0, "Azalış", "Sabit")
            )

            numeric_cols = report.select_dtypes(include=[np.number]).columns
            report[numeric_cols] = report[numeric_cols].round(0).astype(int)

            weekly = report

        st.success("Rapor hazır.")

        # KPI'lar ilk haftanın değerlerini gösterir.
        first_total = weekly["Total Palet"].iloc[0]
        first_capacity = weekly["Kapasite Kullanım %"].iloc[0]
        first_remaining = weekly["Kalan Kapasite Palet"].iloc[0]
        first_status = weekly["Kapasite Durumu"].iloc[0]
        first_week = weekly["Hafta"].iloc[0]

        # Peak hafta sadece ilk 5 ay içinde aranır.
        weekly_for_peak = weekly.copy()
        weekly_for_peak["_date"] = pd.to_datetime(weekly_for_peak["Hafta Başlangıcı"], dayfirst=True, errors="coerce")
        first_date = weekly_for_peak["_date"].min()
        horizon_date = add_months(first_date, 5)
        first_5_months = weekly_for_peak[weekly_for_peak["_date"] < horizon_date].copy()

        if first_5_months.empty:
            first_5_months = weekly_for_peak.copy()

        peak_idx = first_5_months["Total Palet"].idxmax()
        peak_week = first_5_months.loc[peak_idx, "Hafta"]
        peak_pallet = first_5_months.loc[peak_idx, "Total Palet"]
        increasing_week_count = int((first_5_months["Palet Trend"] == "Artış").sum())

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            st.metric("İlk Hafta Total Palet", f"{first_total:,.0f}", first_week)
        with c2:
            st.metric("İlk Hafta Kapasite %", f"{first_capacity:,.0f}%")
        with c3:
            st.metric("İlk Hafta Kalan Kapasite", f"{first_remaining:,.0f} palet")
        with c4:
            st.metric("Peak Hafta / İlk 5 Ay", f"{peak_week}", f"{peak_pallet:,.0f} palet")
        with c5:
            st.metric("Artan Hafta Sayısı / İlk 5 Ay", f"{increasing_week_count}")

        if first_status in ["Kritik", "Kapasite Aşımı"]:
            st.error(f"İlk hafta kapasite durumu: {first_status}")
        elif first_status == "Takip":
            st.warning(f"İlk hafta kapasite durumu: {first_status}")
        else:
            st.success(f"İlk hafta kapasite durumu: {first_status}")

        st.subheader("Yatay Haftalık Görünüm / Excel Formatı")

        pivot_rows = [
            "Ana Ürün Giriş",
            "Ana Ürün Çıkış",
            "Ana Ürün Ekol Stok Seviyesi",
            "Ana Ürün Palet",

            "Mini Sample Giriş",
            "Mini Sample Çıkış",
            "Mini Sample Ekol Stok Seviyesi",
            "Mini Sample Palet",

            "ADR Giriş",
            "ADR Çıkış",
            "ADR Ekol Stok Seviyesi",
            "ADR Palet",

            "Sarf Palet",
            "ADR Düşülecek Palet",
            "Total Palet",
            "Kapasite Kullanım %",
            "Kalan Kapasite Palet",
            "Kapasite Durumu",
            "Palet Trend",
            "Tır Sayısı",
        ]

        horizontal = weekly.set_index("Hafta")[pivot_rows].T

        weekly_date_map = weekly.set_index("Hafta")["Hafta Başlangıcı"]
        campaign_row = weekly.set_index("Hafta")["Kampanya"]

        horizontal.columns = [
            f"{week}\n{weekly_date_map.loc[week]}\n{campaign_row.loc[week] if campaign_row.loc[week] else ''}"
            for week in horizontal.columns
        ]

        # Total Palet önceki haftaya göre artıyorsa o haftayı kritik kırmızı yap.
        weekly_sorted = weekly.copy()
        weekly_sorted["Total Palet Artış"] = weekly_sorted["Total Palet"].diff()
        increased_weeks = weekly_sorted.loc[
            weekly_sorted["Total Palet Artış"] > 0, "Hafta"
        ].astype(str).tolist()

        # İlk 5 aydan sonraki haftaları kırmızı belirteçle işaretle.
        weekly_horizon = weekly.copy()
        weekly_horizon["_date"] = pd.to_datetime(weekly_horizon["Hafta Başlangıcı"], dayfirst=True, errors="coerce")
        first_week_date = weekly_horizon["_date"].min()
        horizon_limit = add_months(first_week_date, 5)
        after_horizon_weeks = weekly_horizon.loc[
            weekly_horizon["_date"] >= horizon_limit, "Hafta"
        ].astype(str).tolist()

        st.caption("Ekran performansı için tabloda ilk 5 ay gösterilir. Excel çıktısında tüm haftalar yer alır.")

        display_cols = [
            col for col in horizontal.columns
            if str(col).split("\\n")[0] not in after_horizon_weeks
        ]
        horizontal_display = horizontal[display_cols] if display_cols else horizontal

        st.dataframe(horizontal_display, use_container_width=True, height=520)

        with st.expander("Okunan Kampanya Takvimi"):
            if campaign_df.empty:
                st.warning("Kampanya takvimi okunamadı. Kampanya sheetinde kampanya adı, start ve end tarihleri olduğundan emin olun.")
            else:
                campaign_view = campaign_df.copy()
                campaign_view["start"] = campaign_view["start"].dt.strftime("%d.%m.%Y")
                campaign_view["end"] = campaign_view["end"].dt.strftime("%d.%m.%Y")
                st.dataframe(campaign_view, use_container_width=True)

        st.subheader("Mevcut Hafta Palet Tablosu")

        mevcut_hafta_report = pd.DataFrame({
            "Kategori": ["Ana Ürün", "Mini Sample", "ADR", "Sarf", "Total"],
            "Başlangıç Stok": [initial_ana, initial_mini, initial_adr, np.nan, np.nan],
            "Palet İçi": [ana_palet_ici, mini_palet_ici, adr_palet_ici, np.nan, np.nan],
            "Mevcut Hafta Palet": [
                mevcut_ana_palet,
                mevcut_mini_palet,
                mevcut_adr_palet,
                sarf_palet,
                mevcut_total_palet
            ]
        })

        for col in ["Başlangıç Stok", "Palet İçi", "Mevcut Hafta Palet"]:
            mevcut_hafta_report[col] = pd.to_numeric(mevcut_hafta_report[col], errors="coerce").round(0)

        st.dataframe(
            mevcut_hafta_report.style.format({
                "Başlangıç Stok": lambda x: "" if pd.isna(x) else f"{x:,.0f}",
                "Palet İçi": lambda x: "" if pd.isna(x) else f"{x:,.0f}",
                "Mevcut Hafta Palet": lambda x: "" if pd.isna(x) else f"{x:,.0f}",
            }),
            use_container_width=True
        )

        st.subheader("Aylık Giriş / Çıkış Toplamları")

        monthly_horizontal = monthly_report.set_index("Ay").T
        st.dataframe(monthly_horizontal, use_container_width=True, height=360)

        # Ekol Depo Data
        ekol_weekly = None
        ekol_capacity = None

        if ekol_file is not None:
            st.subheader("Ekol Depo Data")

            try:
                ekol_weekly, ekol_capacity = read_ekol_file(ekol_file)

                if ekol_capacity is not None:
                    st.write("Ekol Kapasite Özeti")
                    st.dataframe(
                        format_numeric_dataframe(ekol_capacity),
                        use_container_width=True,
                        height=220
                    )

                if ekol_weekly is not None:
                    st.write("Ekol Haftalık Stok / Doluluk Tablosu")
                    st.dataframe(
                        format_numeric_dataframe(ekol_weekly),
                        use_container_width=True,
                        height=420
                    )

                if ekol_weekly is None and ekol_capacity is None:
                    st.warning("Ekol dosyası okundu ancak uygun tablo bulunamadı.")

            except Exception as e:
                st.error(f"Ekol dosyası okunurken hata oluştu: {e}")

        # Depo ekranı için haftalık yatay operasyon tablosu
        depo_operasyon_cols = [
            "Hafta",
            "Hafta Başlangıcı",
            "Kampanya",
            "Ana Ürün Giriş",
            "Ana Ürün Çıkış",
            "Ana Ürün Ekol Stok Seviyesi",
            "Mini Sample Giriş",
            "Mini Sample Çıkış",
            "Mini Sample Ekol Stok Seviyesi",
            "ADR Giriş",
            "ADR Çıkış",
            "ADR Ekol Stok Seviyesi",
            "Tır Sayısı",
        ]

        depo_operasyon = weekly[[c for c in depo_operasyon_cols if c in weekly.columns]].copy()

        if not depo_operasyon.empty and "Hafta" in depo_operasyon.columns:
            meta_cols = ["Hafta", "Hafta Başlangıcı", "Kampanya"]
            value_cols = [c for c in depo_operasyon.columns if c not in meta_cols]

            depo_operasyon["Hafta Kolonu"] = depo_operasyon.apply(
                lambda r: f"{r.get('Hafta', '')}\n{r.get('Hafta Başlangıcı', '')}\n{r.get('Kampanya', '')}",
                axis=1
            )

            depo_yatay_operasyon = depo_operasyon.set_index("Hafta Kolonu")[value_cols].T
        else:
            depo_yatay_operasyon = pd.DataFrame()

        # Excel export
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            horizontal.to_excel(writer, sheet_name="Yatay Özet")
            depo_yatay_operasyon.to_excel(writer, sheet_name="Depo Haftalık Operasyon")
            depo_operasyon.to_excel(writer, sheet_name="Depo Operasyon", index=False)
            mevcut_hafta_report.to_excel(writer, sheet_name="Mevcut Hafta Palet", index=False)
            monthly_horizontal.to_excel(writer, sheet_name="Aylık Giriş Çıkış")
            weekly.to_excel(writer, sheet_name="Veri", index=False)
            pd.DataFrame([sheet_info]).to_excel(writer, sheet_name="Okunan Sheet Bilgisi", index=False)
            category_check.to_excel(writer, sheet_name="Kategori Kontrol", index=False)
            campaign_df.to_excel(writer, sheet_name="Kampanya", index=False)

            if ekol_file is not None:
                if ekol_capacity is not None:
                    ekol_capacity.to_excel(writer, sheet_name="Ekol Kapasite Özeti", index=False)

                if ekol_weekly is not None:
                    ekol_weekly.to_excel(writer, sheet_name="Ekol Haftalık Stok", index=False)

        # Son oluşturulan raporu hafızada tut. Excel kaydında sayılar virgüllü görünür.
        formatted_report_bytes = format_excel_workbook(output.getvalue())
        st.session_state["last_report_bytes"] = formatted_report_bytes
        st.session_state["last_report_default_name"] = f"depo_giris_cikis_raporu_{datetime.now().strftime('%Y%m%d')}"

        st.download_button(
            label="Excel Raporu İndir",
            data=st.session_state["last_report_bytes"],
            file_name="depo_giris_cikis_dashboard_raporu.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.info("Soldaki panelden 3 dosyayı yükleyip parametreleri belirledikten sonra 'Raporu Hesapla' butonuna basın.")



    # ------------------------------------------------------------
    # RAPORU GEÇMİŞE KAYDET
    # ------------------------------------------------------------
    st.divider()
    st.subheader("Raporu Geçmişe Kaydet")

    if "last_report_bytes" in st.session_state:
        report_save_name = st.text_input(
            "Geçmişe kaydetme adı",
            value=st.session_state.get("last_report_default_name", f"depo_giris_cikis_raporu_{datetime.now().strftime('%Y%m%d')}")
        )

        if st.button("Geçmişe Kaydet"):
            clean_name = "".join(
                ch if ch.isalnum() or ch in [" ", "_", "-"] else "_"
                for ch in report_save_name.strip()
            )

            if not clean_name:
                clean_name = f"depo_giris_cikis_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            history_filename = f"{clean_name}.xlsx"

            saved_name = save_report(history_filename, st.session_state["last_report_bytes"])
            st.success(f"Rapor geçmişe kaydedildi: {saved_name}")
    else:
        st.info("Önce raporu hesaplayın. Rapor hesaplandıktan sonra burada geçmişe kaydedebilirsiniz.")

    # ------------------------------------------------------------
    # GEÇMİŞ RAPORLAR
    # ------------------------------------------------------------
    st.divider()
    st.subheader("Geçmiş Raporlar")

    history_files = list_reports()

    if history_files:
        selected_history = st.selectbox(
            "Geçmiş rapor seç",
            options=history_files
        )

        selected_report_bytes = load_report(selected_history)

        st.download_button(
                "Seçili Geçmiş Raporu İndir",
                data=selected_report_bytes,
                file_name=selected_history,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        if st.button("Seçili Geçmiş Raporu Aç"):
            xls_history = pd.ExcelFile(BytesIO(selected_report_bytes))
            tabs = st.tabs(xls_history.sheet_names)

            for tab, sheet_name in zip(tabs, xls_history.sheet_names):
                with tab:
                    old_df = pd.read_excel(BytesIO(selected_report_bytes), sheet_name=sheet_name)
                    st.dataframe(old_df, use_container_width=True)

        st.caption(f"Toplam kayıtlı rapor sayısı: {len(history_files)}")
    else:
        st.info("Henüz geçmiş rapor yok. Raporu oluşturduktan sonra 'Geçmişe Kaydet' butonuna basarsan burada görünür.")
