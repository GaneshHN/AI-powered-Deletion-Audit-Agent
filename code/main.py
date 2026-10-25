"""Deterministic, evidence-first deletion audit for Ghost Data Still Exists.

Only participant-facing data under dataset/ is read. Structured evidence is
parsed into resource observations; workflow activity is never treated as state
proof. The implementation deliberately errs toward INCOMPLETE when it finds a
policy violation and does not invent a clean bill of health from missing data.
"""
from __future__ import annotations

import csv
import argparse
import json
import re
import sqlite3
import sys
import os
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dataset"
OUT = ROOT / "output.csv"
FIELDS = ("step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def normalize(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().casefold())


def load_manifest() -> list[dict[str, str]]:
    manifest = read_csv(DATA / "evidence_files.csv")
    for item in manifest:
        p = (DATA / item["file_path"]).resolve()
        if DATA.resolve() not in p.parents:
            raise ValueError(f"Evidence path escapes dataset: {item['file_id']}")
        item["_path"] = str(p)
    return manifest


def sql_records(path: Path) -> list[tuple[str, dict[str, Any]]]:
    """Execute SQLite-compatible snapshots in memory and return table rows."""
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(path.read_text(encoding="utf-8", errors="replace"))
        records = []
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for (table,) in tables:
            if table == "snapshot_scope":
                continue
            cur = con.execute(f'SELECT * FROM "{table}"')
            names = [x[0] for x in cur.description or []]
            for row in cur.fetchall():
                obj = dict(zip(names, row))
                if obj.get("resource_id"):
                    records.append((table, obj))
        return records
    finally:
        con.close()


def flatten_json(obj: Any, service: str = "") -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    if isinstance(obj, dict):
        if obj.get("resource_id"):
            out.append((service, obj))
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                out.extend(flatten_json(value, key if key.endswith(("_service", "_platform")) else service))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(flatten_json(item, service))
    return out


TABLE_SYSTEM = {
    "customer_profiles": "account_service", "customer_profiles_failover_replica": "account_service",
    "customer_profiles_primary": "account_service", "customer_search_documents": "search_service",
    "search_documents_primary": "search_service", "customer_analytics_profiles": "analytics_platform",
    "support_records": "support_platform", "customer_exports": "export_service",
    "connector_subscriptions": "integration_service", "backup_restore_entries": "backup_service",
    "security_audit_records": "security_service",
}


def infer_system(context: str, obj: dict[str, Any]) -> str:
    c = normalize(context)
    if c in {"account_service", "analytics_platform", "backup_service", "export_service", "identity_service", "integration_service", "search_service", "security_service", "support_platform", "marketing_platform"}:
        return c
    keys = " ".join(map(str, obj.keys())).casefold()
    rid = str(obj.get("resource_id", ""))
    prefix = rid.split("_", 1)[0]
    by_prefix = {"account":"account_service", "search":"search_service", "analytics":"analytics_platform", "support":"support_platform", "export":"export_service", "data":"integration_service", "backup":"backup_service", "audit":"security_service", "marketing":"marketing_platform", "tombstone":"identity_service"}
    if prefix in by_prefix:
        return by_prefix[prefix]
    for needle, system in (("connector", "integration_service"), ("restore", "backup_service"), ("archive", "backup_service"), ("audit", "security_service"), ("support", "support_platform"), ("email", "email_service")):
        if needle in keys:
            return system
    return "unknown"


RESOURCE_PATTERN=re.compile(r"\b(?:account|search|analytics|support|export|backup|audit(?:_record)?|data_flow|marketing|tombstone)_\d+\b",re.I)


def text_observations(content: str, manifest_row: dict[str,str], context: str) -> list[dict[str,Any]]:
    """Turn extracted prose or log lines into searchable resource observations."""
    parsed=[]
    for line in content.splitlines() or [content]:
        structured_line=line.strip().lstrip("-* ")
        columns=[part.strip() for part in structured_line.split("|")]
        if len(columns)==6 and dt(columns[0]) and columns[1] in {
            "account_service","analytics_platform","backup_service","export_service",
            "integration_service","search_service","security_service","support_platform",
        } and RESOURCE_PATTERN.fullmatch(columns[2]):
            event_time,service,rid,category,state,subject=columns
            obj={"resource_id":rid,"record_type":category,"state":state,"_event_time":event_time}
            state_key=normalize(state)
            subject_norm=normalize(subject)
            if subject_norm.startswith("user_"):
                obj["subject_reference" if service=="security_service" else "customer_reference"]=subject
            elif "@" in subject:
                subject_key={
                    "account_service":"email","analytics_platform":"email","backup_service":"customer_email",
                    "export_service":"owner_email","integration_service":"customer_email","search_service":"email",
                    "support_platform":"requester_email",
                }.get(service)
                if subject_key:obj[subject_key]=subject
            if service=="account_service":
                obj["status"]="not_found" if state_key in {"not_found","absent","404"} else state_key
                if state_key in {"not_found","absent","404"}:obj["rows"]=0
                if state_key=="found":obj["rows"]=1
            elif service=="analytics_platform":
                if state_key=="identifiable" and "@" in subject:obj["email"]=subject
            elif service=="backup_service":
                obj["restore_allowed"]=state_key in {"active","allowed","eligible"}
            elif service=="export_service":
                obj["available"]=state_key in {"found","active","available"}
            elif service=="integration_service":
                obj["enabled"]=state_key in {"active","enabled"}
            elif service=="search_service":
                obj["result"]="hit" if state_key in {"found","present","hit"} else "miss"
            elif service=="support_platform" and category=="SUPPORT_ATTACHMENT":
                obj["record_type"]="attachment"
            parsed.append({"evidence_id":manifest_row["file_id"],"captured_at":manifest_row["captured_at"],"context":service,"system":service,"obj":obj,"text":line})
            continue
        pairs=dict(re.findall(r"([\w.-]+)=([^\s,;]+)",line))
        rid=pairs.get("resource_id") or pairs.get("resource") or pairs.get("record_id") or pairs.get("object_id")
        if not rid:
            match=RESOURCE_PATTERN.search(line)
            rid=match.group(0) if match else ""
        if rid:pairs["resource_id"]=rid
        stamp=re.match(r"(\d{4}-\d\d-\d\dT\S+)",line)
        if stamp:pairs["_event_time"]=stamp.group(1)
        if not pairs and not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",line):continue
        svc=pairs.get("service",pairs.get("source",context))
        parsed.append({"evidence_id":manifest_row["file_id"],"captured_at":manifest_row["captured_at"],"context":svc,"system":infer_system(svc,pairs),"obj":pairs,"text":line})

    # Service logs commonly put the subject key on the request-start row and
    # the resource/state on a later row. Propagate identity only within the
    # same trace_id in this one artifact; never across traces or files.
    trace_identifiers:dict[str,dict[str,str]]=defaultdict(dict)
    identity_fields=("lookup_key","subject_key","match_key","correlation_key","customer_reference","subject_reference","subject_ref","customer_email","email","owner_email","requester_email","email_hash","phone","user_id")
    for row in parsed:
        trace=row["obj"].get("trace_id")
        if not trace:continue
        for key in identity_fields:
            value=row["obj"].get(key)
            if value not in (None,"","null"):
                trace_identifiers[trace].setdefault(key,value)
    for row in parsed:
        trace=row["obj"].get("trace_id")
        if trace:
            for key,value in trace_identifiers.get(trace,{}).items():
                row["obj"].setdefault(key,value)
    return parsed


def _warn_evidence(m:dict[str,str],exc:BaseException,action:str)->None:
    print(f"WARN: evidence {m['file_id']} ({m['file_path']}): {action}; {type(exc).__name__}: {exc!r}",file=sys.stderr)


def extract_pdf(m:dict[str,str])->list[dict[str,Any]]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ModuleNotFoundError as exc:
        if exc.name!="pypdf":raise
        _warn_evidence(m,exc,"PDF text extraction unavailable because module 'pypdf' is missing; artifact is not considered clean")
        return []
    try:
        reader=PdfReader(m["_path"])
        content="\n".join(page.extract_text() or "" for page in reader.pages)
    except (OSError,ValueError,PdfReadError) as exc:
        _warn_evidence(m,exc,"PDF could not be read; artifact is not considered clean")
        return []
    if not content.strip():
        print(f"WARN: evidence {m['file_id']} ({m['file_path']}): pypdf read the PDF but extracted no text; artifact is not considered clean",file=sys.stderr)
        return []
    observations=text_observations(content,m,m.get("origin",""))
    resource_ids=set(RESOURCE_PATTERN.findall(content))
    if len(resource_ids)==1:
        # Business PDFs often put the ticket/resource reference in a heading
        # and the customer's identifier on a separate line or page. Link those
        # fields only when the document contains exactly one resource ID.
        rid=next(iter(resource_ids))
        obj={"resource_id":rid}
        service=infer_system(m.get("origin",""),obj)
        emails=sorted({value for value in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",content)})
        if len(emails)==1:
            email_field={"support_platform":"requester_email","account_service":"email","analytics_platform":"email","export_service":"owner_email"}.get(service)
            if email_field:obj[email_field]=emails[0]
        stem=Path(m["file_path"]).stem.casefold()
        if service=="support_platform" and "attachment" in stem:obj["record_type"]="attachment"
        return [{"evidence_id":m["file_id"],"captured_at":m["captured_at"],"context":service,"system":service,"obj":obj,"text":content}]
    return observations


def extract_png(m:dict[str,str])->list[dict[str,Any]]:
    try:
        from PIL import Image,UnidentifiedImageError
    except ModuleNotFoundError as exc:
        if exc.name not in {"PIL","PIL.Image"}:raise
        _warn_evidence(m,exc,"image decoding unavailable because the Pillow module is missing; artifact is not considered clean")
        return []
    try:
        with Image.open(m["_path"]) as image:
            image.verify()
            width,height=image.size
    except (UnidentifiedImageError,OSError) as exc:
        _warn_evidence(m,exc,"Pillow could not decode the image; artifact is not considered clean")
        return []
    try:
        import pytesseract
    except ModuleNotFoundError as exc:
        if exc.name!="pytesseract":raise
        _warn_evidence(m,exc,f"Pillow decoded the {width}x{height} PNG, but OCR was not run because Python module 'pytesseract' is missing; no image text was inferred and the artifact is not considered clean")
        return []
    try:
        with Image.open(m["_path"]) as image:
            content=pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError as exc:
        _warn_evidence(m,exc,"Python module 'pytesseract' is installed but its Tesseract executable is missing; artifact is not considered clean")
        return []
    except pytesseract.TesseractError as exc:
        _warn_evidence(m,exc,"Tesseract OCR failed; artifact is not considered clean")
        return []
    return text_observations(content,m,m.get("origin",""))


def load_evidence(manifest: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Parse each participant artifact once; only expected file errors are caught."""
    all_rows: list[dict[str, Any]] = []
    manifest_capture={m["file_id"]:dt(m.get("captured_at")) for m in manifest}
    for m in manifest:
        path=Path(m["_path"]);ext=path.suffix.lower()
        if ext==".json":
            try:payload=json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError,UnicodeError,json.JSONDecodeError) as exc:
                _warn_evidence(m,exc,"JSON evidence could not be read or decoded; artifact is not considered clean");continue
            for context,obj in flatten_json(payload):
                all_rows.append({"evidence_id":m["file_id"],"captured_at":m["captured_at"],"context":context,"system":infer_system(context,obj),"obj":obj,"text":""})
        elif ext==".sql":
            try:rows=sql_records(path)
            except (OSError,UnicodeError,sqlite3.Error) as exc:
                _warn_evidence(m,exc,"SQL evidence could not be read or executed; artifact is not considered clean");continue
            for table,obj in rows:
                all_rows.append({"evidence_id":m["file_id"],"captured_at":m["captured_at"],"context":table,"system":TABLE_SYSTEM.get(table,infer_system(table,obj)),"obj":obj,"text":""})
        elif ext in (".log",".txt"):
            try:content=path.read_text(encoding="utf-8-sig",errors="strict")
            except (OSError,UnicodeError) as exc:
                _warn_evidence(m,exc,"text evidence could not be read; artifact is not considered clean");continue
            all_rows.extend(text_observations(content,m,m.get("origin","")))
        elif ext==".pdf":
            all_rows.extend(extract_pdf(m))
        elif ext==".png":
            all_rows.extend(extract_png(m))
        else:
            print(f"WARN: evidence {m['file_id']} ({m['file_path']}): unsupported evidence extension {ext!r}; artifact is not considered clean",file=sys.stderr)
    # Normalize once: the old implementation reparsed both timestamps and
    # rebuilt the searchable text for every case/evidence pair.
    for row in all_rows:
        # A line/event timestamp inside a file cannot make the file itself
        # admissible before its manifest capture time.
        row["_captured_dt"] = manifest_capture.get(row["evidence_id"])
        observed = next((str(row["obj"].get(k)) for k in ("observed_at", "event_time", "_event_time", "captured_at", "exported_at") if row["obj"].get(k)), None)
        row["_observed_dt"] = dt(observed)
        row["_state_dt"] = row["_observed_dt"] or row["_captured_dt"]
        row["_match_text"] = build_match_text(row)
    return all_rows


def identifiers_for(email: str, identities: list[dict[str, str]], audits: list[dict[str, str]]) -> tuple[set[str], set[str]]:
    users = {r["user_id"] for r in identities if normalize(r["email"]) == normalize(email)}
    for a in audits:
        if normalize(a["field_name"]) == "email" and normalize(a["old_value"]) == normalize(email):
            users.add(a["user_id"])
    ids: set[str] = {normalize(email)}
    for r in identities:
        if r["user_id"] in users:
            ids.update(normalize(r[k]) for k in ("email", "phone", "name", "email_hash") if r.get(k))
    for a in audits:
        if a["user_id"] in users and a["old_value"]:
            ids.add(normalize(a["old_value"]))
    return users, {x for x in ids if x}


class IdentityIndex:
    """Resolve request emails once through current and historical identity rows."""
    def __init__(self, identities: list[dict[str, str]], audits: list[dict[str, str]]):
        self.current_email_users: dict[str, set[str]] = defaultdict(set)
        self.old_email_users: dict[str, set[str]] = defaultdict(set)
        self.identifiers_by_user: dict[str, set[str]] = defaultdict(set)
        for r in identities:
            uid = r["user_id"]
            if r.get("email"): self.current_email_users[normalize(r["email"])].add(uid)
            for k in ("email", "phone", "name", "email_hash"):
                if r.get(k): self.identifiers_by_user[uid].add(normalize(r[k]))
        for a in audits:
            uid=a["user_id"]
            if normalize(a.get("field_name")) == "email":
                for key in ("old_value","new_value"):
                    if a.get(key):self.old_email_users[normalize(a[key])].add(uid)
            for key in ("old_value","new_value"):
                if a.get(key):self.identifiers_by_user[uid].add(normalize(a[key]))

    def resolve(self, email: str) -> tuple[set[str], set[str]]:
        key=normalize(email)
        users=set(self.current_email_users.get(key, ())) | set(self.old_email_users.get(key, ()))
        identifiers={key}
        for uid in users: identifiers.update(self.identifiers_by_user.get(uid, ()))
        return users, {x for x in identifiers if x}


def build_match_text(row: dict[str, Any]) -> str:
    obj=row["obj"]
    fields=" ".join(normalize(obj.get(k)) for k in ("email","owner_email","customer_email","requester_email","phone","owner_phone","requester_phone","email_hash","full_name","display_name","requester_name","name","customer_reference","user_id","subject_reference","subject_ref","lookup_key","subject_key","match_key","correlation_key"))
    return fields + " " + normalize(row.get("text", ""))


class EvidenceIndex:
    """Inverted identifier/user/resource/system indexes over parsed artifacts."""
    def __init__(self, records: list[dict[str, Any]]):
        self.records=records
        self.by_value: dict[str,set[int]]=defaultdict(set)
        self.by_user: dict[str,set[int]]=defaultdict(set)
        self.by_resource: dict[str,set[int]]=defaultdict(set)
        self.by_system: dict[str,set[int]]=defaultdict(set)
        self.by_gram: dict[str,set[int]]=defaultdict(set)
        user_keys={"user_id","customer_reference","subject_reference","subject_ref","stable_user_id"}
        for i,row in enumerate(records):
            obj=row["obj"]
            sysid,rid=evidence_system_resource(row)
            self.by_system[sysid].add(i)
            if rid: self.by_resource[normalize(rid)].add(i)
            for key in user_keys:
                if obj.get(key): self.by_user[normalize(obj[key])].add(i)
            for value in obj.values():
                if isinstance(value,(str,int)) and value not in (None,""):
                    val=normalize(value)
                    if len(val)>=2: self.by_value[val].add(i)
            searchable=row.get("_match_text") or build_match_text(row)
            row["_match_text"]=searchable
            for gram in self._grams(searchable): self.by_gram[gram].add(i)

    @staticmethod
    def _grams(value: str) -> set[str]:
        return {value[i:i+3] for i in range(max(0,len(value)-2))}

    def candidates(self, users: set[str], identifiers: set[str]) -> list[tuple[dict[str, Any],bool]]:
        indexes:set[int]=set()
        for user in users: indexes.update(self.by_user.get(normalize(user), ()))
        for ident in identifiers:
            query=normalize(ident)
            exact=self.by_value.get(query)
            if exact: indexes.update(exact)
            if len(query)>=3:
                grams=self._grams(query)
                rarest=min(grams,key=lambda g:len(self.by_gram.get(g, ())),default=None)
                if rarest: indexes.update(self.by_gram.get(rarest, ()))
        # The candidate index only narrows; the original predicate remains the
        # authority, so common grams and decoys cannot become matches. Once a
        # resource is tied to the subject by direct identifiers, pull its other
        # readbacks too (for example, a later 404 or redacted tombstone no longer
        # containing an email).
        direct={i for i in indexes if match_record(self.records[i],users,identifiers)}
        linked_resources={normalize(self.records[i]["obj"].get("resource_id")) for i in direct if self.records[i]["obj"].get("resource_id")}
        expanded=set(direct)
        for rid in linked_resources: expanded.update(self.by_resource.get(rid,()))
        return [(self.records[i],i in direct) for i in expanded]


def is_authorized(text: str) -> bool:
    s = normalize(text)
    # An explicit deletion request remains authorized when it also mentions
    # access, correction, downloads, or confirmation. Audit-only questions such
    # as "verify the account was deleted" are deletion audits too.
    deletion = (r"\b(delet(?:e|ed|ing|ion)|eras(?:e|ed|ing|ure)|remove|removal|close|closed|closure|cancel(?:l)?(?:ed|ing)?|suppression|elimin(?:ar|aci[oó]n)|borrar|supprimer|effacer|cancellare|apagar|excluir|exclus[aã]o|usuń|usunię|verwijder|löschen|loeschen|entfernen|удал\w*|silin\w*|hesabımı kapat|حذف)\b|削除|删除|삭제|已删除")
    if re.search(deletion, s):
        return True
    audit_of_deletion = r"\b(verify|check|confirm|audit|inspect)\b.{0,90}\b(account|profile|personal data)\b.{0,80}\b(gone|removed|deleted|erased|absent)\b|\b(whether|if)\b.{0,80}\b(account|profile|data)\b.{0,80}\b(removed|deleted|erased|gone)\b"
    if re.search(audit_of_deletion, s):
        return True
    # Non-deletion requests such as access, correction, marketing opt-out or
    # portability do not authorize deleting the account by themselves.
    return False


STRONG_ID_FIELDS={
    "email","owner_email","customer_email","requester_email","phone","owner_phone","requester_phone",
    "email_hash","user_id","customer_reference","subject_reference","subject_ref","stable_user_id",
    "lookup_key","subject_key","match_key","correlation_key",
}
NAME_ID_FIELDS={"full_name","display_name","requester_name","name"}


def canonical_identifier(value: Any) -> str:
    """Normalize a structured identifier, including quotes around log values."""
    return normalize(value).strip(" \t\r\n\"'`")


def object_fields(obj: Any):
    """Yield nested mapping fields so JSON profile objects remain searchable."""
    if isinstance(obj, dict):
        for key,value in obj.items():
            yield str(key),value
            yield from object_fields(value)
    elif isinstance(obj, list):
        for value in obj:yield from object_fields(value)


def match_record(row: dict[str, Any], users: set[str], ids: set[str]) -> bool:
    obj=row["obj"]
    id_set={canonical_identifier(value) for value in ids if canonical_identifier(value)}
    fields=list(object_fields(obj))
    # Stable subject references are the strongest available correlation.
    for key,value in fields:
        if key in {"user_id","customer_reference","subject_reference","subject_ref","stable_user_id"}:
            if canonical_identifier(value) in users:return True

    strong_values={canonical_identifier(value) for key,value in fields if key in STRONG_ID_FIELDS and value not in (None,"","null")}
    if strong_values & id_set:return True
    # A conflicting email/phone/hash/user key prevents a shared name from
    # linking an unrelated person's record to this request.
    if strong_values:return False

    for key,value in fields:
        if key in NAME_ID_FIELDS and canonical_identifier(value) in id_set:return True

    # Unstructured prose is matched on whole identifier boundaries, never by
    # substring (e.g. a short/shared name inside a different person's name).
    searchable=normalize(row.get("text", ""))
    for identifier in id_set:
        if len(identifier)>=5 and re.search(rf"(?<![\w]){re.escape(identifier)}(?![\w])",searchable):return True
    return False


def evidence_system_resource(item: dict[str, Any]) -> tuple[str, str]:
    obj = item["obj"]
    return item["system"], str(obj.get("resource_id", ""))


def expected_action(item: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return finding operation/state and intended remediation/verification."""
    o, sysid = item["obj"], item["system"]
    event = normalize(o.get("event", o.get("event_name", "")))
    # A trace's start, connection, cache, or export-control event only shows
    # that instrumentation ran. It does not establish the resource's state.
    if event.endswith("_started") or event in {"connection_acquired", "cache_lookup", "export_started", "export_completed"}:
        return None, None, None
    status = normalize(o.get("account_status", o.get("status", "")))
    if sysid == "account_service":
        not_found = (str(o.get("status_code", o.get("http_status", ""))) == "404" or str(o.get("rows", "")) == "0")
        if status in ("deleted", "absent", "404", "not_found") or o.get("profile") is None and not_found:
            return None, None, "VERIFY_RECORD_ABSENT"
        if event and "lookup_completed" in event and not_found:
            return None, None, "VERIFY_RECORD_ABSENT"
        if event and "lookup_completed" in event and not any(k in o for k in ("account_status", "status", "profile")):
            return None, None, None
        direct = any(o.get(k) not in (None, "", "null") for k in ("email", "phone", "email_hash", "full_name", "name"))
        if status in ("tombstone", "deleted_tombstone"):
            return ("REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED") if direct else (None,None,"VERIFY_RECORD_REDACTED")
        return ("REPORT_REMAINING_RECORD","DELETE_RECORD","VERIFY_RECORD_ABSENT")
    if sysid == "search_service":
        if normalize(o.get("result")) in ("miss", "no_hit") or str(o.get("total_hits", "")) == "0": return None,None,"VERIFY_RECORD_ABSENT"
        return "REPORT_REMAINING_RECORD","DELETE_RECORD","VERIFY_RECORD_ABSENT"
    if sysid == "analytics_platform":
        direct = any(o.get(k) not in (None, "", "null") for k in ("email","phone","email_hash","full_name","name","customer_reference","user_id","correlation_key"))
        return ("REPORT_EXPOSED_PII","ANONYMIZE_RECORD","VERIFY_RECORD_ANONYMIZED") if direct else (None,None,"VERIFY_RECORD_ANONYMIZED")
    if sysid == "support_platform":
        pii_scan=event=="message_pii_scan" and normalize(o.get("detector"))=="direct_identifier" and o.get("matched_value") not in (None,"","null")
        direct = pii_scan or any(o.get(k) not in (None, "", "null") for k in ("requester_email","requester_phone","requester_name","email","phone"))
        if normalize(o.get("record_type")) in ("attachment", "identity_document"):
            return "REPORT_REMAINING_RECORD","DELETE_RECORD","VERIFY_RECORD_ABSENT"
        return ("REPORT_EXPOSED_PII","REDACT_RECORD","VERIFY_RECORD_REDACTED") if direct else (None,None,"VERIFY_RECORD_REDACTED")
    if sysid == "backup_service":
        allowed = str(o.get("restore_allowed", "")).casefold() in ("1","true","yes")
        eligible = str(o.get("eligible", "")).casefold() in ("1","true","yes")
        blocked = str(o.get("deletion_block", "")).casefold() in ("1","true","yes")
        allowed = allowed or (eligible and not blocked)
        return ("REPORT_RESTORE_RISK","BLOCK_RESTORE","VERIFY_RESTORE_BLOCKED") if allowed else (None,None,"VERIFY_RESTORE_BLOCKED")
    if sysid == "integration_service":
        enabled = str(o.get("enabled", "")).casefold() in ("1","true","yes")
        return ("REPORT_ACTIVE_DATA_FLOW","DISABLE_DATA_FLOW","VERIFY_DATA_FLOW_DISABLED") if enabled else (None,None,"VERIFY_DATA_FLOW_DISABLED")
    if sysid == "security_service":
        return None,None,"VERIFY_RECORD_PRESENT"
    if sysid in ("export_service", "marketing_platform"):
        available = o.get("download_available", o.get("available", True))
        if str(available).casefold() in ("0","false","no"): return None,None,"VERIFY_RECORD_ABSENT"
        return "REPORT_REMAINING_RECORD","DELETE_RECORD","VERIFY_RECORD_ABSENT"
    if sysid == "identity_service":
        direct=any(o.get(k) not in (None,"","null") for k in ("email","phone","email_hash","full_name","name"))
        return ("REPORT_EXPOSED_PII","REDACT_RECORD","VERIFY_RECORD_REDACTED") if direct else (None,None,"VERIFY_RECORD_REDACTED")
    if sysid == "email_service":
        return "REPORT_EXPOSED_PII","REDACT_RECORD","VERIFY_RECORD_REDACTED"
    return None,None,None


FIND_ORDER = {"REPORT_REMAINING_RECORD":1,"REPORT_EXPOSED_PII":2,"REPORT_ACTIVE_DATA_FLOW":3,"REPORT_RESTORE_RISK":4}
REMEDY_ORDER = {"DISABLE_DATA_FLOW":1,"BLOCK_RESTORE":2,"DELETE_RECORD":3,"REDACT_RECORD":4,"ANONYMIZE_RECORD":5}
VERIFY_ORDER = {"VERIFY_RECORD_ABSENT":1,"VERIFY_RECORD_PRESENT":2,"VERIFY_RECORD_REDACTED":3,"VERIFY_RECORD_ANONYMIZED":4,"VERIFY_DATA_FLOW_DISABLED":5,"VERIFY_RESTORE_BLOCKED":6}


def audit_case(case: dict[str,str], identities: list[dict[str,str]] | IdentityIndex, audits: list[dict[str,str]] | EvidenceIndex, records: list[dict[str,Any]] | None = None, manifest: list[dict[str,str]] | None = None) -> tuple[str,list[dict[str,Any]]]:
    if not is_authorized(case["request_text"]): return "NOT_APPLICABLE", []
    identity_index=identities if isinstance(identities,IdentityIndex) else IdentityIndex(identities,audits if isinstance(audits,list) else [])
    evidence_index=audits if isinstance(audits,EvidenceIndex) else EvidenceIndex(records or [])
    users, ids = identity_index.resolve(case["email"])
    cutoff = dt(case["audit_at"])
    admissible = []
    for r,_direct_match in evidence_index.candidates(users,ids):
        if "_captured_dt" in r:
            cap=r["_captured_dt"]
        else:
            cap=dt(r.get("captured_at"))
        if cutoff and cap and cap > cutoff: continue
        if "_observed_dt" in r:
            observed=r["_observed_dt"] or r.get("_captured_dt")
        else:
            observed=dt(next((str(r["obj"].get(k)) for k in ("observed_at", "event_time", "_event_time", "captured_at", "exported_at") if r["obj"].get(k)), None))
        if cutoff and observed and observed > cutoff: continue
        # EvidenceIndex returns direct identity matches plus readbacks for those
        # already-linked resources, so the resource link itself grounds the row.
        admissible.append(r)
    # Reconstruct the latest observation for each resource in each source/table.
    # Keep separate SQL tables (primary vs failover) so replica drift remains visible.
    unique: dict[tuple[str,str,str],dict[str,Any]] = {}
    for r in admissible:
        sysid, rid = evidence_system_resource(r)
        key=(sysid,rid,r.get("context", ""))
        previous=unique.get(key)
        current_time=r.get("_state_dt") or r.get("_captured_dt")
        previous_time=(previous.get("_state_dt") or previous.get("_captured_dt")) if previous else None
        # Several service readback traces emit *_started and *_completed rows
        # with the same second-resolution timestamp. Prefer completed state
        # observations deterministically when timestamps tie.
        def observation_rank(item: dict[str, Any]) -> tuple[int, int, str]:
            obj=item["obj"]
            event=normalize(obj.get("event", obj.get("event_name", "")))
            completed=int(event.endswith(("_completed", "_complete", "_read")) or any(k in obj for k in ("http_status", "account_status", "enabled", "restore_allowed", "total_hits", "result")))
            return (completed, len(obj), event)
        if previous is None or previous_time is None or (current_time is not None and current_time > previous_time) or (current_time == previous_time and observation_rank(r)>observation_rank(previous)):
            unique[key]=r
    findings=[]; repairs=[]; verifies=[]; found_keys=set()
    for r in unique.values():
        sysid,rid=evidence_system_resource(r)
        if not sysid or not rid: continue
        f,rem,v=expected_action(r)
        if v:
            verifies.append((sysid,rid,v,r["evidence_id"]))
        if f:
            finding_state = "ACTIVE" if f in ("REPORT_ACTIVE_DATA_FLOW","REPORT_RESTORE_RISK") else "PRESENT"
            findings.append((sysid,rid,f,finding_state,r["evidence_id"]))
            repairs.append((sysid,rid,rem,r["evidence_id"]))
            found_keys.add((sysid,rid))
    incomplete=bool(findings)
    steps=[]
    if incomplete:
        for a in sorted(findings,key=lambda x:(FIND_ORDER[x[2]],x[0],x[1])):
            steps.append(dict(phase="FINDING",system_id=a[0],resource_id=a[1],operation=a[2],state=a[3],evidence_id=a[4]))
        for a in sorted(set(repairs),key=lambda x:(REMEDY_ORDER[x[2]],x[0],x[1])):
            rem=a[2]; state={"DISABLE_DATA_FLOW":"DISABLED","BLOCK_RESTORE":"BLOCKED","DELETE_RECORD":"ABSENT","REDACT_RECORD":"REDACTED","ANONYMIZE_RECORD":"ANONYMIZED"}[rem]
            steps.append(dict(phase="REMEDIATION",system_id=a[0],resource_id=a[1],operation=rem,state=state,evidence_id=""))
        # Future verification covers every finding/remediation. Include linked known retained evidence too.
        seen=set()
        for a in verifies:
            if (a[0],a[1]) not in found_keys: continue
            seen.add((a[0],a[1]))
        for sysid,rid,rem,_ in repairs:
            v={"DELETE_RECORD":"VERIFY_RECORD_ABSENT","REDACT_RECORD":"VERIFY_RECORD_REDACTED","ANONYMIZE_RECORD":"VERIFY_RECORD_ANONYMIZED","DISABLE_DATA_FLOW":"VERIFY_DATA_FLOW_DISABLED","BLOCK_RESTORE":"VERIFY_RESTORE_BLOCKED"}[rem]
            verifies=[x for x in verifies if (x[0],x[1])!=(sysid,rid)]
            verifies.append((sysid,rid,v,""))
        # Include required account absence and retained security record checks when available.
        for sysid,rid,v,eid in sorted(set(verifies),key=lambda x:(VERIFY_ORDER[x[2]],x[0],x[1])):
            steps.append(dict(phase="VERIFICATION",system_id=sysid,resource_id=rid,operation=v,state={"VERIFY_RECORD_ABSENT":"ABSENT","VERIFY_RECORD_PRESENT":"PRESENT","VERIFY_RECORD_REDACTED":"REDACTED","VERIFY_RECORD_ANONYMIZED":"ANONYMIZED","VERIFY_DATA_FLOW_DISABLED":"DISABLED","VERIFY_RESTORE_BLOCKED":"BLOCKED"}[v],evidence_id=""))
        status="INCOMPLETE"
    else:
        # Only assert COMPLETE when there is direct, point-in-time evidence. Absence of
        # any matching artifact is not proof. Positive readbacks (404/clean tombstone,
        # redacted/anonymized/retained record, disabled flow, blocked restore) count.
        account_proof = any(
            (x[0] == "account_service" and x[2] in ("VERIFY_RECORD_ABSENT", "VERIFY_RECORD_REDACTED"))
            or (x[0] == "identity_service" and x[2] == "VERIFY_RECORD_REDACTED")
            for x in verifies
        )
        if not verifies or not account_proof:
            status="INCOMPLETE"
            # A clean secondary record alone cannot prove the account was deleted.
            return status, []
        status="COMPLETE"
        for sysid,rid,v,eid in sorted(set(verifies),key=lambda x:(VERIFY_ORDER[x[2]],x[0],x[1])):
            steps.append(dict(phase="VERIFICATION",system_id=sysid,resource_id=rid,operation=v,state={"VERIFY_RECORD_ABSENT":"ABSENT","VERIFY_RECORD_PRESENT":"PRESENT","VERIFY_RECORD_REDACTED":"REDACTED","VERIFY_RECORD_ANONYMIZED":"ANONYMIZED","VERIFY_DATA_FLOW_DISABLED":"DISABLED","VERIFY_RESTORE_BLOCKED":"BLOCKED"}[v],evidence_id=eid))
    for i,s in enumerate(steps,1): s["step_no"]=i
    return status,steps


def generate_output(requests_path: Path, output_path: Path, *, progress: bool = True) -> list[dict[str, str]]:
    """Run the shared audit pipeline for either full or public sample requests."""
    requests=read_csv(requests_path)
    if requests_path.name == "deletion_requests.csv" and len(requests) != 518:
        raise ValueError(f"Expected 518 full evaluation requests, got {len(requests)}")
    identities=read_csv(DATA/"user_identities.csv")
    audits=read_csv(DATA/"user_audit_log.csv")
    manifest=load_manifest()
    records=load_evidence(manifest)
    identity_index=IdentityIndex(identities,audits)
    evidence_index=EvidenceIndex(records)
    output=[]
    for n,case in enumerate(requests,1):
        if progress and (n==1 or n%50==0 or n==len(requests)): print(f"Processing case {n}/{len(requests)}",flush=True)
        status,steps=audit_case(case,identity_index,evidence_index)
        output.append({"case_id":case["case_id"],"deletion_status":status,"steps_json":json.dumps(steps,ensure_ascii=False,separators=(",",":"))})
    output.sort(key=lambda x:x["case_id"])
    from validate_output import validate_file
    output_path=output_path.resolve()
    output_path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp_name=tempfile.mkstemp(prefix=f".{output_path.stem}.",suffix=".tmp",dir=output_path.parent)
    os.close(fd)
    try:
        temp_path=Path(temp_name)
        with temp_path.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=("case_id","deletion_status","steps_json"),lineterminator="\n")
            w.writeheader();w.writerows(output)
        validate_file(temp_path,requests,manifest)
        os.replace(temp_path,output_path)
    except Exception:
        try: Path(temp_name).unlink(missing_ok=True)
        except OSError: pass
        raise
    print(f"Wrote {len(output)} cases to {output_path}")
    print("Status counts:",json.dumps({k:sum(x['deletion_status']==k for x in output) for k in ("COMPLETE","INCOMPLETE","NOT_APPLICABLE")}))
    print(f"Parsed structured evidence records: {len(records)} / manifest files: {len(manifest)}")
    return output


def main() -> None:
    parser=argparse.ArgumentParser(description="Audit deletion requests against supplied evidence")
    parser.add_argument("--sample",action="store_true",help="run the same pipeline on public sample requests")
    args=parser.parse_args()
    requests_path=DATA/("sample_deletion_requests.csv" if args.sample else "deletion_requests.csv")
    output_path=(ROOT/"code"/"evaluation"/"sample_prediction.csv") if args.sample else OUT
    generate_output(requests_path,output_path)


if __name__ == "__main__": main()
