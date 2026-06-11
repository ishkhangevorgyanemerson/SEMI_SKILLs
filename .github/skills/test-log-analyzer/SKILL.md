---
name: test-log-analyzer
description: Analyze semiconductor .std / .stdf test logs and return a concise engineering summary in chat, plus a normalized CSV file if needed. Use this skill for yield review, fail count analysis, top failing tests ranking, site-based failure patterns, and first-pass root-cause guidance.
license: Apache-2.0
compatibility: Requires python3, pandas, and pystdf.
metadata:
  author: Ishkhan Gevorgyan
  version: "1.1.0"
  domain: semiconductor-test
  ## Chat response format
  Every time this skill is used it MUST return the analysis directly in chat using the exact layout below. Do not produce a separate markdown report file; return the content inline in the chat.

  Use this exact template (replace <value> placeholders with actual values):

  ### 1. Summary
  Present the main KPIs in a markdown table.

  | Metric | Value |
  |---|---:|
  | Total Parts Tested | <value> |
  | Passing Parts | <value> |
  | Failing Parts | <value> |
  | Yield % | <value> |
  | Total Fail Count | <value> |

  ### 2. Top Failing Tests
  Present the top failing tests in a markdown table.

  | Rank | Test Name / Test Number | Fail Count | Affected Sites |
  |---:|---|---:|---:|
  | 1 | <value> | <value> | <value> |
  | 2 | <value> | <value> | <value> |
  | 3 | <value> | <value> | <value> |

  If site information is not available, show `N/A`.

  ### 3. Site Pattern Summary
  Summarize site behavior in short bullet points, for example:
  - which site has the highest failure count
  - whether failures are concentrated on one site or spread across multiple sites
  - whether the evidence suggests a site-specific issue

  Explain meaning (do not simply repeat counts) — e.g. "Site 0 has the highest fail concentration and accounts for most failed events, which suggests a site hardware path issue rather than a broad DUT issue." 

  ### 4. Potential Issues
  Based on the observed patterns, explain the most likely issue categories. Use the provided possible interpretations as guidance (single-site concentration, one dominant test, several related parametric fails, many unrelated fails across sites).

  ### 5. What to Check First
  Always give practical first checks appropriate to the observed pattern (site-focused checks, test-focused checks, or global checks). Use short, actionable bullets.

  ### 6. Confidence / Assumptions
  State any important limitations such as missing fields, inferred part IDs, partial parsing, and whether the conclusion is high- or low-confidence.

  Behavior rules:
  - Always return the chat summary in the exact template above.
  - Do not create a markdown file for the primary summary.
  - Include interpretation and first-step checks, not just raw counts.

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
