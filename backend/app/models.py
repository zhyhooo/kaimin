from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Date,
    ForeignKey, Float, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    PUBLIC = "public"
    MEMBER = "member"
    CANDIDATE = "candidate"
    BRANCH_LEADER = "branch_leader"
    ORG_LEADER = "org_leader"
    SUPER_ADMIN = "super_admin"


class MemberStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"  # 待审核


# ============ 用户 & 会员 ============

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(11), unique=True, nullable=False, index=True, comment="手机号(加密存储)")
    password_hash = Column(String(256), nullable=True, comment="密码哈希(管理员登录用)")
    openid = Column(String(128), unique=True, nullable=True, comment="微信OpenID")
    unionid = Column(String(128), nullable=True, comment="微信UnionID")
    role = Column(SAEnum(UserRole), default=UserRole.PUBLIC, comment="用户角色")
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String(50), nullable=False, comment="姓名")
    id_card = Column(String(18), nullable=True, comment="身份证号(加密)")
    gender = Column(String(2), nullable=True, comment="性别")
    birth_date = Column(Date, nullable=True, comment="出生年月")
    avatar = Column(String(500), nullable=True, comment="头像URL")
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
    org_position = Column(String(100), nullable=True, comment="会内职务")
    work_unit = Column(String(200), nullable=True, comment="工作单位")
    work_position = Column(String(100), nullable=True, comment="工作职务")
    title = Column(String(100), nullable=True, comment="职称")
    education = Column(String(50), nullable=True, comment="学历")
    school = Column(String(200), nullable=True, comment="毕业院校及专业")
    specialty = Column(String(200), nullable=True, comment="专业特长")
    social_position = Column(String(200), nullable=True, comment="社会职务")
    native_place = Column(String(100), nullable=True, comment="籍贯")
    join_date = Column(Date, nullable=True, comment="入会时间")
    status = Column(SAEnum(MemberStatus), default=MemberStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", backref="member")
    branch = relationship("Branch", backref="members")


# ============ 组织架构 ============

class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="支部名称")
    parent_id = Column(Integer, ForeignKey("branches.id"), nullable=True, comment="上级(总支)")
    leader_name = Column(String(50), nullable=True, comment="主委姓名")
    leader_phone = Column(String(11), nullable=True, comment="主委电话")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    children = relationship("Branch", backref="parent", remote_side=[id])


# ============ 通知公告 ============

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="标题")
    content = Column(Text, nullable=False, comment="正文(富文本)")
    cover_image = Column(String(500), nullable=True, comment="封面图")
    attachments = Column(JSON, nullable=True, comment="附件列表[{name,url}]")
    external_link = Column(String(500), nullable=True, comment="外部链接")
    event_time = Column(DateTime, nullable=True, comment="关联时间")
    location = Column(String(200), nullable=True, comment="定位地址")
    scope_type = Column(String(20), default="all", comment="范围: all/branch/selected")
    scope_branch_ids = Column(JSON, nullable=True, comment="目标支部ID列表")
    scope_member_ids = Column(JSON, nullable=True, comment="目标会员ID列表")
    is_pinned = Column(Boolean, default=False)
    publish_time = Column(DateTime, nullable=True, comment="定时发布时间")
    expire_time = Column(DateTime, nullable=True, comment="过期时间")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="draft", comment="draft/published/expired")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class NotificationRead(Base):
    __tablename__ = "notification_reads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)


# ============ 活动管理 ============

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="活动标题")
    cover_image = Column(String(500), nullable=True)
    content = Column(Text, nullable=True, comment="详情(图文)")
    event_time = Column(DateTime, nullable=False, comment="活动时间")
    location = Column(String(200), nullable=False, comment="地点")
    max_participants = Column(Integer, nullable=True, comment="人数上限")
    signup_deadline = Column(DateTime, nullable=False, comment="报名截止时间")
    contact_person = Column(String(50), nullable=True, comment="联系人")
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True, comment="所属支部(NULL=全市)")
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    photos = Column(JSON, nullable=True, comment="活动照片")
    links = Column(JSON, nullable=True, comment="宣传链接")
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class EventRegistration(Base):
    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    with_family = Column(Boolean, default=False, comment="是否携带家属")
    family_count = Column(Integer, default=0, comment="家属人数")
    remark = Column(String(500), nullable=True, comment="备注")
    is_leave = Column(Boolean, default=False, comment="是否请假")
    leave_reason = Column(String(500), nullable=True)
    is_checked_in = Column(Boolean, default=False, comment="是否已签到")
    check_in_time = Column(DateTime, nullable=True)
    check_in_method = Column(String(20), nullable=True, comment="online/manual")
    signed_up_at = Column(DateTime, default=datetime.now)
    cancelled_at = Column(DateTime, nullable=True)


