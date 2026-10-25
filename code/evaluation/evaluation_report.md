# Evaluation report

## Full evaluation output

The latest full run used Python 3.13.6 (`C:\Program Files\Python313\python.exe`) and completed all 518 cases in 2.537 seconds. `code/main.py` wrote a same-directory temporary file, validated it, and atomically replaced root `output.csv`. The resulting counts are 46 `COMPLETE`, 467 `INCOMPLETE`, and 5 `NOT_APPLICABLE`. Of the INCOMPLETE rows, 241 have an empty steps array because no positive, admissible evidence link was established. These results are not calibrated to a target distribution.

`python code/validate_output.py` passed: 518 unique sorted IDs, exact header `case_id,deletion_status,steps_json`, allowed statuses, parseable JSON arrays, exactly seven fields per step, consecutive numbering, allowed operation/state combinations, phase ordering, valid evidence references, and audit cutoffs. There is no public answer key for the full 518-case set, so its accuracy is unknown.

## Public sample evaluation

The genuine sample mode runs `python code/main.py --sample` and uses the same evidence loading, indexes, identity resolver, classification, and `audit_case()` as the full run. It writes `code/evaluation/sample_prediction.csv`; SHA-256 before and after the sample run confirmed root `output.csv` was preserved. `code/evaluation/compare_samples.py` compares by `case_id` against the public `dataset/sample_output.csv`.

- Exact status accuracy: 26/32 (81.25%). 4/10 expected COMPLETE cases were recognized; six were false INCOMPLETE. There were no false COMPLETE classifications among the 22 expected INCOMPLETE cases.
- Step counts: 193 expected and 134 predicted; counts differ for 27/32 cases.
- Positional exact step-object accuracy: 100/193 (51.81%). Field accuracy: 827/1,351 (61.21%). Positional operation mismatches, including missing or extra positions: 84.
- Evidence references: all 50/50 predicted non-empty references are valid, visible in the participant dataset, and admissible at the case cutoff. No positional evidence-reference values differ from the sample answer.
- Pure ordering errors (same step multiset in a different order): 0. Exact status-and-step sequences: 4/32 (12.50%).

### Investigation of the six false INCOMPLETE cases

All six cases resolve to the intended user and have a valid deletion request and audit cutoff. The prediction does not find any admissible resource-level verification for the account or all policy-required copies, so the account-completion proof gate keeps the result INCOMPLETE. The sample answer names specific resource IDs that cannot be independently tied to the resolved subject in the extracted participant evidence:

- `case_01` and `case_02`: the reference answer cites `account_001` and `account_002` in `evidence_54`. The extracted SQL failover snapshot has no such subject-linked rows. The manifest capture is within the audit window, but the file-level timestamp does not establish either resource's state.
- `case_04`: the answer cites `account_004` in `evidence_54` and `analytics_901` in `evidence_56`. Neither resource is linked to the resolved identity in the parsed evidence; the analytics row is anonymized and contains no subject identifier. Co-presence in an artifact is not a valid identity link.
- `case_21`: `evidence_92` directly links the retained security audit record to the user. The answer's account resource `account_6440` and analytics resource `analytics_5335` are not linked by identifiers or resource readbacks. The security record alone cannot prove those separate states.
- `case_25`: `evidence_92` directly links the security audit record to the user. It does not link account `account_3136` or analytics `analytics_1895`; their expected clean states cannot be inferred from the audit record.
- `case_28`: the evidence directly links the security, support, backup, and disabled data-flow records to the user. It does not link account `account_5482` or analytics `analytics_6077`. The verified secondary records do not prove the account deletion or the unlinked analytics state.

No shared evidence-backed rule supports marking these six cases COMPLETE. OCR is unlikely to resolve these specific misses: the cited account snapshot is SQL and the case_21/25/28 evidence is structured JSON; missing subject/resource links cannot be recovered from unrelated screenshot text. Therefore no OCR dependency was added.

### Step mismatch analysis and improvements

Step count mismatches fell from 29/32 in the prior measured baseline to 27/32. Exact aligned objects rose from 34.87% to 51.81%, field accuracy from 50.33% to 61.21%, and exact sequences from 1/32 to 4/32. The improvements came from shared parser/linkage corrections, not sample IDs or answer copying:

- Pipe-delimited handover rows now preserve resource, state, service, category, and subject fields instead of losing state and generating incomplete/bogus plans.
- A single-resource PDF may link its heading resource to its sole email across the document, allowing the support attachment to be attributed without joining multiple resources by co-presence.
- A support `message_pii_scan` event with `detector=direct_identifier` and a non-empty match now reports exposed PII and proposes redaction.
- Resource matching requires exact structured identifiers or exact name fields / whole-token prose matches; conflicting strong identifiers block same-name matches.
- Timestamps and evidence references remain cutoff-checked; no evidence-free absence claims were introduced.

Remaining step mismatches include records that the public answer associates by ungrounded resource IDs, differing numbers of verification rows, and a policy difference for attributable analytics: the implementation follows the supplied anonymization policy rather than proposing deletion. Positional evidence-reference agreement is currently exact, though exact sequences remain low. See [sample_comparison.md](sample_comparison.md) for every case's measured differences.

## Automated tests and participant-created evaluation cases

Command: `python code/test_main.py -v` — 25 tests passed.

The suite includes participant-created regression cases for: historical email resolution; excluding evidence after `audit_at`; mapping each data category to policy actions; rejecting non-deletion requests; maintaining finding/remediation/verification order; 404 readback verification; refusing to treat a retained security record as account deletion proof; preferring a later linked readback; tie-breaking a completed lookup over a started trace; identity propagation only within a shared trace; exact name matching with conflicting email rejection; parsing pipe-delimited handovers; single-resource PDF attribution; support PII scanner findings; tombstone treatment; and precise missing-Pillow-OCR diagnostics for otherwise valid PNGs.

## Evidence extraction and remaining limitations

The run parsed 4,094 structured records from 94 manifest files (28 JSON, 26 logs, 24 SQL, one text, four PDFs, and 11 PNGs). `from PIL import Image` successfully decoded all 11 images. `from pypdf import PdfReader` extracted text from all four PDFs. The only current warnings identify the missing optional Python module `pytesseract`; the Tesseract executable is also not installed. Image bytes are decoded, but image text is not inferred and unreadable/unprocessed images are never treated as clean proof.

The deterministic authorization detector is pattern-based, not general language understanding. The full-set classification accuracy is not known, and 241 INCOMPLETE rows have no supported finding steps. Public step-sequence agreement is 4/32. These limitations should be considered before treating the output as high-confidence audit results.
