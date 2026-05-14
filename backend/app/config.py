from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "开明向阳 - 掌上民进之家"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "kaimin"
    DB_PASSWORD: str = ""
    DB_NAME: str = "kaimin"

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # WeChat
    WECHAT_APPID: str = ""
    WECHAT_SECRET: str = ""

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_TARGET: str = ""  # 市委会信息处邮箱

    # 腾讯云 COS（文件存储）
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_REGION: str = ""   # 如 ap-guangzhou, ap-shanghai
    COS_BUCKET: str = ""   # 格式: bucketname-1234567890

    @property
    def DATABASE_URL(self) -> str:
        if self.DEBUG and not self.DB_PASSWORD:
            return "sqlite:///./kaimin_test.db"
        return f"mysql+pymysql://{self.DB_USER}:{quote_plus(self.DB_PASSWORD)}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
