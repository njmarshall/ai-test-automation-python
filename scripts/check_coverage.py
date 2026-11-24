"""
check_coverage.py
-----------------
Enforces per-package coverage floors for shared/ from a coverage.json report.

    COVERAGE_FILE=/tmp/.coverage pytest -m unit --cov=shared --cov-report=json:reports/coverage.json
    python scripts/check_coverage.py reports/coverage.json

Floors live in coverage_thresholds.json. Policy: docs/coverage-policy.md.
Exits 1 when any package, or the overall total, is below its floor, or when
a package exists under shared/ with no floor and no exclusion (so a new
package cannot slip in untested).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

THRESHOLDS = Path("coverage_thresholds.json")


def main(report_path: str) -> int:
    cfg = json.loads(THRESHOLDS.read_text())
    files = json.loads(Path(report_path).read_text())["files"]

    covered: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for path, data in files.items():
        parts = Path(path).parts
        if len(parts) < 3 or parts[0] != "shared":
            continue
        pkg = parts[1]
        covered[pkg] += data["summary"]["covered_lines"]
        total[pkg] += data["summary"]["num_statements"]

    floors: dict[str, float] = cfg["packages"]
    excluded = set(cfg.get("excluded", {}))
    failures: list[str] = []

    print(f"{'package':14} {'covered':>9} {'percent':>8} {'floor':>6}")
    for pkg in sorted(total):
        if total[pkg] == 0:
            continue
        pct = 100 * covered[pkg] / total[pkg]
        if pkg in excluded:
            print(f"{pkg:14} {covered[pkg]:4}/{total[pkg]:<4} {pct:7.1f}%  excluded")
            continue
        floor = floors.get(pkg)
        if floor is None:
            failures.append(f"{pkg}: no floor in {THRESHOLDS} (add one, or exclude it with a reason)")
            print(f"{pkg:14} {covered[pkg]:4}/{total[pkg]:<4} {pct:7.1f}%  MISSING")
            continue
        mark = "ok" if pct >= floor else "FAIL"
        print(f"{pkg:14} {covered[pkg]:4}/{total[pkg]:<4} {pct:7.1f}% {floor:5}%  {mark}")
        if pct < floor:
            failures.append(f"{pkg}: {pct:.1f}% is below its floor of {floor}%")

    gated = [p for p in total if p not in excluded]
    all_cov = sum(covered[p] for p in gated)
    all_tot = sum(total[p] for p in gated)
    overall = 100 * all_cov / all_tot if all_tot else 100.0
    print(f"{'overall':14} {all_cov:4}/{all_tot:<4} {overall:7.1f}% {cfg['overall']:5}%")
    if overall < cfg["overall"]:
        failures.append(f"overall: {overall:.1f}% is below {cfg['overall']}%")

    for name in floors:
        if name not in total:
            failures.append(f"{name}: has a floor but no files under shared/{name}/ (remove the stale floor)")

    if failures:
        print("\nCoverage gate FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nCoverage gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "reports/coverage.json"))
