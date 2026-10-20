"""Real CPU OCR on generated fictional records; no patient attachment is stored."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from patient_follow_up_system.clinical_ocr import recognize


def font_path():
    paths = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]
    path = next((p for p in paths if p.is_file()), None)
    if path is None:
        pytest.skip("Real Chinese OCR fixtures require a CJK font")
    return path


def image_for(lines):
    image = Image.new("RGB", (1500, 1000), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path()), 36)
    for i, text in enumerate(lines):
        draw.text((60, 40 + i * 65), text, font=font, fill="black")
    return image


@pytest.mark.parametrize(
    "kind,lines,expected",
    [
        (
            "outpatient",
            [
                "虚构测试医院 门诊病历",
                "就诊时间：2026-10-20 09:30",
                "姓名：测试甲 性别：女 年龄：53岁",
                "主诉：间断腹胀一月",
                "现病史：饭后腹胀，偶有反复",
                "既往史：无",
                "西医诊断：慢性胃炎",
                "药品处方：虚构药物甲",
                "建议：按时复诊",
            ],
            {
                "patient_name": "测试甲",
                "chief_complaint": "间断腹胀一月",
                "past_history": "无",
                "western_diagnosis": "慢性胃炎",
            },
        ),
        (
            "endoscopy",
            [
                "虚构测试医院 胃镜报告",
                "姓名：测试乙 性别：男 年龄：60岁",
                "检查日期：2026-10-20",
                "胃镜所见：胃窦黏膜充血",
                "胃镜诊断：慢性胃炎",
                "取材部位：胃窦",
            ],
            {
                "patient_name": "测试乙",
                "endoscopy_diagnosis": "慢性胃炎",
                "pathology_site": "胃窦",
            },
        ),
        (
            "pathology",
            [
                "虚构测试医院 病理报告",
                "姓名：测试丙 性别：女 年龄：48岁",
                "报告日期：2026-10-20",
                "病理部位：胃窦",
                "病理诊断：慢性炎症",
                "肠上皮化生：未见",
                "幽门螺杆菌：阴性",
            ],
            {
                "patient_name": "测试丙",
                "pathology_diagnosis": "慢性炎症",
                "intestinal_metaplasia": "未见",
                "hp_result": "阴性",
            },
        ),
    ],
)
def test_real_ocr_rotated_image_and_pdf(tmp_path, kind, lines, expected):
    image = image_for(lines)
    path = tmp_path / ("sample.pdf" if kind == "pathology" else "sample.png")
    if kind == "outpatient":
        image = image.rotate(270, expand=True)
    image.save(path)
    result = recognize(path, "application/pdf" if kind == "pathology" else "image/png")
    assert result["extraction_status"] == "ready"
    assert result["document_type"] == kind
    fields = {f["key"]: f for f in result["fields"]}
    for key, value in expected.items():
        assert fields[key]["candidate_value"] == value
        assert fields[key]["evidence"] and fields[key]["evidence"][0]["page"] == 1
    assert result["pages"][0]["rotation"] == (90 if kind == "outpatient" else 0)


def test_blank_original_never_generates_negative_findings(tmp_path):
    path = tmp_path / "blank.png"
    Image.new("RGB", (400, 300), "white").save(path)
    result = recognize(path, "image/png")
    assert result["extraction_status"] == "manual"
    assert all(f["candidate_value"] is None for f in result["fields"])
