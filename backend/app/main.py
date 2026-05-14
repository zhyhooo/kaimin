from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.database import engine
from app import models
from app.routers.auth import router as auth_router
from app.routers.members import router as members_router
from app.routers.branches import router as branches_router
from app.routers.notifications import router as notifications_router
from app.routers.events import router as events_router
from app.routers.scoring import router as scoring_router
from app.routers.social_info import router as social_info_router
from app.routers.venues import router as venues_router
from app.routers.learning import router as learning_router
from app.routers.public import router as public_router
from app.routers.profile import router as profile_router
from app.routers.users import router as users_router

settings = get_settings()

# 创建所有表
models.Base.metadata.create_all(bind=engine)

# 限流器
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 托管 admin-web 静态文件
admin_path = Path(__file__).parent.parent.parent / "admin-web"
if admin_path.exists():
    app.mount("/admin", StaticFiles(directory=str(admin_path), html=True), name="admin")

# 注册路由
app.include_router(auth_router)
app.include_router(members_router)
app.include_router(branches_router)
app.include_router(notifications_router)
app.include_router(events_router)
app.include_router(scoring_router)
app.include_router(social_info_router)
app.include_router(venues_router)
app.include_router(learning_router)
app.include_router(public_router)
app.include_router(profile_router)
app.include_router(users_router)


@app.get("/")
@limiter.exempt
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health")
@limiter.exempt
async def health():
    return {"status": "ok"}
