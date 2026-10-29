"""Versioned chronic gastritis archive. No diagnosis or treatment inference."""
import json
import math
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from patient_follow_up_system.auth import get_current_user, require_roles
from patient_follow_up_system.database import get_db
from patient_follow_up_system.gastritis_models import GastritisRecord
from patient_follow_up_system.models import Patient, User, UserRole
from patient_follow_up_system.permissions import require_patient
from patient_follow_up_system.portal import get_portal_patient
from patient_follow_up_system.portal_models import PortalProfile

router = APIRouter()
SCHEMA_VERSION = "gastritis-20261029-v2"
TRISTATE = ["未知/待确认", "有", "无"]
SYMPTOMS = dict(zip(
    ["weight_loss", "fullness", "stomach_pain", "rib_discomfort", "cold_stomach", "worse_after_meals", "better_after_meals", "worse_with_emotion", "nausea", "vomiting", "acid_reflux", "heartburn", "belching", "bitter_mouth", "dry_mouth", "sticky_mouth", "bad_breath", "tasteless_mouth", "dry_stool", "loose_stool", "sticky_stool", "weak_defecation", "poor_appetite", "sighing", "chest_tightness", "low_mood", "fatigue", "cold_extremities", "throat_discomfort"],
    ["近期体重下降", "胃部满闷、胀闷", "胃部疼痛", "胁肋不适/疼痛", "胃部怕冷喜暖", "饭后加重", "饭后缓解", "情绪不佳时加重", "恶心", "呕吐", "反酸", "烧心", "打嗝、嗳气", "口苦", "口干", "口黏", "口臭", "口中无味", "便干", "大便不成形", "便黏", "排便无力", "吃饭不好", "长出气、叹气", "胸闷", "心情烦躁、低落", "乏力疲惫", "手脚冰凉", "咽部不适"], strict=True))
HISTORY = ["胃食管返流", "肠易激综合征", "胆囊结石", "胆囊息肉", "胆囊腺肌症", "胆囊切除术后", "保胆取石术后", "胃息肉", "结肠息肉", "脂肪肝", "慢性乙型肝炎", "原发性胆汁性胆管炎", "慢性胰腺炎", "直肠息肉", "甲亢", "甲减"]


def today():
    return (datetime.now(UTC) + timedelta(hours=8)).date()


def field(key, label, kind="text", options=None, **kwargs):
    return {"key": key, "label": label, "kind": kind, **({"options": options} if options else {}), **kwargs}


SECTIONS = [
    {"key": "basic", "label": "基本信息", "fields": [field("name", "姓名"), field("sex", "性别", "select", ["未说明", "男", "女"]), field("date_of_birth", "出生日期", "date"), field("phone", "手机号"), field("height_cm", "身高（cm）", "number", min=30, max=250), field("weight_kg", "体重（kg）", "number", min=1, max=400), field("ethnicity", "民族"), field("occupation", "职业"), field("education", "文化程度", "select", ["未填写", "小学及以下", "初中", "高中/中专", "大专", "本科", "研究生及以上"]), field("region", "居住地区")]},
    {"key": "lifestyle", "label": "生活方式", "fields": [field("smoking", "吸烟", "select", ["未知/待确认", "从不", "既往吸烟", "当前吸烟"]), field("cigarettes_per_day", "每日吸烟支数", "number", min=0, max=200), field("smoking_years", "吸烟年数", "number", min=0, max=120), field("quit_smoking_on", "戒烟时间", "date"), field("drinking", "饮酒", "select", ["未知/待确认", "从不饮酒", "近期戒酒", "偶尔", "经常"]), field("drinking_frequency", "饮酒频率", "select", ["未知/待确认", "几乎每天", "每周3-5次", "每周1-2次", "每月1-2次", "更少"]), field("alcohol_amount", "每次饮酒量（含单位）"), field("drinking_years", "饮酒年数", "number", min=0, max=120), field("quit_drinking_on", "戒酒时间", "date"), field("diet", "饮食习惯", "checks", ["辛辣", "高盐", "腌制", "烧烤烟熏", "清淡", "新鲜蔬菜水果", "素食", "夜宵", "不吃早餐", "咖啡", "茶"]), field("sleep", "睡眠质量", "select", ["未知/待确认", "质量佳", "一般", "差"])]},
    {"key": "past_history", "label": "既往病史", "fields": [field("overall", "既往病史情况", "select", ["未知/待确认", "有", "明确无"]), field("conditions", "既往疾病", "checks", HISTORY), field("detail", "其他病史、诊断或建议", "textarea"), field("source", "病史来源（可填资料编号）")]},
    {"key": "hp", "label": "幽门螺杆菌感染病史", "fields": [field("infection", "既往感染", "select", TRISTATE), field("count", "既往感染次数", "select", ["未知/待确认", "1次", "2次", "2次以上"]), field("last_infection", "最近一次感染时间", "select", ["未知/待确认", "1年前", "1年内"]), field("treated", "是否治疗", "select", ["未知/待确认", "是", "否"]), field("retest", "杀菌治疗后复查", "select", ["未知/待确认", "已转阴", "复查未转阴", "未复查"]), field("source", "检验、检查来源（可填资料编号）")]},
]


