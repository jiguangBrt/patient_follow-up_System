import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from openai import APIError, OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from patient_follow_up_system.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_env,
    require_roles,
)
from patient_follow_up_system.database import get_db
from patient_follow_up_system.models import User, UserRole


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


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole


class RoleDemoResponse(BaseModel):
    message: str
    username: str
    role: UserRole


def app_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def model_client() -> OpenAI:
    return OpenAI(
        base_url=app_env("MODEL_BASE_URL"),
        api_key=app_env("MODEL_API_KEY"),
        timeout=60.0,
    )


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


def role_demo_response(user: User, message: str) -> RoleDemoResponse:
    return RoleDemoResponse(
        message=message,
        username=user.username,
        role=user.role,
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    model_name = app_env("MODEL_NAME")

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


@app.post("/auth/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = authenticate_user(db, request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire_minutes = int(require_env("ACCESS_TOKEN_EXPIRE_MINUTES"))
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        token_type="bearer",
        expires_in=expire_minutes * 60,
    )


@app.get("/auth/me", response_model=UserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return user_response(current_user)


@app.get("/demo/admin", response_model=RoleDemoResponse)
def admin_demo(
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN)),
    ],
) -> RoleDemoResponse:
    return role_demo_response(current_user, "Admin demo access granted.")


@app.get("/demo/doctor", response_model=RoleDemoResponse)
def doctor_demo(
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR)),
    ],
) -> RoleDemoResponse:
    return role_demo_response(current_user, "Doctor demo access granted.")


@app.get("/demo/patient", response_model=RoleDemoResponse)
def patient_demo(
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.PATIENT)),
    ],
) -> RoleDemoResponse:
    return role_demo_response(current_user, "Patient demo access granted.")
