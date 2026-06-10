---
name: test-log-analyzer
description: Analyze semiconductor .std / .stdf test logs and return a concise engineering summary in chat, plus a normalized CSV file if needed. Use this skill for yield review, fail count analysis, top failing tests ranking, site-based failure patterns, and first-pass root-cause guidance.
license: Apache-2.0
compatibility: Requires python3, pandas, and pystdf.
metadata:
  author: Ishkhan Gevorgyan
  version: "1.1.0"
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

The summary must be:
- written directly in chat
- short
- structured
- engineer-friendly
- focused on action

Only generate a `.csv` output file when needed.

## Chat response format
The reply in chat should follow this structure:

### 1. Summary
- total parts tested
- passing parts
- failing parts
- yield %
- total fail count

### 2. Top Failing Tests
For each top failing test include:
- rank
- test name / test number
- fail count
- affected sites if visible

### 3. Site Pattern Summary
Summarize failure concentration by site:
- which site has the highest failure count
- whether the failures are strongly concentrated or distributed
- whether it looks like a site-specific issue

### 4. Potential Issues
Based on the observed results, explain the most likely issue types, for example:
- **Single-site concentration** → possible contactor, pogo, socket, site hardware, instrument path, loadboard channel, relay path, calibration mismatch
- **One dominant failing test** → likely test setup issue, incorrect limit, unstable measurement path, wrong instrument condition, software/test-program issue
- **Multiple related parametric fails** → possible DUT/process shift, voltage drift, temperature drift, analog measurement chain issue
- **Many unrelated fails across all sites** → possible common setup issue, shared supply issue, wrong test conditions, tester state issue, product/process issue

### 5. What to check first
The skill should always suggest the first validation steps, for example:
- if one site dominates failures:
  - compare that site against the others
  - inspect socket/contact path
  - inspect site hardware path
  - verify relay/loadboard/channel integrity
  - re-run with known good unit on the failing site
- if one test dominates:
  - verify test limits
  - verify test method and instrument setup
  - compare passing vs failing measurements
  - check recent program or limit changes
- if failures are global:
  - verify common power rails
  - verify shared instruments
  - verify environment / temperature conditions
  - review lot/process information if available

### 6. Assumptions / Limits
Mention:
- if some fields were missing
- if part IDs were inferred
- if parsing was partial
- if the conclusion is high-confidence or only first-pass guidance

## Workflow
1. Read the input `.std` / `.stdf` file
2. Parse available test records
3. Extract useful data such as:
   - part ID
   - site number
   - test number / test name
   - measured result
   - limits
   - fail status
   - hard bin / soft bin if available
4. Compute:
   - yield
   - passing/failing part counts
   - total fail count
   - top failing tests
   - site-based fail concentration
5. Interpret the result
6. Return the summary directly in chat
7. Generate only a `.csv` file if needed

## Behavior rules
- Focus on the most important failure trends
- Do not dump raw records unless requested
- Do not create a markdown report file
- Always provide interpretation, not only raw counts
- Always explain what looks suspicious
- Always say where the user should check first
- If data is incomplete, still provide the best first-pass engineering assessment
- If parsing dependencies are missing, report the missing package clearly

## Quality rules
A good response should not stop at:
- “Site 0 has 28 failures”

A good response should continue with reasoning such as:
- whether Site 0 dominates the fail population
- whether this points to a site hardware issue
- whether the user should first inspect socket/contact/loadboard/instrument path
- whether the dominant failing test suggests a setup or test-method issue instead of a DUT issue

## Success criteria
A good result must:
- correctly calculate yield
- correctly count failed events
- correctly rank top failing tests
- clearly summarize site-related fail patterns
- provide useful first-pass root-cause guidance
- tell the user what to verify first
- return the summary in chat, not as a markdown file
