from pathlib import Path

ROOT = Path("cin")
OLD_TITLE = "Crypto Intelligence Engine"
NEW_TITLE = "Crypto Intelligence Network (CIN)"

if not ROOT.is_dir():
    raise SystemExit("CIN scaffold directory was not extracted; refusing to continue.")

changed_files = []
for path in ROOT.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    if OLD_TITLE in text:
        path.write_text(text.replace(OLD_TITLE, NEW_TITLE), encoding="utf-8")
        changed_files.append(str(path))

if not changed_files:
    raise SystemExit(
        f"Could not find {OLD_TITLE!r} in extracted CIN Python files; "
        "refusing to deploy with an uncorrected title."
    )

print("Updated CIN API title in: " + ", ".join(changed_files))
