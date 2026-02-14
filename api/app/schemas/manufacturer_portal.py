"""Manufacturer portal schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class ManufacturerProfileResponse(BaseModel):
    """メーカープロフィールレスポンス"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    phone: str | None
    # 請求書関連フィールド
    postal_code: str | None
    address: str | None
    bank_name: str | None
    bank_branch: str | None
    bank_account_type: str | None
    bank_account_number: str | None
    bank_account_holder: str | None
    representative_name: str | None
    invoice_notes: str | None


class ManufacturerProfileUpdate(BaseModel):
    """メーカープロフィール更新リクエスト"""

    phone: str | None = Field(None, max_length=20)
    # 請求書関連フィールド
    postal_code: str | None = Field(None, max_length=10)
    address: str | None = Field(None, max_length=500)
    bank_name: str | None = Field(None, max_length=100)
    bank_branch: str | None = Field(None, max_length=100)
    bank_account_type: Literal["普通", "当座"] | None = None
    bank_account_number: str | None = Field(None, max_length=20)
    bank_account_holder: str | None = Field(None, max_length=100)
    representative_name: str | None = Field(None, max_length=100)
    invoice_notes: str | None = Field(None, max_length=1000)
