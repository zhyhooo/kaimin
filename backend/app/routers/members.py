from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
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


# 管理员可编辑的全部字段
ADMIN_EDITABLE_FIELDS = {
    "name", "phone", "id_card", "branch_id", "org_position",
    "work_unit", "work_position", "title", "education",
    "school", "specialty", "social_position", "native_place", "join_date"
}

# 普通会员仅可编辑的 7 个安全字段
MEMBER_SAFE_FIELDS = {
    "work_unit", "work_position", "title", "education",
    "school", "specialty", "social_position"
}


class MemberUpdate(BaseModel):
    """管理员编辑字段（全量）"""
    name: Optional[str] = None
    phone: Optional[str] = None
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
    # 先查是否已有绑定手机号的小程序用户，复用避免多账号
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        user = User(phone=data.phone, role=UserRole.MEMBER)
        db.add(user)
        db.flush()
    else:
        # 已有用户升级为会员角色
        if user.role == UserRole.PUBLIC:
            user.role = UserRole.MEMBER
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
    is_admin = current_user.role in (UserRole.ORG_LEADER, UserRole.SUPER_ADMIN)
    if not is_admin:
        self_member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if not self_member or self_member.id != member_id:
            raise HTTPException(status_code=403, detail="仅可编辑自己的档案")

    updates = data.dict(exclude_unset=True)

    # 普通会员只允许编辑 7 个安全字段
    if not is_admin:
        blocked = [k for k in updates if k not in MEMBER_SAFE_FIELDS]
        if blocked:
            raise HTTPException(status_code=403, detail=f"无权限编辑以下字段: {', '.join(blocked)}")

    for field, value in updates.items():
        setattr(member, field, value)
    db.commit()
    return {"message": "更新成功", "id": member.id}


@router.delete("/{member_id}")
async def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    """删除会员（组织委员以上）"""
      member = db.query(Member).filter(Member.id == member_id).first()
      if not member:
          raise HTTPException(status_code=404, detail="会员不存在")
      if member.status == MemberStatus.INACTIVE:
          raise HTTPException(status_code=400, detail="会员已离会")

      member.status = MemberStatus.INACTIVE
      db.commit()
      return {"message": "会员已标记为离会"}


