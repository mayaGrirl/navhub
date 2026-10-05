from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://nav:navpass@127.0.0.1:3306/navhub?charset=utf8mb4"
    redis_url: str = "redis://127.0.0.1:6379/0"
    secret_key: str = "change-this-secret"
    admin_gate: str = ""
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me-now"
    proxy_pool_url: str = ""
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    free_monthly_quota: int = 5
    vip_monthly_quota: int = 100


settings = Settings()
