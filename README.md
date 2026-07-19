# YR Logistics Dashboard

## Çalıştırma

```bash
py -m streamlit run app.py
```

## Streamlit Cloud main file

```text
app.py
```

## Varsayılan şifreler

- Tedarik: `tedarik`
- Depo: `depo`

Şifreleri Streamlit Secrets üzerinden değiştirin.

## Kalıcı rapor arşivi

GitHub rapor arşivini kullanmak için Streamlit Secrets alanına:

```toml
GITHUB_TOKEN = "github_pat_..."
GITHUB_REPO = "kullanici/repository"
GITHUB_BRANCH = "main"
GITHUB_REPORTS_FOLDER = "reports"
```

ekleyin. Ayarlar yoksa uygulama yerel `reports/` klasörünü kullanır.
