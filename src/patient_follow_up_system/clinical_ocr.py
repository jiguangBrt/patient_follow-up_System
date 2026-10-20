"""Local OCR and conservative, label-based extraction. Never infer diagnoses."""

import re
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

OCR_VERSION = "rapidocr-onnxruntime-1.4.4/ppocr-v4/labels-v1"
MAX_PAGES = 10
MAX_PIXELS = 24_000_000
OCR_LOCK = threading.Lock()
RENDER_LOCK = threading.Lock()

# Stable keys are shared by the review screen and the structured patient record.
FIELD_LABELS = {
    "patient_name": "姓名",
    "sex": "性别",
    "age": "年龄",
    "visit_time": "就诊时间",
    "hospital": "医疗机构",
    "department": "就诊科室",
    "outpatient_number": "门诊号",
    "report_date": "报告日期",
    "chief_complaint": "主诉",
    "present_illness": "现病史",
    "past_history": "既往史",
    "personal_history": "个人史",
    "allergy_history": "过敏史",
    "family_history": "家族史",
    "tcm_examination": "中医四诊",
    "vital_signs": "生命体征/体格检查",
    "western_diagnosis": "西医诊断",
    "tcm_diagnosis": "中医诊断",
    "medications": "药品处方",
    "herbal_prescription": "中药配方",
    "advice": "建议/医嘱",
    "endoscopy_findings": "胃镜所见",
    "endoscopy_diagnosis": "胃镜诊断",
    "pathology_site": "病理部位",
    "pathology_diagnosis": "病理诊断",
    "hp_result": "幽门螺杆菌",
    "intestinal_metaplasia": "肠上皮化生",
}
ALIASES = {
    "patient_name": ["姓名"],
    "sex": ["性别"],
    "age": ["年龄"],
    "visit_time": ["就诊时间", "就诊日期"],
    "hospital": ["医疗机构", "医院名称"],
    "department": ["就诊科室", "科室"],
    "outpatient_number": ["门诊号", "就诊号", "病历号"],
    "report_date": ["报告日期", "报告时间", "检查日期", "检查时间"],
    "chief_complaint": ["主诉"],
    "present_illness": ["现病史"],
    "past_history": ["既往史", "既病史"],
    "personal_history": ["个人史"],
    "allergy_history": ["过敏史"],
    "family_history": ["家族史"],
    "tcm_examination": ["中医四诊", "四诊"],
    "vital_signs": ["生命体征", "体格检查"],
    "western_diagnosis": ["西医诊断", "临床诊断"],
    "tcm_diagnosis": ["中医诊断"],
    "medications": ["药品处方", "西药处方", "用药记录"],
    "herbal_prescription": ["中药配方", "中药处方"],
    "advice": ["建议", "医嘱"],
    "endoscopy_findings": ["胃镜所见", "内镜所见", "检查所见"],
    "endoscopy_diagnosis": ["胃镜诊断", "内镜诊断", "镜下诊断"],
    "pathology_site": ["病理部位", "取材部位", "送检部位"],
    "pathology_diagnosis": ["病理诊断", "病理结果"],
    "hp_result": ["幽门螺杆菌", "Hp", "HP", "H.pylori"],
    "intestinal_metaplasia": ["肠上皮化生", "肠化"],
}
ALIAS_KEYS = {alias: key for key, aliases in ALIASES.items() for alias in aliases}
LABEL_PATTERN = re.compile(
    "("
    + "|".join(re.escape(a) for a in sorted(ALIAS_KEYS, key=len, reverse=True))
    + r")\s*[:：]"
)
HEADER_KEYS = {
    "patient_name",
    "sex",
    "age",
    "visit_time",
    "hospital",
    "department",
    "outpatient_number",
    "report_date",
}


def render_pages(path: Path, mime_type: str) -> list[Image.Image]:
    # PDFium is not thread-safe even for different documents.
    with RENDER_LOCK:
        return _render_pages(path, mime_type)


def _render_pages(path: Path, mime_type: str) -> list[Image.Image]:
    """Bound decoding, pixel count and PDF pages before OCR or preview."""
    if mime_type == "application/pdf":
        import pypdfium2 as pdfium

        images = []
        with pdfium.PdfDocument(path) as pdf:
            if not 1 <= len(pdf) <= MAX_PAGES:
                raise ValueError(f"PDF 需为 1–{MAX_PAGES} 页，更多页请拆分上传。")
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise ValueError("PDF 页面尺寸无效。")
                    scale = min(2, 2000 / max(width, height))
                    bitmap = page.render(scale=scale)
                    try:
                        images.append(bitmap.to_pil().convert("RGB"))
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        return images
    with Image.open(path) as source:
        if source.format not in ("JPEG", "PNG") or (mime_type == "image/jpeg") != (
            source.format == "JPEG"
        ):
            raise ValueError("文件内容与类型不符。")
        if source.width * source.height > MAX_PIXELS:
            raise ValueError("图片像素过大，请缩小至 2400 万像素以内。")
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((2000, 2000))
        return [image]


@lru_cache(maxsize=1)
def engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR(
        intra_op_num_threads=2,
        inter_op_num_threads=1,
        text_score=0.35,
        det_limit_side_len=1200,
        det_box_thresh=0.35,
    )


