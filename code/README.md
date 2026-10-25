# Ghost Data Still Exists audit agent

## Run

Requires Python 3.13. JSON, SQL, logs, and CSV use the standard library. PDF extraction uses `pypdf`; screenshot decoding uses Pillow. Screenshot OCR additionally requires the `pytesseract` Python package and the Tesseract executable. From the repository root:

```powershell
python code/main.py
python code/main.py --sample
python code/evaluation/compare_samples.py
python code/validate_output.py
python code/test_main.py -v
```

The first command reads only participant-facing files in `dataset/` and writes `output.csv` in the repository root. `--sample` runs the same pipeline against `sample_deletion_requests.csv` and writes `code/evaluation/sample_prediction.csv`; the comparator then reports case-level differences against `sample_output.csv`. Paths are resolved relative to the script, so it also works when invoked from another directory.

Image/PDF extraction uses `from PIL import Image` and `from pypdf import PdfReader`. In the measured Python environment, Pillow 11.3.0 and pypdf 6.21.2 are installed and available to `python .\code\main.py`. The exact missing image dependency is `pytesseract` (`ModuleNotFoundError.name == "pytesseract"`); the Tesseract executable is also absent. Pillow validates image readability but does not extract text. Unsupported or unreadable artifacts are reported to stderr and are never treated as evidence of absence.

## Architecture

The pipeline loads the request, current identity snapshot, historical identity audit, evidence manifest, and deletion policy context. It parses evidence once, normalizes timestamps and text once, and builds current/historical email, user, identifier, trigram, resource, and system indexes. Each case narrows to matching candidates before the capture and observation cutoffs are checked against `audit_at`. Evidence records are classified by system and policy treatment. A finding generates ordered remediation and future-verification steps; a case is marked complete only when point-in-time account evidence and matching verification evidence support it. Workflow statuses and activity success claims are not used as state proof.

Output ordering is deterministic: cases sort by `case_id`, then phases, operation order, system, and resource. `steps_json` is compact JSON with exactly the seven required fields per step.

Progress is printed at case 1, every 50 cases, and the final case. The generator writes a temporary file in the repository root, validates it, and atomically replaces `output.csv` only after validation succeeds.

## Limits and assumptions

This is a deterministic rules-based investigator, not an external-model agent. It does not infer a clean state from missing evidence. PDF and screenshot evidence could not be OCR-extracted in the final environment, so cases depending only on those files need manual review or the optional extractors. Natural-language authorization is pattern-based and supports common English and selected multilingual deletion terms, but it is not a full language model. Sample results and remaining limitations are recorded in `evaluation/`.
