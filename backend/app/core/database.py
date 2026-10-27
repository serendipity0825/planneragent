"""数据库引擎与会话管理 (async SQLAlchemy 2.0 + aiosqlite)"""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

# 后端根目录 (backend/)，用于解析相对的 sqlite 路径
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_settings = get_settings()

_connect_args: dict = {}
if _settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

async_engine = create_async_engine(
    _settings.database_url,
    echo=False,
    connect_args=_connect_args,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


async def get_db():
    """FastAPI 依赖：提供异步数据库会话"""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """创建数据表（首次启动自动建表）"""
    # 确保 sqlite 数据文件所在目录存在
    if _settings.database_url.startswith("sqlite"):
        path_part = _settings.database_url.split("///")[-1]
        if path_part and not os.path.isabs(path_part):
            path_part = os.path.join(_BACKEND_DIR, path_part)
        db_dir = os.path.dirname(path_part)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"[DB] 数据库已初始化: {_settings.database_url}")
    if _settings.jwt_secret_key == "please-change-this-to-a-long-random-secret-key":
        print("[DB] 警告: JWT_SECRET_KEY 仍为默认值，生产环境请务必修改！")
