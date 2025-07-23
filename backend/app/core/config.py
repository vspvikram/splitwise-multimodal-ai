from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    app_name: str = "Splitwise Backend API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API settings
    api_v1_str: str = "/api/v1"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: List[str] = ["image/jpeg", "image/jpg", "image/png"]
    
    # CORS settings
    backend_cors_origins: List[str] = [
        "http://localhost:3000",  # React dev server
        "http://localhost:8501",  # Streamlit default port
        "http://127.0.0.1:8501",
    ]
    
    class Config:
        env_file = ".env"
        # Allow extra fields so LLM env vars don't cause validation errors
        extra = "ignore"


settings = Settings()