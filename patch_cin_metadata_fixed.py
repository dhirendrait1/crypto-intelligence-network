"""Idempotently enforce CIN metadata and install Step 1 market-data router."""
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

# Copy the tracked endpoint module into the extracted application package.
source_module = ROOT / "market_data_step1.py"
target_module = APP_DIR / "market_data_step1.py"
if not source_module.is_file():
    raise SystemExit(f"Market-data module not found: {source_module}")
shutil.copyfile(source_module, target_module)

# Register the router exactly once, preserving the existing app and endpoints.
main_path = APP_DIR / "main.py"
if not main_path.is_file():
    raise SystemExit(f"Expected FastAPI entry point not found: {main_path}")
main_text = main_path.read_text(encoding="utf-8")
registration = "\n# CIN Step 1: public, read-only market data endpoint\nfrom app.market_data_step1 import router as cin_market_data_router\napp.include_router(cin_market_data_router)\n"
if "cin_market_data_router" not in main_text:
    main_path.write_text(main_text.rstrip() + registration, encoding="utf-8")
    changed += 1

print(f"CIN metadata verified; market-data router installed; files updated: {changed}")
