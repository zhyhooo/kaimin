from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Branch, User, Member
from app.auth import get_current_user

router = APIRouter(prefix="/branches", tags=["组织架构"])


@router.get("/tree")
async def get_branch_tree(db: Session = Depends(get_db)):
    """获取组织架构树"""
    branches = db.query(Branch).order_by(Branch.sort_order).all()

    # 构建树
    root_nodes = [b for b in branches if b.parent_id is None]

    def build_tree(branch):
        children = [build_tree(c) for c in branches if c.parent_id == branch.id]
        return {
            "id": branch.id,
            "name": branch.name,
            "leader_name": branch.leader_name,
            "children": children
        }

    return [build_tree(root) for root in root_nodes]


@router.get("/{branch_id}/members")
async def get_branch_members(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定支部的会员列表（卡片式）"""
    members = db.query(Member).filter(
        Member.branch_id == branch_id
    ).order_by(Member.name).all()

    return [{
        "id": m.id,
        "name": m.name,
        "avatar": m.avatar,
        "org_position": m.org_position,
        "work_unit": m.work_unit,
    } for m in members]
