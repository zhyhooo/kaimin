"""种子数据 - 创建测试管理员账号"""
import sys
sys.path.insert(0, '.')

from app.database import engine, SessionLocal, Base
from app.models import User, UserRole, Branch, Member
from app.auth import pwd_context
from datetime import datetime

# 确保表存在
from app import models
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 检查是否已有管理员
existing = db.query(User).filter(
    User.phone == "13800138000",
    User.role == UserRole.SUPER_ADMIN
).first()

if existing:
    # 更新密码（如果还没有设置）
    if not existing.password_hash:
        existing.password_hash = pwd_context.hash("admin123")
        db.commit()
    print("测试管理员已存在:")
    print(f"  ID: {existing.id}, 手机号: {existing.phone}, 角色: {existing.role.value}, 密码: admin123")
else:
    # 创建测试管理员
    admin = User(
        phone="13800138000",
        password_hash=pwd_context.hash("admin123"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        last_login=datetime.now()
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"测试管理员已创建:")
    print(f"  ID: {admin.id}, 手机号: {admin.phone}, 角色: {admin.role.value}, 密码: admin123")

# 同时创建一个 org_leader 测试账号
org_leader = db.query(User).filter(
    User.phone == "13900139000",
    User.role == UserRole.ORG_LEADER
).first()

if org_leader:
    if not org_leader.password_hash:
        org_leader.password_hash = pwd_context.hash("admin123")
        db.commit()
    print(f"\n总支委员测试账号已存在: {org_leader.phone}, 密码: admin123")
else:
    org_leader = User(
        phone="13900139000",
        password_hash=pwd_context.hash("admin123"),
        role=UserRole.ORG_LEADER,
        is_active=True
    )
    db.add(org_leader)
    db.commit()
    print(f"\n总支委员测试账号已创建: 13900139000, 密码: admin123")

db.close()
print("\n种子数据初始化完成!")
print("管理后台测试账号:")
print("  超级管理员: 13800138000 / admin123")
print("  总支委员:   13900139000 / admin123")
