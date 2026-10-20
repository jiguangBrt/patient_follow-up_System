"""Start an isolated, repeatable local acceptance environment for issues #8/#10."""

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = ROOT / ".local" / "issue_8_10_review"
DEMO_PASSWORD = "ReviewLocal2026!"


def create_samples():
    from PIL import Image, ImageDraw, ImageFont

    fonts = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    font_path = next((p for p in fonts if p.is_file()), None)
    if not font_path:
        print("未找到中文字体，未生成中文测试图片。请使用自己的虚构样例。")
        return
    font = ImageFont.truetype(str(font_path), 34)
    samples = {
        "fictional-outpatient.png": [
            "虚构测试医院 门诊病历（仅供测试）",
            "就诊时间：2026-10-20 09:30",
            "姓名：测试甲 性别：女 年龄：53岁",
            "就诊科室：测试门诊 门诊号：TEST0001",
            "主诉：间断腹胀一月",
            "现病史：饭后腹胀，偶有反复",
            "既往史：无",
            "过敏史：未提供",
            "中医四诊：测试描述",
            "生命体征：测试数值待人工核对",
            "西医诊断：慢性胃炎？",
            "中医诊断：测试诊断",
            "药品处方：虚构药物甲，请人工核对",
            "中药配方：虚构处方乙，请人工核对",
            "建议：按时复诊",
        ],
        "fictional-endoscopy.png": [
            "虚构测试医院 胃镜报告（仅供测试）",
            "姓名：测试乙 性别：男 年龄：60岁",
            "检查日期：2026-10-20",
            "胃镜所见：胃窦黏膜充血",
            "胃镜诊断：慢性胃炎",
            "取材部位：胃窦",
        ],
        "fictional-pathology.pdf": [
            "虚构测试医院 病理报告（仅供测试）",
            "姓名：测试丙 性别：女 年龄：48岁",
            "报告日期：2026-10-20",
            "病理部位：胃窦",
            "病理诊断：慢性炎症",
            "肠上皮化生：未见",
            "幽门螺杆菌：阴性",
        ],
    }
    for name, lines in samples.items():
        image = Image.new("RGB", (1500, 1400), "white")
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((60, 40 + index * 75), line, font=font, fill="black")
        image.save(REVIEW_ROOT / name)
        if name == "fictional-outpatient.png":
            image.rotate(270, expand=True).save(
                REVIEW_ROOT / "fictional-outpatient-rotated.png"
            )
    Image.new("RGB", (600, 400), "white").save(REVIEW_ROOT / "blank-manual.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    key_path = REVIEW_ROOT / "auth-secret.txt"
    if not key_path.exists():
        key_path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    os.environ.update(
        {
            "DATABASE_URL": "sqlite:///" + (REVIEW_ROOT / "app.db").as_posix(),
            "AUTH_SECRET_KEY": key_path.read_text(encoding="utf-8"),
            "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
            "CLINICAL_UPLOAD_DIR": str(REVIEW_ROOT / "clinical_uploads"),
            "PATIENT_UPLOAD_DIR": str(REVIEW_ROOT / "patient_uploads"),
            "INTAKE_UPLOAD_DIR": str(REVIEW_ROOT / "intake_uploads"),
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    sys.path.insert(0, str(ROOT / "src"))
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True
    )
    from sqlalchemy import select

    from patient_follow_up_system.auth import hash_password
    from patient_follow_up_system.database import SessionLocal
    from patient_follow_up_system.models import User, UserRole

    with SessionLocal() as db:
        for name, label, role in [
            ("review_admin", "虚构验收管理员", UserRole.ADMIN),
            ("review_doctor", "虚构验收医生", UserRole.DOCTOR),
            ("review_other_doctor", "虚构其他医生", UserRole.DOCTOR),
            ("review_patient", "虚构验收患者账号", UserRole.PATIENT),
        ]:
            if db.scalar(select(User.id).where(User.username == name)) is None:
                db.add(
                    User(
                        username=name,
                        display_name=label,
                        role=role,
                        password_hash=hash_password(DEMO_PASSWORD),
                    )
                )
        db.commit()
    create_samples()
    print(f"独立验收数据和虚构样例：{REVIEW_ROOT}", flush=True)
    print(f"管理员：http://127.0.0.1:{args.port}/admin  账号 review_admin", flush=True)
    print(f"医生：http://127.0.0.1:{args.port}/doctor  账号 review_doctor", flush=True)
    print(f"虚构验收账号初始密码：{DEMO_PASSWORD}（只用于本机隔离测试）", flush=True)
    if not args.prepare_only:
        import uvicorn

        uvicorn.run(
            "patient_follow_up_system.main:app", host="127.0.0.1", port=args.port
        )


if __name__ == "__main__":
    main()
