import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError


class FollowUpIntent(BaseModel):
    category: str
    needs_human: bool
    reason: str


HIGH_RISK_MEDICATION_TERMS = ("减半", "停药", "加药", "减药", "剂量")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    load_dotenv()

    client = OpenAI(
        base_url=require_env("MODEL_BASE_URL"),
        api_key=require_env("MODEL_API_KEY"),
        timeout=60.0,
    )

    question = "患者问：我能不能把医生开的药减半？"
    rule_requires_human = any(
        term in question for term in HIGH_RISK_MEDICATION_TERMS
    )

    response = client.chat.completions.create(
        model=require_env("MODEL_NAME"),
        messages=[
            {
                "role": "system",
                "content": (
                    "你是随访问题分类器。只输出 JSON，不要输出解释或 Markdown。"
                    "字段必须为 category、needs_human、reason。"
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw_content = response.choices[0].message.content or ""
    print(f"Model raw JSON: {raw_content}")

    try:
        parsed = FollowUpIntent.model_validate(json.loads(raw_content))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError("Model output did not match the required structure") from exc

    print("Schema validation passed.")
    print(f"Model decision: needs_human={parsed.needs_human}")

    if rule_requires_human and not parsed.needs_human:
        print("Safety rule override: medication-change question requires a human.")
        parsed.needs_human = True
        parsed.reason = "命中用药调整安全规则，必须转人工处理。"

    print("Final system decision:")
    print(f"category={parsed.category}")
    print(f"needs_human={parsed.needs_human}")
    print(f"reason={parsed.reason}")


if __name__ == "__main__":
    main()
