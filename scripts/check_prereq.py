"""Shared prerequisites for the browser check scripts.

require_runs: makes sure the saved runs a script needs are available. Missing runs are loaded from
the tracked bundles (additive: existing runs are skipped, no model or website calls). Anything else
stops the script with exit code 3 and says what is missing.

require_live: paid scripts refuse to start without an explicit --live.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("FLOWLENS_API", "http://localhost:8000")
BUNDLES = [ROOT / "demo", ROOT / "scripts" / "check-runs"]
MISSING_PREREQUISITE = 3


def _stop(message: str):
    print(f"MISSING PREREQUISITE: {message}", file=sys.stderr, flush=True)
    sys.exit(MISSING_PREREQUISITE)


def _missing(ids: set[str]) -> list[str]:
    return sorted(r for r in ids if httpx.get(f"{API}/api/runs/{r}", timeout=20).status_code == 404)


def _bundle_of(run: str) -> Path | None:
    return next((b for b in BUNDLES if (b / "runs" / run / "records.json").is_file()), None)


def require_runs(*runs: str, load: bool = True) -> None:
    """Needs the given runs plus any run ID named on the command line."""
    ids = set(runs) | set(re.findall(r"run_[0-9a-f]{12}", " ".join(sys.argv[1:])))
    try:
        httpx.get(f"{API}/api/health", timeout=10).raise_for_status()
        missing = _missing(ids)
    except httpx.HTTPError as e:
        _stop(f"backend not reachable at {API} ({e}). Start it first, see docs/setup.md.")
    if not missing:
        return
    if load:
        for bundle in sorted({b for r in missing if (b := _bundle_of(r))}):
            print(f"loading recorded runs from {bundle.relative_to(ROOT)} (no model calls)", flush=True)
            subprocess.run([sys.executable, "-m", "flowlens.demo", "load", "--bundle", str(bundle)], cwd=ROOT / "backend",
                           check=True, stdout=subprocess.DEVNULL)
        missing = _missing(ids)
    if missing:
        _stop(f"saved runs not available from {API}: {', '.join(missing)}. "
              + ("They are not in a tracked bundle, or the backend uses a different database from this script's environment."
                 if load else "Load them with: python -m flowlens.demo load (from backend/)."))


def api_key_configured() -> bool:
    return bool(httpx.get(f"{API}/api/health", timeout=10).json().get("api_key_configured"))


def require_live() -> None:
    """Paid scripts run only with --live, which is removed so positional arguments stay as they were."""
    if "--live" not in sys.argv:
        print(f"{Path(sys.argv[0]).name} starts paid model runs. Nothing was started; add --live to run it.", file=sys.stderr)
        sys.exit(2)
    sys.argv.remove("--live")
