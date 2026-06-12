\
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analyze STD/STDF and print a strict chat-style summary.

Outputs only to stdout. No markdown/json/csv files are written.
Requires: pandas, pystdf
"""

from __future__ import annotations

import argparse
import math
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

TEMPLATE = """## Key findings:

- **Total parts:** {{total_parts}}
- **Yield:** {{yield_percent}}%
- **Passing parts:** {{passing_parts}}
- **Failing parts:** {{failing_parts}}
- **Top failing tests:**
{{top_failing_tests_bullets}}
- **Top failing sites:**
{{top_failing_sites_bullets}}

## Failed coordinate pattern analysis
{{coordinate_pattern_analysis}}
"""


def safe_str(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def to_float(value: object) -> float:
    try:
        if value is None or str(value).strip() == "":
            return math.nan
        return float(value)
    except Exception:
        return math.nan


def to_int(value: object) -> Optional[int]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except Exception:
        return None


def stdf_to_atdf_lines(stdf_path: Path) -> List[str]:
    from pystdf.IO import Parser
    from pystdf.Writers import TextWriter

    parser = Parser(inp=open(stdf_path, "rb"))
    buffer = StringIO()
    parser.addSink(TextWriter(buffer))
    parser.parse()
    return [line.strip() for line in buffer.getvalue().splitlines() if line.strip()]


def parse_stdf(stdf_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return PRR, PTR, FTR dataframes."""
    lines = stdf_to_atdf_lines(stdf_path)

    active_part_by_site: Dict[str, str] = {}
    prr_rows: List[dict] = []
    ptr_rows: List[dict] = []
    ftr_rows: List[dict] = []
    synthetic_part_counter = 0

    for line in lines:
        if ":" not in line:
            continue

        rec_type, payload = line.split(":", 1)
        rec_type = rec_type.strip().upper()
        fields = payload.split("|") if payload else []

        if rec_type == "PIR":
            # HEAD_NUM | SITE_NUM
            site_num = safe_str(fields[1] if len(fields) > 1 else "unknown", "unknown")
            synthetic_part_counter += 1
            active_part_by_site[site_num] = f"P{synthetic_part_counter:06d}"
            continue

        if rec_type == "PRR":
            # HEAD_NUM|SITE_NUM|PART_FLG|NUM_TEST|HARD_BIN|SOFT_BIN|X_COORD|Y_COORD|TEST_T|PART_ID|...
            site_num = safe_str(fields[1] if len(fields) > 1 else "unknown", "unknown")
            hard_bin = to_int(fields[4] if len(fields) > 4 else None)
            soft_bin = to_int(fields[5] if len(fields) > 5 else None)
            x_coord = to_int(fields[6] if len(fields) > 6 else None)
            y_coord = to_int(fields[7] if len(fields) > 7 else None)
            part_id = safe_str(fields[9] if len(fields) > 9 else "", "")
            if not part_id:
                part_id = active_part_by_site.get(site_num, "")
            if not part_id:
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"

            is_fail = False
            if soft_bin is not None and soft_bin > 9:
                is_fail = True
            if hard_bin is not None and hard_bin > 9:
                is_fail = True

            prr_rows.append({
                "part_id": part_id,
                "site_num": site_num,
                "hard_bin": hard_bin,
                "soft_bin": soft_bin,
                "x_coord": x_coord,
                "y_coord": y_coord,
                "is_fail": is_fail,
            })
            continue

        if rec_type == "PTR":
            # TEST_NUM|HEAD_NUM|SITE_NUM|TEST_FLG|PARM_FLG|RESULT|TEST_TXT|...|LO_LIMIT|HI_LIMIT|UNITS|...
            test_num = safe_str(fields[0] if len(fields) > 0 else "", "")
            site_num = safe_str(fields[2] if len(fields) > 2 else "unknown", "unknown")
            result = to_float(fields[5] if len(fields) > 5 else None)
            test_name = safe_str(fields[6] if len(fields) > 6 else "", f"TEST_{test_num or 'UNKNOWN'}")
            lo_limit = to_float(fields[12] if len(fields) > 12 else None)
            hi_limit = to_float(fields[13] if len(fields) > 13 else None)
            part_id = active_part_by_site.get(site_num, "")
            if not part_id:
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"
                active_part_by_site[site_num] = part_id

            is_fail = False
            if not math.isnan(result) and not math.isnan(lo_limit) and result < lo_limit:
                is_fail = True
            if not math.isnan(result) and not math.isnan(hi_limit) and result > hi_limit:
                is_fail = True

            ptr_rows.append({
                "part_id": part_id,
                "site_num": site_num,
                "test_num": test_num,
                "test_name": test_name,
                "is_fail": is_fail,
            })
            continue

        if rec_type == "FTR":
            # Conservative handling: each FTR is treated as a failed functional test event
            test_num = safe_str(fields[0] if len(fields) > 0 else "", "")
            site_num = safe_str(fields[2] if len(fields) > 2 else "unknown", "unknown")
            # Some ATDF variants place TEST_TXT later; fallback to FTR_<test_num>
            test_name = safe_str(fields[22] if len(fields) > 22 else "", f"FTR_{test_num or 'UNKNOWN'}")
            part_id = active_part_by_site.get(site_num, "")
            if not part_id:
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"
                active_part_by_site[site_num] = part_id

            ftr_rows.append({
                "part_id": part_id,
                "site_num": site_num,
                "test_num": test_num,
                "test_name": test_name,
                "is_fail": True,
            })
            continue

    return pd.DataFrame(prr_rows), pd.DataFrame(ptr_rows), pd.DataFrame(ftr_rows)


