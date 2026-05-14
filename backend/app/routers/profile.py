from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import (
    User, Member, Branch, EventRegistration, Event,
    SocialInfo, ScoreRecord, ScoreDimension, Message
)
from app.auth import get_current_user, get_current_member

router = APIRouter(prefix="/profile", tags=["个人中心"])


@router.get("/")
async def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """个人中心主页 - 聚合所有个人信息"""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member and current_user.role.value != "public":
        return {"error": "请先完善会员信息"}

    branch = db.query(Branch).filter(Branch.id == member.branch_id).first() if member else None

    # 未读消息数
    unread_count = db.query(Message).filter(
        Message.user_id == current_user.id,
        Message.is_read == False
    ).count() if current_user.id > 0 else 0

    return {
        "member": {
            "id": member.id,
            "name": member.name,
            "avatar": member.avatar,
            "org_position": member.org_position,
            "work_unit": member.work_unit,
            "join_date": str(member.join_date) if member.join_date else None,
        } if member else None,
        "branch": {
            "id": branch.id,
            "name": branch.name,
            "leader_name": branch.leader_name,
            "leader_phone": branch.leader_phone,
        } if branch else None,
        "unread_messages": unread_count,
        "role": current_user.role.value,
    }


@router.get("/my-events")
async def get_my_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """我的活动记录 - 时间轴"""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        return []

    registrations = db.query(EventRegistration, Event).join(
        Event, EventRegistration.event_id == Event.id
    ).filter(
        EventRegistration.member_id == member.id
    ).order_by(Event.event_time.desc()).all()

    return [{
        "event_id": e.id, "event_title": e.title,
        "event_time": str(e.event_time), "location": e.location,
        "status": "已请假" if r.is_leave else ("已签到" if r.is_checked_in else "已报名"),
        "with_family": r.with_family, "family_count": r.family_count,
        "signed_up_at": str(r.signed_up_at) if r.signed_up_at else None,
        "check_in_time": str(r.check_in_time) if r.check_in_time else None,
    } for r, e in registrations]


@router.get("/my-social-infos")
async def get_my_social_infos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """我的社情民意"""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        return []

    infos = db.query(SocialInfo).filter(
        SocialInfo.author_id == member.id
    ).order_by(SocialInfo.created_at.desc()).all()

    return [{
        "id": i.id, "title": i.title,
        "status": status_labels.get(i.status.value if i.status else "pending", "待审核"),
        "created_at": str(i.created_at),
    } for i in infos]


@router.get("/my-scores")
async def get_my_scores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """我的履职积分（普通会员）"""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        return {"total": 0, "dimensions": {}, "records": []}

    records = db.query(ScoreRecord).filter(
        ScoreRecord.member_id == member.id,
        ScoreRecord.verified_score.isnot(None)
    ).all()

    dim_totals = {}
    for dim in ScoreDimension:
        dim_records = [r for r in records if r.dimension == dim]
        dim_totals[dim.value] = sum(r.verified_score for r in dim_records)

    return {
        "total": sum(dim_totals.values()),
        "dimensions": {k: v for k, v in dim_totals.items() if v > 0},
        "recent_records": [{
            "dimension": r.dimension.value,
            "reason": r.reason,
            "score": r.verified_score,
            "created_at": str(r.created_at)
        } for r in sorted(records, key=lambda x: x.created_at, reverse=True)[:20]]
    }


# ====== 消息中心 ======

@router.get("/messages")
async def get_messages(
    page: int = Query(1), size: int = Query(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """消息列表"""
    messages = db.query(Message).filter(
        Message.user_id == current_user.id
    ).order_by(Message.is_read.asc(), Message.created_at.desc()).offset(
        (page - 1) * size
    ).limit(size).all()

    return {
        "items": [{
            "id": m.id, "type": m.type, "title": m.title,
            "content": m.content, "link": m.link,
            "is_read": m.is_read,
            "created_at": str(m.created_at)
        } for m in messages],
        "page": page, "unread_count": db.query(Message).filter(
            Message.user_id == current_user.id, Message.is_read == False
        ).count()
    }


@router.post("/messages/{message_id}/read")
async def mark_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """标记消息已读"""
    msg = db.query(Message).filter(
        Message.id == message_id, Message.user_id == current_user.id
    ).first()
    if not msg:
        raise HTTPException(status_code=404)
    msg.is_read = True
    msg.read_at = datetime.now()
    db.commit()
    return {"success": True}


@router.post("/messages/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """全部已读"""
    db.query(Message).filter(
        Message.user_id == current_user.id, Message.is_read == False
    ).update({"is_read": True, "read_at": datetime.now()})
    db.commit()
    return {"success": True}


# 辅助函数：创建系统消息
def create_system_message(db: Session, user_id: int, title: str, content: str, link: str = None):
    msg = Message(user_id=user_id, type="system", title=title, content=content, link=link)
    db.add(msg)
    db.commit()


status_labels = {
    "pending": "待审核", "city_adopted": "市级录用",
    "province_adopted": "省级录用", "national_adopted": "全国录用",
    "rejected": "未录用"
}
