import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Anthropic
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Spotify
    spotify_client_id: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    spotify_client_secret: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")

    # Last.fm
    lastfm_api_key: str = os.getenv("LASTFM_API_KEY", "")

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "lineagepassword")

    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # MusicBrainz
    musicbrainz_user_agent: str = os.getenv(
        "MUSICBRAINZ_USER_AGENT", "Lineage/1.0 (lineage@example.com)"
    )

    # App
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    default_seed_depth: int = 2


settings = Settings()
