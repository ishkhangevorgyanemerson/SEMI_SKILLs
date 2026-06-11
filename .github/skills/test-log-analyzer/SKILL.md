---
name: test-log-analyzer
description: Analyze semiconductor .std / .stdf test logs and return a concise engineering summary directly in chat, plus a normalized CSV file when needed. Use this skill for yield review, fail count analysis, top failing tests ranking, site-based failure patterns, and first-pass root-cause guidance.
license: Apache-2.0
compatibility: Requires python3, pandas, and pystdf.
metadata:
  author: Ishkhan Gevorgyan
  version: "1.2.0"
  domain: semiconductor-test
  input-formats:
    - std
    - stdf
  primary-output: chat-summary
  secondary-output: csv
---

# Test Log Analyzer

## Purpose
This skill reads a semiconductor test log file and returns a practical engineering summary directly in chat.

## When to use
Use this skill when the task is to:
- analyze a `.std` or `.stdf` file
- calculate yield
- count failures
- rank top failing tests
- identify site-based failure concentration
- suggest likely issue areas and where to check first

## Input
Expected input:
- a valid `.std` or `.stdf` file path

Example:
```text
C:\Users\igevorgy\Desktop\SEMI_SKILLs\File\Mobile Device Test_10Jun2026_1458.std
```

## Required outputs
This skill must return the result **in chat**.

Primary output in chat:
- yield
- passing part count
- failing part count
- total fail count
- top failing tests ranking
- site pattern summary
- likely issue signals
- suggested first checks

Optional file output:
- normalized `.csv` file

## Important output rule
Do **not** generate a markdown report file.

The answer must be:
- written directly in chat
- short
- structured
- engineer-friendly
- focused on action

Only generate a `.csv` output file when needed.

## Output format
Use the structure defined in `output-template.md`.

That file defines how the chat response should look.

## Workflow
1. Read the input `.std` / `.stdf` file.
2. Parse available test records.
3. Extract useful data such as:
   - part ID
   - site number
   - test number / test name
   - measured result
   - limits
   - fail status
   - hard bin / soft bin if available
4. Compute:
   - total parts tested
   - passing part count
   - failing part count
   - yield %
   - total fail count
   - top failing tests
   - site-based fail concentration
5. Interpret the result.
6. Return the summary directly in chat using `output-template.md`.
7. Generate only a `.csv` file if needed.

## Interpretation rules
Do not return only counts.
Always return:
- interpretation
- likely issue direction
- first validation steps

Examples of expected reasoning:
- If failures are concentrated on one site, suggest a possible socket/contact/loadboard/site hardware issue.
- If one test dominates failures, suggest checking limits, test method, recent program changes, and instrument setup.
- If failures are spread across all sites, suggest checking common rails, shared instruments, environment, or process/product conditions.

## Behavior rules
- Focus on the most important failure trends.
- Do not dump raw records unless requested.
- Do not create a markdown report file.
- Always provide interpretation, not only raw counts.
- Always explain what looks suspicious.
- Always say where the user should check first.
- If data is incomplete, still provide the best first-pass engineering assessment.
- If parsing dependencies are missing, report the missing package clearly.
- Format KPI results as markdown tables.
- Format top failing tests as a markdown table.
- Site pattern summary must include interpretation, not only raw counts.

## Quality rules
A poor response is:
- `Site 0 has 28 failures`

A good response continues with reasoning such as:
- whether Site 0 dominates the fail population
- whether this suggests a site hardware issue or a broader problem
- whether the user should inspect socket/contact/loadboard/instrument path first
- whether the dominant failing test suggests a setup/test-method issue instead of a DUT issue

## Success criteria
A good result must:
- correctly calculate yield
- correctly count failed events
- correctly rank top failing tests
- show the KPI summary in a table
- show top failing tests in a table
- clearly summarize site-related fail patterns
- provide useful first-pass root-cause guidance
- tell the user what to verify first
- return the summary in chat, not as a markdown file