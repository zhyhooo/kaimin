from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models import Event, EventRegistration, User, Member, UserRole
from app.auth import get_current_user, require_leader
from fastapi.responses import StreamingResponse
import openpyxl
from io import BytesIO

router = APIRouter(prefix="/events", tags=["活动管理"])


class EventCreate(BaseModel):
    title: str
    content: Optional[str] = None
    cover_image: Optional[str] = None
    event_time: datetime
    location: Optional[str] = None
    max_participants: Optional[int] = None
    signup_deadline: Optional[datetime] = None
    contact_person: Optional[str] = None
    branch_id: Optional[int] = None  # None=全市


class EventUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    cover_image: Optional[str] = None
    event_time: Optional[datetime] = None
    location: Optional[str] = None
    max_participants: Optional[int] = None
    signup_deadline: Optional[datetime] = None
    contact_person: Optional[str] = None
    branch_id: Optional[int] = None
    status: Optional[str] = None


@router.get("/")
async def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """活动列表 - 支部活动仅本支部可见"""
    query = db.query(Event).filter(Event.status == "published")

    if current_user.role in (UserRole.MEMBER, UserRole.CANDIDATE, UserRole.BRANCH_LEADER):
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if member:
            query = query.filter(
                (Event.branch_id.is_(None)) | (Event.branch_id == member.branch_id)
            )

    events = query.order_by(Event.event_time.desc()).all()
    result = []
    for e in events:
        signup_count = db.query(EventRegistration).filter(
            EventRegistration.event_id == e.id, EventRegistration.cancelled_at.is_(None)
        ).count()
        result.append({
            "id": e.id, "title": e.title, "cover_image": e.cover_image,
            "event_time": str(e.event_time), "location": e.location,
            "signup_deadline": str(e.signup_deadline) if e.signup_deadline else None,
            "contact_person": e.contact_person, "max_participants": e.max_participants,
            "signup_count": signup_count,
            "status": e.status, "branch_id": e.branch_id
        })
    return result


@router.get("/{event_id}")
async def get_event(event_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """活动详情"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="活动不存在")

    # 获取当前用户的报名状态
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    registration = None
    if member:
        registration = db.query(EventRegistration).filter(
            EventRegistration.event_id == event_id,
            EventRegistration.member_id == member.id
        ).first()

    registrations_count = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id, EventRegistration.cancelled_at.is_(None)
    ).count()

    return {
        "id": event.id, "title": event.title, "content": event.content,
        "cover_image": event.cover_image, "event_time": str(event.event_time),
        "location": event.location, "max_participants": event.max_participants,
        "signup_deadline": str(event.signup_deadline),
        "contact_person": event.contact_person,
        "registrations_count": registrations_count,
        "my_registration": {
            "id": registration.id, "with_family": registration.with_family,
            "family_count": registration.family_count, "remark": registration.remark,
            "is_leave": registration.is_leave, "signed_up_at": str(registration.signed_up_at),
            "is_checked_in": registration.is_checked_in
        } if registration else None
    }


@router.post("/{event_id}/signup")
async def signup_event(
    event_id: int,
    with_family: bool = False,
    family_count: int = 0,
    remark: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """在线报名"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="活动不存在")
    if datetime.now() > event.signup_deadline:
        raise HTTPException(status_code=400, detail="报名已截止")

    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        raise HTTPException(status_code=400, detail="请先完善会员信息")

    # 检查是否已报名
    existing = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.member_id == member.id,
        EventRegistration.cancelled_at.is_(None)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已报名，请勿重复")

    reg = EventRegistration(
        event_id=event_id, member_id=member.id,
        with_family=with_family, family_count=family_count, remark=remark
    )
    db.add(reg)
    db.commit()
    return {"message": "报名成功", "id": reg.id}


@router.post("/{event_id}/cancel")
async def cancel_signup(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404)
    # 活动开始后不允许取消
    if datetime.now() > event.event_time:
        raise HTTPException(status_code=400, detail="活动已开始，无法取消报名")

    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        raise HTTPException(status_code=400, detail="请先完善会员信息")
    reg = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.member_id == member.id,
        EventRegistration.cancelled_at.is_(None)
    ).first()
    if not reg:
        raise HTTPException(status_code=404, detail="未找到报名记录")
    reg.cancelled_at = datetime.now()
    db.commit()
    return {"message": "取消报名成功"}


