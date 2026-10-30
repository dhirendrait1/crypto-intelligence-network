"""Idempotently enforce CIN metadata and install read-only API routers."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "cin" / "app"
OLD = "Crypto Intelligence Engine"
NEW = "Crypto Intelligence Network (CIN)"

if not APP_DIR.is_dir():
    raise SystemExit(f"Expected application directory not found: {APP_DIR}")

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
    "cin_derivatives_market_data_api.py",
    "cin_public_news_sentiment_api.py",
    "cin_forecast_ledger_api.py",
)
main_path = APP_DIR / "main.py"
if not main_path.is_file():
    raise SystemExit(f"Expected FastAPI entry point not found: {main_path}")

# Validate every required input before changing any scaffold file.
missing_modules = [ROOT / name for name in MODULES if not (ROOT / name).is_file()]
if missing_modules:
    raise SystemExit(
        "Required CIN module(s) not found: " + ", ".join(str(path) for path in missing_modules)
    )

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
    (
        "cin_derivatives_market_data_router",
        "\n# CIN: read-only public derivatives snapshot; no trading operations\n"
        "from app.cin_derivatives_market_data_api import router as cin_derivatives_market_data_router\n"
        "app.include_router(cin_derivatives_market_data_router)\n",
    ),
    (
        "cin_forecast_ledger_router",
        "\n# CIN: authenticated forecast ledger API; read-only research, no trading\n"
        "from app.cin_forecast_ledger_api import router as cin_forecast_ledger_router\n"
        "app.include_router(cin_forecast_ledger_router)\n",
    ),
    (
        "cin_public_news_sentiment_router",
        "\n# CIN: read-only public news and heuristic headline sentiment\n"
        "from app.cin_public_news_sentiment_api import router as cin_public_news_sentiment_router\n"
        "app.include_router(cin_public_news_sentiment_router)\n",
    ),
]
# Insert registrations before a direct-execution guard so routes are ready
# even when the module is run as a script, not only imported by Uvicorn.
main_guard = 'if __name__ == "__main__":'
registrations_added = 0
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
    registrations_added += 1

# Preflight branding metadata across the full app before writing any scaffold file.
branding_files = list(APP_DIR.rglob("*.py"))
branding_text = {path: path.read_text(encoding="utf-8") for path in branding_files}
if not any(OLD in content or NEW in content for content in branding_text.values()):
    raise SystemExit("Could not find a CIN application title to validate")

# Build every updated file in memory first. Use the route-patched main_text as
# the source for main.py so branding normalization cannot restore stale content
# and silently discard newly inserted router registrations.
original_branding_text = branding_text.copy()
branding_text[main_path] = main_text
updated_text = {
    path: content.replace(OLD, NEW)
    for path, content in branding_text.items()
}
changed = sum(
    1 for path, content in updated_text.items()
    if OLD in original_branding_text[path] and content != original_branding_text[path]
)

# All input validation and transformations complete before the first write.
for path, content in updated_text.items():
    if content != original_branding_text[path]:
        path.write_text(content, encoding="utf-8")

for module_name in MODULES:
    shutil.copyfile(ROOT / module_name, APP_DIR / module_name)


print(f"CIN metadata verified; read-only market data, screening, assessment, evidence, technical-analysis, public market-candle, and authenticated forecast-ledger routers installed; files updated: {changed}")
