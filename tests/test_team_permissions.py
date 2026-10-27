"""Real-login tests of students, patient grants and every supported resource path."""

import base64
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_accounts_clinical import (
    PASSWORD,
    auth,
    field,
    ocr_result,
    png_bytes,
    review,
    upload,
)
from test_accounts_clinical import env as account_env  # noqa: F401 -- shared fixture

from patient_follow_up_system import clinical_ocr
from patient_follow_up_system.models import (
    ClinicalDocument,
    PatientDocument,
    PatientGrant,
    PatientIntakeLink,
    PatientIntakeSubmission,
    PatientNoticeVersion,
    User,
)


@pytest.fixture
def team(request):
    client, factory, ids = request.getfixturevalue("account_env")
    doctor = auth(client)
    response = client.post(
        "/doctor/students",
        headers=doctor,
        json={
            "username": "student_one",
            "display_name": "虚构学生甲",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    student_id = response.json()["id"]
    student = auth(client, "student_one")
    return client, factory, ids, doctor, student, student_id


def grant(team, **changes):
    client, _, _ids, doctor, _, student_id = team
    now = datetime.now(UTC)
    payload = {
        "student_id": student_id,
        "note": "虚构病例整理",
        "starts_at": (now - timedelta(minutes=1)).isoformat(),
        "ends_at": (now + timedelta(days=1)).isoformat(),
        **changes,
    }
    return client.post("/doctor/student-permissions", headers=doctor, json=payload)


def test_team_login_resolves_database_role_and_rejects_other_identities(team):
    client, factory, ids, _, _, _ = team
    for username, expected_role in (("doctor", "doctor"), ("student_one", "student")):
        response = client.post(
            "/auth/login",
            json={"username": username, "password": PASSWORD, "role": "team"},
        )
        assert response.status_code == 200, response.text
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        assert client.get("/auth/me", headers=headers).json()["role"] == expected_role
    for username in ("admin", "patient"):
        with factory() as db:
            before = db.get(User, ids[username]).last_login_at
        response = client.post(
            "/auth/login",
            json={"username": username, "password": PASSWORD, "role": "team"},
        )
        assert response.status_code == 403
        assert "access_token" not in response.json()
        with factory() as db:
            assert db.get(User, ids[username]).last_login_at == before


def student_upload(team):
    client, _, ids, _, student, _ = team
    return client.post(
        "/clinical-documents",
        headers=student,
        json={
            "patient_id": ids["patient_record"],
            "document_name": "fictional.png",
            "document_mime_type": "image/png",
            "document_base64": base64.b64encode(png_bytes()).decode(),
        },
    )


def test_doctor_creates_only_students_in_own_team_and_no_privilege_escalation(team):
    client, _, ids, doctor, student, student_id = team
    admin = auth(client, "admin")
    other = auth(client, "other_doctor")
    account = next(
        a
        for a in client.get("/admin/accounts", headers=admin).json()
        if a["id"] == student_id
    )
    assert account["role"] == "student" and account["mentor_doctor_id"] == ids["doctor"]
    assert "password_hash" not in account and "password" not in account
    assert client.get("/doctor/students", headers=other).json() == []
    assert (
        client.patch(
            f"/doctor/students/{student_id}", headers=other, json={"is_active": False}
        ).status_code
        == 404
    )
    assert client.get("/doctor/students", headers=student).status_code == 403
    assert (
        client.post(
            "/admin/accounts",
            headers=doctor,
            json={
                "username": "bad_doctor",
                "display_name": "bad",
                "password": PASSWORD,
                "role": "doctor",
            },
        ).status_code
        == 403
    )
    for change in (
        {"role": "doctor"},
        {"role": "admin"},
        {"mentor_doctor_id": ids["other_doctor"]},
    ):
        assert (
            client.post(
                "/doctor/students",
                headers=doctor,
                json={
                    "username": "bad_student",
                    "display_name": "bad",
                    "password": PASSWORD,
                    **change,
                },
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/doctor/students",
            headers=doctor,
            json={
                "username": "student_one",
                "display_name": "重复",
                "password": PASSWORD,
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/auth/login",
            json={"username": "student_one", "password": PASSWORD, "role": "student"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/login",
            json={"username": "student_one", "password": PASSWORD, "role": "doctor"},
        ).status_code
        == 403
    )


def test_admin_student_creation_requires_active_doctor_and_can_disable(team):
    client, _, ids, _, student, student_id = team
    admin = auth(client, "admin")
    data = {
        "username": "student_two",
        "display_name": "虚构学生乙",
        "password": PASSWORD,
        "role": "student",
    }
    for owner in (None, ids["admin"], ids["patient"], 99999):
        assert (
            client.post(
                "/admin/accounts",
                headers=admin,
                json={**data, "mentor_doctor_id": owner},
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/admin/accounts",
            headers=admin,
            json={**data, "mentor_doctor_id": ids["other_doctor"]},
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/admin/accounts/{student_id}", headers=admin, json={"is_active": False}
        ).status_code
        == 200
    )
    assert client.get("/patients", headers=student).status_code == 401
    assert (
        client.post(
            "/auth/login", json={"username": "student_one", "password": PASSWORD}
        ).status_code
        == 401
    )


def test_default_deny_then_read_only_patient_scope_cannot_mutate(team):
    client, _, ids, doctor, student, _ = team
    patient_id = ids["patient_record"]
    assert client.get("/patients", headers=student).json() == []
    assert client.get(f"/patients/{patient_id}", headers=student).status_code == 404
    assert grant(team).status_code == 201
    items = client.get("/patients", headers=student).json()
    assert [p["id"] for p in items] == [patient_id]
    assert items[0]["permissions"] == ["view"]
    assert client.get(f"/patients/{patient_id}/workspace", headers=student).json()[
        "permissions"
    ] == ["view"]
    assert (
        client.get(
            f"/patients/{ids['other_record']}/workspace", headers=student
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/patients/{ids['other_record']}/documents", headers=student
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/patients", headers=student, json={"display_name": "bad"}
        ).status_code
        == 403
    )
    assert (
        client.post(f"/patients/{patient_id}/intake-link", headers=student).status_code
        == 403
    )
    assert (
        client.post(
            f"/patients/{patient_id}/encounters",
            headers=student,
            json={"occurred_at": datetime.now(UTC).isoformat(), "display_label": "bad"},
        ).status_code
        == 403
    )
    assert student_upload(team).status_code == 404
    unbound = upload(client, doctor)
    assert (
        client.get(f"/clinical-documents/{unbound['id']}", headers=student).status_code
        == 404
    )
    assert client.get("/clinical-documents", headers=student).json() == []


def test_edit_allows_upload_ocr_pending_drafts_but_not_confirmation(team, monkeypatch):
    client, factory, ids, doctor, student, _ = team
    assert grant(team, can_edit=True).status_code == 201
    response = student_upload(team)
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["permissions"] == ["view", "edit"]
    monkeypatch.setattr(clinical_ocr, "recognize", lambda *_: ocr_result("虚构甲"))
    doc = client.post(
        f"/clinical-documents/{doc['id']}/extract",
        headers=student,
        json={"version": doc["version"]},
    ).json()
    result = review(
        client, student, doc, [field("chief_complaint", "学生录入草稿", "pending")]
    )
    assert result.status_code == 200, result.text
    doc = result.json()
    for action, fields in (
        (
            "file",
            [field("patient_name", "虚构甲"), field("chief_complaint", "绕过确认")],
        ),
        ("save", [field("chief_complaint", "绕过确认")]),
        ("reject", []),
    ):
        assert (
            review(
                client, student, doc, fields, action, patient_id=ids["patient_record"]
            ).status_code
            == 404
        )
    assert (
        client.get(
            f"/patients/{ids['patient_record']}/clinical-records", headers=student
        ).json()
        == []
    )
    with factory() as db:
        assert db.get(ClinicalDocument, doc["id"]).owner_doctor_id == ids["doctor"]
    assert (
        client.get(f"/clinical-documents/{doc['id']}", headers=doctor).status_code
        == 200
    )
    filed = review(
        client,
        doctor,
        doc,
        [field("patient_name", "虚构甲"), field("chief_complaint", "医生核对")],
        "file",
        patient_id=ids["patient_record"],
    )
    assert filed.status_code == 200, filed.text
    assert (
        review(
            client,
            student,
            filed.json(),
            [field("past_history", "不能补填", "pending")],
        ).status_code
        == 404
    )


def test_explicit_review_grant_can_file_but_cannot_create_patient_or_rebind(team):
    client, _, ids, _, student, _ = team
    assert grant(team, can_edit=True, can_review=True).status_code == 201
    doc = student_upload(team).json()
    fields = [field("patient_name", "虚构甲"), field("chief_complaint", "虚构内容")]
    assert (
        review(client, student, doc, fields, "file", create_patient=True).status_code
        == 403
    )
    assert (
        review(
            client, student, doc, fields, "file", patient_id=ids["other_record"]
        ).status_code
        == 409
    )
    result = review(
        client, student, doc, fields, "file", patient_id=ids["patient_record"]
    )
    assert result.status_code == 200, result.text
    records = client.get(
        f"/patients/{ids['patient_record']}/clinical-records", headers=student
    ).json()
    assert len(records) == 1


def test_disabling_view_blocks_existing_token_lists_details_files_preview_and_writes(
    team,
):
    client, factory, ids, doctor, student, _ = team
    authorization = grant(team, can_edit=True, can_review=True).json()
    doc = student_upload(team).json()
    assert (
        client.get(f"/clinical-documents/{doc['id']}/file", headers=student).content
        == png_bytes()
    )
    assert (
        client.get(
            f"/clinical-documents/{doc['id']}/pages/1", headers=student
        ).status_code
        == 200
    )
    result = grant(team, is_permanent=True, can_view=False)
    assert result.status_code == 201 and not result.json()["can_view"]
    assert result.json()["id"] == authorization["id"]
    assert "revoked_at" not in result.json() and "revoked_by_id" not in result.json()
    assert client.get("/doctor/patient-grants", headers=doctor).status_code == 404
    assert (
        client.post(
            f"/doctor/student-permissions/{authorization['id']}/revoke", headers=doctor
        ).status_code
        == 404
    )
    assert client.get("/patients", headers=student).json() == []
    assert client.get("/clinical-documents", headers=student).json() == []
    for path in (
        f"/patients/{ids['patient_record']}",
        f"/patients/{ids['patient_record']}/workspace",
        f"/clinical-documents/{doc['id']}",
        f"/clinical-documents/{doc['id']}/file",
        f"/clinical-documents/{doc['id']}/pages/1",
        f"/clinical-documents/{doc['id']}/history",
    ):
        assert client.get(path, headers=student).status_code == 404, path
    assert review(client, student, doc, []).status_code == 404
    with factory() as db:
        assert len(list(db.scalars(select(PatientGrant)))) == 1
    assert client.get("/doctor/student-permissions", headers=student).status_code == 403
    assert client.patch(
        f"/doctor/student-permissions/{authorization['id']}",
        headers=doctor,
        json={"can_review": True},
    ).status_code in (404, 405)


def test_expiry_scheduling_overlap_and_student_teacher_disable(team):
    client, factory, ids, doctor, student, student_id = team
    future = datetime.now(UTC) + timedelta(days=1)
    assert (
        grant(
            team,
            starts_at=future.isoformat(),
            ends_at=(future + timedelta(days=1)).isoformat(),
        ).status_code
        == 201
    )
    assert client.get("/patients", headers=student).json() == []
    authorization = grant(team).json()
    with factory() as db:
        db.get(PatientGrant, authorization["id"]).ends_at = datetime.now(UTC).replace(
            tzinfo=None
        ) - timedelta(seconds=1)
        db.commit()
    assert client.get("/patients", headers=student).json() == []
    grant(team, can_edit=True)
    grant(team)
    assert client.get("/patients", headers=student).json()[0]["permissions"] == ["view"]
    client.patch(
        f"/doctor/students/{student_id}", headers=doctor, json={"is_active": False}
    )
    assert client.get("/patients", headers=student).status_code == 401
    client.patch(
        f"/doctor/students/{student_id}", headers=doctor, json={"is_active": True}
    )
    admin = auth(client, "admin")
    client.patch(
        f"/admin/accounts/{ids['doctor']}", headers=admin, json={"is_active": False}
    )
    assert client.get("/patients", headers=student).status_code == 401
    assert (
        client.post(
            "/auth/login", json={"username": "student_one", "password": PASSWORD}
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "change",
    [
        {"note": "x" * 301},
        {"ends_at": "2020-01-01T00:00:00Z"},
        {"starts_at": "2020-01-01T00:00:00"},
        {"can_export": True},
    ],
)
def test_invalid_grants_rejected(team, change):
    assert grant(team, **change).status_code == 422


def test_cross_team_and_admin_cannot_grant_or_read_clinical_data(team):
    client, _, ids, doctor, student, student_id = team
    assert grant(team, patient_id=ids["other_record"]).status_code == 422
    other = auth(client, "other_doctor")
    assert (
        client.post(
            "/doctor/student-permissions",
            headers=other,
            json={
                "student_id": student_id,
                "note": "bad",
                "starts_at": datetime.now(UTC).isoformat(),
                "ends_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        ).status_code
        == 404
    )
    admin = auth(client, "admin")
    doc = upload(client, doctor)
    for path in (
        "/patients",
        f"/patients/{ids['patient_record']}/workspace",
        f"/clinical-documents/{doc['id']}",
        f"/clinical-documents/{doc['id']}/file",
    ):
        assert client.get(path, headers=admin).status_code == 403
    assert client.post(
        "/doctor/student-permissions", headers=student, json={}
    ).status_code in (403, 422)


def test_patient_and_intake_originals_import_and_review_share_same_scope(
    team, tmp_path, monkeypatch
):
    client, factory, ids, _doctor, student, _ = team
    monkeypatch.setenv("PATIENT_UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("INTAKE_UPLOAD_DIR", str(tmp_path))
    (tmp_path / "original.png").write_bytes(png_bytes())
    with factory() as db:
        link = PatientIntakeLink(
            token_digest="fictional-digest",
            created_by_doctor_id=ids["doctor"],
            patient_id=ids["patient_record"],
            expires_at=datetime(2030, 1, 1),
        )
        db.add(link)
        db.flush()
        intake = PatientIntakeSubmission(
            intake_link_id=link.id,
            submission_digest="1" * 64,
            display_name="虚构甲",
            sex="女",
            date_of_birth=datetime(2000, 1, 1).date(),
            operator_relationship="本人",
            notice_version="1.0",
            document_name="fictional.png",
            document_storage_name="original.png",
            document_mime_type="image/png",
            document_sha256="0" * 64,
        )
        notice = PatientNoticeVersion(
            notice_key="fixture",
            version="1",
            title="虚构须知",
            content="虚构正文",
            content_sha256="2" * 64,
            status="draft",
        )
        db.add(notice)
        db.flush()
        original = PatientDocument(
            notice_version_id=notice.id,
            notice_content_sha256="2" * 64,
            consented_at=datetime.now(UTC),
            patient_id=ids["patient_record"],
            submitted_by_user_id=ids["patient"],
            event_date=datetime(2026, 10, 1).date(),
            display_label="fictional",
            original_name="fictional.png",
            mime_type="image/png",
            storage_name="original.png",
            sha256="0" * 64,
            size_bytes=len(png_bytes()),
        )
        db.add_all([intake, original])
        db.commit()
        intake_id, original_id = intake.id, original.id
    paths = [
        f"/intake-submissions/{intake_id}/document",
        f"/patient-documents/{original_id}/file",
    ]
    assert client.get("/intake-submissions", headers=student).json() == []
    assert grant(team).status_code == 201
    assert len(client.get("/intake-submissions", headers=student).json()) == 1
    for path in paths:
        response = client.get(path, headers=student)
        assert response.content == png_bytes()
        assert response.headers["cache-control"] == "no-store"
    for kind, source_id in (("intake", intake_id), ("patient", original_id)):
        assert (
            client.post(
                "/clinical-documents/import",
                headers=student,
                json={"source_kind": kind, "source_id": source_id},
            ).status_code
            == 404
        )
    assert (
        client.post(
            f"/intake-submissions/{intake_id}/review",
            headers=student,
            json={"action": "approve"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/patient-documents/{original_id}/review",
            headers=student,
            json={"action": "reject"},
        ).status_code
        == 404
    )
    assert grant(team, can_edit=True).status_code == 201
    imported = []
    for kind, source_id in (("intake", intake_id), ("patient", original_id)):
        response = client.post(
            "/clinical-documents/import",
            headers=student,
            json={"source_kind": kind, "source_id": source_id},
        )
        assert response.status_code == 200, response.text
        imported.append(response.json()["id"])
        assert response.json()["target_patient_id"] == ids["patient_record"]
    grant(team)
    # Read-only users can open an existing import without creating/mutating it.
    assert (
        client.post(
            "/clinical-documents/import",
            headers=student,
            json={"source_kind": "intake", "source_id": intake_id},
        ).status_code
        == 200
    )
    grant(team, is_permanent=True, can_view=False)
    for path in paths + [f"/clinical-documents/{i}/file" for i in imported]:
        assert client.get(path, headers=student).status_code == 404


def test_revoked_while_ocr_runs_discards_result(team, monkeypatch):
    client, factory, _, _, student, _ = team
    authorization = grant(team, can_edit=True).json()
    doc = student_upload(team).json()

    def recognize(*_):
        with factory() as db:
            config = db.get(PatientGrant, authorization["id"])
            config.can_view = config.can_edit = config.can_review = False
            db.commit()
        return ocr_result("虚构甲")

    monkeypatch.setattr(clinical_ocr, "recognize", recognize)
    assert (
        client.post(
            f"/clinical-documents/{doc['id']}/extract",
            headers=student,
            json={"version": doc["version"]},
        ).status_code
        == 404
    )
    with factory() as db:
        assert db.get(ClinicalDocument, doc["id"]).extraction_status == "not_run"


def test_permanent_permissions_cover_all_current_and_future_patients_only_of_mentor(
    team,
):
    client, _, ids, doctor, student, _ = team
    first = client.post(
        "/patients", headers=doctor, json={"display_name": "同一医生的第二名虚构患者"}
    ).json()
    response = grant(team, is_permanent=True, note="")
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["patient_id"] is None and data["scope"] == "doctor"
    assert (
        data["is_permanent"] and data["starts_at"] is None and data["ends_at"] is None
    )
    assert data["can_view"] and data["note"] == ""
    later = client.post(
        "/patients", headers=doctor, json={"display_name": "授权后新增的虚构患者"}
    ).json()
    assert {p["id"] for p in client.get("/patients", headers=student).json()} == {
        ids["patient_record"],
        first["id"],
        later["id"],
    }
    assert (
        client.get(f"/patients/{later['id']}/workspace", headers=student).status_code
        == 200
    )
    assert (
        client.get(
            f"/patients/{ids['other_record']}/workspace", headers=student
        ).status_code
        == 404
    )
    assert grant(team, is_permanent=True, can_view=False).status_code == 201
    assert client.get("/patients", headers=student).json() == []


def test_new_settings_replace_old_rights_and_allow_view_to_be_disabled(team):
    client, factory, _ids, doctor, student, student_id = team
    broad = grant(team, is_permanent=True, can_edit=True, can_review=True).json()
    doc = student_upload(team).json()
    smaller = grant(team, is_permanent=True, note="  可选备注  ").json()
    assert smaller["note"] == "可选备注"
    assert client.get("/patients", headers=student).json()[0]["permissions"] == ["view"]
    assert (
        review(
            client, student, doc, [field("chief_complaint", "越权草稿", "pending")]
        ).status_code
        == 404
    )
    configs = client.get("/doctor/student-permissions", headers=doctor).json()
    assert len(configs) == 1 and configs[0]["id"] == broad["id"] == smaller["id"]
    assert configs[0]["can_review"] is False
    closed = grant(team, is_permanent=True, can_view=False).json()
    assert not closed["can_view"]
    assert client.get("/patients", headers=student).json() == []
    assert (
        client.get(f"/clinical-documents/{doc['id']}/file", headers=student).status_code
        == 404
    )
    assert (
        grant(team, is_permanent=True, can_view=False, can_edit=True).status_code == 422
    )
    with factory() as db:
        active = list(
            db.scalars(
                select(PatientGrant).where(
                    PatientGrant.student_id == student_id,
                )
            )
        )
        assert len(active) == 1 and active[0].id == closed["id"]


def test_legacy_patient_grants_stay_scoped_until_doctor_saves_new_settings(team):
    client, factory, ids, doctor, student, student_id = team
    second = client.post(
        "/patients", headers=doctor, json={"display_name": "旧授权未覆盖的虚构患者"}
    ).json()
    with factory() as db:
        legacy = PatientGrant(
            patient_id=ids["patient_record"],
            student_id=student_id,
            granted_by_id=ids["doctor"],
            purpose="历史用途",
            can_edit=False,
            can_review=False,
            starts_at=datetime.now(UTC) - timedelta(days=1),
            ends_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.add(legacy)
        db.commit()
        legacy_id = legacy.id
    assert [p["id"] for p in client.get("/patients", headers=student).json()] == [
        ids["patient_record"]
    ]
    assert grant(team, is_permanent=True).status_code == 201
    assert {p["id"] for p in client.get("/patients", headers=student).json()} == {
        ids["patient_record"],
        second["id"],
    }
    with factory() as db:
        current = db.get(PatientGrant, legacy_id)
        assert current.patient_id is None and current.purpose == "虚构病例整理"
        assert len(list(db.scalars(select(PatientGrant)))) == 1


def test_parallel_settings_updates_leave_one_configuration(team):
    from concurrent.futures import ThreadPoolExecutor

    client, factory, _, doctor, _, student_id = team

    def save(edit):
        return client.post(
            "/doctor/student-permissions",
            headers=doctor,
            json={"student_id": student_id, "is_permanent": True, "can_edit": edit},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, [True, False]))
    assert all(r.status_code == 201 for r in results)
    with factory() as db:
        records = list(
            db.scalars(
                select(PatientGrant).where(PatientGrant.student_id == student_id)
            )
        )
        assert len(records) == 1
