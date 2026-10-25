import json
import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main


class AuditTests(unittest.TestCase):
    def test_authorization_and_non_deletion(self):
        self.assertTrue(main.is_authorized("Please delete my account and send confirmation"))
        self.assertTrue(main.is_authorized("Je demande la suppression définitive du compte"))
        self.assertTrue(main.is_authorized("Solicito la eliminación permanente de la cuenta"))
        self.assertTrue(main.is_authorized("Solicito a exclusão permanente da conta"))
        self.assertTrue(main.is_authorized("계정의 영구 삭제를 요청합니다"))
        self.assertFalse(main.is_authorized("Please export my data and correct my address"))

    def test_historical_email_resolves_stable_user(self):
        identities = [{"user_id":"u1","email":"new@example.test","name":"A Person","phone":"+1 555 1212","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        audits = [{"audit_id":"a1","user_id":"u1","event_time":"2026-01-01T00:00:00Z","field_name":"email","old_value":"old@example.test","new_value":"new@example.test"}]
        users, ids = main.identifiers_for("old@example.test", identities, audits)
        self.assertEqual(users, {"u1"})
        self.assertIn(main.normalize("new@example.test"), ids)

    def test_audit_new_value_email_resolves_user(self):
        identities=[{"user_id":"u1","email":"current@example.test","name":"A","phone":"+1","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        audits=[{"audit_id":"a1","user_id":"u1","event_time":"2026-01-01T00:00:00Z","field_name":"email","old_value":"older@example.test","new_value":"requested@example.test"}]
        users,ids=main.IdentityIndex(identities,audits).resolve("requested@example.test")
        self.assertEqual(users,{"u1"})
        self.assertIn("current@example.test",ids)

    def test_missing_pytesseract_is_reported_by_exact_module_name(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"valid.png";Image.new("RGB",(2,2),"white").save(p)
            m={"file_id":"evidence_test","file_path":"evidence/images/valid.png","_path":str(p),"captured_at":"2026-01-01T00:00:00Z","origin":"test_service"}
            stream=io.StringIO()
            with patch.dict(sys.modules,{"pytesseract":None}),contextlib.redirect_stderr(stream):
                rows=main.extract_png(m)
            self.assertEqual(rows,[])
            warning=stream.getvalue()
            self.assertIn("module 'pytesseract' is missing",warning)
            self.assertIn("ModuleNotFoundError",warning)
            self.assertNotIn("Pillow module is missing",warning)

    def test_corrupt_png_warns_with_pillow_exception_and_is_not_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"broken.png";p.write_bytes(b"not a png")
            m={"file_id":"evidence_broken","file_path":"evidence/images/broken.png","_path":str(p),"captured_at":"2026-01-01T00:00:00Z","origin":"test_service"}
            stream=io.StringIO()
            with contextlib.redirect_stderr(stream):rows=main.extract_png(m)
            self.assertEqual(rows,[])
            self.assertIn("UnidentifiedImageError",stream.getvalue())
            self.assertIn("not considered clean",stream.getvalue())

    def test_installed_pypdf_extracts_repository_pdf(self):
        pdf=next(m for m in main.load_manifest() if Path(m["file_path"]).suffix.lower()==".pdf")
        rows=main.extract_pdf(pdf)
        self.assertTrue(rows)
        self.assertTrue(all(r["evidence_id"]==pdf["file_id"] for r in rows))

    def test_single_resource_pdf_links_subject_lines_across_document(self):
        pdf=next(m for m in main.load_manifest() if "delivery_correction_attachment" in m["file_path"])
        rows=main.extract_pdf(pdf)
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row["obj"]["resource_id"],"support_001")
        self.assertEqual(row["obj"]["record_type"],"attachment")
        self.assertIn("@",row["obj"]["requester_email"])
        self.assertEqual(main.expected_action(row)[:2],("REPORT_REMAINING_RECORD","DELETE_RECORD"))

    def test_free_text_resource_id_is_linked_to_its_service(self):
        m={"file_id":"evidence_log","captured_at":"2026-01-01T00:00:00Z"}
        rows=main.text_observations("Support lookup completed for support_7712; subject=person@example.test",m,"support_platform")
        self.assertEqual(rows[0]["obj"]["resource_id"],"support_7712")
        self.assertEqual(rows[0]["system"],"support_platform")

    def test_policy_maps_data_categories(self):
        cases = [
            ({"account_status":"ACTIVE","email":"a@example.test"},"account_service","DELETE_RECORD"),
            ({"email":"a@example.test","audience_cohort":"x"},"analytics_platform","ANONYMIZE_RECORD"),
            ({"requester_email":"a@example.test","message_excerpt":"shared"},"support_platform","REDACT_RECORD"),
            ({"restore_allowed":1},"backup_service","BLOCK_RESTORE"),
            ({"enabled":1},"integration_service","DISABLE_DATA_FLOW"),
        ]
        for obj, system, want in cases:
            with self.subTest(system=system):
                self.assertEqual(main.expected_action({"obj":obj,"system":system})[1], want)

    def test_future_artifact_is_not_admissible(self):
        case={"email":"a@example.test","request_text":"Delete my account","audit_at":"2026-01-02T00:00:00Z"}
        identities=[{"user_id":"u1","email":"a@example.test","name":"A","phone":"+1","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        future={"evidence_id":"evidence_1","captured_at":"2026-01-03T00:00:00Z","context":"account_service","system":"account_service","obj":{"resource_id":"account_1","user_id":"u1","email":"a@example.test","account_status":"ACTIVE"},"text":""}
        status, steps=main.audit_case(case, identities, [], [future], [])
        self.assertEqual(status,"INCOMPLETE")
        self.assertEqual(steps, [])

    def test_secondary_clean_record_cannot_prove_account_deletion(self):
        case={"email":"a@example.test","request_text":"Delete my account","audit_at":"2026-01-02T00:00:00Z"}
        identities=[{"user_id":"u1","email":"a@example.test","name":"A","phone":"+1","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        evidence={"evidence_id":"evidence_2","captured_at":"2026-01-01T20:00:00Z","context":"security_service","system":"security_service","obj":{"resource_id":"audit_2","subject_reference":"u1","retention_until":"2030-01-01T00:00:00Z"},"text":""}
        status, steps=main.audit_case(case, identities, [], [evidence], [])
        self.assertEqual(status,"INCOMPLETE")
        self.assertEqual(steps, [])

    def test_redacted_deleted_tombstone_is_account_deletion_proof(self):
        case={"email":"a@example.test","request_text":"Delete my account","audit_at":"2026-01-02T00:00:00Z"}
        identities=[{"user_id":"u1","email":"a@example.test","name":"A","phone":"+1","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        stamp="2026-01-01T20:00:00Z"
        records=[
            {"evidence_id":"evidence_tomb","captured_at":stamp,"context":"identity_service","system":"identity_service","obj":{"resource_id":"tombstone_1","subject_reference":"u1","account_status":"DELETED","name":None,"email":None,"phone":None,"email_hash":None},"text":""},
            {"evidence_id":"evidence_audit","captured_at":stamp,"context":"security_service","system":"security_service","obj":{"resource_id":"audit_1","subject_reference":"u1","event_name":"account_deletion_reviewed"},"text":""},
        ]
        status,steps=main.audit_case(case,main.IdentityIndex(identities,[]),main.EvidenceIndex(records))
        self.assertEqual(status,"COMPLETE")
        self.assertEqual({s["operation"] for s in steps},{"VERIFY_RECORD_REDACTED","VERIFY_RECORD_PRESENT"})

    def test_later_linked_readback_supersedes_old_identifier_row(self):
        case={"email":"a@example.test","request_text":"Delete my account","audit_at":"2026-01-03T00:00:00Z"}
        identities=[{"user_id":"u1","email":"a@example.test","name":"A","phone":"+1","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        base={"system":"account_service","context":"account_service","text":"","_observed_dt":None}
        old={**base,"evidence_id":"evidence_old","captured_at":"2026-01-01T00:00:00Z","_captured_dt":main.dt("2026-01-01T00:00:00Z"),"_state_dt":main.dt("2026-01-01T00:00:00Z"),"_match_text":"a@example.test","obj":{"resource_id":"account_1","email":"a@example.test","account_status":"ACTIVE"}}
        readback={**base,"evidence_id":"evidence_new","captured_at":"2026-01-02T00:00:00Z","_captured_dt":main.dt("2026-01-02T00:00:00Z"),"_state_dt":main.dt("2026-01-02T00:00:00Z"),"_match_text":"","obj":{"resource_id":"account_1","http_status":404,"profile":None}}
        status,steps=main.audit_case(case,main.IdentityIndex(identities,[]),main.EvidenceIndex([old,readback]))
        self.assertEqual(status,"COMPLETE")
        self.assertEqual(steps[0]["resource_id"],"account_1")
        self.assertEqual(steps[0]["operation"],"VERIFY_RECORD_ABSENT")
        self.assertEqual(steps[0]["evidence_id"],"evidence_new")

    def test_completed_readback_wins_timestamp_tie_over_started_trace(self):
        case={"email":"a@example.test","request_text":"Delete my account","audit_at":"2026-01-03T00:00:00Z"}
        identities=[{"user_id":"u1","email":"a@example.test","name":"A","phone":"+1","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        stamp=main.dt("2026-01-02T00:00:00Z")
        base={"evidence_id":"evidence_trace","captured_at":"2026-01-02T00:00:00Z","context":"account_service","system":"account_service","_captured_dt":stamp,"_observed_dt":stamp,"_state_dt":stamp}
        started={**base,"obj":{"resource_id":"account_9","lookup_key":"a@example.test","event":"profile_lookup_started"},"text":""}
        completed={**base,"obj":{"resource_id":"account_9","rows":0,"http_status":404,"event":"profile_lookup_completed"},"text":""}
        status,steps=main.audit_case(case,main.IdentityIndex(identities,[]),main.EvidenceIndex([started,completed]))
        self.assertEqual(status,"COMPLETE")
        self.assertEqual([(s["operation"],s["resource_id"]) for s in steps],[("VERIFY_RECORD_ABSENT","account_9")])

    def test_tombstone_resource_is_identity_service(self):
        self.assertEqual(main.infer_system("",{"resource_id":"tombstone_440","email":None}),"identity_service")
        action=main.expected_action({"system":"identity_service","obj":{"resource_id":"tombstone_440","account_status":"DELETED","subject_reference":"u1","email":None,"phone":None,"name":None,"email_hash":None}})
        self.assertEqual(action,(None,None,"VERIFY_RECORD_REDACTED"))

    def test_trace_id_links_start_row_identity_to_completed_resource_state(self):
        manifest={"file_id":"evidence_trace","captured_at":"2026-01-02T00:00:00Z"}
        content=(
            '2026-01-02T00:00:00Z level=DEBUG service=integration_service trace_id=t1 event=connector_config_read_started subject_key="a@example.test"\n'
            '2026-01-02T00:00:01Z level=WARN service=integration_service trace_id=t1 resource_id=data_flow_8 event=connector_heartbeat enabled=true'
        )
        rows=main.text_observations(content,manifest,"integration_service")
        self.assertEqual(rows[1]["obj"]["subject_key"],'"a@example.test"')
        self.assertTrue(main.match_record(rows[1],set(),{"a@example.test"}))
        finding,remedy,verify=main.expected_action(rows[1])
        self.assertEqual((finding,remedy,verify),("REPORT_ACTIVE_DATA_FLOW","DISABLE_DATA_FLOW","VERIFY_DATA_FLOW_DISABLED"))

    def test_unblocked_eligible_restore_candidate_is_a_restore_risk(self):
        action=main.expected_action({"system":"backup_service","obj":{"resource_id":"backup_12","eligible":"true","deletion_block":"false"}})
        self.assertEqual(action,("REPORT_RESTORE_RISK","BLOCK_RESTORE","VERIFY_RESTORE_BLOCKED"))

    def test_linked_analytics_correlation_key_requires_anonymization(self):
        action=main.expected_action({"system":"analytics_platform","obj":{"resource_id":"analytics_12","correlation_key":"sha256-subject-key"}})
        self.assertEqual(action,("REPORT_EXPOSED_PII","ANONYMIZE_RECORD","VERIFY_RECORD_ANONYMIZED"))

    def test_support_pii_scan_with_direct_identifier_is_exposed_pii(self):
        action=main.expected_action({"system":"support_platform","obj":{
            "resource_id":"support_12","event":"message_pii_scan",
            "detector":"direct_identifier","matched_value":"subject@example.test",
        }})
        self.assertEqual(action,("REPORT_EXPOSED_PII","REDACT_RECORD","VERIFY_RECORD_REDACTED"))

    def test_same_name_with_conflicting_email_does_not_link_evidence(self):
        target_ids={"jonas.berg@example.test","jonas berg","+1 555 0101"}
        unrelated={"obj":{"display_name":"Jonas Berg","email":"different.person@example.test"},"text":""}
        linked={"obj":{"display_name":"Jonas Berg","email":"jonas.berg@example.test"},"text":""}
        self.assertFalse(main.match_record(unrelated,set(),target_ids))
        self.assertTrue(main.match_record(linked,set(),target_ids))

    def test_name_matching_uses_exact_field_or_text_boundaries(self):
        ids={"jonas berg"}
        exact_name={"obj":{"display_name":"Jonas Berg"},"text":""}
        longer_name={"obj":{"display_name":"Jonas Bergman"},"text":""}
        prose_substring={"obj":{},"text":"This record belongs to Jonas Bergman"}
        self.assertTrue(main.match_record(exact_name,set(),ids))
        self.assertFalse(main.match_record(longer_name,set(),ids))
        self.assertFalse(main.match_record(prose_substring,set(),ids))

    def test_pipe_delimited_handover_rows_preserve_state_and_subject(self):
        manifest={"file_id":"evidence_pipe","captured_at":"2026-10-01T12:00:00Z"}
        content="\n".join((
            "2026-10-01T12:00:00Z | account_service | account_8 | USER_PROFILE | NOT_FOUND | a@example.test",
            "2026-10-01T12:00:00Z | analytics_platform | analytics_8 | ANALYTICS_PROFILE | IDENTIFIABLE | a@example.test",
            "2026-10-01T12:00:00Z | backup_service | backup_8 | BACKUP_ARCHIVE | ACTIVE | a@example.test",
            "2026-10-01T12:00:00Z | integration_service | data_flow_8 | DATA_FLOW | ACTIVE | a@example.test",
            "2026-10-01T12:00:00Z | search_service | search_8 | SEARCH_INDEX_ENTRY | FOUND | a@example.test",
            "2026-10-01T12:00:00Z | security_service | audit_record_8 | SECURITY_AUDIT_LOG | FOUND | user_8",
            "2026-10-01T12:00:00Z | support_platform | support_8 | SUPPORT_ATTACHMENT | FOUND | a@example.test",
        ))
        rows=main.text_observations(content,manifest,"handover")
        self.assertEqual(len(rows),7)
        self.assertEqual(rows[0]["obj"]["status"],"not_found")
        self.assertEqual(rows[5]["obj"]["subject_reference"],"user_8")
        operations=[main.expected_action(row)[:2] for row in rows]
        self.assertEqual(operations,[
            (None,None),
            ("REPORT_EXPOSED_PII","ANONYMIZE_RECORD"),
            ("REPORT_RESTORE_RISK","BLOCK_RESTORE"),
            ("REPORT_ACTIVE_DATA_FLOW","DISABLE_DATA_FLOW"),
            ("REPORT_REMAINING_RECORD","DELETE_RECORD"),
            (None,None),
            ("REPORT_REMAINING_RECORD","DELETE_RECORD"),
        ])

    def test_explicit_account_404_is_verification(self):
        finding, remedy, verification = main.expected_action({"system":"account_service","obj":{"resource_id":"account_3","http_status":404,"rows":0}})
        self.assertIsNone(finding)
        self.assertIsNone(remedy)
        self.assertEqual(verification,"VERIFY_RECORD_ABSENT")

    def test_matching_record_produces_ordered_steps_and_evidence(self):
        case={"email":"a@example.test","request_text":"Delete my account","audit_at":"2026-01-02T00:00:00Z"}
        identities=[{"user_id":"u1","email":"a@example.test","name":"A","phone":"+1","email_hash":"h","updated_at":"2026-01-01T00:00:00Z"}]
        evidence={"evidence_id":"evidence_1","captured_at":"2026-01-01T20:00:00Z","context":"account_service","system":"account_service","obj":{"resource_id":"account_1","user_id":"u1","email":"a@example.test","account_status":"ACTIVE"},"text":""}
        status, steps=main.audit_case(case, identities, [], [evidence], [])
        self.assertEqual(status,"INCOMPLETE")
        self.assertEqual([s["phase"] for s in steps],["FINDING","REMEDIATION","VERIFICATION"])
        self.assertEqual([s["step_no"] for s in steps],[1,2,3])
        self.assertEqual(steps[0]["evidence_id"],"evidence_1")
        self.assertEqual(steps[1]["evidence_id"],"")
        self.assertEqual(set(steps[0]),set(main.FIELDS))

    def test_json_csv_round_trip(self):
        row={"case_id":"case_1","deletion_status":"INCOMPLETE","steps_json":json.dumps([{"resource_id":"a,b\"c","step_no":1}])}
        import io, csv
        stream=io.StringIO(newline="")
        writer=csv.DictWriter(stream,fieldnames=("case_id","deletion_status","steps_json")); writer.writeheader(); writer.writerow(row)
        parsed=list(csv.DictReader(io.StringIO(stream.getvalue(),newline="")))[0]
        self.assertEqual(json.loads(parsed["steps_json"])[0]["resource_id"],"a,b\"c")


if __name__ == "__main__":
    unittest.main()
