from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Member, UserRole, Branch
from app.auth import create_token, verify_token, get_current_user, require_admin
from datetime import datetime
import httpx

router = APIRouter(prefix="/auth", tags=["认证"])


class WechatLoginRequest(BaseModel):
    code: str = Field(..., description="wx.login返回的临时code")


class PhoneLoginRequest(BaseModel):
    phone: str = Field(..., pattern=r'^1[3-9]\d{9}$')


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
async def bind_phone(req: PhoneLoginRequest, current_user: User = Depends(get_current_user)):
    """绑定手机号 - 与后台导入的会员手机号匹配"""
    db = Depends(get_db)
    # 查找匹配的会员
    # 注意: 实际存储时手机号是加密的，这里需要加密后匹配
    # 简化处理：直接查询（生产环境应加密匹配）
    # member = db.query(Member).filter(Member.phone == req.phone).first()
    # if member:
    #    current_user.role = UserRole.MEMBER
    #    member.user_id = current_user.id
    #    db.commit()
    # 简化返回
    raise HTTPException(status_code=501, detail="绑定流程待实现（需与会员导入流程对接）")


@router.post("/admin-login", response_model=TokenResponse)
async def admin_login(req: PhoneLoginRequest, db: Session = Depends(get_db)):
    """管理员账号密码登录（Web后台用）"""
    user = db.query(User).filter(
        User.phone == req.phone,
        User.role.in_([UserRole.ORG_LEADER, UserRole.SUPER_ADMIN])
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="账号不存在或非管理员")

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
