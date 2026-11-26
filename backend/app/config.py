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
    # Fallback model provider (team-conversation spec 07, requirement 8): Google Gemini free tier
    gemini_api_key: str = ""
    # Deployment tooling only (ship-it spec 13); never used by the running app
    render_api_key: str = ""
    # Sound-quality spike (spec 05): sample-set downloads and GPU notebooks. Not used at runtime by the app.
    hf_token: str = ""
    kaggle_username: str = ""
    kaggle_key: str = ""
    modal_token_id: str = ""
    modal_token_secret: str = ""

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Dev
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    environment: str = "development"
    # Auth is strict by default. Setting AUTH_REQUIRED=false only has an effect
    # when ENVIRONMENT=development (see app/auth.py: bypass_allowed).
    auth_required: bool = True

    # Procedural music engine
    soundfont_path: str = "assets/MuseScore_General.sf3"
    # Recorded CC0 instruments (VSCO-2 CE / VCSL as SFZ), fetched at build time; empty = FluidSynth only
    sfz_dir: str = "assets/sfz"

    # Frankenstein (spec 14): Frank's two Hugging Face Spaces and the free outside services.
    # Every one is optional: a missing key turns its feature into a plain "I can't do that yet".
    spaces_token: str = ""                   # HF token that may call (and deploy) Frank's own Spaces
    ears_space: str = "Udeibom/frank-ears"
    hands_space: str = "Udeibom/frank-hands"
    groove_humanizer_enabled: bool = False
    groove_humanizer_timeout_s: float = 180.0
    freesound_api_key: str = ""
    jamendo_client_id: str = ""
    jamendo_client_secret: str = ""          # accepted but unused: searching and streaming need only the client id
    exa_api_key: str = ""
    firecrawl_api_key: str = ""
    datamuse_api_key: str = ""               # needed from 1 Feb 2027; keyless before then
    # Monthly caps, set well under the free allowances (services/budget.py). One named song costs at most
    # 1 Exa search and 3 Firecrawl page reads, and each song is researched once for everyone.
    exa_monthly_limit: int = 150
    firecrawl_monthly_limit: int = 120

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
