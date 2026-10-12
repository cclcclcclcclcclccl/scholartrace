"""Optional isolated accounts; local default workspace remains available in local mode."""

import asyncio
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from . import store, database, jobs

PUBLIC = os.getenv("SCHOLARTRACE_PUBLIC", "0") == "1"
AUTH_PATH = store.ROOT / "data/accounts.sqlite3"
router = APIRouter(prefix="/api/account")
schedulers = []


def connect():
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(AUTH_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def initialize():
    with connect() as c:
        c.executescript(
            "CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL); CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL); CREATE TABLE IF NOT EXISTS attempts(client TEXT PRIMARY KEY,failures INTEGER NOT NULL,until REAL NOT NULL);"
        )


def user(request):
    token = request.cookies.get("scholartrace_session", "")
    if not token:
        return None
    with connect() as c:
        row = c.execute(
            "SELECT u.id,u.name FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>?",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    return dict(row) if row else None


def path(identifier):
    return store.ROOT / "data/accounts" / identifier / "library.sqlite3"


def databases():
    with connect() as c:
        return [path(r[0]) for r in c.execute("SELECT id FROM users")]


async def scope(request, call_next):
    if request.url.path.startswith("/api/"):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                from fastapi.responses import JSONResponse

                return JSONResponse({"detail": "来源校验失败"}, 403)
        current = user(request)
        request.state.account = current
        if (
            PUBLIC
            and not current
            and request.url.path
            not in {
                "/api/health",
                "/api/account/status",
                "/api/account/login",
                "/api/account/register",
            }
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "请登录后访问研究空间"}, 401)
        token = store.database_override.set(path(current["id"]) if current else None)
        try:
            return await call_next(request)
        finally:
            store.database_override.reset(token)
    return await call_next(request)


class Credentials(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=10, max_length=200)


@router.get("/status")
def status(request: Request):
    return {
        "account": user(request),
        "public_mode": PUBLIC,
        "local_workspace": not PUBLIC,
    }


@router.post("/register")
async def register(body: Credentials, request: Request, response: Response):
    if not re.fullmatch(r"[\w\u4e00-\u9fff .-]{2,40}", body.name):
        raise HTTPException(422, "用户名包含不支持的字符")
    if PUBLIC and os.getenv("SCHOLARTRACE_REGISTRATION", "0") != "1":
        raise HTTPException(403, "公开实例已关闭注册，请使用评审账号")
    identifier = secrets.token_hex(16)
    salt = secrets.token_hex(16)
    digest = await asyncio.to_thread(
        hashlib.scrypt,
        body.password.encode(),
        salt=bytes.fromhex(salt),
        n=16384,
        r=8,
        p=1,
    )
    try:
        with connect() as c:
            c.execute(
                "INSERT INTO users VALUES(?,?,?,?)",
                (identifier, body.name, salt, digest.hex()),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "用户名已存在") from None
    token = store.database_override.set(path(identifier))
    try:
        from . import discovery

        database.initialize()
        schedulers.append(asyncio.create_task(discovery.scheduler()))
    finally:
        store.database_override.reset(token)
    create_session(identifier, response)
    return {"id": identifier, "name": body.name}


def create_session(identifier, response):
    token = secrets.token_urlsafe(32)
    with connect() as c:
        c.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        c.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                identifier,
                time.time() + 7 * 86400,
            ),
        )
    response.set_cookie(
        "scholartrace_session",
        token,
        httponly=True,
        samesite="strict",
        secure=PUBLIC,
        max_age=7 * 86400,
    )


@router.post("/login")
async def login(body: Credentials, request: Request, response: Response):
    client = request.client.host if request.client else "unknown"
    with connect() as c:
        attempt = c.execute(
            "SELECT * FROM attempts WHERE client=?", (client,)
        ).fetchone()
        if attempt and attempt["failures"] >= 8 and attempt["until"] > time.time():
            raise HTTPException(429, "登录尝试过多，请 10 分钟后重试")
        row = c.execute("SELECT * FROM users WHERE name=?", (body.name,)).fetchone()
    digest = await asyncio.to_thread(
        hashlib.scrypt,
        body.password.encode(),
        salt=bytes.fromhex(row["salt"]) if row else b"0" * 16,
        n=16384,
        r=8,
        p=1,
    )
    if not row or not hmac.compare_digest(digest.hex(), row["password"]):
        with connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO attempts VALUES(?,?,?)",
                (
                    client,
                    (
                        attempt["failures"]
                        if attempt and attempt["until"] > time.time()
                        else 0
                    )
                    + 1,
                    time.time() + 600,
                ),
            )
        raise HTTPException(401, "用户名或密码不正确")
    with connect() as c:
        c.execute("DELETE FROM attempts WHERE client=?", (client,))
    create_session(row["id"], response)
    return {"id": row["id"], "name": row["name"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("scholartrace_session", "")
    with connect() as c:
        c.execute(
            "DELETE FROM sessions WHERE token=?",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )
    response.delete_cookie("scholartrace_session")
    return {"ok": True}
