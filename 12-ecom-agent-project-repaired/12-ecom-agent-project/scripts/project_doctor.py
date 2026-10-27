"""Offline structural and syntax checks for the multi-service project."""
from __future__ import annotations
import ast
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
IGNORE = {".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}
REQUIRED = ["ingestion/run.py", "ingestion/requirements.txt", "agent/nlq/agent_code/main.py", "agent/chart_gen/agent_code/main.py", "agent/supervisor/agent_code/main.py", "webapp/backend/app/main.py", "webapp/frontend/package.json"]
def main() -> int:
    errors = [f"missing required file: {x}" for x in REQUIRED if not (ROOT / x).is_file()]
    count = 0
    for path in ROOT.rglob("*.py"):
        if any(part in IGNORE for part in path.parts): continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path)); count += 1
        except (SyntaxError, UnicodeDecodeError) as exc: errors.append(f"{path.relative_to(ROOT)}: {exc}")
    if errors:
        print("PROJECT CHECK FAILED\n" + "\n".join("- " + x for x in errors)); return 1
    print(f"Project structure OK; parsed {count} Python files.")
    print("Static check only: install service dependencies and run tests before deployment.")
    return 0
if __name__ == "__main__": raise SystemExit(main())
