from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Member, UserRole, Branch
from app.auth import create_token, verify_token, get_current_user, require_admin, pwd_context
from datetime import datetime
import httpx

router = APIRouter(prefix="/auth", tags=["认证"])


class WechatLoginRequest(BaseModel):
    code: str = Field(..., description="wx.login返回的临时code")


class PhoneLoginRequest(BaseModel):
    phone: str = Field(..., pattern=r'^1[3-9]\d{9}$')
    password: str | None = None


class BindPhoneRequest(BaseModel):
    code: str  # 微信 getPhoneNumber 返回的动态令牌


class RegisterRequest(BaseModel):
    phone: str = Field(..., pattern=r'^1[3-9]\d{9}$')
    password: str = Field(..., min_length=6, max_length=50)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    member_id: int | None = None


@router.post("/wechat-login", response_model=TokenResponse)
async def wechat_login(req: WechatLoginRequest, db: Session = Depends(get_db)):
    """微信小程序登录 - 获取openid"""
    from app.config import get_settings
    settings = get_settings()

    # 调用微信接口换取openid
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": settings.WECHAT_APPID,
                "secret": settings.WECHAT_SECRET,
                "js_code": req.code,
                "grant_type": "authorization_code"
            }
        )
        data = resp.json()

    openid = data.get("openid")
    if not openid:
        raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg', '未知错误')}")

    # 查找或创建用户
    user = db.query(User).filter(User.openid == openid).first()
    if user is None:
        # 新用户 - 创建匿名用户，后续绑定手机号
        user = User(openid=openid, role=UserRole.PUBLIC)
        db.add(user)
        db.commit()
        db.refresh(user)

    user.last_login = datetime.now()
    db.commit()

    # 获取关联会员ID
    member = db.query(Member).filter(Member.user_id == user.id).first()
    member_id = member.id if member else None

    token = create_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token, role=user.role.value, member_id=member_id)


@router.post("/bind-phone", response_model=TokenResponse)
async def bind_phone(req: BindPhoneRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """绑定手机号 - 通过微信 getPhoneNumber code 换取真实手机号"""
    from app.config import get_settings
    settings = get_settings()

    # 第一步：获取 access_token
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": settings.WECHAT_APPID,
                "secret": settings.WECHAT_SECRET
            }
        )
        token_data = resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail=f"获取access_token失败: {token_data.get('errmsg', '')}")

    # 第二步：用 code 换手机号
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.weixin.qq.com/wxa/business/getuserphonenumber",
            params={"access_token": access_token},
            json={"code": req.code}
        )
        phone_data = resp.json()

    if phone_data.get("errcode") != 0:
        raise HTTPException(status_code=400, detail=f"获取手机号失败: {phone_data.get('errmsg', '')}")

    phone = phone_data.get("phone_info", {}).get("purePhoneNumber")
    if not phone:
        raise HTTPException(status_code=400, detail="未获取到手机号")

    # 检查手机号是否已被其他用户绑定
    existing = db.query(User).filter(User.phone == phone, User.id != current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已被其他账号绑定")

    # 绑定手机号到当前用户
    current_user.phone = phone

    # 查找是否已有该手机号的会员档案
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        # 检查是否有其他 user 关联了该手机号的会员（历史数据清理）
        other_user = db.query(User).filter(User.phone == phone).first()
        if other_user and other_user.id != current_user.id:
            other_member = db.query(Member).filter(Member.user_id == other_user.id).first()
            if other_member:
                # 把会员档案转移到当前用户
                other_member.user_id = current_user.id
                member = other_member
                # 删除旧的空 user
                db.delete(other_user)

    if not member and current_user.role == UserRole.PUBLIC:
        current_user.role = UserRole.MEMBER

    db.commit()

    member_id = member.id if member else None
    token = create_token({"sub": str(current_user.id), "role": current_user.role.value})
    return TokenResponse(access_token=token, role=current_user.role.value, member_id=member_id)


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """管理员注册（仅限超级管理员角色）"""
    existing = db.query(User).filter(User.phone == req.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已注册")

    user = User(
        phone=req.phone,
        password_hash=pwd_context.hash(req.password),
        role=UserRole.SUPER_ADMIN,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token, role=user.role.value)


@router.post("/admin-login", response_model=TokenResponse)
async def admin_login(req: PhoneLoginRequest, db: Session = Depends(get_db)):
    """管理员账号密码登录（Web后台用）"""
    user = db.query(User).filter(
        User.phone == req.phone,
        User.role.in_([UserRole.ORG_LEADER, UserRole.SUPER_ADMIN, UserRole.BRANCH_LEADER])
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="账号不存在或非管理员")

    # 如果用户设置了密码，则验证密码
    if user.password_hash:
        if not req.password:
            raise HTTPException(status_code=401, detail="请输入密码")
        if not pwd_context.verify(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="密码错误")
    # 没有密码的用户（旧数据）允许无密码登录

    user.last_login = datetime.now()
    db.commit()

    token = create_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token, role=user.role.value)


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取当前登录用户信息"""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    branch = db.query(Branch).filter(Branch.id == member.branch_id).first() if member else None

    return {
        "user_id": current_user.id,
        "phone": current_user.phone,
        "role": current_user.role.value,
        "member": {
            "id": member.id,
            "name": member.name,
            "avatar": member.avatar,
            "branch_name": branch.name if branch else None,
            "org_position": member.org_position,
        } if member else None
    }
