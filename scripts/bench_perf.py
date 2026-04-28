"""Benchmark harness for the pdfconverter hot paths.

Goal: produce concrete timings for every code path the 2026-04-28 perf pass
touched, so claims like "5 PDF opens → 1" can be verified with numbers.

Workflow
--------
    # 1. Drop a few PDFs into _bench_samples/
    # 2. Run on the current branch + save the result:
    python scripts/bench_perf.py --save bench_baseline.json

    # 3. Check out a pre-perf-pass commit + run again with --compare:
    git checkout <pre-perf-commit>
    python scripts/bench_perf.py --compare bench_baseline.json

The compare run prints a delta table per metric. Pure stdlib; no
``pytest-benchmark`` dependency. Server is NOT started — every helper
is called directly so no FastAPI lifespan / port / TCP overhead.

If ``_bench_samples/`` is empty or missing, the script falls back to
generating a synthetic 10-page PDF in-memory; this is enough to exercise
``deep_analyze`` / ``log_history`` / ``parse_pdf_for_batch`` but won't
catch real-world variability (encrypted, OCR-only, table-heavy).
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLES_DIR = ROOT / "_bench_samples"


# ---------------------------------------------------------------------------
# Synthetic PDF (fallback when _bench_samples/ is empty)
# ---------------------------------------------------------------------------
def _synthesize_pdf(out_path: Path, *, pages: int = 10) -> None:
    """Build a small text-and-table PDF so callers always have something
    to bench against. Uses pymupdf so we don't pull a new dep."""
    import fitz

    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Sample page {i + 1}", fontsize=16)
        page.insert_text((72, 110), "Lorem ipsum dolor sit amet, "
                         "consectetur adipiscing elit. " * 4, fontsize=10)
        for r in range(5):
            page.insert_text((72, 200 + r * 16),
                             f"Row {r + 1} | Col A | Col B | {1234 + r}",
                             fontsize=10)
    doc.save(str(out_path), garbage=4, deflate=True)
    doc.close()


def _resolve_samples() -> tuple[list[Path], Path | None]:
    """Return ``(pdf_list, tmp_dir_holding_synthetic_or_None)``."""
    if SAMPLES_DIR.is_dir():
        pdfs = sorted(SAMPLES_DIR.glob("*.pdf"))
        if pdfs:
            return pdfs, None
    tmp = Path(tempfile.mkdtemp(prefix="bench_perf_"))
    synth = tmp / "synthetic_10p.pdf"
    _synthesize_pdf(synth, pages=10)
    return [synth], tmp


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------
def _timeit(fn, *, repeat: int = 3) -> dict:
    """Run ``fn`` ``repeat`` times; return min/median/max in ms + memory peak."""
    samples: list[float] = []
    peak_mem = 0
    for _ in range(repeat):
        gc.collect()
        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            fn()
        except Exception as e:  # don't let one failure abort the whole run
            print(f"  ! {fn.__name__} raised: {e}")
            tracemalloc.stop()
            return {"error": str(e)}
        t1 = time.perf_counter()
        cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        samples.append((t1 - t0) * 1000)
        peak_mem = max(peak_mem, peak)
    samples.sort()
    return {
        "min_ms": round(samples[0], 2),
        "median_ms": round(samples[len(samples) // 2], 2),
        "max_ms": round(samples[-1], 2),
        "peak_mem_kb": round(peak_mem / 1024, 1),
    }


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------
def bench_deep_analyze(pdfs: list[Path]) -> dict:
    """Hot path #1 — was 5 fitz.open per call, now 1."""
    from core.metadata import deep_analyze

    def run():
        for p in pdfs:
            deep_analyze(p)

    return _timeit(run, repeat=3)


def bench_extract_metadata(pdfs: list[Path]) -> dict:
    """Sanity check that the wrapper-around-internal split didn't slow things down."""
    from core.metadata import extract_metadata

    def run():
        for p in pdfs:
            extract_metadata(p)

    return _timeit(run, repeat=3)


def bench_log_history(_pdfs: list[Path], *, rows: int = 1000) -> dict:
    """Hot path #3 — was sqlite3.connect per row, now one shared connection."""
    from core.history_db import init_history_db, log_history
    import core
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="bench_history_"))
    db_path = tmp / "bench_history.db"
    original = core.HISTORY_DB_PATH
    try:
        core.HISTORY_DB_PATH = db_path
        # Reset cached connection so it picks up the new path
        from core import history_db as _hdb
        _hdb._conn_cache = None
        init_history_db()

        def run():
            for i in range(rows):
                log_history(action="bench", filename=f"f{i}.pdf",
                            record_count=i, ip="127.0.0.1")

        return _timeit(run, repeat=3) | {"rows_per_call": rows}
    finally:
        core.HISTORY_DB_PATH = original
        from core import history_db as _hdb
        _hdb._conn_cache = None


