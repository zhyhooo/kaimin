from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def create_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def hash_phone(phone: str) -> str:
    """手机号哈希（用于数据库存储）"""
    return pwd_context.hash(phone)


def verify_phone(phone: str, hashed: str) -> bool:
    return pwd_context.verify(phone, hashed)


# --- 获取当前用户 ---

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        # 未登录，返回匿名用户
        user = User(role=UserRole.PUBLIC)
        user.id = 0
        return user

    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效或已过期")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return user


async def get_current_member(
    current_user: User = Depends(get_current_user)
) -> User:
    """仅允许已认证的会员及以上角色"""
    if current_user.role == UserRole.PUBLIC:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    return current_user


# --- 角色权限依赖 ---

def require_role(*roles: UserRole):
    """要求用户具备指定角色之一"""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        return current_user
    return role_checker


# 常用权限组合
require_member = require_role(UserRole.MEMBER, UserRole.CANDIDATE, UserRole.BRANCH_LEADER, UserRole.ORG_LEADER, UserRole.SUPER_ADMIN)
require_leader = require_role(UserRole.BRANCH_LEADER, UserRole.ORG_LEADER, UserRole.SUPER_ADMIN)
require_org_leader = require_role(UserRole.ORG_LEADER, UserRole.SUPER_ADMIN)
require_admin = require_role(UserRole.SUPER_ADMIN)
