"""Version history, explicit unknown, clinical confirmation and access boundaries."""
from datetime import date, timedelta

import pytest
from test_accounts_clinical import auth
from test_accounts_clinical import env as account_env  # noqa: F401

from patient_follow_up_system.gastritis import RecordRequest, SCHEMA_VERSION


@pytest.fixture
def archive(request):
    client, factory, ids = request.getfixturevalue("account_env")
    return client, factory, ids, auth(client)


def payload(**changes):
    return {"recorded_on": date.today().isoformat(), "payload": {"hp": {"infection": "未知/待确认"}, "symptoms": {"nausea": {"presence": "unknown"}, "stomach_pain": {"presence": "yes", "grade": 2, "pain_type": "灼痛"}}, **changes}}


def test_records_keep_versions_and_unknown_distinct_from_no(archive):
    client, _, ids, doctor = archive
    path = f'/patients/{ids["patient_record"]}/gastritis-records'
    first = client.post(path, headers=doctor, json=payload())
    assert first.status_code == 201, first.text
    assert first.headers["cache-control"] == "no-store"
    second_payload = payload(hp={"infection": "无"})
    second = client.post(path, headers=doctor, json=second_payload)
    assert second.status_code == 201
    history = client.get(path, headers=doctor)
    assert history.headers["cache-control"] == "no-store"
    records = history.json()["records"]
    assert [r["version"] for r in records] == [2, 1]
    assert records[0]["payload"]["hp"]["infection"] == "无"
    assert records[1]["payload"]["hp"]["infection"] == "未知/待确认"
    assert records[1]["payload"]["symptoms"]["nausea"]["presence"] == "unknown"
    assert client.get(path, headers=auth(client, "other_doctor")).status_code == 404
    assert client.post(path, headers=auth(client, "other_doctor"), json=payload()).status_code == 404
    assert client.get(path, headers=auth(client, "patient")).status_code == 403


def test_doctor_can_confirm_record_without_options_gate_and_retired_endpoint_is_gone(archive):
    client, _, ids, doctor = archive
    path = f'/patients/{ids["patient_record"]}/gastritis-records'
    data = payload() | {"status": "confirmed"}
    confirmation = {"schema_version": SCHEMA_VERSION, "note": "虚构测试：核对量表29症状、三级含义及周岁/BMI计算口径"}
    assert client.post("/doctor/gastritis-options/confirm", headers=auth(client, "patient"), json=confirmation).status_code == 404
    assert client.post("/doctor/gastritis-options/confirm", headers=doctor, json=confirmation).status_code == 404
    result = client.post(path, headers=doctor, json=data)
    assert result.status_code == 201, result.text
    record = result.json()
    assert record["status"] == "confirmed"
    assert record["confirmed_by_id"] == ids["doctor"]
    assert record["confirmed_at"] and record["created_by_id"] == ids["doctor"]
    assert "option_confirmation" not in client.get(path, headers=doctor).json()


@pytest.mark.parametrize("changes", [
    {"symptoms": {"nausea": {"presence": "no", "grade": 2}}},
    {"symptoms": {"nausea": {"presence": "yes", "pain_type": "绞痛"}}},
    {"symptoms": {"weight_loss": {"presence": "yes", "weight_loss_kg": -3}}},
    {"symptoms": {"weight_loss": {"presence": "unknown", "weight_loss_period": "1年"}}},
    {"past_history": {"overall": "明确无", "conditions": ["胃息肉"]}},
    {"hp": {"infection": "无", "count": "1次"}},
    {"lifestyle": {"smoking": "编造选项"}},
    {"basic": {"height_cm": float("inf")}},
    {"diagnoses": [{"date": (date.today() + timedelta(days=1)).isoformat(), "name": "测试", "source": "测试资料"}]},
    {"lab_results": [{"date": date.today().isoformat(), "name": "虚构检验", "source": ""}]},
])
def test_rejects_contradictions_and_invalid_clinical_entries(changes):
    with pytest.raises(ValueError):
        RecordRequest.model_validate(payload(**changes))