class Symptom(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presence: Literal["unknown", "yes", "no"] = "unknown"
    grade: int | None = Field(default=None, ge=1, le=3)
    detail: str = Field(default="", max_length=500)
    weight_loss_period: Literal["更长时间", "1年", "半年", "3个月内", "1个月内", "更短时间"] | None = None
    weight_loss_kg: float | None = Field(default=None, gt=0, le=200, allow_inf_nan=False)
    pain_type: Literal["隐隐作痛", "针扎疼痛", "绞痛", "灼痛", "说不清"] | None = None
    appetite_type: Literal["没胃口、一吃就饱", "饥饿、但不敢多吃饭"] | None = None


class ClinicalEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(default="", max_length=500)
    source: str = Field(min_length=1, max_length=300)

    @field_validator("date")
    @classmethod
    def not_future(cls, value):
        if value > today():
            raise ValueError("临床记录日期不能晚于今天")
        return value

    @field_validator("name", "source")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("名称和来源不能为空")
        return value.strip()


class RecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recorded_on: date
    payload: dict
    status: Literal["draft", "confirmed"] = "draft"

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 60000:
            raise ValueError("档案内容过长")
        allowed = {s["key"] for s in SECTIONS} | {"symptoms", "other_symptoms", "diagnoses", "medications", "lab_results"}
        if set(value) - allowed:
            raise ValueError("档案包含未知分类")
        result = {}
        for section in SECTIONS:
            data = value.get(section["key"], {})
            if not isinstance(data, dict) or set(data) - {f["key"] for f in section["fields"]}:
                raise ValueError("档案字段不正确")
            for spec in section["fields"]:
                item = data.get(spec["key"])
                if item is None or item == "":
                    continue
                kind = spec["kind"]
                if kind == "number":
                    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or not spec["min"] <= item <= spec["max"]:
                        raise ValueError(f'{spec["label"]}数值超出范围')
                elif kind == "checks":
                    if not isinstance(item, list) or any(x not in spec["options"] for x in item) or len(set(item)) != len(item):
                        raise ValueError("多选内容不正确")
                elif not isinstance(item, str) or len(item) > 3000:
                    raise ValueError("文本内容不正确")
                elif kind == "select" and item not in spec["options"]:
                    raise ValueError("选项不正确")
                elif kind == "date" and date.fromisoformat(item) > today():
                    raise ValueError("病情日期不能晚于今天")
            result[section["key"]] = data
        symptoms = value.get("symptoms", {})
        if not isinstance(symptoms, dict) or set(symptoms) - set(SYMPTOMS):
            raise ValueError("症状项目不正确")
        result["symptoms"] = {}
        for key, raw in symptoms.items():
            symptom = Symptom.model_validate(raw)
            extras = symptom.model_dump(exclude={"presence", "grade", "detail"}, exclude_none=True)
            permitted = {"weight_loss": {"weight_loss_period", "weight_loss_kg"}, "stomach_pain": {"pain_type"}, "poor_appetite": {"appetite_type"}}.get(key, set())
            if set(extras) - permitted:
                raise ValueError("症状补充选项不匹配")
            if symptom.presence != "yes" and (symptom.grade is not None or symptom.detail or extras):
                raise ValueError("无或未知症状不能包含分级或补充内容")
            result["symptoms"][key] = symptom.model_dump(exclude_none=True)
        other = value.get("other_symptoms", "")
        if not isinstance(other, str) or len(other) > 3000:
            raise ValueError("其他症状内容过长")
        result["other_symptoms"] = other
        for category in ("diagnoses", "medications", "lab_results"):
            entries = value.get(category, [])
            if not isinstance(entries, list) or len(entries) > 100:
                raise ValueError("临床记录过多")
            result[category] = [ClinicalEntry.model_validate(e).model_dump(mode="json") for e in entries]
        if result["hp"].get("infection") == "无" and any(result["hp"].get(k) not in (None, "", "未知/待确认") for k in ("count", "last_infection", "treated", "retest")):
            raise ValueError("无感染史时不应填写感染追问")
        if result["past_history"].get("overall") == "明确无" and result["past_history"].get("conditions"):
            raise ValueError("明确无病史与已选疾病矛盾")
        return result


@router.get("/gastritis/schema")
def schema():
    return {"version": SCHEMA_VERSION, "sections": SECTIONS, "symptoms": SYMPTOMS, "history_conditions": HISTORY, "grades": {"1": "偶有、程度较轻", "2": "时有、中等程度", "3": "经常、严重"}, "source": "杜宏波主任信息随访网站设计构思"}


def record_response(row):
    return {key: getattr(row, key) for key in ("id", "patient_id", "version", "recorded_on", "payload", "source", "status", "created_by_id", "confirmed_by_id", "confirmed_at", "created_at")}


def records(db, patient, response):
    response.headers["Cache-Control"] = "no-store"
    rows = db.scalars(select(GastritisRecord).where(GastritisRecord.patient_id == patient.id).order_by(GastritisRecord.version.desc())).all()
    basic = {"name": patient.display_name}
    profile = db.get(PortalProfile, patient.id)
    if profile:
        basic.update({"sex": profile.sex, "date_of_birth": profile.date_of_birth.isoformat(), "phone": profile.phone or ""})
        allowed = {f["key"] for f in SECTIONS[0]["fields"]} - {"name", "sex", "date_of_birth", "phone"}
        basic.update({k: v for k, v in (profile.extra or {}).items() if k in allowed})
    return {"records": [record_response(row) for row in rows], "initial_payload": {"basic": basic}}


def append_record(db, patient, request, user=None):
    if request.recorded_on > today():
        raise HTTPException(422, "记录日期不能晚于今天")
    # Acquire SQLite's write lock before selecting the next per-patient version.
    db.execute(update(Patient).where(Patient.id == patient.id).values(id=Patient.id))
    confirmed = bool(user and request.status == "confirmed")
    version = (db.scalar(select(func.max(GastritisRecord.version)).where(GastritisRecord.patient_id == patient.id)) or 0) + 1
    row = GastritisRecord(patient_id=patient.id, version=version, recorded_on=request.recorded_on, payload=request.payload, source="staff" if user else "patient", status="confirmed" if confirmed else "draft", created_by_id=user.id if user else None, confirmed_by_id=user.id if confirmed else None, confirmed_at=datetime.now(UTC) if confirmed else None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return record_response(row)


@router.get("/patients/{patient_id}/gastritis-records")
def staff_records(patient_id: int, response: Response, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles(UserRole.DOCTOR, UserRole.STUDENT))]):
    return records(db, require_patient(db, patient_id, user), response)


