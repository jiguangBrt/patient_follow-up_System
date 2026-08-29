import os

from dotenv import load_dotenv
from openai import OpenAI


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    load_dotenv()

    base_url = require_env("MODEL_BASE_URL")
    model_name = require_env("MODEL_NAME")
    api_key = require_env("MODEL_API_KEY")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=60.0,
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": "你是患者随访系统的开发学习助手，只回答软件开发问题。",
            },
            {
                "role": "user",
                "content": "请只回答：Python 已成功调用本地模型",
            },
        ],
        temperature=0,
    )

    answer = response.choices[0].message.content
    print(answer)


if __name__ == "__main__":
    main()
