# Chat Response Template — Test Log Analyzer

## Key findings:

- **Total parts:** {{total_parts}}
- **Yield:** {{yield_percent}}%
- **Passing parts:** {{passing_parts}}
- **Failing parts:** {{failing_parts}}
- **Total failed test events:** {{failed_test_events}}
- **Top failing tests:**
{{top_failing_tests_bullets}}
- **Most failure-heavy sites:**
{{site_failure_bullets}}

## Initial interpretation
{{initial_interpretation}}

## Potential causes
{{potential_causes}}

## What to check first
{{first_checks}}

## Suggested improvements / next actions
{{next_actions}}

## Confidence / assumptions
{{assumptions_notes}}

---

## Placeholder guidance

### `{{top_failing_tests_bullets}}`
Use nested bullets, for example:

```md
  - Coff_RF1_1880M — 4 failures
  - Cont_A1_to_GND — 4 failures
  - Roff_DC_RF1_AOFF — 4 failures
```

### `{{site_failure_bullets}}`
Use nested bullets, for example:

```md
  - Site 9: 6 failures
  - Site 6: 4 failures
  - Site 7: 4 failures
  - Site 8: 4 failures
```

### `{{initial_interpretation}}`
Briefly explain what the pattern means, for example:

```md
- Yield is still high, so the issue does not look like a broad systemic production problem.
- Failures are concentrated in a small number of tests and sites, which suggests a localized issue rather than a full product-wide shift.
- The site pattern should be checked before assuming a DUT or process issue.
```

### `{{potential_causes}}`
Connect the observed pattern to likely issue categories, for example:

```md
- Concentration on a few sites suggests possible **socket/contact**, **site channel**, **relay path**, or **loadboard path** issues.
- A small set of dominant failing tests suggests **test setup**, **limit configuration**, **instrument path**, or **program change** issues.
- If the same tests fail repeatedly with similar counts, verify whether the issue is method-related before suspecting broad DUT failures.
```

### `{{first_checks}}`
Always give practical validation steps, for example:

```md
- Re-run a known good unit on the most failure-heavy site.
- Compare failing sites against passing sites using the same unit if possible.
- Check socket/contact quality, pogo resistance, relay path, and loadboard channel mapping.
- Verify test limits, instrument setup, and recent program changes for the top failing tests.
```

### `{{next_actions}}`
Suggest useful actions after the first checks, for example:

```md
- If site correlation is confirmed, isolate and swap the suspect hardware path.
- If one test remains dominant, review test method stability and guardband strategy.
- Trend the same failing tests across more logs to see whether the issue is persistent or lot-specific.
```

### `{{assumptions_notes}}`
State confidence and limits, for example:

```md
- This is a first-pass analysis based on parsed STD/STDF records.
- If some records were partially parsed or part IDs were inferred, confidence is reduced.
- The conclusions are intended to guide early debug, not replace detailed failure analysis.
```
