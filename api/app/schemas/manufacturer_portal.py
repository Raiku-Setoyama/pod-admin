"""Manufacturer portal schemas."""

from pydantic import BaseModel, EmailStr


class ManufacturerLoginRequest(BaseModel):
    """メーカーログインリクエスト"""

    email: EmailStr
    password: str


class ManufacturerLoginResponse(BaseModel):
    """メーカーログインレスポンス"""

    access_token: str
    refresh_token: str
    manufacturer_id: str
    manufacturer_name: str
