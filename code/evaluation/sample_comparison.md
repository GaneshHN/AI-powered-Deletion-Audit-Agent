# Public sample comparison

- Prediction source: `python code/main.py --sample` (same parser and audit algorithm as full evaluation).
- Generated predictions: `sample_prediction.csv`, compared by `case_id`.
- Status accuracy: 26/32 (81.25%)
- Expected COMPLETE predicted INCOMPLETE: 6; expected INCOMPLETE predicted COMPLETE: 0
- Step counts: expected 193, predicted 134; cases with count mismatch: 27/32
- Aligned step accuracy: 100/193 (51.81%) exact step objects; field accuracy: 827/1351 (61.21%)
- Positional operation mismatches (including missing/extra positions): 84
- Evidence-reference validity: 50/50 predicted non-empty references valid and admissible; positional reference mismatches vs. public answers: 0
- Cases with correct step multiset but incorrect order: 0
- Exact status-and-step results: 4/32 (12.50%)
- Confusion: {"COMPLETE->COMPLETE": 4, "COMPLETE->INCOMPLETE": 6, "INCOMPLETE->INCOMPLETE": 22}

## Classification errors

- case_01: false INCOMPLETE (expected COMPLETE)
- case_02: false INCOMPLETE (expected COMPLETE)
- case_04: false INCOMPLETE (expected COMPLETE)
- case_21: false INCOMPLETE (expected COMPLETE)
- case_25: false INCOMPLETE (expected COMPLETE)
- case_28: false INCOMPLETE (expected COMPLETE)

## Case-level step mismatches

