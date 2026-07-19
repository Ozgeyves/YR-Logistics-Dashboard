from pathlib import Path

APP_NAME = "YR Logistics Dashboard"
APP_VERSION = "1.0.0"

APP_DIR = Path(__file__).parent
LOCAL_REPORTS_DIR = APP_DIR / "reports"
LOCAL_REPORTS_DIR.mkdir(exist_ok=True)

DEFAULTS = {
    "ana_palet_ici": 2400,
    "mini_palet_ici": 15000,
    "adr_palet_ici": 5540,
    "sarf_palet": 250.0,
    "tir_kapasitesi": 40,
    "depo_kapasitesi": 1100.0,
    "takip_esigi": 85.0,
    "kritik_esigi": 99.0,
}
