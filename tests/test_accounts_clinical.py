import base64
import hashlib
import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from patient_follow_up_system import clinical_ocr
from patient_follow_up_system.auth import hash_password, verify_password
from patient_follow_up_system.database import Base, get_db
from patient_follow_up_system.main import app
from patient_follow_up_system.models import (
    AccountEvent,
    ClinicalDocument,
    ClinicalField,
    Patient,
    PatientDemoConsent,
    PatientDocument,
    PatientIntakeLink,
    PatientIntakeSubmission,
    PatientNoticeVersion,
    User,
    UserRole,
)

PASSWORD = "Review-test-2026!"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", "isolated-test-secret-with-at-least-32-bytes")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("CLINICAL_UPLOAD_DIR", str(tmp_path / "clinical"))
    monkeypatch.setenv("PATIENT_UPLOAD_DIR", str(tmp_path / "patient"))
    monkeypatch.setenv("INTAKE_UPLOAD_DIR", str(tmp_path / "intake"))
    engine = create_engine(
        f"sqlite:///{tmp_path / 'app.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        hashed = hash_password(PASSWORD)
        users = [
            User(username=name, display_name=name, password_hash=hashed, role=role)
            for name, role in [
                ("admin", UserRole.ADMIN),
                ("doctor", UserRole.DOCTOR),
                ("other_doctor", UserRole.DOCTOR),
                ("patient", UserRole.PATIENT),
            ]
        ]
        db.add_all(users)
        db.flush()
        patient = Patient(
            patient_code="TEST-001",
            display_name="虚构甲",
            responsible_doctor_id=users[1].id,
            patient_user_id=users[3].id,
        )
        other = Patient(
            patient_code="TEST-002",
            display_name="虚构乙",
            responsible_doctor_id=users[2].id,
        )
        db.add_all([patient, other])
        db.commit()
        ids = {u.username: u.id for u in users} | {
            "patient_record": patient.id,
            "other_record": other.id,
        }

    def database():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            yield client, factory, ids
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def auth(client, username="doctor"):
    response = client.post(
        "/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(output, format="PNG")
    return output.getvalue()


def upload(client, headers):
    response = client.post(
        "/clinical-documents",
        headers=headers,
        json={
            "document_name": "fictional.png",
            "document_mime_type": "image/png",
            "document_base64": base64.b64encode(png_bytes()).decode(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def field(key, value, status="corrected"):
    return {"key": key, "confirmed_value": value, "review_status": status}


def review(client, headers, doc, fields, action="save", **kwargs):
    return client.post(
        f"/clinical-documents/{doc['id']}/review",
        headers=headers,
        json={"version": doc["version"], "action": action, "fields": fields, **kwargs},
    )


def ocr_result(name="虚构甲"):
    lines = [
        {
            "id": i,
            "page": 1,
            "text": text,
            "confidence": 0.98,
            "box": [0.1, i / 10, 0.9, i / 10 + 0.08],
        }
        for i, text in enumerate(
            [
                f"姓名：{name} 性别：女 年龄：53岁",
                "主诉：腹胀",
                "现病史：间断腹胀一月",
                "既往史：无",
            ]
        )
    ]
    return clinical_ocr.extract_fields(
        [{"number": 1, "rotation": 0, "width": 300, "height": 200, "lines": lines}]
    )


def test_admin_create_disable_blocks_new_login_and_existing_token(env):
    client, factory, _ids = env
    admin = auth(client, "admin")
    for role in ("doctor", "patient"):
        response = client.post(
            "/admin/accounts",
            headers=admin,
            json={
                "username": f"new_{role}",
                "display_name": f"虚构{role}",
                "password": PASSWORD,
                "role": role,
            },
        )
        assert response.status_code == 201, response.text
        account = response.json()
        assert (
            account["is_active"]
            and "password_hash" not in account
            and "password" not in account
        )
        headers = auth(client, f"new_{role}")
        assert client.get("/auth/me", headers=headers).json()["role"] == role
        assert client.get("/patients", headers=headers).status_code == 200
        if role == "doctor":
            assert (
                client.post(
                    "/patients", headers=headers, json={"display_name": "虚构新档案"}
                ).status_code
                == 201
            )
        else:
            assert (
                client.post(
                    "/patients", headers=headers, json={"display_name": "越权"}
                ).status_code
                == 403
            )
        assert (
            client.patch(
                f"/admin/accounts/{account['id']}",
                headers=admin,
                json={"is_active": False},
            ).status_code
            == 200
        )
        assert client.get("/patients", headers=headers).status_code == 401
        assert (
            client.post(
                "/auth/login", json={"username": f"new_{role}", "password": PASSWORD}
            ).status_code
            == 401
        )
        assert client.patch(
            f"/admin/accounts/{account['id']}", headers=admin, json={"is_active": True}
        ).json()["is_active"]
        assert auth(client, f"new_{role}")
    with factory() as db:
        assert len(db.scalars(select(AccountEvent)).all()) == 6
        user = db.scalar(select(User).where(User.username == "new_patient"))
        assert user.password_hash != PASSWORD and verify_password(
            PASSWORD, user.password_hash
        )


def test_account_permissions_duplicates_validation_and_no_admin_escalation(env):
    client, _, ids = env
    assert client.get("/admin/accounts").status_code == 401
    for role in ("doctor", "patient"):
        headers = auth(client, role)
        assert client.get("/admin/accounts", headers=headers).status_code == 403
        assert (
            client.patch(
                f"/admin/accounts/{ids['doctor']}",
                headers=headers,
                json={"is_active": False},
            ).status_code
            == 403
        )
    admin = auth(client, "admin")
    payload = {
        "username": "doctor",
        "display_name": "虚构",
        "password": PASSWORD,
        "role": "doctor",
    }
    assert (
        client.post("/admin/accounts", headers=admin, json=payload).status_code == 409
    )
    for patch in (
        {"role": "admin"},
        {"display_name": "   "},
        {"password": "123"},
        {"username": "!"},
    ):
        assert (
            client.post(
                "/admin/accounts", headers=admin, json=payload | patch
            ).status_code
            == 422
        )
    assert (
        client.patch(
            f"/admin/accounts/{ids['admin']}", headers=admin, json={"is_active": False}
        ).status_code
        == 404
    )


def test_unbound_buffer_original_hash_extract_review_partial_file_and_later_pending(
    env, monkeypatch
):
    client, factory, ids = env
    headers = auth(client)
    doc = upload(client, headers)
    assert doc["patient_id"] is None and doc["status"] == "buffered"
    assert doc["sha256"] == hashlib.sha256(png_bytes()).hexdigest()
    assert (
        client.get(f"/clinical-documents/{doc['id']}/file", headers=headers).content
        == png_bytes()
    )
    monkeypatch.setattr(clinical_ocr, "recognize", lambda *_: ocr_result("误识别姓名"))
    response = client.post(
        f"/clinical-documents/{doc['id']}/extract",
        headers=headers,
        json={"version": doc["version"]},
    )
    assert response.status_code == 200, response.text
    doc = response.json()
    assert doc["patient_id"] is None and doc["candidate_name"] == "误识别姓名"
    assert (
        client.get(
            f"/patients/{ids['patient_record']}/clinical-records", headers=headers
        ).json()
        == []
    )
    assert (
        client.get(
            f"/clinical-documents/{doc['id']}/pages/1", headers=headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/clinical-documents/{doc['id']}/pages/0", headers=headers
        ).status_code
        == 404
    )
    response = review(
        client,
        headers,
        doc,
        [
            field("patient_name", "虚构甲"),
            field("chief_complaint", "腹胀", "confirmed"),
        ],
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["patient_id"] is None
    assert (
        client.post(
            f"/clinical-documents/{saved['id']}/extract",
            headers=headers,
            json={"version": saved["version"]},
        ).status_code
        == 409
    )
    assert review(client, headers, doc, []).status_code == 409
    response = review(
        client, headers, saved, [], "file", patient_id=ids["patient_record"]
    )
    assert response.status_code == 200, response.text
    filed = response.json()
    records = client.get(
        f"/patients/{ids['patient_record']}/clinical-records", headers=headers
    ).json()
    assert {f["key"] for f in records[0]["fields"]} == {
        "patient_name",
        "chief_complaint",
    }
    assert records[0]["pending_fields"] > 0
    response = review(
        client, headers, filed, [field("past_history", "无", "confirmed")]
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert (
        review(client, headers, updated, [field("chief_complaint", "其他")]).status_code
        == 409
    )
    assert review(client, headers, updated, [], "reject").status_code == 409
    events = client.get(
        f"/clinical-documents/{doc['id']}/history", headers=headers
    ).json()
    assert [e["action"] for e in events] == [
        "upload",
        "extract",
        "save",
        "file",
        "save",
    ]
    assert events[2]["changes"]["patient_name"]["after"]["value"] == "虚构甲"
    with factory() as db:
        assert db.get(Patient, ids["patient_record"]).patient_user_id == ids["patient"]


def test_document_scope_and_wrong_patient_do_not_file(env):
    client, factory, ids = env
    headers = auth(client)
    doc = upload(client, headers)
    for username, expected in (("other_doctor", 404), ("patient", 403), ("admin", 403)):
        other = auth(client, username)
        for suffix in ("", "/file", "/pages/1", "/history"):
            assert (
                client.get(
                    f"/clinical-documents/{doc['id']}{suffix}", headers=other
                ).status_code
                == expected
            )
        assert (
            client.post(
                f"/clinical-documents/{doc['id']}/extract",
                headers=other,
                json={"version": doc["version"]},
            ).status_code
            == expected
        )
        assert review(client, other, doc, []).status_code == expected
    fields = [field("patient_name", "虚构甲"), field("chief_complaint", "腹胀")]
    assert (
        review(
            client, headers, doc, fields, "file", patient_id=ids["other_record"]
        ).status_code
        == 404
    )
    assert (
        review(
            client,
            headers,
            doc,
            [field("patient_name", "姓名有误"), field("chief_complaint", "腹胀")],
            "file",
            patient_id=ids["patient_record"],
        ).status_code
        == 409
    )
    with factory() as db:
        assert db.get(ClinicalDocument, doc["id"]).patient_id is None
        assert all(
            f.review_status == "pending" for f in db.scalars(select(ClinicalField))
        )


def test_manual_fallback_create_patient_and_reject_retains_original(env, monkeypatch):
    client, factory, _ids = env
    headers = auth(client)
    doc = upload(client, headers)

    def failed(*_):
        raise RuntimeError("internal provider details must not leak")

    monkeypatch.setattr(clinical_ocr, "recognize", failed)
    result = client.post(
        f"/clinical-documents/{doc['id']}/extract",
        headers=headers,
        json={"version": doc["version"]},
    ).json()
    assert (
        result["extraction_status"] == "failed"
        and "internal" not in result["extraction_error"]
    )
    assert all(f["candidate_value"] is None for f in result["fields"])
    response = review(
        client,
        headers,
        result,
        [field("patient_name", "虚构新患者"), field("chief_complaint", "间断腹胀")],
        "file",
        create_patient=True,
    )
    assert response.status_code == 200, response.text
    patient_id = response.json()["patient_id"]
    with factory() as db:
        patient = db.get(Patient, patient_id)
        assert patient.display_name == "虚构新患者" and patient.patient_user_id is None
    rejected = upload(client, headers)
    response = review(
        client, headers, rejected, [field("patient_name", "虚构驳回")], "reject"
    )
    assert response.status_code == 200 and response.json()["patient_id"] is None
    assert (
        client.get(
            f"/clinical-documents/{rejected['id']}/file", headers=headers
        ).status_code
        == 200
    )
    assert (
        review(
            client, headers, response.json(), [], "file", create_patient=True
        ).status_code
        == 409
    )


def test_validation_does_not_confirm_missing_unknown_or_duplicate_field(env):
    client, _, _ids = env
    headers = auth(client)
    doc = upload(client, headers)
    for fields in (
        [field("patient_name", "虚构甲", "confirmed")],
        [field("patient_name", "")],
        [field("patient_name", "虚构甲"), field("patient_name", "虚构甲")],
        [field("invented", "无")],
    ):
        assert review(client, headers, doc, fields).status_code == 422
    assert (
        review(client, headers, doc, [], "file", create_patient=True).status_code == 422
    )
    assert (
        review(
            client,
            headers,
            doc,
            [field("patient_name", "虚构甲")],
            "file",
            create_patient=True,
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "content,mime",
    [
        (b"\x89PNG\r\n\x1a\nmalformed", "image/png"),
        (b"%PDF-malformed", "application/pdf"),
        (png_bytes(), "image/jpeg"),
    ],
)
def test_invalid_original_is_not_accepted(env, content, mime):
    client, factory, _ = env
    response = client.post(
        "/clinical-documents",
        headers=auth(client),
        json={
            "document_name": "bad",
            "document_mime_type": mime,
            "document_base64": base64.b64encode(content).decode(),
        },
    )
    assert response.status_code == 422
    with factory() as db:
        assert db.scalar(select(ClinicalDocument)) is None


def test_ocr_missing_low_confidence_conflict_and_section_boundaries():
    def line(i, text, score=0.99):
        return {
            "id": i,
            "page": 1,
            "text": text,
            "confidence": score,
            "box": [0, 0, 1, 1],
        }

    result = clinical_ocr.extract_fields(
        [
            {
                "number": 1,
                "lines": [
                    line(0, "姓名：虚构甲"),
                    line(1, "姓名：虚构乙"),
                    line(2, "主诉：腹胀", 0.6),
                    line(3, "现病史：一月"),
                    line(4, "偶有反复"),
                    line(5, "既往史："),
                    line(6, "病理部位：胃窦"),
                    line(7, "病理诊断：慢性炎症；肠化未知"),
                ],
            }
        ]
    )
    fields = {f["key"]: f for f in result["fields"]}
    assert fields["patient_name"]["candidate_status"] == "conflict"
    assert fields["chief_complaint"]["candidate_status"] == "low_confidence"
    assert fields["present_illness"]["candidate_value"] == "一月\n偶有反复"
    assert fields["past_history"]["candidate_value"] is None
    assert fields["hp_result"]["candidate_value"] is None
    assert fields["intestinal_metaplasia"]["candidate_value"] is None
    assert result["document_type"] == "pathology"
    assert fields["pathology_diagnosis"]["evidence"][0]["page"] == 1


def test_late_extraction_cannot_overwrite_a_saved_review(env, monkeypatch):
    client, factory, _ids = env
    headers = auth(client)
    doc = upload(client, headers)

    def concurrent(*_):
        with factory() as db:
            record = db.get(ClinicalDocument, doc["id"])
            record.version += 1
            db.commit()
        return ocr_result()

    monkeypatch.setattr(clinical_ocr, "recognize", concurrent)
    response = client.post(
        f"/clinical-documents/{doc['id']}/extract",
        headers=headers,
        json={"version": doc["version"]},
    )
    assert response.status_code == 409
    assert (
        client.get(f"/clinical-documents/{doc['id']}", headers=headers).json()[
            "extraction_status"
        ]
        == "not_run"
    )


def test_patient_upload_import_reuses_original_and_requires_original_patient(
    env, monkeypatch, tmp_path
):
    client, factory, ids = env
    headers = auth(client)
    with factory() as db:
        notice = PatientNoticeVersion(
            notice_key="test",
            version="1",
            title="虚构须知",
            content="虚构正文",
            content_sha256="a" * 64,
            status="draft",
        )
        db.add(notice)
        db.flush()
        source = PatientDocument(
            patient_id=ids["patient_record"],
            submitted_by_user_id=ids["patient"],
            notice_version_id=notice.id,
            event_date=datetime(2026, 10, 1).date(),
            display_label="虚构原件",
            original_name="sample.png",
            mime_type="image/png",
            storage_name="sample.png",
            sha256=hashlib.sha256(png_bytes()).hexdigest(),
            size_bytes=len(png_bytes()),
            notice_content_sha256="a" * 64,
            consented_at=datetime.now(UTC),
        )
        db.add(source)
        db.commit()
        source_id = source.id
    root = tmp_path / "patient"
    root.mkdir()
    (root / "sample.png").write_bytes(png_bytes())
    payload = {"source_kind": "patient", "source_id": source_id}
    assert (
        client.post(
            "/clinical-documents/import",
            headers=auth(client, "other_doctor"),
            json=payload,
        ).status_code
        == 404
    )
    response = client.post("/clinical-documents/import", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    doc = response.json()
    assert doc["patient_id"] is None
    assert (
        client.post("/clinical-documents/import", headers=headers, json=payload).json()[
            "id"
        ]
        == doc["id"]
    )
    assert (
        client.get(f"/clinical-documents/{doc['id']}/file", headers=headers).content
        == png_bytes()
    )
    fields = [field("patient_name", "虚构甲"), field("chief_complaint", "腹胀")]
    assert (
        review(client, headers, doc, fields, "file", create_patient=True).status_code
        == 409
    )
    response = review(
        client, headers, doc, fields, "file", patient_id=ids["patient_record"]
    )
    assert response.status_code == 200, response.text
    with factory() as db:
        source = db.get(PatientDocument, source_id)
        assert source.review_status == "approved"
        assert source.sha256 == doc["sha256"]


def test_intake_import_stays_unbound_until_corrected_name_is_filed(env, tmp_path):
    client, factory, ids = env
    headers = auth(client)
    with factory() as db:
        link = PatientIntakeLink(
            token_digest="d" * 64,
            created_by_doctor_id=ids["doctor"],
            expires_at=datetime(2030, 1, 1),
        )
        notice = PatientNoticeVersion(
            notice_key="test",
            version="1",
            title="虚构须知",
            content="正文",
            content_sha256="a" * 64,
            status="draft",
        )
        db.add_all([link, notice])
        db.flush()
        submission = PatientIntakeSubmission(
            intake_link_id=link.id,
            submission_digest="b" * 64,
            display_name="待核对的申请姓名",
            sex="女",
            date_of_birth=datetime(1970, 1, 1).date(),
            operator_relationship="本人",
            notice_version="1",
            document_name="intake.png",
            document_mime_type="image/png",
            document_storage_name="intake.png",
            document_sha256=hashlib.sha256(png_bytes()).hexdigest(),
        )
        db.add(submission)
        db.flush()
        db.add(
            PatientDemoConsent(
                notice_version_id=notice.id,
                intake_submission_id=submission.id,
                consented_at=datetime.now(UTC),
                context="test",
                notice_content_sha256="a" * 64,
            )
        )
        db.commit()
        source_id = submission.id
    root = tmp_path / "intake"
    root.mkdir()
    (root / "intake.png").write_bytes(png_bytes())
    payload = {"source_kind": "intake", "source_id": source_id}
    assert (
        client.post(
            "/clinical-documents/import",
            headers=auth(client, "other_doctor"),
            json=payload,
        ).status_code
        == 404
    )
    response = client.post("/clinical-documents/import", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    doc = response.json()
    assert doc["patient_id"] is None
    response = review(
        client,
        headers,
        doc,
        [
            field("patient_name", "人工核对后的虚构姓名"),
            field("chief_complaint", "腹胀"),
        ],
        "file",
        create_patient=True,
    )
    assert response.status_code == 200, response.text
    patient_id = response.json()["patient_id"]
    assert (
        client.get(f"/clinical-documents/{doc['id']}/file", headers=headers).content
        == png_bytes()
    )
    with factory() as db:
        patient = db.get(Patient, patient_id)
        assert (
            patient.display_name == "人工核对后的虚构姓名"
            and patient.patient_user_id is None
        )
        submission = db.get(PatientIntakeSubmission, source_id)
        assert (
            submission.status == "approved"
            and submission.created_patient_id == patient_id
        )
        assert db.scalar(select(PatientDemoConsent)).patient_id == patient_id