- case_01: status COMPLETE -> INCOMPLETE; steps 1 -> 0; operations: step 1: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_54'] -> []
- case_02: status COMPLETE -> INCOMPLETE; steps 1 -> 0; operations: step 1: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_54'] -> []
- case_03: status COMPLETE -> COMPLETE; steps 3 -> 2; operations: step 3: VERIFY_RECORD_ANONYMIZED -> <missing>; evidence refs: ['evidence_94', 'evidence_94', 'evidence_94'] -> ['evidence_94', 'evidence_94']
- case_04: status COMPLETE -> INCOMPLETE; steps 2 -> 0; operations: step 1: VERIFY_RECORD_ABSENT -> <missing>, step 2: VERIFY_RECORD_ANONYMIZED -> <missing>; evidence refs: ['evidence_54', 'evidence_56'] -> []
- case_06: status INCOMPLETE -> INCOMPLETE; steps 4 -> 3; operations: step 4: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_57', '', '', ''] -> ['evidence_57', '', '']
- case_07: status INCOMPLETE -> INCOMPLETE; steps 4 -> 3; operations: step 4: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_58', '', '', ''] -> ['evidence_58', '', '']
- case_08: status INCOMPLETE -> INCOMPLETE; steps 4 -> 3; operations: step 4: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_59', '', '', ''] -> ['evidence_59', '', '']
- case_09: status INCOMPLETE -> INCOMPLETE; steps 5 -> 3; operations: step 3: VERIFY_RECORD_ABSENT -> VERIFY_RESTORE_BLOCKED, step 4: VERIFY_RECORD_PRESENT -> <missing>, step 5: VERIFY_RESTORE_BLOCKED -> <missing>; evidence refs: ['evidence_93', '', '', '', ''] -> ['evidence_93', '', '']
- case_10: status INCOMPLETE -> INCOMPLETE; steps 4 -> 0; operations: step 1: REPORT_REMAINING_RECORD -> <missing>, step 2: DELETE_RECORD -> <missing>, step 3: VERIFY_RECORD_ABSENT -> <missing>, step 4: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_61', '', '', ''] -> []
- case_12: status INCOMPLETE -> INCOMPLETE; steps 5 -> 4; operations: step 1: REPORT_REMAINING_RECORD -> REPORT_EXPOSED_PII, step 2: DELETE_RECORD -> ANONYMIZE_RECORD, step 4: VERIFY_RECORD_ABSENT -> VERIFY_RECORD_ANONYMIZED, step 5: VERIFY_RECORD_PRESENT -> <missing>; evidence refs: ['evidence_01', '', '', '', ''] -> ['evidence_01', '', '', '']
- case_15: status INCOMPLETE -> INCOMPLETE; steps 5 -> 4; operations: step 4: VERIFY_RECORD_PRESENT -> VERIFY_DATA_FLOW_DISABLED, step 5: VERIFY_DATA_FLOW_DISABLED -> <missing>; evidence refs: ['evidence_01', '', '', '', ''] -> ['evidence_01', '', '', '']
- case_16: status INCOMPLETE -> INCOMPLETE; steps 7 -> 0; operations: step 1: REPORT_REMAINING_RECORD -> <missing>, step 2: REPORT_REMAINING_RECORD -> <missing>, step 3: DELETE_RECORD -> <missing>, step 4: DELETE_RECORD -> <missing>, step 5: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_05', 'evidence_05', '', '', '', '', ''] -> []
- case_17: status INCOMPLETE -> INCOMPLETE; steps 5 -> 5; operations: step 4: VERIFY_RECORD_PRESENT -> VERIFY_RECORD_ABSENT
- case_18: status INCOMPLETE -> INCOMPLETE; steps 14 -> 12; operations: step 10: VERIFY_RECORD_ABSENT -> VERIFY_RECORD_REDACTED, step 11: VERIFY_RECORD_PRESENT -> VERIFY_RECORD_ANONYMIZED, step 12: VERIFY_RECORD_REDACTED -> VERIFY_DATA_FLOW_DISABLED, step 13: VERIFY_RECORD_ANONYMIZED -> <missing>, step 14: VERIFY_DATA_FLOW_DISABLED -> <missing>; evidence refs: ['evidence_94', 'evidence_94', 'evidence_94', 'evidence_94', '', '', '', '', '', '', '', '', '', ''] -> ['evidence_94', 'evidence_94', 'evidence_94', 'evidence_94', '', '', '', '', '', '', '', '']
- case_19: status INCOMPLETE -> INCOMPLETE; steps 8 -> 7; operations: step 7: VERIFY_RECORD_PRESENT -> VERIFY_RECORD_REDACTED, step 8: VERIFY_RECORD_REDACTED -> <missing>; evidence refs: ['evidence_01', 'evidence_01', '', '', '', '', '', ''] -> ['evidence_01', 'evidence_01', '', '', '', '', '']
- case_20: status INCOMPLETE -> INCOMPLETE; steps 8 -> 6; operations: step 6: VERIFY_RECORD_ABSENT -> VERIFY_DATA_FLOW_DISABLED, step 7: VERIFY_RECORD_PRESENT -> <missing>, step 8: VERIFY_DATA_FLOW_DISABLED -> <missing>; evidence refs: ['evidence_94', 'evidence_94', '', '', '', '', '', ''] -> ['evidence_94', 'evidence_94', '', '', '', '']
- case_21: status COMPLETE -> INCOMPLETE; steps 3 -> 0; operations: step 1: VERIFY_RECORD_ABSENT -> <missing>, step 2: VERIFY_RECORD_PRESENT -> <missing>, step 3: VERIFY_RECORD_ANONYMIZED -> <missing>; evidence refs: ['evidence_92', 'evidence_92', 'evidence_92'] -> []
- case_22: status INCOMPLETE -> INCOMPLETE; steps 8 -> 0; operations: step 1: REPORT_REMAINING_RECORD -> <missing>, step 2: REPORT_EXPOSED_PII -> <missing>, step 3: DELETE_RECORD -> <missing>, step 4: ANONYMIZE_RECORD -> <missing>, step 5: VERIFY_RECORD_ABSENT -> <missing>; evidence refs: ['evidence_05', 'evidence_05', '', '', '', '', '', ''] -> []
- case_23: status INCOMPLETE -> INCOMPLETE; steps 8 -> 6; operations: step 7: VERIFY_RECORD_ABSENT -> <missing>, step 8: VERIFY_RECORD_PRESENT -> <missing>; evidence refs: ['evidence_92', 'evidence_92', '', '', '', '', '', ''] -> ['evidence_92', 'evidence_92', '', '', '', '']
- case_24: status INCOMPLETE -> INCOMPLETE; steps 7 -> 6; operations: step 7: VERIFY_RECORD_PRESENT -> <missing>; evidence refs: ['evidence_92', 'evidence_92', '', '', '', '', ''] -> ['evidence_92', 'evidence_92', '', '', '', '']
- case_25: status COMPLETE -> INCOMPLETE; steps 3 -> 0; operations: step 1: VERIFY_RECORD_ABSENT -> <missing>, step 2: VERIFY_RECORD_PRESENT -> <missing>, step 3: VERIFY_RECORD_ANONYMIZED -> <missing>; evidence refs: ['evidence_92', 'evidence_92', 'evidence_92'] -> []
- case_26: status COMPLETE -> COMPLETE; steps 6 -> 5; operations: step 4: VERIFY_RECORD_ANONYMIZED -> VERIFY_DATA_FLOW_DISABLED, step 5: VERIFY_DATA_FLOW_DISABLED -> VERIFY_RESTORE_BLOCKED, step 6: VERIFY_RESTORE_BLOCKED -> <missing>; evidence refs: ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92'] -> ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92']
- case_27: status COMPLETE -> COMPLETE; steps 6 -> 5; operations: step 4: VERIFY_RECORD_ANONYMIZED -> VERIFY_DATA_FLOW_DISABLED, step 5: VERIFY_DATA_FLOW_DISABLED -> VERIFY_RESTORE_BLOCKED, step 6: VERIFY_RESTORE_BLOCKED -> <missing>; evidence refs: ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92'] -> ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92']
- case_28: status COMPLETE -> INCOMPLETE; steps 6 -> 0; operations: step 1: VERIFY_RECORD_ABSENT -> <missing>, step 2: VERIFY_RECORD_PRESENT -> <missing>, step 3: VERIFY_RECORD_REDACTED -> <missing>, step 4: VERIFY_RECORD_ANONYMIZED -> <missing>, step 5: VERIFY_DATA_FLOW_DISABLED -> <missing>; evidence refs: ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', 'evidence_92'] -> []
- case_29: status INCOMPLETE -> INCOMPLETE; steps 14 -> 12; operations: step 10: VERIFY_RECORD_ABSENT -> VERIFY_RECORD_REDACTED, step 11: VERIFY_RECORD_PRESENT -> VERIFY_RECORD_ANONYMIZED, step 12: VERIFY_RECORD_REDACTED -> VERIFY_DATA_FLOW_DISABLED, step 13: VERIFY_RECORD_ANONYMIZED -> <missing>, step 14: VERIFY_DATA_FLOW_DISABLED -> <missing>; evidence refs: ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', '', '', '', '', '', '', '', '', '', ''] -> ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', '', '', '', '', '', '', '', '']
- case_30: status INCOMPLETE -> INCOMPLETE; steps 14 -> 12; operations: step 10: VERIFY_RECORD_ABSENT -> VERIFY_RECORD_REDACTED, step 11: VERIFY_RECORD_PRESENT -> VERIFY_RECORD_ANONYMIZED, step 12: VERIFY_RECORD_REDACTED -> VERIFY_DATA_FLOW_DISABLED, step 13: VERIFY_RECORD_ANONYMIZED -> <missing>, step 14: VERIFY_DATA_FLOW_DISABLED -> <missing>; evidence refs: ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', '', '', '', '', '', '', '', '', '', ''] -> ['evidence_92', 'evidence_92', 'evidence_92', 'evidence_92', '', '', '', '', '', '', '', '']
- case_31: status COMPLETE -> COMPLETE; steps 3 -> 2; operations: step 1: VERIFY_RECORD_ABSENT -> VERIFY_RECORD_PRESENT, step 2: VERIFY_RECORD_PRESENT -> VERIFY_RECORD_REDACTED, step 3: VERIFY_RECORD_REDACTED -> <missing>; evidence refs: ['evidence_51', 'evidence_51', 'evidence_51'] -> ['evidence_51', 'evidence_51']
- case_32: status INCOMPLETE -> INCOMPLETE; steps 5 -> 4; operations: step 3: VERIFY_RECORD_ABSENT -> VERIFY_RECORD_PRESENT, step 4: VERIFY_RECORD_PRESENT -> VERIFY_RECORD_REDACTED, step 5: VERIFY_RECORD_REDACTED -> <missing>; evidence refs: ['evidence_51', '', '', '', ''] -> ['evidence_51', '', '', '']

