"""Strict output contract validation, also used before atomic publication."""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"dataset"
STATUSES={"COMPLETE","INCOMPLETE","NOT_APPLICABLE"}
FIELDS={"step_no","phase","system_id","resource_id","operation","state","evidence_id"}
PHASE_ORDER={"FINDING":0,"REMEDIATION":1,"VERIFICATION":2}
OP_ORDER={
    "REPORT_REMAINING_RECORD":0,"REPORT_EXPOSED_PII":1,"REPORT_ACTIVE_DATA_FLOW":2,"REPORT_RESTORE_RISK":3,
    "DISABLE_DATA_FLOW":0,"BLOCK_RESTORE":1,"DELETE_RECORD":2,"REDACT_RECORD":3,"ANONYMIZE_RECORD":4,
    "VERIFY_RECORD_ABSENT":0,"VERIFY_RECORD_PRESENT":1,"VERIFY_RECORD_REDACTED":2,"VERIFY_RECORD_ANONYMIZED":3,"VERIFY_DATA_FLOW_DISABLED":4,"VERIFY_RESTORE_BLOCKED":5,
}
STATES={
    "REPORT_REMAINING_RECORD":"PRESENT","REPORT_EXPOSED_PII":"PRESENT","REPORT_ACTIVE_DATA_FLOW":"ACTIVE","REPORT_RESTORE_RISK":"ACTIVE",
    "DISABLE_DATA_FLOW":"DISABLED","BLOCK_RESTORE":"BLOCKED","DELETE_RECORD":"ABSENT","REDACT_RECORD":"REDACTED","ANONYMIZE_RECORD":"ANONYMIZED",
    "VERIFY_RECORD_ABSENT":"ABSENT","VERIFY_RECORD_PRESENT":"PRESENT","VERIFY_RECORD_REDACTED":"REDACTED","VERIFY_RECORD_ANONYMIZED":"ANONYMIZED","VERIFY_DATA_FLOW_DISABLED":"DISABLED","VERIFY_RESTORE_BLOCKED":"BLOCKED",
}

def read(path:Path)->list[dict[str,str]]:
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def validate_file(path:Path, requests:list[dict[str,str]]|None=None, manifest:list[dict[str,str]]|None=None)->dict[str,int]:
    requests=requests if requests is not None else read(DATA/"deletion_requests.csv")
    manifest=manifest if manifest is not None else read(DATA/"evidence_files.csv")
    expected={r["case_id"] for r in requests}
    req_by_id={r["case_id"]:r for r in requests}
    manifest_by_id={r["file_id"]:r for r in manifest}
    valid_refs={**{k:dt_value(v.get("captured_at")) for k,v in manifest_by_id.items()}}
    for r in read(DATA/"system_activity.csv"):valid_refs[r["activity_id"]]=dt_value(r["event_time"])
    for r in read(DATA/"user_audit_log.csv"):valid_refs[r["audit_id"]]=dt_value(r["event_time"])
    with path.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        assert reader.fieldnames==["case_id","deletion_status","steps_json"],f"bad header: {reader.fieldnames}"
        rows=list(reader)
    expected_count=len(requests)
    assert len(rows)==expected_count,f"expected {expected_count} rows, got {len(rows)}"
    ids=[r["case_id"] for r in rows]
    assert len(set(ids))==expected_count,"duplicate case IDs"
    assert set(ids)==expected,"missing or unexpected case IDs"
    assert ids==sorted(ids),"case IDs not sorted"
    for row in rows:
        cid=row["case_id"];status=row["deletion_status"]
        assert status in STATUSES,(cid,status)
        steps=json.loads(row["steps_json"])
        assert isinstance(steps,list),f"{cid}: steps_json must be an array"
        if status=="NOT_APPLICABLE":assert steps==[],f"{cid}: NOT_APPLICABLE must have []"
        phases=[];sort_keys=[]
        for n,s in enumerate(steps,1):
            assert set(s)==FIELDS,(cid,n,"step keys")
            assert s["step_no"]==n,(cid,n,"step numbering")
            phase=s["phase"];op=s["operation"]
            assert phase in PHASE_ORDER,(cid,n,phase)
            assert op in OP_ORDER and s["state"]==STATES[op],(cid,n,op,s["state"])
            expected_phase=0 if op.startswith("REPORT_") else 1 if op in {"DISABLE_DATA_FLOW","BLOCK_RESTORE","DELETE_RECORD","REDACT_RECORD","ANONYMIZE_RECORD"} else 2
            assert PHASE_ORDER[phase]==expected_phase,(cid,n,phase,op)
            phases.append(PHASE_ORDER[phase]);sort_keys.append((PHASE_ORDER[phase],OP_ORDER[op],s["system_id"],s["resource_id"]))
            eid=s["evidence_id"]
            if status=="COMPLETE":
                assert phase=="VERIFICATION" and eid,(cid,n,"complete must cite verification evidence")
            if phase=="FINDING":assert eid,(cid,n,"finding must cite evidence")
            if phase!="FINDING" and status=="INCOMPLETE":assert eid=="",(cid,n,"proposed step must not cite evidence")
            if eid:
                assert eid in valid_refs,(cid,n,"unknown evidence reference",eid)
                ref_time=valid_refs[eid];audit_time=dt_value(req_by_id[cid]["audit_at"])
                assert ref_time is not None and audit_time is not None and ref_time<=audit_time,(cid,n,"evidence is after audit_at or has no timestamp",eid)
        assert phases==sorted(phases),(cid,"phase order")
        assert sort_keys==sorted(sort_keys),(cid,"operation/system/resource ordering")
    return {"rows":len(rows),"evidence_references":sum(1 for r in rows for s in json.loads(r["steps_json"]) if s["evidence_id"])}

def dt_value(value:str|None):
    from datetime import datetime
    try:return datetime.fromisoformat(value.replace("Z","+00:00")) if value else None
    except (TypeError,ValueError):return None

if __name__=="__main__":
    result=validate_file(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"output.csv")
    print(f"VALID: {result['rows']} unique sorted cases; schema, JSON, ordering, and evidence admissibility passed")