@router.post("/{event_id}/leave")
async def leave_event(
    event_id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="活动不存在")

    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        raise HTTPException(status_code=400, detail="请先完善会员信息")

    reg = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.member_id == member.id,
        EventRegistration.cancelled_at.is_(None)
    ).first()
    if not reg:
        raise HTTPException(status_code=404, detail="未报名，无法请假")

    # 活动开始后不允许请假
    if datetime.now() > event.event_time:
        raise HTTPException(status_code=400, detail="活动已开始，无法请假")

    reg.is_leave = True
    reg.leave_reason = reason
    db.commit()
    return {"message": "请假提交成功"}


@router.get("/{event_id}/registrations")
async def get_registrations(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """干部端查看报名/请假名单"""
    registrations = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id
    ).all()

    signed_up = []
    leaves = []
    for r in registrations:
        member = db.query(Member).filter(Member.id == r.member_id).first()
        item = {
            "member_id": member.id, "name": member.name,
            "with_family": r.with_family, "family_count": r.family_count,
            "remark": r.remark, "is_checked_in": r.is_checked_in,
            "signed_up_at": str(r.signed_up_at) if r.signed_up_at else None
        }
        if r.is_leave:
            item["leave_reason"] = r.leave_reason
            leaves.append(item)
        else:
            signed_up.append(item)

    return {"signed_up": signed_up, "leaves": leaves}


@router.get("/{event_id}/registrations/export")
async def export_registrations(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """导出报名名单Excel"""
    event = db.query(Event).filter(Event.id == event_id).first()
    registrations = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id, EventRegistration.cancelled_at.is_(None)
    ).all()

    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "报名名单"
    ws.append(["姓名", "支部", "携带家属", "家属人数", "备注", "签到状态", "报名时间"])
    for r in registrations:
        member = db.query(Member).filter(Member.id == r.member_id).first()
        branch = db.query(Member).join(Member.branch).filter(Member.id == r.member_id).first()
        branch_name = member.branch.name if member and member.branch else ""
        ws.append([member.name if member else "", branch_name,
                   "是" if r.with_family else "否", r.family_count, r.remark,
                   "已签到" if r.is_checked_in else "未签到",
                   str(r.signed_up_at)])

    output = BytesIO(); wb.save(output); output.seek(0)
    return StreamingResponse(output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=event_{event_id}_registrations.xlsx"})


@router.post("/{event_id}/checkin/{member_id}")
async def manual_checkin(
    event_id: int, member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """手动补录签到"""
    reg = db.query(EventRegistration).filter(
        EventRegistration.event_id == event_id,
        EventRegistration.member_id == member_id
    ).first()
    if not reg:
        raise HTTPException(status_code=404)
    reg.is_checked_in = True
    reg.check_in_time = datetime.now()
    reg.check_in_method = "manual"
    db.commit()
    return {"message": "补录签到成功"}


@router.post("/")
async def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """发布活动"""
    if current_user.role == UserRole.BRANCH_LEADER:
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        data.branch_id = member.branch_id if member else None

    event = Event(**data.dict(), author_id=current_user.id, status="published")
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"id": event.id, "message": "活动发布成功"}


@router.put("/{event_id}")
async def update_event(
    event_id: int,
    data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """更新活动"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="活动不存在")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)
    db.commit()
    return {"id": event.id, "message": "活动更新成功"}


@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """删除活动"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="活动不存在")
    db.delete(event)
    db.commit()
    return {"message": "活动已删除"}