# ============ 积分系统 ============

class ScoreDimension(str, enum.Enum):
    POLITICAL = "political"        # 政治思想
    MEETING = "meeting"             # 会务活动
    PARTICIPATION = "participation" # 参政议政
    SOCIAL = "social"               # 社会服务
    PUBLICITY = "publicity"         # 宣传报道
    PERFORMANCE = "performance"     # 工作业绩


class ScoreRule(Base):
    __tablename__ = "score_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dimension = Column(SAEnum(ScoreDimension), nullable=False)
    activity_type = Column(String(100), nullable=False, comment="活动类型")
    score = Column(Float, nullable=False, comment="单次分值")
    max_score = Column(Float, nullable=True, comment="上限分值")
    period = Column(String(20), default="year", comment="year/quarter")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class ScoreRecord(Base):
    __tablename__ = "score_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    dimension = Column(SAEnum(ScoreDimension), nullable=False)
    self_score = Column(Float, default=0, comment="自评分")
    verified_score = Column(Float, nullable=True, comment="核定分")
    reason = Column(String(500), nullable=False, comment="事由")
    attachment = Column(String(500), nullable=True, comment="佐证附件")
    verifier_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


# ============ 社情民意 ============

class SocialInfoStatus(str, enum.Enum):
    PENDING = "pending"
    CITY_ADOPTED = "city_adopted"
    PROVINCE_ADOPTED = "province_adopted"
    NATIONAL_ADOPTED = "national_adopted"
    REJECTED = "rejected"


class SocialInfo(Base):
    __tablename__ = "social_infos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="标题")
    is_joint = Column(Boolean, default=False, comment="是否联名")
    content = Column(Text, nullable=False, comment="正文")
    attachment = Column(String(500), nullable=True, comment="附件URL")
    author_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    status = Column(SAEnum(SocialInfoStatus), default=SocialInfoStatus.PENDING)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ============ 阵地管理 ============

class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="阵地名称")
    photos = Column(JSON, nullable=True, comment="实景照片列表")
    address = Column(String(300), nullable=False)
    capacity = Column(Integer, nullable=True, comment="容纳人数")
    equipment = Column(JSON, nullable=True, comment="设备清单")
    open_time = Column(String(200), nullable=True, comment="开放时间")
    rules = Column(Text, nullable=True, comment="使用规定")
    contact = Column(String(100), nullable=True, comment="联系方式")
    qrcode = Column(String(500), nullable=True, comment="签到二维码")
    created_at = Column(DateTime, default=datetime.now)


class VenueBooking(Base):
    __tablename__ = "venue_bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    date = Column(Date, nullable=False)
    time_slot = Column(String(20), nullable=False, comment="上午/下午/晚上")
    purpose = Column(String(200), nullable=False)
    people_count = Column(Integer, nullable=False)
    contact_name = Column(String(50), nullable=False)
    contact_phone = Column(String(11), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="pending", comment="pending/approved/rejected")
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reject_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class DutySchedule(Base):
    __tablename__ = "duty_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False)
    date = Column(Date, nullable=False)
    time_slot = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_checked_in = Column(Boolean, default=False)
    check_in_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


# ============ 学习园地 ============

class LearningMaterial(Base):
    __tablename__ = "learning_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False, comment="分类: history/charter/theory/meeting/duty")
    content = Column(Text, nullable=True, comment="图文内容")
    cover_image = Column(String(500), nullable=True)
    file_url = Column(String(500), nullable=True, comment="PDF/视频URL")
    file_type = Column(String(20), nullable=True, comment="pdf/video/audio")
    tags = Column(JSON, nullable=True, comment="标签列表")
    is_pinned = Column(Boolean, default=False)
    is_required = Column(Boolean, default=False, comment="是否必读")
    view_count = Column(Integer, default=0)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="published")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class LearningRecord(Base):
    __tablename__ = "learning_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("learning_materials.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    duration_seconds = Column(Integer, default=0, comment="阅读时长(秒)")
    is_completed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)


# ============ 消息中心 ============

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False, comment="system/comment/like")
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    link = Column(String(500), nullable=True, comment="点击跳转路径")
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


# ============ 操作日志 ============

class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False, comment="操作类型")
    target_type = Column(String(50), nullable=True, comment="操作对象类型")
    target_id = Column(Integer, nullable=True, comment="操作对象ID")
    content = Column(Text, nullable=True, comment="操作内容摘要")
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
