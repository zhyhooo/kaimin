from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models import Branch, User, Member, UserRole
from app.auth import get_current_user, require_org_leader

router = APIRouter(prefix="/branches", tags=["组织架构"])


class BranchCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    leader_name: Optional[str] = None
    leader_phone: Optional[str] = None
    sort_order: int = 0


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    leader_name: Optional[str] = None
    leader_phone: Optional[str] = None
    sort_order: Optional[int] = None


@router.get("/")
async def list_branches(db: Session = Depends(get_db)):
    """获取所有支部列表（平铺）"""
    branches = db.query(Branch).order_by(Branch.sort_order).all()
    return [{
        "id": b.id, "name": b.name, "parent_id": b.parent_id,
        "leader_name": b.leader_name, "leader_phone": b.leader_phone,
        "sort_order": b.sort_order,
        "member_count": db.query(Member).filter(Member.branch_id == b.id).count()
    } for b in branches]


@router.get("/tree")
async def get_branch_tree(db: Session = Depends(get_db)):
    """获取组织架构树"""
    branches = db.query(Branch).order_by(Branch.sort_order).all()

    # 构建树
    root_nodes = [b for b in branches if b.parent_id is None]

    def build_tree(branch):
        children = [build_tree(c) for c in branches if c.parent_id == branch.id]
        member_count = db.query(Member).filter(Member.branch_id == branch.id).count()
        return {
            "id": branch.id,
            "name": branch.name,
            "leader_name": branch.leader_name,
            "member_count": member_count,
            "children": children
        }

    return [build_tree(root) for root in root_nodes]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_branch(
    data: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    """新建支部（总支委员以上）"""
    existing = db.query(Branch).filter(Branch.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="支部名称已存在")

    # 验证父级存在
    if data.parent_id:
        parent = db.query(Branch).filter(Branch.id == data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父级支部不存在")

    branch = Branch(
        name=data.name, parent_id=data.parent_id,
        leader_name=data.leader_name, leader_phone=data.leader_phone,
        sort_order=data.sort_order
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return {"id": branch.id, "name": branch.name, "message": "创建成功"}


@router.put("/{branch_id}")
async def update_branch(
    branch_id: int,
    data: BranchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    """编辑支部"""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="支部不存在")

    if data.name is not None:
        existing = db.query(Branch).filter(Branch.name == data.name, Branch.id != branch_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="支部名称已存在")
        branch.name = data.name
    if data.parent_id is not None:
        if data.parent_id == branch_id:
            raise HTTPException(status_code=400, detail="不能将自己设为父级")
        branch.parent_id = data.parent_id
    if data.leader_name is not None:
        branch.leader_name = data.leader_name
    if data.leader_phone is not None:
        branch.leader_phone = data.leader_phone
    if data.sort_order is not None:
        branch.sort_order = data.sort_order

    db.commit()
    return {"id": branch.id, "name": branch.name, "message": "更新成功"}


@router.delete("/{branch_id}")
async def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_org_leader)
):
    """删除支部（仅限无子节点和无会员的支部）"""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="支部不存在")

    # 检查是否有子支部
    children = db.query(Branch).filter(Branch.parent_id == branch_id).count()
    if children > 0:
        raise HTTPException(status_code=400, detail="该支部下还有子支部，请先删除子支部")

    # 检查是否有会员
    member_count = db.query(Member).filter(Member.branch_id == branch_id).count()
    if member_count > 0:
        raise HTTPException(status_code=400, detail=f"该支部下还有 {member_count} 名会员，请先转移会员")

    db.delete(branch)
    db.commit()
    return {"message": "删除成功"}


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
