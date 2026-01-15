"""
Track Filter - Validates tracks against configured rules
"""
from bot.config import MAX_DURATION_SECONDS, BLOCKED_KEYWORDS


def is_valid_track(title: str, duration_ms: int, is_stream: bool) -> tuple[bool, str]:
    """
    Check if a track passes all filters.
    
    Returns:
        (is_valid, reason) - reason is empty if valid, else explains why rejected
    """
    title_lower = title.lower()
    
    # Check if live stream
    if is_stream:
        return False, "❌ Không hỗ trợ live stream"
    
    # Check duration
    duration_sec = duration_ms / 1000
    if duration_sec > MAX_DURATION_SECONDS:
        minutes = int(duration_sec / 60)
        return False, f"❌ Video quá dài ({minutes} phút > 90 phút)"
    
    # Check blocked keywords
    for keyword in BLOCKED_KEYWORDS:
        if keyword in title_lower:
            return False, f"❌ Video bị chặn (chứa '{keyword}')"
    
    return True, ""


def filter_search_results(tracks: list, recent_ids: set[str]) -> list:
    """
    Filter a list of tracks, removing invalid ones.
    
    Args:
        tracks: List of wavelink.Playable tracks
        recent_ids: Set of video IDs to skip (anti-repeat)
    
    Returns:
        Filtered list of valid tracks
    """
    valid_tracks = []
    
    for track in tracks:
        # Skip if recently played
        if track.identifier in recent_ids:
            continue
        
        # Check against filters
        is_valid, _ = is_valid_track(
            title=track.title,
            duration_ms=track.length,
            is_stream=track.is_stream
        )
        
        if is_valid:
            valid_tracks.append(track)
    
    return valid_tracks