@router.post("/patients/{patient_id}/gastritis-records", status_code=201)
def staff_save(patient_id: int, request: RecordRequest, http_request: Request, response: Response, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles(UserRole.DOCTOR, UserRole.STUDENT))]):
    response.headers["Cache-Control"] = "no-store"
    patient = require_patient(db, patient_id, user, "review" if request.status == "confirmed" else "edit")
    db.execute(update(Patient).where(Patient.id == patient_id).values(id=Patient.id))
    db.expire_all()
    user = get_current_user(http_request.headers.get("authorization", "").removeprefix("Bearer "), db)
    patient = require_patient(db, patient_id, user, "review" if request.status == "confirmed" else "edit")
    return append_record(db, patient, request, user)


@router.get("/portal/gastritis-records")
def patient_records(response: Response, patient: Annotated[Patient, Depends(get_portal_patient)], db: Annotated[Session, Depends(get_db)]):
    return records(db, patient, response)


@router.post("/portal/gastritis-records", status_code=201)
def patient_save(request: RecordRequest, http_request: Request, response: Response, patient: Annotated[Patient, Depends(get_portal_patient)], db: Annotated[Session, Depends(get_db)]):
    response.headers["Cache-Control"] = "no-store"
    if request.status == "confirmed":
        raise HTTPException(403, "患者填写保存为自述，不能确认临床档案")
    db.execute(update(Patient).where(Patient.id == patient.id).values(id=Patient.id))
    db.expire_all()
    patient = get_portal_patient(http_request, db)
    return append_record(db, patient, request)
