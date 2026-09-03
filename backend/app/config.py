from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "MuleNet AML Risk Intelligence"
    API_V1_STR: str = "/api/v1"
    
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR.parent / "data"
    ARTIFACTS_DIR: Path = BASE_DIR / "artifacts"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/mule_net.db"
    
    # Graduated Thresholds
    TIER_LOW_MAX: float = 0.30
    TIER_MEDIUM_MAX: float = 0.60
    TIER_HIGH_MAX: float = 0.85
    
    class Config:
        env_file = ".env"

settings = Settings()
