---
name: test-log-analyzer
description: Analyze semiconductor test logs in STDF or CSV format and produce a concise, structured markdown summary of yield, top failing tests, fail counts, site patterns, and likely root-cause signals. Use when the task involves ATE datalogs, test failures, yield triage, binning trends, parametric limit violations, or quick post-run summaries.
license: Apache-2.0
compatibility: Requires python3 and pandas. For binary STDF input, prefer an installed parser backend such as stdfast or pystdf. Reads ./assets/output-template.md and executes ./scripts/analyze_test_logs.py.
metadata:
  author: Ishkhan Gevorgyan
  version: "1.0.0"
  domain: semiconductor-test
  input-formats:
    - stdf
    - csv
  output-format: markdown
allowed-tools: read_skill_resource run_skill_script
---

# Test Log Analyzer

## When to use this skill
Use this skill when a user asks to:
- summarize an STDF or CSV test log
- calculate yield, fail counts, or top failing tests
- identify bad sites, retest-heavy patterns, or likely problem areas
- turn raw datalogs into a short engineering summary

## Skill objective
Convert raw semiconductor test logs into a short, decision-ready report. The report must help an engineer understand:
1. overall yield and volume
2. which tests fail most often
3. whether failures are concentrated by site, bin, or limit direction
4. which issues deserve immediate triage

## Inputs this skill accepts
### Preferred input
- A **binary STDF (.stdf, .std)** file
- A **CSV** file with test-level rows

### Minimum fields expected for CSV
The script will try to auto-map common aliases. Best results come from these columns:
- `part_id`
- `site_num`
- `test_name` or `test_num`
- `result` or `measured_value`
- `lo_limit`
- `hi_limit`
- optional: `status`, `units`, `soft_bin`, `hard_bin`

### CSV alias handling
The script auto-detects common column variants such as:
- part identifier: `part_id`, `part`, `serial_number`, `dut`, `device_id`
- site: `site`, `site_num`, `site_number`
- result: `result`, `measured_value`, `value`, `measurement`
- limits: `lo_limit`, `lsl`, `lower_limit`, `hi_limit`, `usl`, `upper_limit`
- pass/fail: `status`, `pf`, `pass_fail`, `test_passed`

## Output contract
The final report must follow the markdown structure in:
- `./assets/output-template.md`

The skill should generate a filled report with:
- short executive summary
- key metrics
- ranked failing tests
- site pattern summary
- likely issue signals
- recommended next actions
- assumptions / data quality notes

## Execution workflow
1. **Inspect input type**
   - If extension is `.csv`, read as tabular data.
   - If extension is `.stdf` or `.std`, parse via available STDF backend.

2. **Normalize records**
   Convert input into a common row model:
   - `part_id`
   - `site_num`
   - `test_num`
   - `test_name`
   - `result`
   - `lo_limit`
   - `hi_limit`
   - `units`
   - `status` (`PASS` / `FAIL`)
   - `source_record`

3. **Compute core metrics**
   - total tested parts
   - passing parts
   - failing parts
   - yield percent
   - total failed test events
   - top failing tests by fail count
   - fail concentration by site
   - soft/hard bin distributions when present

4. **Detect simple patterns**
   Highlight only high-signal patterns such as:
   - one site accounts for a disproportionate share of failures
   - one or two tests dominate the failure population
   - mostly high-side or low-side parametric violations
   - missing limits or malformed rows that weaken confidence

5. **Generate output**
   Fill the markdown template in `./assets/output-template.md`.

## Script to run
Use:
- `./scripts/analyze_test_logs.py`

### Recommended examples
```bash
python3 ./scripts/analyze_test_logs.py ./sample.stdf
python3 ./scripts/analyze_test_logs.py ./sample.csv --top 10 --output ./sample_summary.md
```

## Output style rules
- keep the summary concise and readable
- prefer ranked bullets over long paragraphs
- avoid raw dumps of every failing row
- mention confidence limits and missing data explicitly
- if data quality is weak, say so in **Assumptions and Data Quality Notes**

## Heuristics for “Potential Issues”
Use these signals only when supported by the data:
- **Low yield risk**: yield < 95%
- **Dominant test issue**: top failing test contributes >= 30% of failed events
- **Single-site issue**: one site contributes >= 50% of failed events with multi-site data
- **Limit drift signal**: parametric failures cluster mostly above `hi_limit` or below `lo_limit`

## Edge cases
### If STDF parsing backend is unavailable
Return a clear message that CSV is supported immediately, and STDF requires one of the supported parser libraries.

### If `status` is absent in CSV
Infer pass/fail from limits when `result`, `lo_limit`, and/or `hi_limit` exist.

### If `part_id` is missing
Create a synthetic part identifier from row index, but mention the limitation in the report.

### If there are duplicate part/test rows
Keep them as independent test events unless the user explicitly requests deduplication.

## Deliverables from this skill
- filled markdown summary report
- optional normalized CSV export (future enhancement)
- optional JSON metrics export (already supported by the script)

## Files in this skill
- `SKILL.md` — discovery metadata + instructions
- `assets/output-template.md` — required report structure
- `scripts/analyze_test_logs.py` — parser, analyzer, and report generator
