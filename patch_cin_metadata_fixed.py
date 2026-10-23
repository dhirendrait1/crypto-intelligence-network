"""Idempotently enforce the official Crypto Intelligence Network (CIN) API title."""
from pathlib import Path

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

print(f"CIN metadata verified; files updated: {changed}")
