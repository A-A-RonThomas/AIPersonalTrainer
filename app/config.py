from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    hevy_api_key: str
    anthropic_api_key: str

    model_config = {"env_file": ".env"}


settings = Settings()
