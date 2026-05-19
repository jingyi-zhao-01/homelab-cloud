import os
from itertools import count
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import psycopg
from psycopg.rows import dict_row

app = FastAPI(title="user-service", version="0.1.0")

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_UNAVAILABLE_MESSAGE = "database unavailable"


class UserCreate(BaseModel):
    name: str
    email: EmailStr


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr


_users: dict[int, UserOut] = {}
_counter = count(1)
_lock = Lock()


def _db_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL

    if DB_HOST and DB_NAME and DB_USER and DB_PASSWORD:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    return ""


def _use_postgres() -> bool:
    return bool(_db_url())


def _init_db() -> None:
    if not _use_postgres():
        return

    with psycopg.connect(_db_url(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE
                )
                """)


def _to_user(row: dict[str, Any]) -> UserOut:
    return UserOut(
        id=int(row["id"]),
        name=str(row["name"]),
        email=str(row["email"]),
    )


@app.on_event("startup")
def startup() -> None:
    try:
        _init_db()
    except Exception:
        # Keep service available even if DB startup checks fail.
        pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "user-service"}


@app.post(
    "/users",
    status_code=201,
    responses={
        409: {"description": "User email already exists"},
        503: {"description": "Database unavailable"},
    },
)
def create_user(payload: UserCreate) -> UserOut:
    if _use_postgres():
        try:
            with psycopg.connect(
                _db_url(), autocommit=True, row_factory=dict_row
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO users (name, email)
                        VALUES (%s, %s)
                        RETURNING id, name, email
                        """,
                        (payload.name, payload.email),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(
                            status_code=503, detail="user persistence failed"
                        )
                    return _to_user(row)
        except psycopg.errors.UniqueViolation as exc:
            raise HTTPException(
                status_code=409, detail="user email already exists"
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    with _lock:
        user_id = next(_counter)
        user = UserOut(id=user_id, name=payload.name, email=payload.email)
        _users[user_id] = user
    return user


@app.get(
    "/users/{user_id}",
    responses={
        404: {"description": "User not found"},
        503: {"description": "Database unavailable"},
    },
)
def get_user(user_id: int) -> UserOut:
    if _use_postgres():
        try:
            with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, name, email
                        FROM users
                        WHERE id = %s
                        """,
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail="user not found")
                    return _to_user(row)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    user = _users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.get(
    "/users",
    responses={503: {"description": "Database unavailable"}},
)
def list_users() -> list[UserOut]:
    if _use_postgres():
        try:
            with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, name, email
                        FROM users
                        ORDER BY id DESC
                        """)
                    rows = cur.fetchall()
                    return [_to_user(row) for row in rows]
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    return list(_users.values())
