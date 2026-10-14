# RUN_AUDIT_SCHEMA — output contract + verdict rule

## Schema

```
attestation{read_products, read_stdout, stdout_sha256_matched, detail},
verdict(pass|fail),
number_checks[]{value, source, found_in_file?, recomputed?, status(match|format_match|fabrication|not_found|derivation_mismatch), note?},
freshness_checks[]{path, git_status, sha_changed?, mtime_in_window, json_timestamp_in_window?, status(fresh|stale|mtime_out_of_window|metadata_mismatch)},
run_health{exit_code_ok, errors_in_log, sanity_gate(passed|failed|absent|not_applicable), sanity_discriminative, sanity_evidence, status(healthy|unhealthy)},
blocking_flags[]{check?, offending?, why}
```

## Verdict rule (strict AND)

`verdict:"pass"` is allowed **only if ALL** of the following hold:

- `attestation.read_products == true`
- `attestation.read_stdout == true`
- `attestation.stdout_sha256_matched == true`
- every `number_checks[].status ∈ {match, format_match}`
- every `freshness_checks[].status == "fresh"`
- `run_health.status == "healthy"` — which REQUIRES the sanity self-check to be present, passed, AND
  discriminative (`sanity_discriminative == true`). A vacuous/field-presence sanity (`sanity_discriminative
  == false`) ⇒ `run_health.status == "unhealthy"` ⇒ FAIL: a number you cannot tie to a hard-to-forge
  self-check is not certifiable.

Anything else ⇒ `verdict:"fail"` with `blocking_flags` listing each failing check. A tooling
failure (could not read, sha mismatch) is a FAIL, never a courtesy PASS. On FAIL the orchestrator
blesses nothing and escalates the item to the author.