## False INCOMPLETE trace review

The six status errors are `case_01`, `case_02`, `case_04`, `case_21`, `case_25`, and `case_28`. In each, request authorization, identity resolution, and the cutoff are valid; the blocker is admissible proof for the resource state(s) named by the sample answer.

- `case_01` / `case_02`: expected output points to `account_001` / `account_002` in `evidence_54`. Those resource rows are not present in the extracted SQL failover snapshot, and no direct identity-linked candidate is available. A manifest capture timestamp alone does not prove that the account row was absent.
- `case_04`: the expected account (`account_004`, `evidence_54`) and analytics (`analytics_901`, `evidence_56`) resource IDs are not linked to this user in parsed records. The expected analytics record has no subject identifiers; artifact co-location is insufficient.
- `case_21`: `evidence_92` links `audit_record_3737` to the user, but no linked `account_6440` or `analytics_5335` readback was extracted. The audit record does not prove those separate resources' states.
- `case_25`: `evidence_92` links the retained audit record to the user, but not account `account_3136` or analytics `analytics_1895`.
- `case_28`: subject-linked support (`support_2351`), backup (`backup_838`), data flow (`data_flow_2337`), and security audit (`audit_record_9265`) evidence is available. No linked account `account_5482` or analytics `analytics_6077` state is established.

These cases remain INCOMPLETE because none has the admissible account deletion proof required by the policy gate, and some also lack proof for other expected resource states. No resource is inferred from sample answer IDs. OCR is not a likely remedy for these mismatches: the relevant account snapshot is SQL and the later cases' records are structured JSON; OCR cannot supply absent identity/resource relationships. The one focused support PII scan correction added a regression test and raised step-object agreement without changing the status confusion matrix.
