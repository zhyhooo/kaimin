from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models import Notification, NotificationRead, User, Member, UserRole
from app.auth import get_current_user, require_leader

router = APIRouter(prefix="/notifications", tags=["通知公告"])


class NotificationCreate(BaseModel):
    title: str
    content: str
    cover_image: Optional[str] = None
    attachments: Optional[list] = None
    external_link: Optional[str] = None
    event_time: Optional[datetime] = None
    location: Optional[str] = None
    scope_type: str = "all"
    scope_branch_ids: Optional[list] = None
    scope_member_ids: Optional[list] = None
    is_pinned: bool = False
    publish_time: Optional[datetime] = None
    expire_time: Optional[datetime] = None


@router.get("/")
async def list_notifications(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通知列表 - 根据发布范围过滤"""
    now = datetime.now()
    from sqlalchemy import or_
    query = db.query(Notification).filter(
        Notification.status == "published",
        or_(Notification.publish_time <= now, Notification.publish_time.is_(None))
    )

    # 根据用户角色和支部过滤
    if current_user.role == UserRole.PUBLIC:
        return []

    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if current_user.role in (UserRole.MEMBER, UserRole.CANDIDATE, UserRole.BRANCH_LEADER):
        query = query.filter(
            (Notification.scope_type == "all") |
            ((Notification.scope_type == "branch") & Notification.scope_branch_ids.contains(
                [member.branch_id] if member else [])
            ) |
            ((Notification.scope_type == "selected") & Notification.scope_member_ids.contains(
                [member.id] if member else [])
            )
        )

    notifications = query.order_by(
        Notification.is_pinned.desc(),
        Notification.publish_time.desc()
    ).all()

    # 检查已读状态
    result = []
    for n in notifications:
        read_record = db.query(NotificationRead).filter(
            NotificationRead.notification_id == n.id,
            NotificationRead.user_id == current_user.id
        ).first()
        result.append({
            "id": n.id, "title": n.title, "content": n.content, "cover_image": n.cover_image,
            "event_time": str(n.event_time) if n.event_time else None,
            "location": n.location, "is_pinned": n.is_pinned,
            "publish_time": str(n.publish_time),
            "is_read": read_record.is_read if read_record else False
        })
    return result


@router.get("/{notification_id}")
async def get_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通知详情 - 标记已读"""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    # 记录已读
    read_record = db.query(NotificationRead).filter(
        NotificationRead.notification_id == notification_id,
        NotificationRead.user_id == current_user.id
    ).first()
    if not read_record:
        read_record = NotificationRead(
            notification_id=notification_id, user_id=current_user.id,
            is_read=True, read_at=datetime.now()
        )
        db.add(read_record)
    else:
        read_record.is_read = True
        read_record.read_at = datetime.now()
    db.commit()

    return {
        "id": notification.id, "title": notification.title,
        "content": notification.content, "cover_image": notification.cover_image,
        "attachments": notification.attachments, "external_link": notification.external_link,
        "event_time": str(notification.event_time) if notification.event_time else None,
        "location": notification.location, "publish_time": str(notification.publish_time),
        "author": notification.author_id
    }


@router.get("/{notification_id}/read-status")
async def get_read_status(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """干部端查看已读/未读名单"""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404)

    # 获取目标用户列表
    reads = db.query(NotificationRead).filter(
        NotificationRead.notification_id == notification_id
    ).all()
    read_user_ids = {r.user_id for r in reads if r.is_read}

    # 获取所有目标会员
    members = db.query(Member).all()
    unread = [{"id": m.id, "name": m.name} for m in members if m.user_id not in read_user_ids]
    read = [{"id": m.id, "name": m.name} for m in members if m.user_id in read_user_ids]

    return {"read": read, "unread": unread, "read_count": len(read), "unread_count": len(unread)}


@router.post("/")
async def create_notification(
    data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """创建通知"""
    # 支部主委只能发本支部
    if current_user.role == UserRole.BRANCH_LEADER:
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        data.scope_type = "branch"
        data.scope_branch_ids = [member.branch_id] if member else []

    now = datetime.now()
    if not data.publish_time:
        data.publish_time = now
    notification = Notification(
        **data.dict(),
        author_id=current_user.id,
        status="published" if data.publish_time <= now else "draft"
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return {"id": notification.id, "message": "发布成功"}


@router.put("/{notification_id}")
async def update_notification(
    notification_id: int,
    data: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """更新通知"""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(notification, key, value)
    db.commit()
    return {"id": notification.id, "message": "更新成功"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """删除通知"""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    db.delete(notification)
    db.commit()
    return {"message": "已删除"}
