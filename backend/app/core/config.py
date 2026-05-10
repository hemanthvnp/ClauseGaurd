from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'ClauseGuard'
    api_v1_prefix: str = '/api/v1'
    database_url: str = Field('postgresql://clauseguard:clauseguard@localhost:5432/clauseguard', alias='DATABASE_URL')
    redis_url: str = Field('redis://localhost:6379/0', alias='REDIS_URL')
    anthropic_api_key: str | None = Field(default=None, alias='ANTHROPIC_API_KEY')
    groq_api_key: str | None = Field(default=None, alias='GROQ_API_KEY')
    aws_access_key_id: str | None = Field(default=None, alias='AWS_ACCESS_KEY_ID')
    aws_secret_access_key: str | None = Field(default=None, alias='AWS_SECRET_ACCESS_KEY')
    aws_s3_bucket: str = Field('clauseguard-docs', alias='AWS_S3_BUCKET')
    s3_endpoint_url: str | None = Field(default=None, alias='S3_ENDPOINT_URL')
    jwt_secret: str = Field('change-me', alias='JWT_SECRET')
    jwt_algorithm: str = Field('HS256', alias='JWT_ALGORITHM')
    jwt_expire_minutes: int = Field(60, alias='JWT_EXPIRE_MINUTES')
    access_token_expire_minutes: int = Field(60, alias='ACCESS_TOKEN_EXPIRE_MINUTES')
    refresh_token_expire_days: int = Field(14, alias='REFRESH_TOKEN_EXPIRE_DAYS')
    max_upload_mb: int = Field(50, alias='MAX_UPLOAD_MB')
    cors_origins: str = Field('http://localhost:5173', alias='CORS_ORIGINS')
    processing_storage_path: str = Field('./storage', alias='PROCESSING_STORAGE_PATH')
    spacy_model: str = Field('en_core_web_trf', alias='SPACY_MODEL')
    bert_model_name: str = Field('', alias='BERT_MODEL_NAME')
    claude_model: str = Field('claude-sonnet-4-6', alias='CLAUDE_MODEL')
    enable_demo_seed: bool = Field(True, alias='ENABLE_DEMO_SEED')
    huggingface_api_key: str | None = Field(default=None, alias='HUGGINGFACE_API_KEY')

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
