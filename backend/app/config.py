from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/deal_copilot.db"
    upload_dir: str = "./data/uploads"
    llm_provider: str = "mimo"
    llm_default_model: str = "mimo-v2.6-flash"
    llm_complex_model: str = "mimo-v2.6-pro"
    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_api_key: str = ""
    demo_mode: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def ensure_dirs(self) -> None:
        Path(self.upload_dir).mkdir(parents=True, exist_ok=True)
        Path("./data").mkdir(parents=True, exist_ok=True)

settings = Settings()
