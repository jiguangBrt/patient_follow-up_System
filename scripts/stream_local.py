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

    client = OpenAI(
        base_url=require_env("MODEL_BASE_URL"),
        api_key=require_env("MODEL_API_KEY"),
        timeout=60.0,
    )

    stream = client.chat.completions.create(
        model=require_env("MODEL_NAME"),
        messages=[
            {
                "role": "system",
                "content": "你是软件学习助手，回答简洁准确。",
            },
            {
                "role": "user",
                "content": "用一句话解释什么是流式输出。",
            },
        ],
        temperature=0,
        stream=True,
    )

    print("Streaming response:")
    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            print(text, end="", flush=True)
    print()
    print("Stream completed.")


if __name__ == "__main__":
    main()
