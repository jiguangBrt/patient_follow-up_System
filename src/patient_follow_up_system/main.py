import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import APIError, OpenAI
from pydantic import BaseModel, Field


load_dotenv()

app = FastAPI(
    title="Patient Follow-up System MVP",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    status: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    model: str


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def model_client() -> OpenAI:
    return OpenAI(
        base_url=require_env("MODEL_BASE_URL"),
        api_key=require_env("MODEL_API_KEY"),
        timeout=60.0,
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    model_name = require_env("MODEL_NAME")

    try:
        response = model_client().chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "你是患者随访系统的软件演示助手，不提供诊断或用药建议。",
                },
                {"role": "user", "content": request.message},
            ],
            temperature=0,
        )
    except APIError as exc:
        raise HTTPException(
            status_code=503,
            detail="Local model service is temporarily unavailable.",
        ) from exc

    answer = response.choices[0].message.content or ""
    return ChatResponse(answer=answer, model=model_name)
