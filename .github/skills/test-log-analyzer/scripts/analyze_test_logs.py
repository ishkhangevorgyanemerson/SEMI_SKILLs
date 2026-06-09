\
#!/usr/bin/env python3
"""Analyze semiconductor test logs (CSV or STDF) and generate a markdown summary."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

SUPPORTED_EXTS = {".csv", ".stdf", ".std"}
DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "output-template.md"
CSV_ALIASES = {
    "part_id": ["part_id", "part", "serial_number", "serial", "dut", "device_id", "unit_id", "chip_id"],
    "site_num": ["site_num", "site", "site_number", "test_site"],
    "test_num": ["test_num", "testnumber", "tnum"],
    "test_name": ["test_name", "test_txt", "test", "measurement_name", "param_name", "name"],
    "result": ["result", "measured_value", "measurement", "value", "meas", "reading"],
    "lo_limit": ["lo_limit", "low_limit", "lsl", "lower_limit", "min_limit", "min_spec"],
    "hi_limit": ["hi_limit", "high_limit", "usl", "upper_limit", "max_limit", "max_spec"],
    "status": ["status", "pf", "pass_fail", "passfail", "binning_result", "test_passed"],
    "units": ["units", "unit", "uom"],
    "hard_bin": ["hard_bin", "hbin", "hardware_bin"],
    "soft_bin": ["soft_bin", "sbin", "software_bin"],
}

@dataclass
class AnalysisResult:
    normalized: pd.DataFrame
    metrics: Dict[str, object]
    report_markdown: str
    output_path: Path
    metrics_json_path: Path

def _lower_clean(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")

def _find_first_supported(directory: Path) -> Optional[Path]:
    candidates = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]

def _coerce_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")

def _coerce_int_like(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round().astype("Int64")

def _safe_status_from_text(val: object) -> Optional[str]:
    if pd.isna(val):
        return None
    s = str(val).strip().lower()
    if s in {"pass", "p", "true", "1", "good"}:
        return "PASS"
    if s in {"fail", "f", "false", "0", "bad", "ng"}:
        return "FAIL"
    return None

def _site_key(value: object) -> str:
    if pd.isna(value):
        return "unknown"
    return str(value)

def _auto_map_csv_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    cleaned = {_lower_clean(c): c for c in df.columns}
    mapping: Dict[str, Optional[str]] = {k: None for k in CSV_ALIASES}
    for canonical, aliases in CSV_ALIASES.items():
        for alias in aliases:
            alias_clean = _lower_clean(alias)
            if alias_clean in cleaned:
                mapping[canonical] = cleaned[alias_clean]
                break
    return mapping

def load_csv_as_normalized(path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    df = pd.read_csv(path)
    mapping = _auto_map_csv_columns(df)
    norm = pd.DataFrame(index=df.index)
    if mapping["part_id"]:
        norm["part_id"] = df[mapping["part_id"]].astype(str)
        part_id_synthetic = False
    else:
        norm["part_id"] = [f"ROW_{i+1}" for i in range(len(df))]
        part_id_synthetic = True
    norm["site_num"] = df[mapping["site_num"]] if mapping["site_num"] else pd.Series([pd.NA] * len(df))
    norm["test_num"] = df[mapping["test_num"]] if mapping["test_num"] else pd.Series([pd.NA] * len(df))
    norm["test_name"] = df[mapping["test_name"]].astype(str) if mapping["test_name"] else norm["test_num"].astype(str).radd("TEST_")
    norm["result"] = _coerce_float(df[mapping["result"]]) if mapping["result"] else pd.Series([math.nan] * len(df))
    norm["lo_limit"] = _coerce_float(df[mapping["lo_limit"]]) if mapping["lo_limit"] else pd.Series([math.nan] * len(df))
    norm["hi_limit"] = _coerce_float(df[mapping["hi_limit"]]) if mapping["hi_limit"] else pd.Series([math.nan] * len(df))
    norm["units"] = df[mapping["units"]].astype(str) if mapping["units"] else pd.Series([""] * len(df))
    norm["hard_bin"] = _coerce_int_like(df[mapping["hard_bin"]]) if mapping["hard_bin"] else pd.Series([pd.NA] * len(df), dtype="Int64")
    norm["soft_bin"] = _coerce_int_like(df[mapping["soft_bin"]]) if mapping["soft_bin"] else pd.Series([pd.NA] * len(df), dtype="Int64")
    inferred_status = df[mapping["status"]].map(_safe_status_from_text) if mapping["status"] else pd.Series([None] * len(df), dtype="object")
    fail_mask = pd.Series([False] * len(df), index=df.index)
    fail_mask |= norm["result"].notna() & norm["lo_limit"].notna() & (norm["result"] < norm["lo_limit"])
    fail_mask |= norm["result"].notna() & norm["hi_limit"].notna() & (norm["result"] > norm["hi_limit"])
    status = inferred_status.fillna(fail_mask.map(lambda x: "FAIL" if x else None))
    status = status.fillna((norm["result"].notna() & ~fail_mask & (norm["lo_limit"].notna() | norm["hi_limit"].notna())).map(lambda x: "PASS" if x else None))
    norm["status"] = status.fillna("UNKNOWN")
    norm["source_record"] = "CSV"
    return norm, {"ignored_rows": 0, "part_id_synthetic": part_id_synthetic, "csv_column_mapping": mapping}

def load_stdf_as_normalized(path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    try:
        import stdfast as sf  # type: ignore
        parsed = sf.parse_stdf(str(path))
        data = parsed["data"]
        df = data.to_pandas() if hasattr(data, "to_pandas") else (data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data))
        cols = {_lower_clean(c): c for c in df.columns}
        def col(*names):
            for n in names:
                if _lower_clean(n) in cols:
                    return cols[_lower_clean(n)]
            return None
        norm = pd.DataFrame(index=df.index)
        part_col = col("part_id", "device_id", "dut", "serial_number")
        norm["part_id"] = df[part_col].astype(str) if part_col else [f"PART_{i+1}" for i in range(len(df))]
        norm["site_num"] = df[col("site_num", "site")] if col("site_num", "site") else pd.Series([pd.NA] * len(df))
        norm["test_num"] = df[col("test_num")] if col("test_num") else pd.Series([pd.NA] * len(df))
        name_col = col("test_name", "test_txt", "test")
        norm["test_name"] = df[name_col].astype(str) if name_col else norm["test_num"].astype(str).radd("TEST_")
        norm["result"] = _coerce_float(df[col("result", "value", "measurement")]) if col("result", "value", "measurement") else pd.Series([math.nan] * len(df))
        norm["lo_limit"] = _coerce_float(df[col("lo_limit", "low_limit", "lsl")]) if col("lo_limit", "low_limit", "lsl") else pd.Series([math.nan] * len(df))
        norm["hi_limit"] = _coerce_float(df[col("hi_limit", "high_limit", "usl")]) if col("hi_limit", "high_limit", "usl") else pd.Series([math.nan] * len(df))
        norm["units"] = df[col("units")].astype(str) if col("units") else pd.Series([""] * len(df))
        norm["hard_bin"] = _coerce_int_like(df[col("hard_bin", "hbin")]) if col("hard_bin", "hbin") else pd.Series([pd.NA] * len(df), dtype="Int64")
        norm["soft_bin"] = _coerce_int_like(df[col("soft_bin", "sbin")]) if col("soft_bin", "sbin") else pd.Series([pd.NA] * len(df), dtype="Int64")
        status_col = col("status", "pass_fail", "pf")
        status = df[status_col].map(_safe_status_from_text) if status_col else pd.Series([None] * len(df), dtype="object")
        fail_mask = pd.Series([False] * len(df), index=df.index)
        fail_mask |= norm["result"].notna() & norm["lo_limit"].notna() & (norm["result"] < norm["lo_limit"])
        fail_mask |= norm["result"].notna() & norm["hi_limit"].notna() & (norm["result"] > norm["hi_limit"])
        norm["status"] = status.fillna(fail_mask.map(lambda x: "FAIL" if x else None)).fillna("UNKNOWN")
        norm["source_record"] = df[col("record_type", "source_record")].astype(str) if col("record_type", "source_record") else "STDF"
        return norm, {"backend": "stdfast", "ignored_rows": 0, "part_id_synthetic": part_col is None}
    except Exception as exc1:
        stdfast_error = str(exc1)
    try:
        import pystdf.V4 as v4  # noqa: F401
        from pystdf.IO import Parser
        from pystdf.Writers import TextWriter
        p = Parser(inp=open(path, "rb"))
        buf = StringIO(); p.addSink(TextWriter(buf)); p.parse(); atdf = buf.getvalue()
        lines = [line.strip() for line in atdf.splitlines() if line.strip()]
        active_part_by_site, rows, prr_rows = {}, [], []
        synthetic_part_counter = 0
        for line in lines:
            if ":" not in line:
                continue
            rec, payload = line.split(":", 1)
            rec = rec.strip().upper(); parts = payload.split("|") if payload else []
            if rec == "PIR":
                site = parts[1] if len(parts) > 1 else "unknown"
                synthetic_part_counter += 1
                active_part_by_site[site] = f"P{synthetic_part_counter:06d}"
            elif rec == "PTR":
                site = parts[2] if len(parts) > 2 else "unknown"
                test_num = parts[0] if len(parts) > 0 else None
                test_name = parts[6] if len(parts) > 6 and parts[6] else (f"TEST_{test_num}" if test_num else "UNKNOWN_TEST")
                result = float(parts[5]) if len(parts) > 5 and parts[5] not in ["", None] else math.nan
                lo = float(parts[12]) if len(parts) > 12 and parts[12] not in ["", None] else math.nan
                hi = float(parts[13]) if len(parts) > 13 and parts[13] not in ["", None] else math.nan
                units = parts[14] if len(parts) > 14 else ""
                part_id = active_part_by_site.get(site, f"P{synthetic_part_counter+1:06d}")
                fail = (not pd.isna(result) and not pd.isna(lo) and result < lo) or (not pd.isna(result) and not pd.isna(hi) and result > hi)
                rows.append({"part_id": part_id, "site_num": site, "test_num": test_num, "test_name": test_name, "result": result, "lo_limit": lo, "hi_limit": hi, "units": units, "hard_bin": pd.NA, "soft_bin": pd.NA, "status": "FAIL" if fail else "PASS", "source_record": "PTR"})
            elif rec == "FTR":
                site = parts[2] if len(parts) > 2 else "unknown"
                test_num = parts[0] if len(parts) > 0 else None
                test_name = parts[22] if len(parts) > 22 and parts[22] else (f"FTR_{test_num}" if test_num else "UNKNOWN_FTR")
                part_id = active_part_by_site.get(site, f"P{synthetic_part_counter+1:06d}")
                rows.append({"part_id": part_id, "site_num": site, "test_num": test_num, "test_name": test_name, "result": math.nan, "lo_limit": math.nan, "hi_limit": math.nan, "units": "", "hard_bin": pd.NA, "soft_bin": pd.NA, "status": "FAIL", "source_record": "FTR"})
            elif rec == "PRR":
                prr_rows.append(parts)
        norm = pd.DataFrame(rows)
        if norm.empty:
            raise RuntimeError("No PTR/FTR rows were extracted from the STDF file")
        return norm, {"backend": "pystdf", "ignored_rows": max(0, len(lines)-len(rows)), "part_id_synthetic": True}
    except Exception as exc2:
        raise RuntimeError(f"No supported STDF parser backend was available. Install 'stdfast' or 'pystdf', or convert STDF to CSV first. stdfast error: {stdfast_error}; pystdf error: {exc2}")

def analyze(normalized: pd.DataFrame, source_file: Path, input_format: str, top_n: int, data_quality: Dict[str, object]) -> Dict[str, object]:
    df = normalized.copy()
    df["part_id"] = df["part_id"].astype(str)
    df["site_num"] = df["site_num"].astype("string")
    df["test_name"] = df["test_name"].astype(str)
    df["status"] = df["status"].fillna("UNKNOWN").astype(str).str.upper()
    failed_rows = df[df["status"] == "FAIL"].copy()
    part_summary = df.groupby("part_id", dropna=False)["status"].apply(lambda s: "FAIL" if (s == "FAIL").any() else ("PASS" if (s == "PASS").any() else "UNKNOWN")).reset_index(name="part_status")
    total_parts = int(part_summary["part_id"].nunique())
    passing_parts = int((part_summary["part_status"] == "PASS").sum())
    failing_parts = int((part_summary["part_status"] == "FAIL").sum())
    yield_percent = round((passing_parts / total_parts * 100.0), 2) if total_parts else 0.0
    rows_analyzed = int(len(df)); failed_test_events = int(len(failed_rows)); site_count = int(df["site_num"].dropna().nunique()) if "site_num" in df else 0
    if failed_rows.empty:
        top_tests = pd.DataFrame(columns=["test_name", "fail_count", "unique_parts", "sites", "share_of_failed_events"])
        site_failure = pd.DataFrame(columns=["site_num", "fail_count", "unique_parts", "share_of_failed_events"])
        top_site = "None"; dominant_test = "None"
    else:
        top_tests = failed_rows.groupby("test_name", dropna=False).agg(fail_count=("test_name", "size"), unique_parts=("part_id", pd.Series.nunique), sites=("site_num", lambda s: ", ".join(sorted({_site_key(x) for x in s.dropna().tolist()})) or "unknown")).reset_index().sort_values(["fail_count", "unique_parts", "test_name"], ascending=[False, False, True]).head(top_n)
        top_tests["share_of_failed_events"] = (top_tests["fail_count"] / max(failed_test_events, 1) * 100.0).round(2)
        site_failure = failed_rows.groupby("site_num", dropna=False).agg(fail_count=("site_num", "size"), unique_parts=("part_id", pd.Series.nunique)).reset_index().sort_values(["fail_count", "unique_parts"], ascending=[False, False])
        site_failure["share_of_failed_events"] = (site_failure["fail_count"] / max(failed_test_events, 1) * 100.0).round(2)
        top_site = f"Site {site_failure.iloc[0]['site_num']} ({int(site_failure.iloc[0]['fail_count'])} fails, {float(site_failure.iloc[0]['share_of_failed_events']):.2f}% of failed events)" if not site_failure.empty else "None"
        dominant_test = f"{top_tests.iloc[0]['test_name']} ({int(top_tests.iloc[0]['fail_count'])} fails, {float(top_tests.iloc[0]['share_of_failed_events']):.2f}% of failed events)" if not top_tests.empty else "None"
    hi_side = int(((df["status"] == "FAIL") & df["result"].notna() & df["hi_limit"].notna() & (df["result"] > df["hi_limit"])).sum())
    lo_side = int(((df["status"] == "FAIL") & df["result"].notna() & df["lo_limit"].notna() & (df["result"] < df["lo_limit"])).sum())
    dominant_limit_side = "high-side" if hi_side > lo_side and hi_side > 0 else ("low-side" if lo_side > hi_side and lo_side > 0 else "mixed")
    issues = []
    if total_parts and yield_percent < 95: issues.append(f"Yield is {yield_percent:.2f}%, below the 95% triage threshold.")
    if not top_tests.empty and float(top_tests.iloc[0]["share_of_failed_events"]) >= 30.0: issues.append(f"A single test dominates the failure population: {top_tests.iloc[0]['test_name']} contributes {float(top_tests.iloc[0]['share_of_failed_events']):.2f}% of all failed events.")
    if site_count > 1 and not site_failure.empty and float(site_failure.iloc[0]["share_of_failed_events"]) >= 50.0: issues.append(f"Failures are concentrated on site {site_failure.iloc[0]['site_num']} ({float(site_failure.iloc[0]['share_of_failed_events']):.2f}% of failed events), suggesting a site-specific issue.")
    if hi_side or lo_side: issues.append(f"Parametric limit violations are {dominant_limit_side} dominated (high-side={hi_side}, low-side={lo_side}).")
    if bool(data_quality.get("part_id_synthetic", False)): issues.append("Part IDs were synthesized for at least part of the data, so part-level grouping confidence is reduced.")
    actions = [f"Review test limits, instrumentation path, and recent changes for **{row['test_name']}**." for _, row in top_tests.head(min(3, len(top_tests))).iterrows()] if not top_tests.empty else ["No critical failure concentration detected. Continue with normal yield monitoring and spot-check top tests."]
    if site_count > 1 and not site_failure.empty and float(site_failure.iloc[0]["share_of_failed_events"]) >= 50.0: actions.append(f"Compare site {site_failure.iloc[0]['site_num']} hardware path, contactor, calibration, and loadboard conditions against the other sites.")
    if dominant_limit_side in {"high-side", "low-side"}: actions.append(f"Inspect process shift / measurement drift for {dominant_limit_side} violations and verify guardbands versus product limits.")
    assumptions = [f"Analysis used {rows_analyzed} normalized test-event rows from `{source_file.name}`."]
    if data_quality.get("backend"): assumptions.append(f"STDF backend used: {data_quality['backend']}.")
    if bool(data_quality.get("part_id_synthetic", False)): assumptions.append("At least some part IDs were synthesized because the source data did not provide stable identifiers.")
    ignored_rows = int(data_quality.get("ignored_rows", 0) or 0)
    if ignored_rows: assumptions.append(f"{ignored_rows} rows/records were ignored or not directly analyzable by the lightweight parser.")
    if input_format.lower() == "csv": assumptions.append("CSV pass/fail status was inferred from explicit status columns where available, otherwise from numeric limits.")
    if input_format.lower() == "stdf": assumptions.append("STDF parsing focuses on MIR/PIR/PTR/FTR/PRR-style information needed for quick yield triage, not full record preservation.")
    executive_summary = f"Analyzed **{total_parts}** parts: **{passing_parts}** pass, **{failing_parts}** fail, for an overall yield of **{yield_percent:.2f}%**. The main failure driver is **{dominant_test}**. Top site signal: **{top_site}**." + (f" Primary concern: {issues[0]}" if issues else " No high-severity concentration signal was detected.")
    return {"source_file": str(source_file), "input_format": input_format.upper(), "rows_analyzed": rows_analyzed, "total_parts": total_parts, "passing_parts": passing_parts, "failing_parts": failing_parts, "yield_percent": yield_percent, "failed_test_events": failed_test_events, "site_count": site_count, "ignored_rows": ignored_rows, "top_failing_site": top_site, "dominant_failing_test": dominant_test, "top_failing_tests": top_tests.to_dict(orient="records"), "site_failure_breakdown": site_failure.to_dict(orient="records"), "potential_issues": issues, "recommended_actions": actions, "assumptions_notes": assumptions, "data_quality": data_quality, "executive_summary": executive_summary}

def render_markdown(template_text: str, metrics: Dict[str, object]) -> str:
    top_tests = metrics.get("top_failing_tests", []) or []
    if top_tests:
        lines = ["| Rank | Test | Fail Count | Unique Parts | Failed Event Share | Sites |", "|---:|---|---:|---:|---:|---|"]
        for idx, row in enumerate(top_tests, 1):
            lines.append(f"| {idx} | {row.get('test_name','')} | {int(row.get('fail_count',0))} | {int(row.get('unique_parts',0))} | {float(row.get('share_of_failed_events',0.0)):.2f}% | {row.get('sites','')} |")
        top_table = "\n".join(lines)
    else:
        top_table = "No failing tests were detected."
    site_breakdown = metrics.get("site_failure_breakdown", []) or []
    site_summary = "\n".join([f"- Site **{row.get('site_num', 'unknown')}**: **{int(row.get('fail_count', 0))}** failed events across **{int(row.get('unique_parts', 0))}** parts ({float(row.get('share_of_failed_events', 0.0)):.2f}% of failed events)." for row in site_breakdown[:5]]) if site_breakdown else "No site-related failure concentration was detected or site data was unavailable."
    issues_text = "\n".join(f"- {x}" for x in (metrics.get("potential_issues", []) or [])) or "- No strong issue signal identified."
    actions_text = "\n".join(f"- {x}" for x in (metrics.get("recommended_actions", []) or [])) or "- None."
    assumptions_text = "\n".join(f"- {x}" for x in (metrics.get("assumptions_notes", []) or [])) or "- None."
    replacements = {
        "executive_summary": str(metrics.get("executive_summary", "")),
        "source_file": Path(str(metrics.get("source_file", ""))).name,
        "input_format": str(metrics.get("input_format", "")),
        "rows_analyzed": str(metrics.get("rows_analyzed", 0)),
        "total_parts": str(metrics.get("total_parts", 0)),
        "site_count": str(metrics.get("site_count", 0)),
        "ignored_rows": str(metrics.get("ignored_rows", 0)),
        "yield_percent": f"{float(metrics.get('yield_percent', 0.0)):.2f}",
        "passing_parts": str(metrics.get("passing_parts", 0)),
        "failing_parts": str(metrics.get("failing_parts", 0)),
        "failed_test_events": str(metrics.get("failed_test_events", 0)),
        "top_failing_site": str(metrics.get("top_failing_site", "None")),
        "dominant_failing_test": str(metrics.get("dominant_failing_test", "None")),
        "top_failing_tests_table": top_table,
        "site_pattern_summary": site_summary,
        "potential_issues": issues_text,
        "recommended_actions": actions_text,
        "assumptions_notes": assumptions_text,
    }
    rendered = template_text
    for key, value in replacements.items(): rendered = rendered.replace("{{" + key + "}}", value)
    return rendered

def run(input_path: Path, output_path: Optional[Path], top_n: int, template_path: Path) -> AnalysisResult:
    ext = input_path.suffix.lower()
    if ext == ".csv": normalized, data_quality = load_csv_as_normalized(input_path); input_format = "csv"
    elif ext in {".stdf", ".std"}: normalized, data_quality = load_stdf_as_normalized(input_path); input_format = "stdf"
    else: raise RuntimeError(f"Unsupported file extension: {ext}")
    metrics = analyze(normalized, input_path, input_format, top_n, data_quality)
    report_markdown = render_markdown(template_path.read_text(encoding="utf-8"), metrics)
    if output_path is None: output_path = input_path.with_name(f"{input_path.stem}_summary.md")
    output_path.write_text(report_markdown, encoding="utf-8")
    metrics_json_path = output_path.with_suffix(".json")
    metrics_json_path.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    return AnalysisResult(normalized, metrics, report_markdown, output_path, metrics_json_path)

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze STDF or CSV test logs and generate a markdown summary.")
    p.add_argument("input", nargs="?", help="Path to .stdf/.std/.csv file. If omitted, the script directory is searched.")
    p.add_argument("--output", "-o", help="Output markdown path. Default: <input>_summary.md")
    p.add_argument("--top", type=int, default=10, help="Number of top failing tests to include. Default: 10")
    p.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to markdown template. Default: assets/output-template.md")
    return p.parse_args(argv)

def main(argv: List[str]) -> int:
    args = parse_args(argv); script_dir = Path(__file__).resolve().parent
    input_path = Path(args.input).expanduser().resolve() if args.input else _find_first_supported(script_dir)
    if input_path is None or not input_path.exists():
        print("No input file provided and no .stdf/.std/.csv file found in the scripts folder.", file=sys.stderr); return 2
    output_path = Path(args.output).expanduser().resolve() if args.output else None
    template_path = Path(args.template).expanduser().resolve()
    try:
        result = run(input_path, output_path, max(1, args.top), template_path)
    except Exception as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr); return 1
    print(result.report_markdown)
    print(f"\nSaved markdown summary to: {result.output_path}")
    print(f"Saved metrics JSON to: {result.metrics_json_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
