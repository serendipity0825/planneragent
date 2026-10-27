"""认证服务"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import create_access_token, hash_password, verify_password
from ..models.db_models import User
from ..models.schemas import UserCreate


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    """注册新用户，用户名/邮箱重复时抛 ValueError"""
    existing = await db.execute(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("用户名或邮箱已被注册")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, username: str, password: str):
    """校验用户名/邮箱 + 密码，返回 User 或 None"""
    result = await db.execute(
        select(User).where((User.username == username) | (User.email == username))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_token_for(user: User) -> str:
    """为用户生成 access token"""
    return create_access_token(subject=str(user.id), extra={"username": user.username})
