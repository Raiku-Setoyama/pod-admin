---
name: fastapi-architecture
description: FastAPI シンプルレイヤードアーキテクチャの設計・実装ガイド。バックエンド新規構築時に参照。
---

# FastAPI シンプルレイヤードアーキテクチャ 実装指針

> Docker + Alembic + SQLAlchemy によるシンプルなAPI開発環境

---

## ディレクトリ構造

```
project/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── requirements.txt
├── .env
├── .env.example
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── xxxx_initial.py
└── app/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── database.py
    ├── routers/
    │   ├── __init__.py
    │   └── users.py
    ├── services/
    │   ├── __init__.py
    │   └── user_service.py
    ├── repositories/
    │   ├── __init__.py
    │   └── user_repository.py
    ├── models/
    │   ├── __init__.py
    │   └── user.py
    ├── schemas/
    │   ├── __init__.py
    │   └── user.py
    └── exceptions.py
```

---

## 各層の責務

| 層 | 責務 | 許可される操作 |
|---|---|---|
| **Router** | HTTPの入出力処理 | リクエスト受付、レスポンス返却、Service呼び出し |
| **Service** | ビジネスロジック | 業務ルール実装、複数Repository連携、トランザクション管理 |
| **Repository** | データ永続化 | CRUD操作、クエリ構築 |
| **Schema** | データ構造定義 | バリデーション、シリアライズ |
| **Model** | DBテーブル定義 | ORMマッピング |

---

## 依存ルール

```
Router → Service → Repository → Model
                        ↓
                     Database
```

**守るべきこと**

- 上位層は下位層のみに依存する
- 同一層同士は依存しない（Service → Service は避ける）
- 逆方向の依存は禁止（Repository → Service など）

---

## 命名規則

```python
# Router
routers/users.py          # 複数形
router = APIRouter(prefix="/users", tags=["users"])

# Service（関数として実装）
services/user_service.py  # 単数形 + _service
def create(db, data): ...
def get_by_id(db, user_id): ...

# Repository（関数として実装）
repositories/user_repository.py  # 単数形 + _repository
def create(db, data): ...
def find_by_id(db, user_id): ...

# Schema
schemas/user.py
class UserCreate(BaseModel):    # 用途を接尾辞に
class UserUpdate(BaseModel):
class UserResponse(BaseModel):

# Model
models/user.py
class User(Base):               # テーブル名と一致
```

---

## 各層の実装パターン

### Router（薄く保つ）

```python
# routers/users.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.user import UserCreate, UserResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    return user_service.create(db, data)

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return user_service.get_by_id(db, user_id)
```

**Router でやらないこと**

- ビジネスロジックの記述
- 直接のDB操作
- 複雑な条件分岐

---

### Service（ロジックを集約）

```python
# services/user_service.py
from sqlalchemy.orm import Session
from app.repositories import user_repository
from app.schemas.user import UserCreate
from app.models.user import User
from app.exceptions import EmailAlreadyExistsError, NotFoundError

def create(db: Session, data: UserCreate) -> User:
    if user_repository.exists_by_email(db, data.email):
        raise EmailAlreadyExistsError()
    return user_repository.create(db, data)

def get_by_id(db: Session, user_id: int) -> User:
    user = user_repository.find_by_id(db, user_id)
    if not user:
        raise NotFoundError("User")
    return user
```

**Service の責務**

- 入力値の業務検証
- 複数エンティティの操作
- 例外の発生

---

### Repository（データ操作に専念）

```python
# repositories/user_repository.py
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate

def create(db: Session, data: UserCreate) -> User:
    user = User(**data.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def find_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()

def exists_by_email(db: Session, email: str) -> bool:
    return db.query(User).filter(User.email == email).first() is not None
```

**Repository でやらないこと**

- ビジネスルールの判定
- 複数テーブルにまたがるトランザクション制御

---

### Model（DBテーブル定義）

```python
# models/user.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

---

### Schema（入出力定義）

```python
# schemas/user.py
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    name: str

class UserUpdate(BaseModel):
    name: str | None = None

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## 例外処理

```python
# exceptions.py
class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

class NotFoundError(AppException):
    def __init__(self, resource: str):
        super().__init__(404, f"{resource} not found")

class EmailAlreadyExistsError(AppException):
    def __init__(self):
        super().__init__(409, "Email already exists")

class ValidationError(AppException):
    def __init__(self, detail: str):
        super().__init__(422, detail)
```

```python
# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.exceptions import AppException
from app.routers import users

app = FastAPI(title="API Server")

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

app.include_router(users.router)
```

---

## 新規リソース追加チェックリスト

新しいリソース（例: Post）を追加する際の手順：

1. [ ] `models/post.py` - DBモデル定義
2. [ ] `schemas/post.py` - 入出力スキーマ定義
3. [ ] `repositories/post_repository.py` - データアクセス層（関数）
4. [ ] `services/post_service.py` - ビジネスロジック層（関数）
5. [ ] `routers/posts.py` - エンドポイント定義
6. [ ] `main.py` - ルーター登録
7. [ ] `alembic/env.py` - モデルインポート追加
8. [ ] `make migrate-new MSG="add posts table"` - マイグレーション作成
9. [ ] `make migrate` - マイグレーション適用

---

## やること / やらないこと

| ✅ やること | ❌ やらないこと |
|---|---|
| Service/Repositoryは関数で実装 | Routerにロジックを書く |
| Schemaで入出力を明示 | Modelを直接レスポンスに使う |
| 例外はServiceで発生させる | Repositoryで業務判定する |
| dbセッションを引数で渡す | グローバル変数でDB接続を管理 |
| Alembicでスキーマ変更を管理 | 手動でDBスキーマを変更する |
| docker-composeで環境統一 | ローカルに直接DBをインストール |
| Makefileでコマンドを標準化 | 長いコマンドを毎回手打ち |
