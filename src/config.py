import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DB_URI = "postgresql://neondb_owner:npg_rcHJQu7Ei8tT@ep-steep-wave-adv9vu73-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


class Config:
    """Base configuration for Vertikal Agent Flask app"""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key_change_in_prod")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", DEFAULT_DB_URI)

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_AGENT_MODEL = os.environ.get("OPENAI_AGENT_MODEL", "gpt-4o-mini")
    OPENAI_SYSTEM_PROMPT = os.environ.get(
        "OPENAI_SYSTEM_PROMPT",
        (
            "You are the Vertikal Agent AI assistant. "
            "Collect key customer details, offer helpful guidance, and note follow-up actions."
        ),
    )

    # LiveKit voice agent configuration
    LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
    LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")
    LIVEKIT_AGENT_ID = os.environ.get("LIVEKIT_AGENT_ID")
    LIVEKIT_AGENT_TEMPLATE = os.environ.get("LIVEKIT_AGENT_TEMPLATE")
    LIVEKIT_STATIC_TOKEN = os.environ.get("LIVEKIT_STATIC_TOKEN")
    LIVEKIT_STATIC_ROOM = os.environ.get("LIVEKIT_STATIC_ROOM")
    LIVEKIT_STATIC_IDENTITY = os.environ.get("LIVEKIT_STATIC_IDENTITY")

    # Shared engine + session for non-Flask contexts (e.g., LiveKit workers)
    engine = create_engine(SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


# Default configuration selection
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
