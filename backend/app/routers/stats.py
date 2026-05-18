from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Event, EventRegistration, SocialInfo, User
from app.auth import get_current_user

router = APIRouter(prefix="/stats", tags=["数据统计"])


@router.get("/dashboard")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """仪表盘统计数据"""
    now = datetime.now()

    # 最近 6 个月活动参与率（按月）
    event_monthly = []
    for i in range(5, -1, -1):
        month_start = datetime(now.year, now.month, 1) - timedelta(days=30 * i)
        if month_start.month == 12:
            month_end = datetime(month_start.year + 1, 1, 1)
        else:
            month_end = datetime(month_start.year, month_start.month + 1, 1)

        # 该月活动总数
        event_count = db.query(Event).filter(
            Event.event_time >= month_start, Event.event_time < month_end
        ).count()

        # 该月报名人次
        event_ids = db.query(Event.id).filter(
            Event.event_time >= month_start, Event.event_time < month_end
        ).subquery()
        signup_count = db.query(EventRegistration).filter(
            EventRegistration.event_id.in_(event_ids),
            EventRegistration.cancelled_at.is_(None)
        ).count()

        label = f"{month_start.month}月"
        rate = round(signup_count / event_count, 1) if event_count > 0 else 0
        event_monthly.append({"label": label, "events": event_count, "signups": signup_count, "rate": rate})

    # 最近 6 个月社情民意提交量
    info_monthly = []
    for i in range(5, -1, -1):
        month_start = datetime(now.year, now.month, 1) - timedelta(days=30 * i)
        if month_start.month == 12:
            month_end = datetime(month_start.year + 1, 1, 1)
        else:
            month_end = datetime(month_start.year, month_start.month + 1, 1)

        count = db.query(SocialInfo).filter(
            SocialInfo.created_at >= month_start, SocialInfo.created_at < month_end
        ).count()
        info_monthly.append({"label": f"{month_start.month}月", "count": count})

    return {"event_monthly": event_monthly, "info_monthly": info_monthly}