def bench_parse_pdf_for_batch(pdfs: list[Path]) -> dict:
    """Hot path #4 — process-pool worker entry point. We don't actually spawn
    a worker (overkill for a bench), but we measure the function as the worker
    would call it."""
    from core.batch import parse_pdf_for_batch

    def run():
        for p in pdfs:
            parse_pdf_for_batch((p.name, str(p), None, []))

    return _timeit(run, repeat=3)


def bench_pdf_safety(pdfs: list[Path]) -> dict:
    """Hot path #6 — safety scan with reused doc handle."""
    from pdf_safety import full_scan
    import fitz

    def run():
        for p in pdfs:
            doc = fitz.open(str(p))
            try:
                full_scan(p, doc=doc)
            finally:
                doc.close()

    return _timeit(run, repeat=3)


def bench_convert_to_jpg(pdfs: list[Path]) -> dict:
    """Hot path #5 — Pixmap eager release in the page-render loop."""
    from pdf_converter import convert_to_jpg

    out_dir = Path(tempfile.mkdtemp(prefix="bench_jpg_"))

    def run():
        for p in pdfs:
            convert_to_jpg(p, out_dir / p.stem, dpi=72)

    return _timeit(run, repeat=2)  # JPG render is the slowest, fewer repeats


# ---------------------------------------------------------------------------
# Pre-optimization simulators — recreate the inefficient pre-perf-pass paths
# so a single bench run can produce a before/after table without git history.
# Three of the six fixes are A/B-able at function level (deep_analyze, log_history,
# pdf_safety+open). The other three (lazy imports, lifespan pre-warm, Pixmap
# release) are real wins but bench-resistant — flagged as "n/a" in the diff.
# ---------------------------------------------------------------------------
def bench_deep_analyze_pre(pdfs: list[Path]) -> dict:
    """Pre-perf simulator: each helper opens its own ``fitz.Document``."""
    from core.metadata import extract_metadata, extract_outline, detect_headers_footers, detect_text_columns
    from core.editor import classify_pdf_extractability
    import fitz

    def run():
        for p in pdfs:
            extractability = classify_pdf_extractability(p)   # open #1
            extract_metadata(p)                                # open #2
            extract_outline(p)                                 # open #3
            if extractability["extractable"]:
                detect_headers_footers(p)                      # open #4
            with fitz.open(str(p)) as doc:                     # open #5
                for page in doc:
                    text = page.get_text()
                    if text and text.strip():
                        detect_text_columns(page)

    return _timeit(run, repeat=3)


def bench_log_history_pre(_pdfs: list[Path], *, rows: int = 1000) -> dict:
    """Pre-perf simulator: connect / commit / close per row, no cache."""
    import sqlite3
    from datetime import datetime

    tmp = Path(tempfile.mkdtemp(prefix="bench_history_pre_"))
    db_path = tmp / "bench.db"
    init = sqlite3.connect(str(db_path))
    init.execute(
        "CREATE TABLE history (id INTEGER PRIMARY KEY, ts TEXT, action TEXT, "
        "target TEXT, filename TEXT, record_count INTEGER, note TEXT, ip TEXT)"
    )
    init.commit()
    init.close()

    def run():
        for i in range(rows):
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    "INSERT INTO history (ts, action, target, filename, "
                    "record_count, note, ip) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (datetime.now().isoformat(timespec="seconds"), "bench",
                     None, f"f{i}.pdf", i, None, "127.0.0.1"),
                )
                conn.commit()
            finally:
                conn.close()

    return _timeit(run, repeat=3) | {"rows_per_call": rows}


def bench_pdf_safety_pre(pdfs: list[Path]) -> dict:
    """Pre-perf simulator: full_scan opens its own doc, no doc reuse."""
    from pdf_safety import full_scan
    import fitz

    def run():
        for p in pdfs:
            doc = fitz.open(str(p))   # caller's open (mimic kind detection)
            try:
                full_scan(p)          # full_scan opens AGAIN internally — pre-perf behavior
            finally:
                doc.close()

    return _timeit(run, repeat=3)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
