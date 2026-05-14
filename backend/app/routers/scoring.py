from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models import ScoreRecord, ScoreRule, ScoreDimension, User, Member, UserRole
from app.auth import get_current_user, require_leader, require_org_leader

router = APIRouter(prefix="/scoring", tags=["积分考察"])


class ManualScoreCreate(BaseModel):
    member_id: int
    dimension: str  # political/meeting/participation/social/publicity/performance
    reason: str
    self_score: float = 0
    verified_score: float


class ThoughtReport(BaseModel):
    content: Optional[str] = None
    attachment_url: Optional[str] = None


@router.get("/candidate/{member_id}")
async def get_candidate_scoreboard(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """积极分子积分看板 - 总分+六维得分"""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    # 获取规则中的目标总分（默认90）
    target_score = 90.0

    dimensions = {}
    for dim in ScoreDimension:
        records = db.query(ScoreRecord).filter(
            ScoreRecord.member_id == member_id,
            ScoreRecord.dimension == dim,
            ScoreRecord.verified_score.isnot(None)
        ).all()
        total = sum(r.verified_score for r in records)
        # 获取该维度的上限分
        rule = db.query(ScoreRule).filter(
            ScoreRule.dimension == dim, ScoreRule.is_active == True
        ).first()
        max_s = rule.max_score if rule else 0
        dimensions[dim.value] = {
            "label": dim_map.get(dim.value, dim.value),
            "score": total,
            "max_score": max_s,
            "is_reached": total >= max_s if max_s > 0 else False
        }

    total = sum(d["score"] for d in dimensions.values())
    return {
        "member_id": member_id,
        "member_name": member.name,
        "total_score": total,
        "target_score": target_score,
        "progress_pct": round(total / target_score * 100, 1) if target_score > 0 else 0,
        "dimensions": dimensions
    }


@router.get("/candidate/{member_id}/records")
async def get_score_records(
    member_id: int,
    db: Session = Depends(get_db)
):
    """积分明细列表"""
    records = db.query(ScoreRecord).filter(
        ScoreRecord.member_id == member_id
    ).order_by(ScoreRecord.created_at.desc()).all()

    return [{
        "id": r.id,
        "dimension": dim_map.get(r.dimension.value if r.dimension else "", ""),
        "reason": r.reason,
        "self_score": r.self_score,
        "verified_score": r.verified_score,
        "verifier": r.verifier_id,
        "created_at": str(r.created_at)
    } for r in records]


@router.post("/manual")
async def manual_add_score(
    data: ManualScoreCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """手动核分（组织委员）"""
    try:
        dim = ScoreDimension(data.dimension)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的维度: {data.dimension}")

    record = ScoreRecord(
        member_id=data.member_id, dimension=dim,
        self_score=data.self_score, verified_score=data.verified_score,
        reason=data.reason, verifier_id=current_user.id,
        verified_at=datetime.now()
    )
    db.add(record)
    db.commit()
    return {"id": record.id, "message": "手动核分成功"}


@router.get("/rules")
async def get_score_rules(db: Session = Depends(get_db)):
    rules = db.query(ScoreRule).filter(ScoreRule.is_active == True).all()
    return [{"id": r.id, "dimension": r.dimension.value, "activity_type": r.activity_type,
             "score": r.score, "max_score": r.max_score, "period": r.period} for r in rules]


@router.post("/rules")
async def create_score_rule(
    dimension: str, activity_type: str, score: float, max_score: Optional[float] = None,
    period: str = "year",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    try:
        dim = ScoreDimension(dimension)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效维度: {dimension}")

    rule = ScoreRule(dimension=dim, activity_type=activity_type, score=score,
                     max_score=max_score, period=period)
    db.add(rule)
    db.commit()
    return {"id": rule.id, "message": "规则创建成功"}


@router.post("/candidate/{member_id}/thought-report")
async def submit_thought_report(
    member_id: int,
    data: ThoughtReport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """思想汇报提交"""
    # 自动记分：政治思想维度
    dim = ScoreDimension.POLITICAL
    record = ScoreRecord(
        member_id=member_id, dimension=dim,
        self_score=5, verified_score=5,  # 默认5分，后续可配置
        reason="提交思想汇报",
        verifier_id=None, verified_at=datetime.now()
    )
    db.add(record)
    db.commit()
    return {"id": record.id, "message": "思想汇报提交成功，已自动记分"}


@router.get("/candidate/{member_id}/tasks")
async def get_task_suggestions(
    member_id: int,
    db: Session = Depends(get_db)
):
    """任务清单 - 根据未达标项智能推送"""
    suggestions = []
    for dim in ScoreDimension:
        rule = db.query(ScoreRule).filter(
            ScoreRule.dimension == dim, ScoreRule.is_active == True
        ).first()
        if not rule or not rule.max_score:
            continue
        records = db.query(ScoreRecord).filter(
            ScoreRecord.member_id == member_id,
            ScoreRecord.dimension == dim,
            ScoreRecord.verified_score.isnot(None)
        ).all()
        current = sum(r.verified_score for r in records)
        if current < rule.max_score and rule.score > 0:
            needed = int((rule.max_score - current) / rule.score + 0.5)
            suggestions.append({
                "dimension": dim_map.get(dim.value, dim.value),
                "current": current, "max": rule.max_score,
                "suggestion": f"还需完成 {needed} 次「{rule.activity_type}」"
            })
    return suggestions


# 维度中文映射
dim_map = {
    "political": "政治思想",
    "meeting": "会务活动",
    "participation": "参政议政",
    "social": "社会服务",
    "publicity": "宣传报道",
    "performance": "工作业绩"
}