@router.post("/{member_id}/restore")
async def restore_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    """恢复已离会会员"""
    member = db.query(Member).filter(Member.id == member_id, Member.status == MemberStatus.INACTIVE).first()
    if not member:
        raise HTTPException(status_code=404, detail="未找到已离会的会员")
    member.status = MemberStatus.ACTIVE
    db.commit()
    return {"message": "会员已恢复"}


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
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    """批量导入会员（Excel文件，含字段校验和错误提示）"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 格式")

    try:
        contents = await file.read()
        wb = openpyxl.load_workbook(BytesIO(contents))
        ws = wb.active
    except Exception:
        raise HTTPException(status_code=400, detail="无法解析Excel文件，请检查格式")

    # 读取表头（第1行）
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel文件为空或缺少数据行")

    headers = [str(h).strip() if h else "" for h in rows[0]]
    # 期望的列：姓名, 手机号, 身份证号, 支部名称, 会内职务, 工作单位, 工作职务, 职称, 学历, 毕业院校, 专业特长, 社会职务, 籍贯, 入会时间
    col_map = {name: idx for idx, name in enumerate(headers)}

    required_fields = ["姓名", "手机号"]
    for f in required_fields:
        if f not in col_map:
            raise HTTPException(status_code=400, detail=f"缺少必填列: {f}")

    success_count = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], start=2):
        try:
            name = str(row[col_map["姓名"]]).strip() if col_map.get("姓名") is not None and row[col_map["姓名"]] else ""
            phone = str(row[col_map["手机号"]]).strip() if col_map.get("手机号") is not None and row[col_map["手机号"]] else ""

            if not name:
                errors.append(f"第{row_idx}行: 姓名为空")
                continue
            if not phone or len(phone) != 11 or not phone.startswith("1"):
                errors.append(f"第{row_idx}行: 手机号格式不正确 ({phone})")
                continue

            # 检查手机号是否已存在
            existing_user = db.query(User).filter(User.phone == phone).first()
            if existing_user:
                errors.append(f"第{row_idx}行: 手机号 {phone} 已存在")
                continue

            # 读取可选字段
            id_card = str(row[col_map["身份证号"]]).strip() if col_map.get("身份证号") is not None and row[col_map["身份证号"]] else None
            branch_name = str(row[col_map["支部名称"]]).strip() if col_map.get("支部名称") is not None and row[col_map["支部名称"]] else None
            org_position = str(row[col_map["会内职务"]]).strip() if col_map.get("会内职务") is not None and row[col_map["会内职务"]] else None
            work_unit = str(row[col_map["工作单位"]]).strip() if col_map.get("工作单位") is not None and row[col_map["工作单位"]] else None
            work_position = str(row[col_map["工作职务"]]).strip() if col_map.get("工作职务") is not None and row[col_map["工作职务"]] else None
            title = str(row[col_map["职称"]]).strip() if col_map.get("职称") is not None and row[col_map["职称"]] else None
            education = str(row[col_map["学历"]]).strip() if col_map.get("学历") is not None and row[col_map["学历"]] else None
            school = str(row[col_map["毕业院校"]]).strip() if col_map.get("毕业院校") is not None and row[col_map["毕业院校"]] else None
            specialty = str(row[col_map["专业特长"]]).strip() if col_map.get("专业特长") is not None and row[col_map["专业特长"]] else None
            social_position = str(row[col_map["社会职务"]]).strip() if col_map.get("社会职务") is not None and row[col_map["社会职务"]] else None
            native_place = str(row[col_map["籍贯"]]).strip() if col_map.get("籍贯") is not None and row[col_map["籍贯"]] else None
            join_date_str = str(row[col_map["入会时间"]]).strip() if col_map.get("入会时间") is not None and row[col_map["入会时间"]] else None

            # 查找支部
            branch_id = None
            if branch_name:
                branch = db.query(Branch).filter(Branch.name == branch_name).first()
                if branch:
                    branch_id = branch.id
                else:
                    errors.append(f"第{row_idx}行: 支部 '{branch_name}' 不存在，已跳过支部关联")

            # 身份证号推算性别和出生年月
            gender = None
            birth_date = None
            if id_card and len(id_card) == 18:
                try:
                    gender_code = int(id_card[16])
                    gender = "女" if gender_code % 2 == 0 else "男"
                    birth_date = date(int(id_card[6:10]), int(id_card[10:12]), int(id_card[12:14]))
                except (ValueError, IndexError):
                    errors.append(f"第{row_idx}行: 身份证号格式有误，无法推算性别/生日")

            # 解析入会时间
            parsed_join_date = None
            if join_date_str:
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"]:
                    try:
                        parsed_join_date = datetime.strptime(join_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if not parsed_join_date:
                    errors.append(f"第{row_idx}行: 入会时间格式无法识别 ({join_date_str})，已跳过")

            # 复用已有手机号用户，避免多账号
            user = db.query(User).filter(User.phone == phone).first()
            if not user:
                user = User(phone=phone, role=UserRole.MEMBER)
                db.add(user)
                db.flush()
            elif user.role == UserRole.PUBLIC:
                user.role = UserRole.MEMBER
                db.flush()

            # 创建 Member
            member = Member(
                user_id=user.id, name=name, id_card=id_card,
                gender=gender, birth_date=birth_date,
                branch_id=branch_id, org_position=org_position,
                work_unit=work_unit, work_position=work_position,
                title=title, education=education, school=school,
                specialty=specialty, social_position=social_position,
                native_place=native_place, join_date=parsed_join_date
            )
            db.add(member)
            success_count += 1

        except Exception as e:
            errors.append(f"第{row_idx}行: 系统错误 - {str(e)}")

    db.commit()

    return {
        "message": f"导入完成: 成功 {success_count} 条, 失败 {len(errors)} 条",
        "success_count": success_count,
        "error_count": len(errors),
        "errors": errors
    }