def _lines(result, width: int, height: int, page: int) -> list[dict]:
    tokens = []
    slopes = [
        (box[1][1] - box[0][1]) / (box[1][0] - box[0][0])
        for box, _, _ in result or []
        if box[1][0] - box[0][0] > width * 0.25
    ]
    slope = float(np.median(slopes)) if slopes else 0
    for box, text, score in result or []:
        if not text.strip():
            continue
        xs, ys = zip(*box)
        baseline = (box[0][1] + box[3][1]) / 2 - slope * box[0][0]
        tokens.append(
            {
                "text": text,
                "confidence": float(score),
                "box": [min(xs), min(ys), max(xs), max(ys)],
                "baseline": baseline,
                "height": max(1, box[3][1] - box[0][1]),
            }
        )
    # Text detector may split header cells and prescription columns. Group by baseline.
    rows = []
    for token in sorted(tokens, key=lambda t: t["baseline"]):
        box = token["box"]
        center, line_height = token["baseline"], token["height"]
        if (
            rows
            and abs(center - rows[-1][0])
            < min(line_height, min(t["height"] for t in rows[-1][1])) * 0.45
        ):
            rows[-1][1].append(token)
        else:
            rows.append((center, [token]))
    output = []
    for index, (_, row) in enumerate(rows):
        row.sort(key=lambda t: t["box"][0])
        output.append(
            {
                "id": index,
                "page": page,
                "text": "  ".join(t["text"] for t in row),
                "confidence": min(t["confidence"] for t in row),
                "box": [
                    min(t["box"][0] for t in row) / width,
                    min(t["box"][1] for t in row) / height,
                    max(t["box"][2] for t in row) / width,
                    max(t["box"][3] for t in row) / height,
                ],
            }
        )
    return output


def recognize(path: Path, mime_type: str) -> dict:
    pages = []
    # ONNX engine and PDFium are serialized; SQLite transactions are not held while OCR runs.
    with OCR_LOCK:
        images = render_pages(path, mime_type)
        for number, image in enumerate(images, start=1):
            best, best_score = None, -1
            for rotation in (0, 90, 270, 180):
                rotated = image.rotate(rotation, expand=True)
                # RapidOCR accepts OpenCV BGR arrays.
                result, _ = engine()(np.asarray(rotated)[:, :, ::-1].copy())
                lines = _lines(result, rotated.width, rotated.height, number)
                text = "\n".join(line["text"] for line in lines)
                anchors = len(LABEL_PATTERN.findall(text))
                horizontal = sum(
                    1
                    for box, _, _ in result or []
                    if abs(box[1][0] - box[0][0]) > abs(box[3][1] - box[0][1])
                ) / max(1, len(result or []))
                score = (
                    anchors * 30 + sum(len(l["text"]) * l["confidence"] for l in lines)
                ) * horizontal
                if score > best_score:
                    best_score = score
                    best = {
                        "number": number,
                        "rotation": rotation,
                        "width": rotated.width,
                        "height": rotated.height,
                        "lines": lines,
                    }
                if anchors >= 5 and horizontal > 0.85:
                    break
            pages.append(best)
    return extract_fields(pages)


def extract_fields(pages: list[dict]) -> dict:
    collected = {key: [] for key in FIELD_LABELS}
    for page in pages:
        current = None
        for line in page["lines"]:
            text = line["text"]
            if re.search(r"以下空白|第\s*\d+\s*页|门诊医生|签名|签字", text):
                current = None
                continue
            matches = list(LABEL_PATTERN.finditer(text))
            if not matches and text.strip() in ALIAS_KEYS:
                key = ALIAS_KEYS[text.strip()]
                collected[key].append(
                    {"value": "", "evidence": [line], "explicit": True}
                )
                current = key if key not in HEADER_KEYS else None
                continue
            if matches:
                for i, match in enumerate(matches):
                    key = ALIAS_KEYS[match.group(1)]
                    value = text[
                        match.end() : matches[i + 1].start()
                        if i + 1 < len(matches)
                        else len(text)
                    ].strip()
                    collected[key].append(
                        {"value": value, "evidence": [line], "explicit": True}
                    )
                    current = key if key not in HEADER_KEYS else None
            elif current and not re.search(r"第\s*\d+\s*页|门诊医生|签名|签字", text):
                collected[current][-1]["value"] += "\n" + text
                collected[current][-1]["evidence"].append(line)
            elif not matches and "医院" in text and not collected["hospital"]:
                collected["hospital"].append(
                    {"value": text, "evidence": [line], "explicit": True}
                )
    fields = []
    for key, entries in collected.items():
        nonempty = [
            e
            for e in entries
            if e["value"].strip()
            and e["value"].strip() not in ("(以下空白)", "（以下空白）")
        ]
        values = list(dict.fromkeys(e["value"].strip() for e in nonempty))
        evidence = [line for e in entries for line in e["evidence"]]
        confidence = min((l["confidence"] for l in evidence), default=None)
        conflict = key in HEADER_KEYS and len(values) > 1
        fields.append(
            {
                "key": key,
                "candidate_value": "\n".join(values) or None,
                "confidence": confidence,
                "evidence": evidence,
                "candidate_status": "conflict"
                if conflict
                else "missing"
                if not values
                else "low_confidence"
                if confidence < 0.85
                else "recognized",
            }
        )
    text = "\n".join(line["text"] for page in pages for line in page["lines"])
    title = "\n".join(line["text"] for page in pages[:1] for line in page["lines"][:2])
    # A history mentioning a pathology/endoscopy exam does not change the document type.
    if "门诊病历" in title:
        kind = "outpatient"
    elif "病理" in title:
        kind = "pathology"
    elif re.search("胃镜|内镜|肠镜", title):
        kind = "endoscopy"
    elif collected["pathology_diagnosis"]:
        kind = "pathology"
    elif collected["endoscopy_diagnosis"]:
        kind = "endoscopy"
    else:
        kind = "outpatient" if re.search("主诉|现病史", text) else "unknown"
    has_text = any(page["lines"] for page in pages)
    return {
        "pages": pages,
        "fields": fields,
        "document_type": kind,
        "extraction_status": "ready"
        if has_text and any(f["candidate_value"] for f in fields)
        else "manual",
        "extraction_version": OCR_VERSION,
    }