def compute_summary(prr_df: pd.DataFrame, ptr_df: pd.DataFrame, ftr_df: pd.DataFrame, top_n: int) -> Dict[str, object]:
    # Part-level metrics from PRR when available
    if not prr_df.empty:
        part_df = prr_df.drop_duplicates(subset=["part_id"], keep="last").copy()
        total_parts = int(part_df["part_id"].nunique())
        failing_parts = int(part_df["is_fail"].sum())
        passing_parts = total_parts - failing_parts
    else:
        part_events = []
        if not ptr_df.empty:
            part_events.append(ptr_df[["part_id", "is_fail"]])
        if not ftr_df.empty:
            part_events.append(ftr_df[["part_id", "is_fail"]])
        if part_events:
            parts = pd.concat(part_events, ignore_index=True)
            rolled = parts.groupby("part_id", dropna=False)["is_fail"].max().reset_index()
            total_parts = int(rolled["part_id"].nunique())
            failing_parts = int(rolled["is_fail"].sum())
            passing_parts = total_parts - failing_parts
        else:
            total_parts = passing_parts = failing_parts = 0

    yield_pct = round((passing_parts / total_parts * 100.0), 2) if total_parts else 0.0

    # Failed test events: PTR fails + all FTR rows
    fail_frames = []
    if not ptr_df.empty:
        fail_frames.append(ptr_df[ptr_df["is_fail"] == True][["test_num", "test_name", "site_num"]].copy())
    if not ftr_df.empty:
        fail_frames.append(ftr_df[["test_num", "test_name", "site_num"]].copy())

    if fail_frames:
        failed_tests_df = pd.concat(fail_frames, ignore_index=True)
        top_tests_df = (
            failed_tests_df.groupby(["test_num", "test_name"], dropna=False)
            .size()
            .reset_index(name="fail_count")
            .sort_values(["fail_count", "test_name"], ascending=[False, True])
            .head(top_n)
        )
        top_sites_df = (
            failed_tests_df.groupby("site_num", dropna=False)
            .size()
            .reset_index(name="fail_count")
            .sort_values(["fail_count", "site_num"], ascending=[False, True])
            .head(top_n)
        )
    else:
        top_tests_df = pd.DataFrame(columns=["test_num", "test_name", "fail_count"])
        top_sites_df = pd.DataFrame(columns=["site_num", "fail_count"])

    # Failed coordinate pattern from failing PRR only
    coord_analysis = build_coordinate_analysis(prr_df)

    return {
        "total_parts": total_parts,
        "passing_parts": passing_parts,
        "failing_parts": failing_parts,
        "yield_percent": yield_pct,
        "top_tests_df": top_tests_df,
        "top_sites_df": top_sites_df,
        "coordinate_pattern_analysis": coord_analysis,
    }


