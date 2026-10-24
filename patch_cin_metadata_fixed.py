"""Idempotently enforce CIN metadata and install read-only API routers."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "cin" / "app"
OLD = "Crypto Intelligence Engine"
NEW = "Crypto Intelligence Network (CIN)"

if not APP_DIR.is_dir():
    raise SystemExit(f"Expected application directory not found: {APP_DIR}")

changed = 0
found = False
for path in APP_DIR.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    if OLD in text:
        text = text.replace(OLD, NEW)
        path.write_text(text, encoding="utf-8")
        changed += 1
        found = True
    if NEW in text:
        found = True

if not found:
    raise SystemExit("Could not find a CIN application title to validate")

MODULES = (
    "market_data_step1.py",
    "coin_screening_step2.py",
    "commodity_backing_assessment.py",
    "commodity_backing_api.py",
    "growth_fundamentals_assessment.py",
    "growth_fundamentals_api.py",
    "cin_evidence_ingestion.py",
    "cin_evidence_ingestion_api.py",
    "cin_technical_analysis.py",
    "cin_technical_analysis_api.py",
    "cin_public_market_candles_api.py",
)
for module_name in MODULES:
    source_module = ROOT / module_name
    target_module = APP_DIR / module_name
    if not source_module.is_file():
        raise SystemExit(f"Required CIN module not found: {source_module}")
    shutil.copyfile(source_module, target_module)

main_path = APP_DIR / "main.py"
if not main_path.is_file():
    raise SystemExit(f"Expected FastAPI entry point not found: {main_path}")
main_text = main_path.read_text(encoding="utf-8")

registrations = [
    (
        "cin_market_data_router",
        "\n# CIN Step 1: public, read-only market data endpoint\n"
        "from app.market_data_step1 import router as cin_market_data_router\n"
        "app.include_router(cin_market_data_router)\n",
    ),
    (
        "cin_coin_screening_router",
        "\n# CIN Step 2: explainable, read-only coin screening endpoint\n"
        "from app.coin_screening_step2 import router as cin_coin_screening_router\n"
        "app.include_router(cin_coin_screening_router)\n",
    ),
    (
        "cin_commodity_backing_router",
        "\n# CIN: read-only commodity backing evidence assessment endpoint\n"
        "from app.commodity_backing_api import router as cin_commodity_backing_router\n"
        "app.include_router(cin_commodity_backing_router)\n",
    ),
    (
        "cin_growth_fundamentals_router",
        "\n# CIN: read-only growth fundamentals evidence endpoint\n"
        "from app.growth_fundamentals_api import router as cin_growth_fundamentals_router\n"
        "app.include_router(cin_growth_fundamentals_router)\n",
    ),
    (
        "cin_public_evidence_router",
        "\n# CIN Milestone 2: allowlisted public evidence ingestion (read-only)\n"
        "from app.cin_evidence_ingestion_api import router as cin_public_evidence_router\n"
        "app.include_router(cin_public_evidence_router)\n",
    ),
    (
        "cin_technical_analysis_router",
        "\n# CIN Milestone 3: caller-supplied OHLC technical analysis (read-only)\n"
        "from app.cin_technical_analysis_api import router as cin_technical_analysis_router\n"
        "app.include_router(cin_technical_analysis_router)\n",
    ),
    (
        "cin_public_market_candles_router",
        "\n# CIN: public timestamped OHLCV and market-backed analysis (read-only)\n"
        "from app.cin_public_market_candles_api import router as cin_public_market_candles_router\n"
        "app.include_router(cin_public_market_candles_router)\n",
    ),
]
# Insert registrations before a direct-execution guard so routes are ready
# even when the module is run as a script, not only imported by Uvicorn.
main_guard = 'if __name__ == "__main__":'
for marker, registration in registrations:
    lines = [line for line in registration.splitlines() if line.strip()]
    import_line = next((line for line in lines if line.startswith("from app.")), None)
    include_line = next((line for line in lines if line.startswith("app.include_router(")), None)
    if import_line is None or include_line is None:
        raise SystemExit(f"Invalid router registration definition for {marker}")

    has_import = import_line in main_text
    has_include = include_line in main_text
    if has_import and has_include:
        continue
    if marker in main_text or has_import or has_include:
        raise SystemExit(
            f"Partial router registration detected for {marker}; refusing to patch ambiguously"
        )

    if main_guard in main_text:
        main_text = main_text.replace(main_guard, registration + "\n" + main_guard, 1)
    else:
        main_text = main_text.rstrip() + registration
    changed += 1

main_path.write_text(main_text, encoding="utf-8")

print(f"CIN metadata verified; read-only market data, screening, assessment, evidence, and technical-analysis and public market-candle routers installed; files updated: {changed}")
