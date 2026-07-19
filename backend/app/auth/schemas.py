from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RepoOut(BaseModel):
    id: str
    url: str
    num_files: int
    num_chunks: int
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryOut(BaseModel):
    id: str
    repo_id: str
    repo_url: str
    action_type: str
    question: str
    answer: str
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardOut(BaseModel):
    user: UserOut
    repos: list[RepoOut]
    history: list[HistoryOut]
