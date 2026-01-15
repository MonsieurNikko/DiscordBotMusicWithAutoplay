"""
Utility functions - logging, formatting, helpers
"""
import logging
import re
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


def extract_genre_from_text(text: str) -> str | None:
    """
    Attempt to extract genre/style keywords from a string (title/author).
    Returns the first matched genre key or None.
    """
    if not text:
        return None
        
    text_lower = text.lower()
    
    # Keyword map: Genre key -> List of keywords
    genre_keywords = {
        'remix': ['remix', 'mix', 'mashup', 'dj', 'club', 'vinahouse', 'edm'],
        'lofi': ['lofi', 'lo-fi', 'chill', 'relax', 'study', 'beats'],
        'acoustic': ['acoustic', 'unplugged', 'guitar', 'piano', 'cover'],
        'nightcore': ['nightcore', 'sped up', 'speed up'],
        'live': ['live performance', 'live at', 'concert'],
        'rap': ['rap', 'hip hop', 'hiphop', 'freestyle'],
        'karaoke': ['karaoke', 'instrumental', 'beat', 'off vocal']
    }
    
    for genre, keywords in genre_keywords.items():
        for kw in keywords:
            # Check for keyword as a whole word boundary to avoid false positives
            # e.g. "grape" shouldn't match "rap"
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                return genre
                
    return None
