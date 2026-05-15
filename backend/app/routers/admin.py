from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
from app.auth import get_current_user
from app.models import User, UserRole, Member

router = APIRouter(prefix="/api/templates", tags=["管理后台模板"])

# 模板目录
TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "admin-web" / "templates"

# 栏目权限映射
SECTION_PERMISSIONS = {
    "dashboard":  None,  # 所有登录用户可见
    "users":      ["super_admin"],
    "members":    ["super_admin", "org_leader"],
    "branches":   ["super_admin", "org_leader"],
    "events":     ["super_admin", "org_leader", "branch_leader"],
    "social":     ["super_admin", "org_leader"],
    "venues":     ["super_admin", "org_leader"],
    "scoring":    ["super_admin", "org_leader"],
    "notifications": ["super_admin", "org_leader"],
    "settings":   ["super_admin"],
}


@router.get("/{section}", response_class=HTMLResponse)
async def get_template(
    section: str,
    current_user: User = Depends(get_current_user)
):
    """按权限下发栏目模板"""
    # 校验栏目存在
    if section not in SECTION_PERMISSIONS:
        raise HTTPException(status_code=404, detail="栏目不存在")

    # 校验权限
    allowed_roles = SECTION_PERMISSIONS[section]
    if allowed_roles is not None:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(status_code=403, detail="无权限访问该栏目")

    # 读取模板文件
    template_path = TEMPLATE_DIR / f"{section}.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="模板文件不存在")

    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))