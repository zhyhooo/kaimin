from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.database import get_db
from app.models import Venue, VenueBooking, DutySchedule, User, Member, UserRole
from app.auth import get_current_user, require_leader

router = APIRouter(prefix="/venues", tags=["阵地管理"])


class BookingCreate(BaseModel):
    venue_id: int
    date: date
    time_slot: str  # 上午/下午/晚上
    purpose: str
    people_count: int
    contact_name: str
    contact_phone: str


class DutyCreate(BaseModel):
    venue_id: int
    date: date
    time_slot: str
    user_id: int


# ====== 阵地详情 ======

@router.get("/{venue_id}")
async def get_venue(venue_id: int, db: Session = Depends(get_db)):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="阵地不存在")
    return {
        "id": venue.id, "name": venue.name,
        "photos": venue.photos, "address": venue.address,
        "capacity": venue.capacity, "equipment": venue.equipment,
        "open_time": venue.open_time, "rules": venue.rules,
        "contact": venue.contact
    }


# ====== 预约日历 ======

@router.get("/{venue_id}/calendar")
async def get_calendar(
    venue_id: int,
    year: int = Query(None), month: int = Query(None),
    db: Session = Depends(get_db)
):
    """月视图预约日历 - 仅显示已预约状态"""
    now = datetime.now()
    y = year or now.year
    m = month or now.month

    bookings = db.query(VenueBooking).filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.status == "approved",
        VenueBooking.date >= date(y, m, 1),
        VenueBooking.date < date(y if m < 12 else y + 1, m + 1 if m < 12 else 1, 1)
    ).all()

    slots = {}
    for b in bookings:
        key = str(b.date)
        if key not in slots:
            slots[key] = []
        slots[key].append(b.time_slot)

    return {"year": y, "month": m, "booked_slots": slots}


# ====== 预约申请 ======

@router.post("/{venue_id}/book")
async def create_booking(
    venue_id: int,
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    venue = db.query(Venue).filter(Venue.id == venue_id).first()
    if not venue:
        raise HTTPException(status_code=404, detail="阵地不存在")

    # 检查冲突
    existing = db.query(VenueBooking).filter(
        VenueBooking.venue_id == venue_id,
        VenueBooking.date == data.date,
        VenueBooking.time_slot == data.time_slot,
        VenueBooking.status == "approved"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该时段已被预约")

    booking = VenueBooking(
        venue_id=venue_id, date=data.date, time_slot=data.time_slot,
        purpose=data.purpose, people_count=data.people_count,
        contact_name=data.contact_name, contact_phone=data.contact_phone,
        user_id=current_user.id if current_user.id > 0 else None,
        status="pending"
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"id": booking.id, "message": "预约申请已提交，等待审批"}


# ====== 审批流 ======

@router.get("/bookings/pending")
async def list_pending_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    bookings = db.query(VenueBooking).filter(
        VenueBooking.status == "pending"
    ).order_by(VenueBooking.created_at.desc()).all()
    return [{
        "id": b.id, "venue_id": b.venue_id, "date": str(b.date),
        "time_slot": b.time_slot, "purpose": b.purpose,
        "people_count": b.people_count, "contact_name": b.contact_name,
        "contact_phone": b.contact_phone, "created_at": str(b.created_at)
    } for b in bookings]


@router.post("/bookings/{booking_id}/approve")
async def approve_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    booking = db.query(VenueBooking).filter(VenueBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404)
    if booking.status != "pending":
        raise HTTPException(status_code=400, detail="该预约已处理")

    # 再次检查冲突
    conflict = db.query(VenueBooking).filter(
        VenueBooking.venue_id == booking.venue_id,
        VenueBooking.date == booking.date,
        VenueBooking.time_slot == booking.time_slot,
        VenueBooking.status == "approved",
        VenueBooking.id != booking_id
    ).first()
    if conflict:
        raise HTTPException(status_code=400, detail="该时段已被其他预约占用")

    booking.status = "approved"
    booking.approver_id = current_user.id
    db.commit()
    return {"message": "审批通过，时段已锁定"}


@router.post("/bookings/{booking_id}/reject")
async def reject_booking(
    booking_id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    booking = db.query(VenueBooking).filter(VenueBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404)
    booking.status = "rejected"
    booking.reject_reason = reason
    booking.approver_id = current_user.id
    db.commit()
    return {"message": "已驳回", "reason": reason}


# ====== 值班管理 ======

@router.post("/{venue_id}/duty")
async def create_duty_schedule(
    venue_id: int,
    data: DutyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_leader)
):
    duty = DutySchedule(
        venue_id=venue_id, date=data.date,
        time_slot=data.time_slot, user_id=data.user_id
    )
    db.add(duty)
    db.commit()
    db.refresh(duty)
    return {"id": duty.id, "message": "排班已发布"}


@router.get("/{venue_id}/duty")
async def list_duty_schedule(
    venue_id: int,
    year: int = Query(None), month: int = Query(None),
    db: Session = Depends(get_db)
):
    now = datetime.now()
    y = year or now.year; m = month or now.month
    duties = db.query(DutySchedule).filter(
        DutySchedule.venue_id == venue_id,
        DutySchedule.date >= date(y, m, 1),
        DutySchedule.date < date(y if m < 12 else y + 1, m + 1 if m < 12 else 1, 1)
    ).order_by(DutySchedule.date.asc()).all()
    return [{
        "id": d.id, "date": str(d.date), "time_slot": d.time_slot,
        "user_id": d.user_id, "is_checked_in": d.is_checked_in,
        "check_in_time": str(d.check_in_time) if d.check_in_time else None
    } for d in duties]


@router.post("/{venue_id}/checkin")
async def checkin(
    venue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """值班扫码签到"""
    today = date.today()
    duty = db.query(DutySchedule).filter(
        DutySchedule.venue_id == venue_id,
        DutySchedule.date == today,
        DutySchedule.user_id == current_user.id,
        DutySchedule.is_checked_in == False
    ).first()
    if not duty:
        raise HTTPException(status_code=400, detail="今天没有您的值班安排或已签到")
    duty.is_checked_in = True
    duty.check_in_time = datetime.now()
    db.commit()
    return {"message": "签到成功", "time": str(datetime.now())}
