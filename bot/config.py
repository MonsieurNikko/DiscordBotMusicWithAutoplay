"""
Discord Music Bot - Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = "p"

# Lavalink
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "localhost")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")
LAVALINK_SSL = os.getenv("LAVALINK_SSL", "false").lower() == "true"

# Bot Settings
DEFAULT_VOLUME = 50
MAX_DURATION_SECONDS = 90 * 60  # 90 minutes
IDLE_TIMEOUT_SECONDS = 300  # 5 minutes

# Recommendation Settings
HISTORY_LIMIT = 10  # Token learning from last N songs
ANTI_REPEAT_LIMIT = 20  # Don't repeat last N songs
MAX_SAME_CHANNEL = 3  # Max songs from same channel in recommendations

# Blocked keywords (lowercase) - Block hoàn toàn, không cho phát
BLOCKED_KEYWORDS = [
    "shorts", "short", "#shorts",
    "compilation", "megamix",
    "full album", "album",
    "live", "concert", "trực tiếp",
    "loop", "1 hour", "10 hours",
    "8d", "8d audio",
]

# MV keywords (lowercase) - Hạn chế trong autoplay, vẫn cho phát khi user request trực tiếp
# Mục đích: tránh các video MV có phần cinematic/phim không có nhạc
MV_KEYWORDS = [
    "mv", "m/v", "official mv", "official m/v",
    "official music video", "music video",
    "official video", 
    "phim ngắn", "short film",
    "behind the scenes", "making of",
    "teaser", "trailer",
]

