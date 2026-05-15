from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models import SocialInfo, SocialInfoStatus, User, Member, ScoreRecord, ScoreDimension, UserRole
from app.auth import get_current_user, require_leader, require_member
from app.config import get_settings
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.responses import StreamingResponse
import openpyxl
from io import BytesIO

router = APIRouter(prefix="/social-info", tags=["社情民意"])


class SocialInfoCreate(BaseModel):
    title: str
    is_joint: bool = False
    content: str
    attachment: Optional[str] = None


class AdoptRequest(BaseModel):
    level: str  # city/province/national


@router.post("/")
async def submit_social_info(
    data: SocialInfoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """提交社情民意信息"""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        raise HTTPException(status_code=400, detail="请先完善会员信息")

    info = SocialInfo(
        title=data.title, is_joint=data.is_joint,
        content=data.content, attachment=data.attachment,
        author_id=member.id
    )
    db.add(info)
    db.commit()
    db.refresh(info)

    # 自动发送邮件
    await send_email_async(info)

    # 自动记分
    auto_score = ScoreRecord(
        member_id=member.id, dimension=ScoreDimension.PARTICIPATION,
        self_score=3, verified_score=3,
        reason=f"提交社情民意: {data.title}",
        verified_at=datetime.now()
    )
    db.add(auto_score)
    db.commit()

    return {"id": info.id, "message": "提交成功"}


async def send_email_async(info: SocialInfo):
    """发送邮件至市委会指定邮箱"""
    settings = get_settings()
    if not settings.EMAIL_TARGET or not settings.SMTP_HOST:
        return  # 未配置则跳过

    msg = MIMEMultipart()
    msg["Subject"] = f"社情民意: {info.title}"
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.EMAIL_TARGET
    msg.attach(MIMEText(f"标题: {info.title}\n联名: {'是' if info.is_joint else '否'}\n正文:\n{info.content}", "plain", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=True
        )
        # 标记已发送
        from app.database import SessionLocal
        db = SessionLocal()
        db.query(SocialInfo).filter(SocialInfo.id == info.id).update({"email_sent": True, "email_sent_at": datetime.now()})
        db.commit()
        db.close()
    except Exception:
        pass  # 邮件发送失败不阻塞提交流程


@router.get("/my")
async def my_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """个人提交历史"""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        return []

    infos = db.query(SocialInfo).filter(
        SocialInfo.author_id == member.id
    ).order_by(SocialInfo.created_at.desc()).all()

    return [{"id": i.id, "title": i.title, "is_joint": i.is_joint,
             "status": i.status.value if i.status else "pending",
             "created_at": str(i.created_at)} for i in infos]


@router.get("/admin")
async def admin_list(
    status: Optional[str] = Query(None),
    branch_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """后台信息列表"""
    query = db.query(SocialInfo)
    if status:
        query = query.filter(SocialInfo.status == status)
    if branch_id:
        query = query.join(Member).filter(Member.branch_id == branch_id)

    infos = query.order_by(SocialInfo.created_at.desc()).all()
    result = []
    for i in infos:
        author = db.query(Member).filter(Member.id == i.author_id).first()
        branch = author.branch if author else None
        result.append({
            "id": i.id, "title": i.title, "is_joint": i.is_joint,
            "author_name": author.name if author else "",
            "branch_name": branch.name if branch else "",
            "status": i.status.value if i.status else "",
            "email_sent": i.email_sent,
            "created_at": str(i.created_at)
        })
    return result


@router.post("/{info_id}/adopt")
async def adopt_info(
    info_id: int,
    data: AdoptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """录录用标记"""
    info = db.query(SocialInfo).filter(SocialInfo.id == info_id).first()
    if not info:
        raise HTTPException(status_code=404)

    level_map = {"city": SocialInfoStatus.CITY_ADOPTED, "province": SocialInfoStatus.PROVINCE_ADOPTED,
                 "national": SocialInfoStatus.NATIONAL_ADOPTED}
    if data.level not in level_map:
        raise HTTPException(status_code=400, detail="无效录用级别")

    info.status = level_map[data.level]
    # 额外记分
    bonus = {"city": 5, "province": 10, "national": 20}
    auto_score = ScoreRecord(
        member_id=info.author_id, dimension=ScoreDimension.PARTICIPATION,
        self_score=bonus.get(data.level, 5), verified_score=bonus.get(data.level, 5),
        reason=f"社情民意被{level_display.get(data.level, data.level)}录用: {info.title}",
        verified_at=datetime.now()
    )
    db.add(auto_score)
    db.commit()
    return {"message": f"已标记为{level_display[data.level]}"}


@router.delete("/{info_id}")
async def delete_social_info(
    info_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """删除社情民意"""
    info = db.query(SocialInfo).filter(SocialInfo.id == info_id).first()
    if not info:
        raise HTTPException(status_code=404, detail="社情民意不存在")
    db.delete(info)
    db.commit()
    return {"message": "已删除"}


@router.get("/leaderboard")
async def get_leaderboard(
    period: str = Query("year"),
    db: Session = Depends(get_db)
):
    """信息风云榜"""
    infos = db.query(SocialInfo).all()

    # 个人榜
    person_stats = {}
    for i in infos:
        pid = i.author_id
        if pid not in person_stats:
            author = db.query(Member).filter(Member.id == pid).first()
            person_stats[pid] = {"name": author.name if author else "", "submitted": 0, "adopted": 0}
        person_stats[pid]["submitted"] += 1
        if i.status not in (SocialInfoStatus.PENDING, SocialInfoStatus.REJECTED):
            person_stats[pid]["adopted"] += 1

    ranking = sorted(person_stats.values(), key=lambda x: x["adopted"], reverse=True)
    return {"period": period, "ranking": ranking}


@router.get("/export")
async def export_social_infos(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    """导出Excel（含录用标记）"""
    infos = db.query(SocialInfo).order_by(SocialInfo.created_at.desc()).all()
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "社情民意"
    ws.append(["标题", "作者", "支部", "联名", "状态", "提交时间", "邮件已发"])
    for i in infos:
        author = db.query(Member).filter(Member.id == i.author_id).first()
        ws.append([i.title, author.name if author else "", author.branch.name if author and author.branch else "",
                   "是" if i.is_joint else "否", level_display.get(i.status.value if i.status else "pending", "待审核"),
                   str(i.created_at), "是" if i.email_sent else "否"])

    output = BytesIO(); wb.save(output); output.seek(0)
    return StreamingResponse(output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=social_infos.xlsx"})


level_display = {"pending": "待审核", "city_adopted": "市级录用", "province_adopted": "省级录用",
                 "national_adopted": "全国录用", "rejected": "未录用"}
