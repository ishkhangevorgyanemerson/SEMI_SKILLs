# Chat Response Template — Test Log Analyzer

## 1. Summary

| Metric | Value |
|---|---:|
| Total Parts Tested | {{total_parts}} |
| Passing Parts | {{passing_parts}} |
| Failing Parts | {{failing_parts}} |
| Yield % | {{yield_percent}} |
| Total Fail Count | {{total_fail_count}} |

## 2. Top Failing Tests

| Rank | Test Name / Test Number | Fail Count | Affected Sites |
|---:|---|---:|---|
{{top_failing_tests_rows}}

## 3. Site Pattern Summary
{{site_pattern_summary}}

## 4. Potential Issues
{{potential_issues}}

## 5. What to Check First
{{first_checks}}

## 6. Confidence / Assumptions
{{assumptions_notes}}

---

## Placeholder guidance

### `{{top_failing_tests_rows}}`
Use one markdown table row per test, for example:

```md
| 1 | Coff_RF1_1880M | 4 | 0 |
| 2 | D_Count_A1_to_GND | 4 | 0 |
| 3 | Off_DC_RF1_AOFF | 4 | 4 |
```

If site information is not available, show `N/A`.

### `{{site_pattern_summary}}`
Use short bullets with interpretation, for example:

```md
- Site **0** has the highest failure concentration.
- Failures are mainly concentrated on a small number of sites rather than being evenly distributed.
- This pattern suggests a **site-specific issue** is more likely than a broad DUT/process issue.
```

### `{{potential_issues}}`
Connect the observed pattern to likely issue categories, for example:

```md
- The strong failure concentration on one site suggests possible issues in the **socket/contact path**, **site hardware path**, **relay/loadboard channel**, or **instrument path**.
- Because a small number of tests dominate the failures, the issue may also be related to **test setup**, **limit configuration**, or **channel-specific instrumentation**.
```

### `{{first_checks}}`
Always give practical validation steps, for example:

```md
- Re-run a known good unit on the dominant failing site.
- Compare the failing site against passing sites using the same unit if possible.
- Inspect **socket/contact quality**, **pogo/contact resistance**, **relay path**, and **loadboard channel mapping**.
- Verify limits, instrument setup, and any recent program changes for the top failing tests.
```

### `{{assumptions_notes}}`
State confidence and limits, for example:

```md
- This is a first-pass analysis based on parsed STD/STDF records.
- If some records were partially parsed or part IDs were inferred, confidence is reduced.
- The conclusions are intended to guide early debug, not replace detailed failure analysis.
```
