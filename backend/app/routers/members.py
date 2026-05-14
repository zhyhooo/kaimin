from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from pydantic import BaseModel, Field
from datetime import date, datetime
from app.database import get_db
from app.models import User, Member, Branch, MemberStatus, UserRole
from app.auth import get_current_user, require_member, require_leader, require_org_leader
import openpyxl
from io import BytesIO
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/members", tags=["会员档案"])


# ============ Pydantic Schemas ============

class MemberCreate(BaseModel):
    name: str
    phone: str = Field(pattern=r'^1[3-9]\d{9}$')
    id_card: Optional[str] = None
    branch_id: Optional[int] = None
    org_position: Optional[str] = None
    work_unit: Optional[str] = None
    work_position: Optional[str] = None
    title: Optional[str] = None
    education: Optional[str] = None
    school: Optional[str] = None
    specialty: Optional[str] = None
    social_position: Optional[str] = None
    native_place: Optional[str] = None
    join_date: Optional[date] = None


class MemberUpdate(BaseModel):
    """会员可自主编辑的字段"""
    phone: Optional[str] = None
    work_unit: Optional[str] = None
    work_position: Optional[str] = None
    title: Optional[str] = None
    education: Optional[str] = None
    school: Optional[str] = None
    specialty: Optional[str] = None
    social_position: Optional[str] = None


class MemberResponse(BaseModel):
    id: int
    name: str
    gender: Optional[str]
    avatar: Optional[str]
    branch_id: Optional[int]
    branch_name: Optional[str]
    org_position: Optional[str]
    work_unit: Optional[str]
    work_position: Optional[str]
    title: Optional[str]
    education: Optional[str]
    join_date: Optional[date]
    status: str

    class Config:
        from_attributes = True


# ============ CRUD 接口 ============

@router.get("/", response_model=list[MemberResponse])
async def list_members(
    keyword: Optional[str] = Query(None, description="搜索关键字(姓名/单位)"),
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """会员列表 - 权限隔离"""
    query = db.query(Member)

    # 权限隔离
    if current_user.role == UserRole.MEMBER:
        # 普通会员仅见本支部
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if member:
            query = query.filter(Member.branch_id == member.branch_id)
    elif current_user.role == UserRole.BRANCH_LEADER:
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if member:
            query = query.filter(Member.branch_id == member.branch_id)
    # ORG_LEADER / SUPER_ADMIN 可见全体

    if branch_id:
        query = query.filter(Member.branch_id == branch_id)
    if keyword:
        query = query.filter(
            or_(Member.name.like(f"%{keyword}%"), Member.work_unit.like(f"%{keyword}%"))
        )

    members = query.order_by(Member.branch_id, Member.name).all()
    result = []
    for m in members:
        branch = db.query(Branch).filter(Branch.id == m.branch_id).first()
        result.append(MemberResponse(
            id=m.id, name=m.name, gender=m.gender, avatar=m.avatar,
            branch_id=m.branch_id, branch_name=branch.name if branch else None,
            org_position=m.org_position, work_unit=m.work_unit,
            work_position=m.work_position, title=m.title, education=m.education,
            join_date=m.join_date, status=m.status.value if m.status else ""
        ))
    return result


@router.get("/{member_id}")
async def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """会员详情"""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    # 权限检查：普通会员/支部主委跨支部查看受限
    if current_user.role in (UserRole.MEMBER, UserRole.BRANCH_LEADER):
        self_member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if self_member and self_member.branch_id != member.branch_id:
            # 仅返回公开字段
            return {"id": member.id, "name": member.name, "branch_name": member.branch.name if member.branch else None}

    branch = db.query(Branch).filter(Branch.id == member.branch_id).first()
    return {
        "id": member.id, "name": member.name, "gender": member.gender,
        "birth_date": str(member.birth_date) if member.birth_date else None,
        "avatar": member.avatar, "branch_id": member.branch_id,
        "branch_name": branch.name if branch else None,
        "org_position": member.org_position,
        "work_unit": member.work_unit, "work_position": member.work_position,
        "title": member.title, "education": member.education,
        "school": member.school, "specialty": member.specialty,
        "social_position": member.social_position, "native_place": member.native_place,
        "join_date": str(member.join_date) if member.join_date else None,
        "status": member.status.value if member.status else ""
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_member(
    data: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """创建会员（组织委员权限）"""
    # 创建 User
    from app.auth import hash_phone
    user = User(phone=data.phone, role=UserRole.MEMBER)
    db.add(user)
    db.flush()

    # 身份证号推算性别和出生年月
    gender = None
    birth_date = None
    if data.id_card and len(data.id_card) == 18:
        gender_code = int(data.id_card[16])
        gender = "女" if gender_code % 2 == 0 else "男"
        try:
            birth_date = date(int(data.id_card[6:10]), int(data.id_card[10:12]), int(data.id_card[12:14]))
        except ValueError:
            pass

    member = Member(
        user_id=user.id, name=data.name, id_card=data.id_card,
        gender=gender, birth_date=birth_date,
        branch_id=data.branch_id, org_position=data.org_position,
        work_unit=data.work_unit, work_position=data.work_position,
        title=data.title, education=data.education, school=data.school,
        specialty=data.specialty, social_position=data.social_position,
        native_place=data.native_place, join_date=data.join_date
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"id": member.id, "name": member.name, "message": "创建成功"}


@router.put("/{member_id}")
async def update_member(
    member_id: int,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """编辑会员档案（会员本人或组织委员）"""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    # 权限：本人或组织委员及以上
    if current_user.role not in (UserRole.ORG_LEADER, UserRole.SUPER_ADMIN):
        self_member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if not self_member or self_member.id != member_id:
            raise HTTPException(status_code=403, detail="仅可编辑自己的档案")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    return {"message": "更新成功", "id": member.id}


@router.get("/export/excel")
async def export_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """导出通讯录Excel（含动态水印）"""
    members = db.query(Member).order_by(Member.branch_id, Member.name).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "会员通讯录"

    headers = ["姓名", "性别", "支部", "会内职务", "工作单位", "工作职务", "手机号", "入会时间"]
    ws.append(headers)

    for m in members:
        branch = db.query(Branch).filter(Branch.id == m.branch_id).first()
        ws.append([
            m.name, m.gender, branch.name if branch else "",
            m.org_position, m.work_unit, m.work_position,
            m.user.phone if m.user else "", str(m.join_date) if m.join_date else ""
        ])

    # 添加水印
    from openpyxl.styles import Font
    watermark = f"导出人: {current_user.phone} | 时间: {datetime.now():%Y-%m-%d %H:%M} | 富阳总支"
    ws.append([]); ws.append([watermark])
    ws[f"A{ws.max_row}"].font = Font(color="808080", size=10)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    now = datetime.now().strftime("%Y%m%d_%H%M")
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=members_{now}.xlsx"}
    )


@router.post("/import/excel")
async def import_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    """批量导入会员（骨架，需接收上传文件）"""
    # TODO: 接收上传的Excel文件，解析并批量创建
    raise HTTPException(status_code=501, detail="批量导入功能待实现")
