from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models import LearningMaterial, LearningRecord, User, Member, UserRole
from app.auth import get_current_user, require_leader

router = APIRouter(prefix="/learning", tags=["学习园地"])


class MaterialCreate(BaseModel):
    title: str
    category: str  # history/charter/theory/meeting/duty
    content: Optional[str] = None
    cover_image: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None  # pdf/video/audio
    tags: Optional[list] = None
    is_pinned: bool = False
    is_required: bool = False


CATEGORIES = {
    "history": "会史会章",
    "charter": "章程制度",
    "theory": "统战理论",
    "meeting": "重要会议精神",
    "duty": "履职知识"
}


@router.get("/")
async def list_materials(
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """分类资料库"""
    query = db.query(LearningMaterial).filter(LearningMaterial.status == "published")

    if category:
        query = query.filter(LearningMaterial.category == category)
    if keyword:
        query = query.filter(LearningMaterial.title.like(f"%{keyword}%"))
    if tag:
        query = query.filter(LearningMaterial.tags.contains([tag]))

    materials = query.order_by(
        LearningMaterial.is_pinned.desc(),
        LearningMaterial.created_at.desc()
    ).all()

    return [{
        "id": m.id, "title": m.title,
        "category": m.category,
        "category_label": CATEGORIES.get(m.category, m.category),
        "cover_image": m.cover_image, "file_type": m.file_type,
        "tags": m.tags, "is_pinned": m.is_pinned,
        "is_required": m.is_required, "view_count": m.view_count,
        "created_at": str(m.created_at)
    } for m in materials]


@router.get("/{material_id}")
async def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """资料详情 - 记录阅读"""
    material = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404)

    material.view_count += 1
    db.commit()

    # 记录阅读行为
    if current_user.id > 0:
        record = LearningRecord(
            material_id=material_id, user_id=current_user.id,
            started_at=datetime.now()
        )
        db.add(record)
        db.commit()

    return {
        "id": material.id, "title": material.title,
        "category": material.category, "content": material.content,
        "cover_image": material.cover_image, "file_url": material.file_url,
        "file_type": material.file_type, "tags": material.tags,
        "is_required": material.is_required,
        "view_count": material.view_count
    }


@router.post("/")
async def create_material(
    data: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """上传学习资料（干部端）"""
    material = LearningMaterial(
        **data.dict(), author_id=current_user.id
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return {"id": material.id, "message": "资料发布成功"}


@router.put("/{material_id}")
async def update_material(
    material_id: int,
    data: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """编辑资料"""
    material = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404)
    for field, value in data.dict(exclude_unset=True).items():
        setattr(material, field, value)
    db.commit()
    return {"message": "更新成功"}


@router.post("/{material_id}/toggle-pin")
async def toggle_pin(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """置顶/取消置顶"""
    material = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404)
    material.is_pinned = not material.is_pinned
    db.commit()
    return {"is_pinned": material.is_pinned}


@router.post("/{material_id}/archive")
async def archive_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """下架资料"""
    material = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404)
    material.status = "archived"
    db.commit()
    return {"message": "已下架"}


@router.get("/records/my")
async def my_learning_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """我的学习记录"""
    records = db.query(LearningRecord).filter(
        LearningRecord.user_id == current_user.id
    ).order_by(LearningRecord.started_at.desc()).limit(50).all()

    return [{
        "id": r.id,
        "material_title": db.query(LearningMaterial).filter(LearningMaterial.id == r.material_id).first().title,
        "duration_seconds": r.duration_seconds,
        "is_completed": r.is_completed,
        "started_at": str(r.started_at)
    } for r in records]


@router.post("/records/{record_id}/complete")
async def complete_reading(
    record_id: int,
    duration_seconds: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """完成阅读"""
    record = db.query(LearningRecord).filter(
        LearningRecord.id == record_id,
        LearningRecord.user_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404)
    record.is_completed = True
    record.duration_seconds = duration_seconds
    record.completed_at = datetime.now()
    db.commit()

    # 如果是必读资料，自动加学习积分
    material = db.query(LearningMaterial).filter(LearningMaterial.id == record.material_id).first()
    if material and material.is_required:
        from app.models import ScoreRecord, ScoreDimension
        member = db.query(Member).filter(Member.user_id == current_user.id).first()
        if member:
            # 每日上限检查（简化：检查今日是否已有同材料积分）
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            existing = db.query(ScoreRecord).filter(
                ScoreRecord.member_id == member.id,
                ScoreRecord.reason.like(f"%完成必读: {material.title}%"),
                ScoreRecord.created_at >= today_start
            ).first()
            if not existing:
                sr = ScoreRecord(
                    member_id=member.id, dimension=ScoreDimension.POLITICAL,
                    self_score=2, verified_score=2,
                    reason=f"完成必读: {material.title}",
                    verified_at=datetime.now()
                )
                db.add(sr)
                db.commit()

    return {"message": "已记录"}
