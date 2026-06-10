#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze STDF test log files and produce yield/failure summary
"""

import math
import json
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Configuration
INPUT_FILE = Path(r"C:\Users\igevorgy\Desktop\SEMI_SKILLs\File\Mobile Device Test_10Jun2026_1458.std")
TOP_N = 10


def parse_float(value: object) -> float:
    if value is None or value == "":
        return math.nan
    try:
        return float(str(value).strip())
    except:
        return math.nan


def parse_int(value: object) -> Optional[int]:
    f = parse_float(value)
    if math.isnan(f):
        return None
    return int(round(f))


def parse_stdf(stdf_path: Path) -> Tuple[pd.DataFrame, Dict]:
    """Parse STDF file using pystdf and return normalized dataframe"""
    from pystdf.IO import Parser
    from pystdf.Writers import TextWriter

    parser = Parser(inp=open(stdf_path, "rb"))
    buffer = StringIO()
    parser.addSink(TextWriter(buffer))
    parser.parse()
    atdf_text = buffer.getvalue()

    lines = [line.strip() for line in atdf_text.splitlines() if line.strip()]

    active_part_by_site: Dict[str, str] = {}
    rows: List[Dict] = []
    bin_names: Dict[Tuple[str, int], str] = {}
    synthetic_part_counter = 0

    for line in lines:
        if "|" not in line:
            continue

        parts = line.split("|")
        if not parts:
            continue

        rec_type = parts[0].strip().upper()
        payload = parts[1:] if len(parts) > 1 else []

        # Parse HBR (Hard Bin Record)
        if rec_type == "HBR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            hbin_num = parse_int(payload[2] if len(payload) > 2 else None)
            hbin_nam = payload[5] if len(payload) > 5 else ""
            if hbin_num is not None:
                bin_names[(f"H{site_num}", hbin_num)] = hbin_nam
            continue

        # Parse SBR (Soft Bin Record)
        if rec_type == "SBR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            sbin_num = parse_int(payload[2] if len(payload) > 2 else None)
            sbin_nam = payload[5] if len(payload) > 5 else ""
            if sbin_num is not None:
                bin_names[(f"S{site_num}", sbin_num)] = sbin_nam
            continue

        # Parse PIR (Part Initial Record)
        if rec_type == "PIR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            synthetic_part_counter += 1
            active_part_by_site[site_num] = f"P{synthetic_part_counter:06d}"
            continue

        # Parse PRR (Part Results Record)
        if rec_type == "PRR":
            site_num = payload[1] if len(payload) > 1 else "unknown"
            part_flag = payload[2] if len(payload) > 2 else "0"
            num_test = parse_int(payload[3] if len(payload) > 3 else None)
            hard_bin = parse_int(payload[4] if len(payload) > 4 else None)
            soft_bin = parse_int(payload[5] if len(payload) > 5 else None)
            test_time = parse_float(payload[8] if len(payload) > 8 else None)
            part_id = payload[9] if len(payload) > 9 and payload[9] else None

            if part_id is None or part_id == "":
                part_id = active_part_by_site.get(site_num)
            if part_id is None or part_id == "":
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"

            # Determine pass/fail: typically hard_bin=1 is pass, others are fail/other bins
            status = "PASS" if hard_bin == 1 else "FAIL"

            rows.append({
                "part_id": str(part_id),
                "site_num": str(site_num),
                "test_num": None,
                "test_name": f"Part Result (HBin:{hard_bin}, SBin:{soft_bin})",
                "result": test_time,
                "lo_limit": 0.0 if num_test is not None else math.nan,
                "hi_limit": float(num_test) if num_test is not None else math.nan,
                "units": "tests" if num_test is not None else "ms",
                "hard_bin": hard_bin,
                "soft_bin": soft_bin,
                "status": status,
                "source_record": "PRR",
            })
            continue

        # Parse PTR (Parametric Test Record)
        if rec_type == "PTR":
            test_num = payload[0] if len(payload) > 0 else None
            site_num = payload[2] if len(payload) > 2 else "unknown"
            result = parse_float(payload[5] if len(payload) > 5 else None)
            test_name = payload[6] if len(payload) > 6 and payload[6] else f"TEST_{test_num or 'UNKNOWN'}"
            lo_limit = parse_float(payload[12] if len(payload) > 12 else None)
            hi_limit = parse_float(payload[13] if len(payload) > 13 else None)
            units = payload[14] if len(payload) > 14 else ""

            part_id = active_part_by_site.get(site_num)
            if part_id is None:
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"
                active_part_by_site[site_num] = part_id

            fail = False
            if not math.isnan(result) and not math.isnan(lo_limit) and result < lo_limit:
                fail = True
            if not math.isnan(result) and not math.isnan(hi_limit) and result > hi_limit:
                fail = True

            rows.append({
                "part_id": str(part_id),
                "site_num": str(site_num),
                "test_num": str(test_num) if test_num else None,
                "test_name": str(test_name),
                "result": result,
                "lo_limit": lo_limit,
                "hi_limit": hi_limit,
                "units": str(units),
                "hard_bin": pd.NA,
                "soft_bin": pd.NA,
                "status": "FAIL" if fail else "PASS",
                "source_record": "PTR",
            })
            continue

        # Parse FTR (Functional Test Record)
        if rec_type == "FTR":
            test_num = payload[0] if len(payload) > 0 else None
            site_num = payload[2] if len(payload) > 2 else "unknown"
            test_name = payload[22] if len(payload) > 22 and payload[22] else f"FTR_{test_num or 'UNKNOWN'}"

            part_id = active_part_by_site.get(site_num)
            if part_id is None:
                synthetic_part_counter += 1
                part_id = f"P{synthetic_part_counter:06d}"
                active_part_by_site[site_num] = part_id

            rows.append({
                "part_id": str(part_id),
                "site_num": str(site_num),
                "test_num": str(test_num) if test_num else None,
                "test_name": str(test_name),
                "result": math.nan,
                "lo_limit": math.nan,
                "hi_limit": math.nan,
                "units": "",
                "hard_bin": pd.NA,
                "soft_bin": pd.NA,
                "status": "FAIL",
                "source_record": "FTR",
            })
            continue

    if not rows:
        raise ValueError("No test data (PTR/FTR/PRR) extracted from STDF file")

    norm_df = pd.DataFrame(rows)
    return norm_df, {"backend": "pystdf", "ignored_rows": len(lines) - len(rows)}


def compute_metrics(df: pd.DataFrame) -> Dict:
    """Compute yield and failure metrics"""
    total_parts = df["part_id"].nunique()
    passing_parts = len(df[df["status"] == "PASS"]["part_id"].unique())
    failing_parts = len(df[df["status"] == "FAIL"]["part_id"].unique())
    yield_pct = (passing_parts / total_parts * 100.0) if total_parts > 0 else 0.0
    
    failed_events = len(df[df["status"] == "FAIL"])
    
    # Top failing tests
    top_failing = (
        df[df["status"] == "FAIL"]
        .groupby("test_name")
        .size()
        .sort_values(ascending=False)
        .head(TOP_N)
    )
    
    # Site pattern
    site_fail_count = df[df["status"] == "FAIL"].groupby("site_num").size().sort_values(ascending=False)
    
    return {
        "total_parts": int(total_parts),
        "passing_parts": int(passing_parts),
        "failing_parts": int(failing_parts),
        "yield_pct": round(yield_pct, 2),
        "failed_events": int(failed_events),
        "top_failing_tests": top_failing.to_dict() if not top_failing.empty else {},
        "site_failures": site_fail_count.to_dict() if not site_fail_count.empty else {},
        "unique_sites": int(df["site_num"].nunique()),
    }


def generate_report(df: pd.DataFrame, metrics: Dict, info: Dict, input_file: Path) -> str:
    """Generate markdown report"""
    
    report = f"""# Test Log Analysis Summary

