from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import Event, Branch, Member, User
from app.auth import get_current_user

router = APIRouter(prefix="/public", tags=["公众展示"])


@router.get("/organization")
async def get_organization(db: Session = Depends(get_db)):
    """组织介绍 - 无需登录"""
    branches = db.query(Branch).order_by(Branch.sort_order).all()
    root = [b for b in branches if b.parent_id is None]

    return {
        "intro": {
            "name": "中国民主促进会杭州市富阳区总支部",
            "short_name": "富阳民进总支",
            "description": "中国民主促进会（简称民进）是以从事教育文化出版工作的高中级知识分子为主的、具有政治联盟性质的政党，是同中国共产党通力合作的中国特色社会主义参政党。",
            "founded": "1945年12月30日",
            "headquarters": "北京"
        },
        "leadership": [
            {"title": "主委", "name": b.leader_name or ""}
            for b in root
        ],
        "branches": [
            {"id": b.id, "name": b.name, "member_count": db.query(Member).filter(Member.branch_id == b.id).count()}
            for b in branches if b.parent_id is not None
        ]
    }


@router.get("/news")
async def get_public_news(
    page: int = Query(1), size: int = Query(10),
    db: Session = Depends(get_db)
):
    """公开动态 - 精选活动报道"""
    events = db.query(Event).filter(
        Event.status == "published"
    ).order_by(Event.event_time.desc()).offset((page - 1) * size).limit(size).all()

    return {
        "items": [{
            "id": e.id, "title": e.title,
            "cover_image": e.cover_image,
            "event_time": str(e.event_time),
            "summary": e.content[:200] if e.content else ""
        } for e in events],
        "page": page, "size": size
    }


@router.get("/news/{event_id}")
async def get_public_news_detail(event_id: int, db: Session = Depends(get_db)):
    """公开动态详情 - 会员姓名脱敏"""
    event = db.query(Event).filter(Event.id == event_id, Event.status == "published").first()
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    # 脱敏处理：正文中会员姓名替换为"张**"
    import re
    content = event.content or ""
    # 简单脱敏：两个汉字姓名替换为"姓*"，三个字替换为"姓**"
    content = re.sub(r'(?<=[，。\s])[\u4e00-\u9fa5]{2,3}(?=[，。\s同志])',
                     lambda m: m.group()[0] + '*' * (len(m.group()) - 1), content)

    return {
        "id": event.id, "title": event.title,
        "cover_image": event.cover_image,
        "event_time": str(event.event_time),
        "location": event.location,
        "content": content
    }


@router.get("/guide")
async def get_membership_guide():
    """入会指南"""
    return {
        "conditions": [
            "拥护中国民主促进会章程",
            "具有大学本科及以上学历（或中级及以上职称）",
            "从事教育、文化、出版、科技等相关工作",
            "在社会上有一定影响力和代表性",
            "年龄一般在45周岁以下（特殊情况可适当放宽）"
        ],
        "process": [
            "1. 提交入会申请书",
            "2. 总支初审",
            "3. 确定为入会积极分子（考察期6-12个月）",
            "4. 参加组织活动并累计积分",
            "5. 总支审议推荐",
            "6. 市委会审批",
            "7. 正式入会"
        ],
        "contact": {
            "phone": "0571-XXXXXXXX",
            "address": "杭州市富阳区富春街道XX路XX号",
            "office_hours": "工作日 9:00-17:00"
        }
    }
