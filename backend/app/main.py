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
from app.routers import auth, members, branches, notifications, events, scoring, social_info, venues, learning, public, profile, users

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
app.include_router(auth.router)
app.include_router(members.router)
app.include_router(branches.router)
app.include_router(notifications.router)
app.include_router(events.router)
app.include_router(scoring.router)
app.include_router(social_info.router)
app.include_router(venues.router)
app.include_router(learning.router)
app.include_router(public.router)
app.include_router(profile.router)
app.include_router(users.router)


@app.get("/")
@limiter.exempt
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health")
@limiter.exempt
async def health():
    return {"status": "ok"}