## Executive Summary
Analyzed **{metrics['total_parts']}** parts: **{metrics['passing_parts']}** pass, **{metrics['failing_parts']}** fail, for an overall yield of **{metrics['yield_pct']}%**. Total failed test events: **{metrics['failed_events']}**.

## Input Snapshot
- **Source file:** `{input_file.name}`
- **Detected format:** `STDF`
- **Rows / test events analyzed:** **{len(df)}**
- **Unique parts analyzed:** **{metrics['total_parts']}**
- **Unique sites observed:** **{metrics['unique_sites']}**
- **Records ignored/unprocessed:** **{info['ignored_rows']}**

## KPI Snapshot
- **Yield:** **{metrics['yield_pct']}%**
- **Passing parts:** **{metrics['passing_parts']}**
- **Failing parts:** **{metrics['failing_parts']}**
- **Total failed test events:** **{metrics['failed_events']}**
"""

    if metrics['top_failing_tests']:
        report += "\n## Top Failing Tests\n"
        for i, (test_name, count) in enumerate(sorted(metrics['top_failing_tests'].items(), key=lambda x: x[1], reverse=True), 1):
            report += f"{i}. **{test_name}**: {count} failures\n"
    else:
        report += "\n## Top Failing Tests\nNo failing tests detected.\n"

    if metrics['site_failures']:
        report += "\n## Site Pattern Summary\n"
        for site, count in sorted(metrics['site_failures'].items(), key=lambda x: x[1], reverse=True):
            report += f"- **Site {site}**: {count} failures\n"
    else:
        report += "\n## Site Pattern Summary\nNo site-related failures or insufficient site data.\n"

    report += f"""
## Recommended Next Actions
- Continue normal yield monitoring
- Investigate top failing tests for systematic issues

## Assumptions and Data Quality Notes
- Parser backend used: {info['backend']}
- Analysis used {len(df)} normalized test-event rows
- {info['ignored_rows']} non-test records were ignored or unparseable
"""
    
    return report


def main():
    input_file = INPUT_FILE
    
    print(f"Analyzing {input_file}...")
    
    # Parse STDF
    df, info = parse_stdf(input_file)
    
    # Compute metrics
    metrics = compute_metrics(df)
    
    # Generate report
    report = generate_report(df, metrics, info, input_file)
    print(report)
    
    # Save outputs
    output_dir = input_file.parent
    
    # Save markdown
    md_path = output_dir / f"{input_file.stem}_summary.md"
    md_path.write_text(report)
    print(f"\nSaved to: {md_path}")
    
    # Save JSON metrics
    json_path = output_dir / f"{input_file.stem}_summary.json"
    json_path.write_text(json.dumps(metrics, indent=2))
    print(f"Saved to: {json_path}")
    
    # Save normalized CSV
    csv_path = output_dir / f"{input_file.stem}_normalized.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved to: {csv_path}")


if __name__ == "__main__":
    main()
