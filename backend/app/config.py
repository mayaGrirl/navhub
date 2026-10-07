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
    mail_provider: str = "log"
    mail_from: str = "noreply@example.com"
    mail_from_name: str = "NEXA"
    mail_from_address: str = ""
    mail_smtp_host: str = "smtp.gmail.com"
    mail_smtp_port: int = 465
    mail_smtp_encryption: str = "ssl"
    mail_smtp_user: str = ""
    mail_smtp_pass: str = ""
    mail_smtp_fallback: bool = True
    mail_smtp_timeout: int = 20
    mail_smtp_verify_peer: bool = True
    mail_smtp_163_host: str = "smtp.163.com"
    mail_smtp_163_port: int = 465
    mail_smtp_163_encryption: str = "ssl"
    mail_smtp_163_user: str = ""
    mail_smtp_163_pass: str = ""
    mail_smtp_163_from: str = ""
    mail_smtp_163_from_name: str = ""
    sendgrid_api_key: str = ""
    mailgun_api_key: str = ""
    mailgun_domain: str = ""
    mailgun_region: str = "us"
    aws_ses_key: str = ""
    aws_ses_secret: str = ""
    aws_ses_region: str = "us-east-1"
    notify_mail_default: bool = False
    mail_money_dm: bool = False


settings = Settings()