def build_coordinate_analysis(prr_df: pd.DataFrame) -> str:
    if prr_df.empty or "is_fail" not in prr_df.columns:
        return "- Coordinate analysis unavailable because no part-level result records were parsed."

    fail_coords = prr_df[(prr_df["is_fail"] == True)].copy()
    if fail_coords.empty:
        return "- No failing parts were found, so there are no failing coordinates to analyze."

    fail_coords = fail_coords.dropna(subset=["x_coord", "y_coord"])
    if fail_coords.empty:
        return "- Coordinate analysis unavailable because failing PRR records do not contain usable X/Y coordinates."

    coord_counts = (
        fail_coords.groupby(["x_coord", "y_coord"], dropna=False)
        .size()
        .reset_index(name="fail_count")
        .sort_values(["fail_count", "x_coord", "y_coord"], ascending=[False, True, True])
    )

    total_fail_coords = int(coord_counts["fail_count"].sum())
    top1 = int(coord_counts.iloc[0]["fail_count"])
    top1_share = top1 / total_fail_coords if total_fail_coords else 0.0
    top3_share = coord_counts.head(3)["fail_count"].sum() / total_fail_coords if total_fail_coords else 0.0

    bullets: List[str] = []
    bullets.append(f"- Failing coordinate records with usable X/Y: {total_fail_coords}")

    top_rows = []
    for _, row in coord_counts.head(3).iterrows():
        x = int(row["x_coord"])
        y = int(row["y_coord"])
        c = int(row["fail_count"])
        top_rows.append(f"  - ({x}, {y}) — {c} failures")

    if top_rows:
        bullets.append("- Most frequent failing coordinates:")
        bullets.extend(top_rows)

    if top1_share >= 0.50 or top3_share >= 0.75:
        bullets.append("- Pattern result: failing coordinates are concentrated in a small location set, not broadly scattered.")
    else:
        bullets.append("- Pattern result: failing coordinates look scattered rather than concentrated in one dominant location.")

    return "\n".join(bullets)


def bullets_for_top_tests(df: pd.DataFrame) -> str:
    if df.empty:
        return "  - N/A"
    lines = []
    for _, row in df.iterrows():
        test_label = safe_str(row.get("test_name"), "UNKNOWN_TEST")
        fail_count = int(row.get("fail_count", 0))
        lines.append(f"  - {test_label} — {fail_count} failures")
    return "\n".join(lines)


def bullets_for_top_sites(df: pd.DataFrame) -> str:
    if df.empty:
        return "  - N/A"
    lines = []
    for _, row in df.iterrows():
        site = safe_str(row.get("site_num"), "N/A")
        fail_count = int(row.get("fail_count", 0))
        lines.append(f"  - Site {site}: {fail_count} failures")
    return "\n".join(lines)


def render_output(metrics: Dict[str, object]) -> str:
    replacements = {
        "total_parts": str(metrics["total_parts"]),
        "yield_percent": f"{float(metrics['yield_percent']):.2f}",
        "passing_parts": str(metrics["passing_parts"]),
        "failing_parts": str(metrics["failing_parts"]),
        "top_failing_tests_bullets": bullets_for_top_tests(metrics["top_tests_df"]),
        "top_failing_sites_bullets": bullets_for_top_sites(metrics["top_sites_df"]),
        "coordinate_pattern_analysis": str(metrics["coordinate_pattern_analysis"]),
    }

    text = TEMPLATE
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze STD/STDF and print a strict chat summary.")
    parser.add_argument("input_file", help="Path to .std / .stdf file")
    parser.add_argument("--top", type=int, default=5, help="Top N tests/sites to show")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if input_path.suffix.lower() not in {".std", ".stdf"}:
        raise ValueError("Input file must be .std or .stdf")

    prr_df, ptr_df, ftr_df = parse_stdf(input_path)
    metrics = compute_summary(prr_df, ptr_df, ftr_df, top_n=max(1, args.top))
    print(render_output(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
