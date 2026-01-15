"""
Utility functions - logging, formatting, helpers
"""
import logging
from datetime import datetime


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Setup structured logging for the bot."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger('musicbot')


def format_duration(ms: int) -> str:
    """Format milliseconds to MM:SS or HH:MM:SS."""
    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_progress_bar(current_ms: int, total_ms: int, length: int = 15) -> str:
    """Create text progress bar."""
    if total_ms == 0:
        return "░" * length
    
    progress = current_ms / total_ms
    filled = int(length * progress)
    empty = length - filled
    
    return "█" * filled + "░" * empty


def truncate(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
