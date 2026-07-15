"""Cross-platform release quality gate; paid model calls are never executed."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPM = "npm.cmd" if os.name == "nt" else "npm"


def run(label: str, command: list[str], cwd: Path = ROOT) -> None:
    print(f"\n==> {label}")
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Release check failed: {label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-e2e",
        action="store_true",
        help="Run mocked Playwright tests; requires an installed Chromium binary.",
    )
    parser.add_argument(
        "--with-integration",
        action="store_true",
        help="Run admin console integration smoke test; requires initialized services.",
    )
    args = parser.parse_args()

    run("Python compileall", [sys.executable, "-m", "compileall", "app", "scripts"])
    run("Compose config", ["docker", "compose", "config", "--quiet"])
    run(
        "Git whitespace check",
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "diff", "--check"],
    )
    run("Frontend typecheck", [NPM, "run", "typecheck"], ROOT / "frontend")
    run("Frontend unit tests", [NPM, "test"], ROOT / "frontend")
    run("Frontend production build", [NPM, "run", "build"], ROOT / "frontend")
    if args.with_e2e:
        run("Mocked browser E2E", [NPM, "run", "test:e2e"], ROOT / "frontend")
    if args.with_integration:
        run(
            "Admin console integration",
            [sys.executable, "-m", "scripts.test_admin_console"],
        )
    print("\nRelease quality gate passed. No paid model API was called.")


if __name__ == "__main__":
    main()