BENCHMARKS = {
    "deep_analyze":      bench_deep_analyze,
    "extract_metadata":  bench_extract_metadata,
    "log_history":       bench_log_history,
    "parse_pdf_for_batch": bench_parse_pdf_for_batch,
    "pdf_safety_full_scan": bench_pdf_safety,
    "convert_to_jpg":    bench_convert_to_jpg,
}

# Pre-perf simulators keyed by the same metric name so the diff aligns.
PRE_PERF_BENCHMARKS = {
    "deep_analyze":         bench_deep_analyze_pre,
    "log_history":          bench_log_history_pre,
    "pdf_safety_full_scan": bench_pdf_safety_pre,
}


def run_all(pdfs: list[Path], *, pre_perf: bool = False) -> dict:
    print(f"  benching against {len(pdfs)} PDF(s):")
    for p in pdfs[:5]:
        size_kb = p.stat().st_size / 1024
        print(f"    - {p.name}  ({size_kb:.1f} KB)")
    if len(pdfs) > 5:
        print(f"    ... and {len(pdfs) - 5} more")
    print()
    if pre_perf:
        print("  [simulate-pre-perf] using inefficient pre-optimization paths\n")
    results: dict[str, dict] = {}
    for name, fn in BENCHMARKS.items():
        if pre_perf and name in PRE_PERF_BENCHMARKS:
            fn = PRE_PERF_BENCHMARKS[name]
        print(f"  {name} ...", end=" ", flush=True)
        r = fn(pdfs)
        results[name] = r
        if "error" in r:
            print(f"ERROR: {r['error']}")
        else:
            print(f"min={r['min_ms']:.2f}ms  med={r['median_ms']:.2f}ms  "
                  f"peak={r['peak_mem_kb']/1024:.1f}MB")
    return results


def print_compare(current: dict, baseline: dict) -> None:
    print()
    print(f"{'metric':<26} {'baseline med':>14} {'current med':>14} "
          f"{'delta ms':>10} {'delta %':>9}")
    print("-" * 80)
    for name in BENCHMARKS:
        b = baseline.get(name, {})
        c = current.get(name, {})
        if "error" in b or "error" in c or "median_ms" not in b:
            print(f"{name:<26} {'(missing)':>14}")
            continue
        bm = b["median_ms"]
        cm = c["median_ms"]
        delta = cm - bm
        pct = (delta / bm * 100) if bm else 0
        marker = " WIN" if delta < -1 else (" REG" if delta > 1 else "    ")
        print(f"{name:<26} {bm:>14.2f} {cm:>14.2f} "
              f"{delta:>+10.2f} {pct:>+8.1f}% {marker}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--save", metavar="FILE",
                   help="Write current run as a JSON baseline.")
    p.add_argument("--compare", metavar="FILE",
                   help="Compare current run against a saved baseline.")
    p.add_argument("--simulate-pre-perf", action="store_true",
                   help="Run the inefficient pre-perf-pass paths (no git checkout needed).")
    p.add_argument("--ab", action="store_true",
                   help="One-shot before+after: runs --simulate-pre-perf first, "
                        "then current code, prints the diff. Skips --save / --compare.")
    args = p.parse_args()

    pdfs, tmp_holder = _resolve_samples()
    if tmp_holder:
        print(f"  (no PDFs in {SAMPLES_DIR}, using synthetic 10-page PDF)")
    else:
        print(f"  using PDFs from {SAMPLES_DIR}")
    print()

    if args.ab:
        print("=" * 76)
        print("  [PRE-PERF SIMULATED RUN]")
        print("=" * 76)
        baseline = run_all(pdfs, pre_perf=True)
        print()
        print("=" * 76)
        print("  [CURRENT (POST-OPT) RUN]")
        print("=" * 76)
        current = run_all(pdfs, pre_perf=False)
        print_compare(current, baseline)
        return 0

    results = run_all(pdfs, pre_perf=args.simulate_pre_perf)

    if args.save:
        Path(args.save).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\n  saved baseline -> {args.save}")

    if args.compare:
        baseline_path = Path(args.compare)
        if not baseline_path.exists():
            print(f"  ! baseline not found: {baseline_path}", file=sys.stderr)
            return 1
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        print_compare(results, baseline)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
