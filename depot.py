from io import BytesIO

import pandas as pd
import streamlit as st

from auth import logout_button
from github_reports import list_reports, load_report


def _format_display(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    for col in output.columns:
        numeric = pd.to_numeric(output[col], errors="coerce")
        if numeric.notna().sum() >= max(1, len(output) * 0.4):
            output[col] = numeric.map(lambda x: "" if pd.isna(x) else f"{x:,.0f}")
    return output


def render_depot() -> None:
    st.title("YR Logistics Dashboard")
    st.caption("Depo operasyon ekranı")
    logout_button("depo_logout")

    reports = list_reports()
    if not reports:
        st.warning("Henüz kayıtlı rapor yok. Rapor önce tedarik ekranından kaydedilmelidir.")
        return

    selected = st.selectbox("Kayıtlı rapor seç", reports)
    report_bytes = load_report(selected)

    try:
        xls = pd.ExcelFile(BytesIO(report_bytes))
    except Exception as exc:
        st.error(f"Rapor açılırken hata oluştu: {exc}")
        return

    allowed = [
        "Depo Haftalık Operasyon",
        "Aylık Giriş Çıkış",
        "Ekol Kapasite Özeti",
        "Ekol Haftalık Stok",
    ]
    sheets = [name for name in allowed if name in xls.sheet_names]

    if "Depo Haftalık Operasyon" not in sheets and "Veri" in xls.sheet_names:
        sheets.insert(0, "Veri")

    if not sheets:
        st.warning("Bu raporda depo ekranında gösterilecek uygun veri bulunamadı.")
        return

    tabs = st.tabs(sheets)

    for tab, sheet_name in zip(tabs, sheets):
        with tab:
            df = pd.read_excel(BytesIO(report_bytes), sheet_name=sheet_name)

            if sheet_name == "Veri":
                safe_cols = [
                    "Hafta", "Hafta Başlangıcı", "Kampanya",
                    "Ana Ürün Giriş", "Ana Ürün Çıkış", "Ana Ürün Ekol Stok Seviyesi",
                    "Mini Sample Giriş", "Mini Sample Çıkış", "Mini Sample Ekol Stok Seviyesi",
                    "ADR Giriş", "ADR Çıkış", "ADR Ekol Stok Seviyesi",
                ]
                df = df[[c for c in safe_cols if c in df.columns]]

                if "Hafta" in df.columns:
                    meta = ["Hafta", "Hafta Başlangıcı", "Kampanya"]
                    values = [c for c in df.columns if c not in meta]
                    pivot_source = df.copy()
                    pivot_source["Hafta Kolonu"] = pivot_source.apply(
                        lambda r: f"{r.get('Hafta', '')}\n{r.get('Hafta Başlangıcı', '')}\n{r.get('Kampanya', '')}",
                        axis=1,
                    )
                    df = pivot_source.set_index("Hafta Kolonu")[values].T

            # Depo tarafında palet, kapasite, trend ve tır görünmez.
            hidden = ["palet", "kapasite", "trend", "tır", "truck", "düşülecek"]
            visible_columns = [
                c for c in df.columns
                if not any(term in str(c).lower() for term in hidden)
            ]
            if visible_columns:
                df = df[visible_columns]

            # Yatay operasyon sheet'inde yasaklı satırları da kaldır.
            if sheet_name == "Depo Haftalık Operasyon" and len(df.columns) > 0:
                first_col = df.columns[0]
                forbidden_rows = df[first_col].astype(str).str.lower().str.contains(
                    "palet|kapasite|trend|tır|truck|düşülecek",
                    regex=True,
                    na=False,
                )
                df = df.loc[~forbidden_rows]

            st.dataframe(_format_display(df), use_container_width=True, height=520)

    st.download_button(
        "Seçili Raporu İndir",
        data=report_bytes,
        file_name=selected,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