def test_active_categories_and_dated_clinical_sources_round_trip(archive):
    client, _, ids, doctor = archive
    clinical = {"date": date.today().isoformat(), "name": "虚构条目", "value": "仅用于测试", "source": "虚构报告1"}
    data = payload(basic={"height_cm": 170, "weight_kg": 60}, lifestyle={"smoking": "从不", "diet": ["清淡"]}, past_history={"overall": "有", "conditions": ["脂肪肝"], "source": "虚构病历"}, hp={"infection": "有", "count": "1次", "treated": "是", "retest": "已转阴"}, diagnoses=[clinical], medications=[clinical], lab_results=[clinical])
    path = f'/patients/{ids["patient_record"]}/gastritis-records'
    result = client.post(path, headers=doctor, json=data)
    assert result.status_code == 201, result.text
    saved = client.get(path, headers=doctor).json()["records"][0]["payload"]
    for key, value in data["payload"].items():
        if key != "symptoms":
            assert saved[key] == value
    schema = client.get("/gastritis/schema").json()
    assert len(schema["symptoms"]) == 29
    assert "gastroscopy" not in {section["key"] for section in schema["sections"]}
    assert "gastroscopy" not in saved
    assert client.post(path, headers=doctor, json=payload(gastroscopy={})).status_code == 422


def test_student_view_edit_review_are_separate(archive):
    client, _, ids, doctor = archive
    from test_accounts_clinical import PASSWORD
    result = client.post("/doctor/students", headers=doctor, json={"username": "gastritis_student", "display_name": "虚构学生", "password": PASSWORD})
    assert result.status_code == 201
    student = auth(client, "gastritis_student")
    path = f'/patients/{ids["patient_record"]}/gastritis-records'
    permission = {"student_id": result.json()["id"], "note": "虚构测试", "starts_at": None, "ends_at": None, "is_permanent": True, "can_view": True, "can_edit": False, "can_review": False}
    assert client.post("/doctor/student-permissions", headers=doctor, json=permission).status_code in (200, 201)
    assert client.get(path, headers=student).status_code == 200
    assert client.post(path, headers=student, json=payload()).status_code == 404
    assert client.post(path, headers=student, json=payload() | {"status": "confirmed"}).status_code == 404
    assert client.post("/doctor/student-permissions", headers=doctor, json=permission | {"can_edit": True}).status_code in (200, 201)
    assert client.post(path, headers=student, json=payload()).status_code == 201
    assert client.post(path, headers=student, json=payload() | {"status": "confirmed"}).status_code == 404
    assert client.post("/doctor/student-permissions", headers=doctor, json=permission | {"can_review": True}).status_code in (200, 201)
    confirmed = client.post(path, headers=student, json=payload() | {"status": "confirmed"})
    assert confirmed.status_code == 201, confirmed.text
    assert client.post("/doctor/gastritis-options/confirm", headers=student, json={"schema_version": SCHEMA_VERSION, "note": "不应允许"}).status_code == 404


def test_initial_profile_prefills_only_allowed_fields_and_never_overwrites_versions(archive):
    from patient_follow_up_system.portal_models import PortalProfile
    from patient_follow_up_system.models import Patient
    client, factory, ids, doctor = archive
    patient_id = ids["patient_record"]
    with factory() as db:
        db.add(PortalProfile(patient_id=patient_id, sex="女", date_of_birth=date(1980, 1, 2), phone="13800000000", operator_relationship="本人", extra={"height_cm": 165, "ethnicity": "汉族", "name": "不应覆盖真实姓名", "sex": "男", "unexpected": "不应进入档案"}))
        db.commit()
        expected_name = db.get(Patient, patient_id).display_name
    path = f"/patients/{patient_id}/gastritis-records"
    data = client.get(path, headers=doctor).json()
    assert data["records"] == []
    assert data["initial_payload"]["basic"] == {"name": expected_name, "sex": "女", "date_of_birth": "1980-01-02", "phone": "13800000000", "height_cm": 165, "ethnicity": "汉族"}
    saved = payload(basic={"name": "历史填写姓名", "height_cm": 170})
    assert client.post(path, headers=doctor, json=saved).status_code == 201
    data = client.get(path, headers=doctor).json()
    assert data["records"][0]["payload"]["basic"] == saved["payload"]["basic"]
    assert data["initial_payload"]["basic"]["height_cm"] == 165
