"""Generate public-sample predictions with the full pipeline, then compare them."""
from __future__ import annotations

import collections
import json
import subprocess
import sys
from pathlib import Path

CODE=Path(__file__).resolve().parents[1]
ROOT=CODE.parent
sys.path.insert(0,str(CODE))
import main
from validate_output import validate_file


def signature(step: dict) -> tuple:
    return tuple(step.get(k) for k in ("phase","system_id","resource_id","operation","state"))


def compare() -> dict:
    sample_requests=main.read_csv(main.DATA/"sample_deletion_requests.csv")
    gold_rows=main.read_csv(main.DATA/"sample_output.csv")
    gold={row["case_id"]:row for row in gold_rows}
    if set(gold)!= {row["case_id"] for row in sample_requests} or len(gold)!=len(gold_rows):
        raise ValueError("Public sample inputs and answer file do not have the same unique case IDs")

    prediction_path=CODE/"evaluation"/"sample_prediction.csv"
    subprocess.run([sys.executable,str(CODE/"main.py"),"--sample"],check=True,cwd=ROOT)
    predicted_rows=main.read_csv(prediction_path)
    predicted={row["case_id"]:row for row in predicted_rows}
    if set(predicted)!=set(gold) or len(predicted)!=len(predicted_rows):
        raise ValueError("Generated sample output does not contain each public sample case exactly once")
    output_validation=validate_file(prediction_path,sample_requests,main.load_manifest())

    confusion=collections.Counter()
    exact_status=0
    exact_steps=0
    gold_step_total=pred_step_total=0
    aligned_positions=exact_step_matches=field_cells=exact_field_matches=0
    count_error_cases=operation_errors=evidence_errors=order_errors=0
    case_lines=[]
    class_errors=[]
    for case in sample_requests:
        cid=case["case_id"]
        expected_status=gold[cid]["deletion_status"]
        actual_status=predicted[cid]["deletion_status"]
        expected=json.loads(gold[cid]["steps_json"])
        actual=json.loads(predicted[cid]["steps_json"])
        confusion[(expected_status,actual_status)]+=1
        exact_status += expected_status==actual_status
        gold_step_total+=len(expected);pred_step_total+=len(actual)
        if expected==actual:exact_steps+=1
        if len(expected)!=len(actual):count_error_cases+=1

        this_op_errors=[]
        for i in range(max(len(expected),len(actual))):
            left=expected[i] if i<len(expected) else None
            right=actual[i] if i<len(actual) else None
            aligned_positions+=1
            exact_step_matches+=left is not None and left==right
            for field in main.FIELDS:
                field_cells+=1
                exact_field_matches+=left is not None and right is not None and left.get(field)==right.get(field)
            if left is None or right is None or left.get("operation")!=right.get("operation"):
                operation_errors+=1
                this_op_errors.append(f"step {i+1}: {left.get('operation') if left else '<missing>'} -> {right.get('operation') if right else '<missing>'}")
            if left is not None and right is not None and left.get("evidence_id")!=right.get("evidence_id"):
                evidence_errors+=1

        expected_signatures=[signature(step) for step in expected]
        actual_signatures=[signature(step) for step in actual]
        if expected_signatures!=actual_signatures and collections.Counter(expected_signatures)==collections.Counter(actual_signatures):
            order_errors+=1

        if expected_status!=actual_status:
            if expected_status=="COMPLETE" and actual_status=="INCOMPLETE":
                kind="false INCOMPLETE (expected COMPLETE)"
            elif expected_status=="INCOMPLETE" and actual_status=="COMPLETE":
                kind="false COMPLETE (expected INCOMPLETE)"
            else:
                kind=f"status error ({expected_status} -> {actual_status})"
            class_errors.append(f"{cid}: {kind}")
        if expected_status!=actual_status or expected!=actual:
            details=[f"{cid}: status {expected_status} -> {actual_status}; steps {len(expected)} -> {len(actual)}"]
            if this_op_errors:details.append("operations: "+", ".join(this_op_errors[:5]))
            exp_eids=[step.get("evidence_id","") for step in expected]
            act_eids=[step.get("evidence_id","") for step in actual]
            if exp_eids!=act_eids:details.append(f"evidence refs: {exp_eids} -> {act_eids}")
            if expected_signatures!=actual_signatures and collections.Counter(expected_signatures)==collections.Counter(actual_signatures):
                details.append("same steps in a different order")
            case_lines.append("; ".join(details))

    confusion_items=sorted(confusion.items())
    status_summary=f"Status accuracy: {exact_status}/{len(sample_requests)} ({exact_status/len(sample_requests):.2%})"
    complete_false_negatives=confusion[("COMPLETE","INCOMPLETE")]
    complete_false_positives=confusion[("INCOMPLETE","COMPLETE")]
    summary=[
        status_summary,
        f"Expected COMPLETE predicted INCOMPLETE: {complete_false_negatives}; expected INCOMPLETE predicted COMPLETE: {complete_false_positives}",
        f"Step counts: expected {gold_step_total}, predicted {pred_step_total}; cases with count mismatch: {count_error_cases}/{len(sample_requests)}",
        f"Aligned step accuracy: {exact_step_matches}/{aligned_positions} ({exact_step_matches/aligned_positions:.2%}) exact step objects; field accuracy: {exact_field_matches}/{field_cells} ({exact_field_matches/field_cells:.2%})",
        f"Positional operation mismatches (including missing/extra positions): {operation_errors}",
        f"Evidence-reference validity: {output_validation['evidence_references']}/{output_validation['evidence_references']} predicted non-empty references valid and admissible; positional reference mismatches vs. public answers: {evidence_errors}",
        f"Cases with correct step multiset but incorrect order: {order_errors}",
        f"Exact status-and-step results: {exact_steps}/{len(sample_requests)} ({exact_steps/len(sample_requests):.2%})",
        "Confusion: "+json.dumps({f"{a}->{b}":n for (a,b),n in confusion_items},sort_keys=True),
    ]
    report=("# Public sample comparison\n\n"
            +"- Prediction source: `python code/main.py --sample` (same parser and audit algorithm as full evaluation).\n"
            +"- Generated predictions: `sample_prediction.csv`, compared by `case_id`.\n"
            +"\n".join(f"- {line}" for line in summary)
            +"\n\n## Classification errors\n\n"
            +("\n".join(f"- {line}" for line in class_errors) or "None.")
            +"\n\n## Case-level step mismatches\n\n"
            +("\n".join(f"- {line}" for line in case_lines) or "None.")
            +"\n")
    report_path=CODE/"evaluation"/"sample_comparison.md"
    report_path.write_text(report,encoding="utf-8")
    for line in summary:print(line)
    print(f"Classification errors: {len(class_errors)}; case-level step mismatches: {len(case_lines)}")
    print(f"Wrote {prediction_path} and {report_path}")
    return {"summary":summary,"classification_errors":class_errors,"case_mismatches":case_lines}


if __name__=="__main__":
    compare()
