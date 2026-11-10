from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Supabase
    supabase_url: str
    supabase_service_role_key: str

    # External AI APIs
    groq_api_key: str = ""
    huggingface_api_key: str = ""
    replicate_api_token: str = ""

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Dev
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    environment: str = "development"
    # Auth is strict by default. Setting AUTH_REQUIRED=false only has an effect
    # when ENVIRONMENT=development (see app/auth.py: bypass_allowed).
    auth_required: bool = True

    # Procedural music engine
    soundfont_path: str = "assets/FluidR3Mono_GM.sf3"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
