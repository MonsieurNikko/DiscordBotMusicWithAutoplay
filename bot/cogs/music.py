"""
Music Cog - All music commands
"""
import asyncio
import random
import logging
import discord
from discord.ext import commands
import wavelink

# Setup logger for this cog
logger = logging.getLogger('music')

from bot.config import (
    DEFAULT_VOLUME, 
    MAX_DURATION_SECONDS,
    IDLE_TIMEOUT_SECONDS,
)
from bot.filters import is_valid_track, filter_search_results, is_likely_mv


class Music(commands.Cog):
    """Music commands for playing YouTube audio."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Per-guild state
        self.autoplay_enabled: dict[int, bool] = {}  # Default: True
        self.loop_mode: dict[int, str] = {}  # "off", "track", "queue"
        self._idle_tasks: dict[int, asyncio.Task] = {}
        self._recent_ids: dict[int, list[str]] = {}  # Tránh lặp bài
        self._next_autoplay: dict[int, wavelink.Playable] = {}  # Bài autoplay đã prefetch

    # ... existing methods ...

    
    def get_autoplay(self, guild_id: int) -> bool:
        """Get autoplay status for guild (default: True)."""
        return self.autoplay_enabled.get(guild_id, True)
    
    def get_loop_mode(self, guild_id: int) -> str:
        """Get loop mode for guild (default: off)."""
        return self.loop_mode.get(guild_id, "off")
    
    # ==================== EVENTS ====================
    
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Called when a track starts playing."""
        player = payload.player
        track = payload.track
        
        if not player or not player.guild:
            return
        
        guild_id = player.guild.id
        
        # Log track start
        logger.info(f"[PLAYING] Guild {guild_id}: '{track.title}' by {track.author} ({track.length // 1000}s)")
        
        # Lưu video_id để tránh lặp khi autoplay
        self._add_recent_id(guild_id, track.identifier)
        
        # Send now playing message
        if hasattr(player, 'text_channel') and player.text_channel:
            embed = self._create_now_playing_embed(track)
            await player.text_channel.send(embed=embed)
        
        # Cancel idle timer
        if guild_id in self._idle_tasks:
            self._idle_tasks[guild_id].cancel()
        
        # Nếu đây là bài cuối trong queue và autoplay ON, prefetch và hiển thị bài tiếp theo
        if not player.queue and self.get_autoplay(guild_id):
            await self._prefetch_and_notify(player, track)
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Called when a track ends."""
        player = payload.player
        
        if not player or not player.guild:
            return
        
        guild_id = player.guild.id
        track_title = payload.track.title if payload.track else "Unknown"
        
        # Log track end with reason
        logger.info(f"[TRACK_END] Guild {guild_id}: '{track_title}' - Reason: {payload.reason}")
        
        # Only handle natural track endings - not replacements, stops, or skips
        # Only handle natural track endings or force stops (skips)
        # "replaced" means we played another track manually, so don't autoplay
        if payload.reason == "replaced":
            logger.debug(f"[SKIP] Guild {guild_id}: Ignoring track end (reason: {payload.reason})")
            return
        
        logger.info(f"[FINISHED] Guild {guild_id}: Track finished ({payload.reason}), checking next action...")
        
        # Handle loop modes - Only on natural finish
        loop = self.get_loop_mode(guild_id)
        if loop == "track" and payload.track and payload.reason == "finished":
            logger.info(f"[LOOP_TRACK] Guild {guild_id}: Replaying same track")
            await player.play(payload.track)
            return
        
        # Check if queue has more tracks
        if player.queue:
            next_track = player.queue.get()
            logger.info(f"[QUEUE] Guild {guild_id}: Playing next from queue: '{next_track.title}'")
            await player.play(next_track)
            return
        
        # Custom Autoplay logic
        if self.get_autoplay(guild_id):
            logger.info(f"[AUTOPLAY] Guild {guild_id}: Autoplay enabled, getting next track...")
            await self._do_autoplay(player)
            return
        else:
            logger.info(f"[AUTOPLAY_OFF] Guild {guild_id}: Autoplay is disabled")
        
        # No autoplay or no tracks available, start idle timer
        logger.info(f"[IDLE] Guild {guild_id}: Starting idle timer ({IDLE_TIMEOUT_SECONDS}s)")
        self._start_idle_timer(player)
    
    async def _do_autoplay(self, player: wavelink.Player):
        """Lấy bài tiếp theo từ YouTube Radio Mix hoặc dùng bài đã prefetch."""
        if not player.guild:
            return
        
        guild_id = player.guild.id
        
        # Kiểm tra nếu đã có bài prefetch
        if guild_id in self._next_autoplay:
            chosen = self._next_autoplay.pop(guild_id)
            logger.info(f"[AUTOPLAY] Guild {guild_id}: Dùng bài đã prefetch: '{chosen.title}'")
            
            try:
                self._add_recent_id(guild_id, chosen.identifier)
                await player.play(chosen)
                
                if hasattr(player, 'text_channel') and player.text_channel:
                    embed = discord.Embed(
                        title="🔄 Autoplay",
                        description=f"**{chosen.title}**",
                        color=discord.Color.purple()
                    )
                    embed.add_field(name="Channel", value=chosen.author, inline=True)
                    await player.text_channel.send(embed=embed)
                return
            except Exception as e:
                logger.error(f"[AUTOPLAY] Guild {guild_id}: Lỗi phát bài prefetch: {e}")
                # Fallback sang search mới
        
        # Không có prefetch hoặc prefetch fail, search mới
        if not player.current:
            logger.warning(f"[AUTOPLAY] Guild {guild_id}: Không có bài hiện tại để tìm gợi ý")
            self._start_idle_timer(player)
            return
            
        video_id = player.current.identifier
        current_title = player.current.title
        
        logger.info(f"[AUTOPLAY] Guild {guild_id}: Tìm bài tiếp theo cho '{current_title}'")
        
        # Lấy danh sách bài đã phát gần đây
        recent_ids = set(self._recent_ids.get(guild_id, []))
        recent_ids.add(video_id)  # Thêm bài hiện tại
        
        # Thử YouTube Radio Mix trước
        try:
            # YouTube Radio Mix URL
            mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
            logger.info(f"[AUTOPLAY] Guild {guild_id}: Đang load YouTube Mix...")
            
            results = await wavelink.Playable.search(mix_url)
            
            if results and len(results) > 1:
                # Lọc bỏ bài hiện tại và các bài đã phát
                non_mv_tracks = []  # Ưu tiên
                mv_tracks = []      # Fallback
                
                for track in results[1:]:  # Bỏ bài đầu (bài hiện tại)
                    if track.identifier not in recent_ids:
                        # Kiểm tra tên giống bài hiện tại → bỏ qua
                        if self._is_similar_title(current_title, track.title):
                            logger.debug(f"[AUTOPLAY] Skip bài tên giống: '{track.title}'")
                            continue
                        
                        # Kiểm tra filter (shorts, live, quá dài)
                        is_valid, _ = is_valid_track(
                            title=track.title,
                            duration_ms=track.length,
                            is_stream=track.is_stream
                        )
                        if is_valid:
                            # Phân loại: MV hay không
                            if is_likely_mv(track.title):
                                mv_tracks.append(track)
                            else:
                                non_mv_tracks.append(track)
                
                # Ưu tiên bài không phải MV, nếu không có thì dùng MV
                valid_tracks = non_mv_tracks if non_mv_tracks else mv_tracks
                
                if valid_tracks:
                    # Lấy thông tin genre/language của bài hiện tại
                    source_info = self._detect_genre_language(
                        current_title, 
                        player.current.author if player.current else ""
                    )
                    
                    # Tính điểm cho mỗi track và sắp xếp theo điểm giảm dần
                    scored_tracks = []
                    for track in valid_tracks[:10]:  # Chỉ xét 10 bài đầu
                        score = self._calculate_similarity_score(source_info, track.title, track.author)
                        scored_tracks.append((track, score))
                    
                    # Sắp xếp theo điểm giảm dần
                    scored_tracks.sort(key=lambda x: x[1], reverse=True)
                    
                    # Chọn ngẫu nhiên từ top 3 bài điểm cao nhất để vẫn có sự đa dạng
                    top_tracks = [t[0] for t in scored_tracks[:3]]
                    chosen = random.choice(top_tracks) if top_tracks else valid_tracks[0]
                    
                    # Log điểm của bài được chọn
                    chosen_score = next((s for t, s in scored_tracks if t == chosen), 0)
                    logger.info(f"[AUTOPLAY] Guild {guild_id}: Đã chọn từ Mix: '{chosen.title}' (score={chosen_score})")
                    
                    # Lưu vào recent_ids để tránh lặp
                    self._add_recent_id(guild_id, chosen.identifier)
                    
                    await player.play(chosen)
                    
                    if hasattr(player, 'text_channel') and player.text_channel:
                        embed = discord.Embed(
                            title="🔄 Autoplay (YouTube Mix)",
                            description=f"**{chosen.title}**",
                            color=discord.Color.purple()
                        )
                        embed.add_field(name="Channel", value=chosen.author, inline=True)
                        await player.text_channel.send(embed=embed)
                    return
                    
        except Exception as e:
            logger.warning(f"[AUTOPLAY] Guild {guild_id}: YouTube Mix thất bại: {e}")
        
        # Fallback: Tìm kiếm thông thường
        logger.info(f"[AUTOPLAY] Guild {guild_id}: Fallback sang search...")
        
        fallback_queries = [
            f"{current_title} similar songs",
            f"{player.current.author} music" if player.current.author else None,
        ]
        fallback_queries = [q for q in fallback_queries if q]
        
        for query in fallback_queries:
            try:
                results = await wavelink.Playable.search(f"ytsearch:{query}")
                if not results:
                    continue
                
                # Lọc kết quả
                valid = filter_search_results(results[:10], recent_ids)
                if valid:
                    chosen = random.choice(valid[:3])
                    self._add_recent_id(guild_id, chosen.identifier)
                    
                    logger.info(f"[AUTOPLAY] Guild {guild_id}: Đã chọn từ search: '{chosen.title}'")
                    await player.play(chosen)
                    
                    if hasattr(player, 'text_channel') and player.text_channel:
                        embed = discord.Embed(
                            title="🔄 Autoplay",
                            description=f"**{chosen.title}**",
                            color=discord.Color.purple()
                        )
                        await player.text_channel.send(embed=embed)
                    return
                    
            except Exception as e:
                logger.error(f"[AUTOPLAY] Guild {guild_id}: Search thất bại: {e}")
                continue
        
        # Không tìm được bài nào
        logger.warning(f"[AUTOPLAY] Guild {guild_id}: Không tìm được bài tiếp theo")
        if hasattr(player, 'text_channel') and player.text_channel:
            await player.text_channel.send("🔇 Autoplay: Không tìm được bài phù hợp.")
        
        self._start_idle_timer(player)
    
    async def _prefetch_and_notify(self, player: wavelink.Player, current_track: wavelink.Playable):
        """Prefetch bài autoplay tiếp theo và thông báo cho user."""
        if not player.guild:
            return
        
        guild_id = player.guild.id
        video_id = current_track.identifier
        
        logger.info(f"[PREFETCH] Guild {guild_id}: Đang prefetch bài tiếp theo...")
        
        # Lấy danh sách bài đã phát gần đây
        recent_ids = set(self._recent_ids.get(guild_id, []))
        recent_ids.add(video_id)
        
        try:
            # YouTube Radio Mix URL
            mix_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
            results = await wavelink.Playable.search(mix_url)
            
            if results and len(results) > 1:
                # Lọc bỏ bài hiện tại và các bài đã phát
                non_mv_tracks = []  # Ưu tiên
                mv_tracks = []      # Fallback
                
                for track in results[1:]:
                    if track.identifier not in recent_ids:
                        # Kiểm tra tên giống bài hiện tại → bỏ qua
                        if self._is_similar_title(current_track.title, track.title):
                            continue
                        
                        is_valid, _ = is_valid_track(
                            title=track.title,
                            duration_ms=track.length,
                            is_stream=track.is_stream
                        )
                        if is_valid:
                            if is_likely_mv(track.title):
                                mv_tracks.append(track)
                            else:
                                non_mv_tracks.append(track)
                
                # Ưu tiên bài không phải MV
                valid_tracks = non_mv_tracks if non_mv_tracks else mv_tracks
                
                if valid_tracks:
                    # Chọn ngẫu nhiên từ 5 bài đầu
                    chosen = random.choice(valid_tracks[:5])
                    self._next_autoplay[guild_id] = chosen
                    
                    logger.info(f"[PREFETCH] Guild {guild_id}: Đã prefetch: '{chosen.title}'")
                    
                    # Thông báo bài tiếp theo
                    if hasattr(player, 'text_channel') and player.text_channel:
                        embed = discord.Embed(
                            title="🎵 Bài cuối trong Queue",
                            description=(
                                f"Đang phát: **{current_track.title}**\n\n"
                                f"⏭️ **Tiếp theo (Autoplay):** {chosen.title}"
                            ),
                            color=discord.Color.orange()
                        )
                        if chosen.artwork:
                            embed.set_thumbnail(url=chosen.artwork)
                        await player.text_channel.send(embed=embed)
                    return
            
            # Fallback: search
            query = f"{current_track.title} similar songs"
            results = await wavelink.Playable.search(f"ytsearch:{query}")
            if results:
                valid = filter_search_results(results[:10], recent_ids)
                if valid:
                    chosen = random.choice(valid[:3])
                    self._next_autoplay[guild_id] = chosen
                    
                    logger.info(f"[PREFETCH] Guild {guild_id}: Đã prefetch (search): '{chosen.title}'")
                    
                    if hasattr(player, 'text_channel') and player.text_channel:
                        embed = discord.Embed(
                            title="🎵 Bài cuối trong Queue",
                            description=(
                                f"Đang phát: **{current_track.title}**\n\n"
                                f"⏭️ **Tiếp theo (Autoplay):** {chosen.title}"
                            ),
                            color=discord.Color.orange()
                        )
                        await player.text_channel.send(embed=embed)
                    return
                    
        except Exception as e:
            logger.error(f"[PREFETCH] Guild {guild_id}: Lỗi: {e}")
        
        # Không prefetch được
        logger.warning(f"[PREFETCH] Guild {guild_id}: Không tìm được bài để prefetch")
    
    def _add_recent_id(self, guild_id: int, video_id: str):
        """Thêm video_id vào danh sách đã phát để tránh lặp."""
        if guild_id not in self._recent_ids:
            self._recent_ids[guild_id] = []
        
        self._recent_ids[guild_id].append(video_id)
        # Giữ tối đa 20 bài gần nhất
        if len(self._recent_ids[guild_id]) > 20:
            self._recent_ids[guild_id].pop(0)
    
    def _is_similar_title(self, title1: str, title2: str) -> bool:
        """
        Kiểm tra 2 tên bài có giống nhau/quá tương tự không.
        Trả về True nếu giống → cần bỏ qua.
        """
        import re
        
        def clean_title(title: str) -> str:
            """Loại bỏ ký tự đặc biệt và chuẩn hóa."""
            # Loại bỏ phần trong ngoặc và dấu đặc biệt
            title = re.sub(r'\([^)]*\)', '', title)  # (official mv), (lyrics)
            title = re.sub(r'\[[^\]]*\]', '', title)  # [official video]
            title = re.sub(r'[^\w\s]', '', title)  # Dấu đặc biệt
            title = title.lower().strip()
            # Loại bỏ các từ phổ biến (bao gồm remix, cover, etc)
            common_words = [
                'official', 'mv', 'music', 'video', 'audio', 'lyric', 'lyrics', 
                'hd', '4k', 'visualizer', 'vietsub', 'engsub',
                'remix', 'cover', 'karaoke', 'instrumental', 'acoustic',
                'live', 'version', 'ver', 'edit', 'extended', 'radio',
                'nightcore', 'slowed', 'reverb', 'bass', 'boosted',
                'pt', 'dj', 'ft', 'feat', 'prod'
            ]
            words = title.split()
            words = [w for w in words if w not in common_words]
            return ' '.join(words)
        
        clean1 = clean_title(title1)
        clean2 = clean_title(title2)
        
        # Nếu một trong hai rỗng sau khi clean, không xét
        if not clean1 or not clean2:
            return False
        
        # Nếu giống hệt
        if clean1 == clean2:
            return True
        
        # Nếu một cái chứa cái kia (tên ngắn hơn nằm trong tên dài)
        if len(clean1) > 3 and len(clean2) > 3:
            if clean1 in clean2 or clean2 in clean1:
                return True
        
        # Tính độ giống nhau dựa trên từ chung
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        if len(words1) >= 2 and len(words2) >= 2:
            common = words1 & words2
            similarity = len(common) / min(len(words1), len(words2))
            if similarity >= 0.7:  # 70% từ giống nhau → coi như trùng
                return True
        
        return False
    
    def _detect_genre_language(self, title: str, author: str = "") -> dict:
        """
        Phát hiện thể loại và ngôn ngữ từ title/author.
        Trả về dict với 'genres' (set) và 'languages' (set).
        """
        text = f"{title} {author}".lower()
        
        result = {
            'genres': set(),
            'languages': set()
        }
        
        # Phát hiện thể loại
        genre_keywords = {
            'pop': ['pop', 'ballad', 'acoustic'],
            'rock': ['rock', 'metal', 'punk', 'alternative'],
            'hiphop': ['rap', 'hip hop', 'hiphop', 'trap', 'drill'],
            'edm': ['edm', 'remix', 'electronic', 'house', 'techno', 'trance', 'dubstep', 'dj'],
            'rnb': ['r&b', 'rnb', 'soul', 'funk'],
            'lofi': ['lofi', 'lo-fi', 'chill', 'study', 'relax'],
            'classical': ['classical', 'piano', 'orchestra', 'symphony'],
            'jazz': ['jazz', 'blues', 'swing'],
            'country': ['country', 'folk', 'acoustic'],
            'kpop': ['kpop', 'k-pop', 'bts', 'blackpink', 'twice', 'exo', 'nct'],
            'vpop': ['vpop', 'v-pop'],
            'anime': ['anime', 'ost', 'opening', 'ending', 'naruto', 'one piece'],
        }
        
        for genre, keywords in genre_keywords.items():
            for kw in keywords:
                if kw in text:
                    result['genres'].add(genre)
                    break
        
        # Phát hiện ngôn ngữ (dựa trên ký tự và keywords)
        # Tiếng Việt
        vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
        vietnamese_keywords = ['việt', 'viet', 'nha', 'nhac', 'bai', 'hat', 'vietsub']
        if any(c in text for c in vietnamese_chars) or any(kw in text for kw in vietnamese_keywords):
            result['languages'].add('vi')
        
        # Tiếng Hàn
        korean_keywords = ['한국', 'korea', 'korean', 'kpop', 'k-pop', 'hangul']
        if any(kw in text for kw in korean_keywords) or any('\uac00' <= c <= '\ud7a3' for c in text):
            result['languages'].add('ko')
        
        # Tiếng Nhật
        japanese_keywords = ['日本', 'japan', 'japanese', 'anime', 'jpop', 'j-pop']
        if any(kw in text for kw in japanese_keywords) or any('\u3040' <= c <= '\u30ff' for c in text):
            result['languages'].add('ja')
        
        # Tiếng Anh (mặc định nếu có chữ Latin và không có ngôn ngữ khác)
        english_keywords = ['english', 'eng', 'lyrics']
        if any(kw in text for kw in english_keywords) or (not result['languages'] and any(c.isalpha() for c in text)):
            result['languages'].add('en')
        
        return result
    
    def _calculate_similarity_score(self, source_info: dict, track_title: str, track_author: str = "") -> int:
        """
        Tính điểm tương đồng giữa bài nguồn và bài candidate.
        Điểm cao hơn = ưu tiên hơn.
        """
        target_info = self._detect_genre_language(track_title, track_author)
        score = 0
        
        # Cùng thể loại: +3 điểm mỗi thể loại chung
        common_genres = source_info['genres'] & target_info['genres']
        score += len(common_genres) * 3
        
        # Cùng ngôn ngữ: +2 điểm mỗi ngôn ngữ chung
        common_languages = source_info['languages'] & target_info['languages']
        score += len(common_languages) * 2
        
        return score
    
    def _start_idle_timer(self, player: wavelink.Player):
        """Start idle disconnect timer."""
        if not player.guild:
            return
        
        guild_id = player.guild.id
        
        # Cancel existing timer
        if guild_id in self._idle_tasks:
            self._idle_tasks[guild_id].cancel()
        
        async def idle_disconnect():
            await asyncio.sleep(IDLE_TIMEOUT_SECONDS)
            if player.connected and not player.playing:
                await player.disconnect()
                if hasattr(player, 'text_channel') and player.text_channel:
                    await player.text_channel.send("👋 Rời voice do không hoạt động.")
        
        self._idle_tasks[guild_id] = asyncio.create_task(idle_disconnect())
    
    def _create_now_playing_embed(self, track: wavelink.Playable) -> discord.Embed:
        """Create embed for now playing message."""
        duration = self._format_duration(track.length)
        
        embed = discord.Embed(
            title="🎵 Đang phát",
            description=f"**{track.title}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Channel", value=track.author, inline=True)
        embed.add_field(name="Thời lượng", value=duration, inline=True)
        
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        
        return embed
    
    def _format_duration(self, ms: int) -> str:
        """Format milliseconds to MM:SS or HH:MM:SS."""
        seconds = ms // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    def _create_progress_bar(self, current_ms: int, total_ms: int, length: int = 15) -> str:
        """Create text progress bar."""
        if total_ms == 0:
            return "░" * length
        
        progress = current_ms / total_ms
        filled = int(length * progress)
        empty = length - filled
        
        return "█" * filled + "░" * empty
    
    # ==================== COMMANDS ====================
    
    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """Phát nhạc từ YouTube URL hoặc từ khóa."""
        # Check if user is in voice
        if not ctx.author.voice:
            return await ctx.send("❌ Bạn phải vào voice channel trước!")
        
        voice_channel = ctx.author.voice.channel
        
        # Get or create player
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            try:
                player = await voice_channel.connect(cls=wavelink.Player)
                player.text_channel = ctx.channel  # type: ignore
                # Disable Wavelink's built-in autoplay to use our custom logic
                player.autoplay = wavelink.AutoPlayMode.disabled
                await player.set_volume(DEFAULT_VOLUME)
            except Exception as e:
                return await ctx.send(f"❌ Không thể kết nối voice: {e}")
        
        # Search for track
        try:
            # Check if it's a URL or search query
            if query.startswith(("http://", "https://")):
                tracks = await wavelink.Playable.search(query)
            else:
                tracks = await wavelink.Playable.search(f"ytsearch:{query}")
            
            if not tracks:
                return await ctx.send("❌ Không tìm thấy kết quả. Thử từ khóa khác?")
            
            # Xử lý playlist (nhiều tracks) vs single track
            if isinstance(tracks, wavelink.Playlist):
                # Đây là playlist - load toàn bộ
                playlist_name = tracks.name or "Unknown Playlist"
                playlist_tracks = list(tracks.tracks)
                
                if not playlist_tracks:
                    return await ctx.send("❌ Playlist trống hoặc không thể load.")
                
                # Validate và filter tracks
                valid_tracks = []
                for track in playlist_tracks:
                    is_valid, _ = is_valid_track(
                        title=track.title,
                        duration_ms=track.length,
                        is_stream=track.is_stream
                    )
                    if is_valid:
                        valid_tracks.append(track)
                
                if not valid_tracks:
                    return await ctx.send("❌ Không có bài nào trong playlist phù hợp (có thể quá dài hoặc bị chặn).")
                
                # Tính tổng thời gian
                total_duration = sum(track.length for track in valid_tracks)
                total_duration_str = self._format_duration(total_duration)
                
                # Add tracks to queue
                if player.playing:
                    for track in valid_tracks:
                        player.queue.put(track)
                    
                    embed = discord.Embed(
                        title="📋 Đã thêm Playlist vào queue",
                        description=f"**{playlist_name}**",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Số bài", value=f"{len(valid_tracks)} bài", inline=True)
                    embed.add_field(name="Tổng thời gian", value=total_duration_str, inline=True)
                    embed.add_field(name="Bỏ qua", value=f"{len(playlist_tracks) - len(valid_tracks)} bài", inline=True)
                    await ctx.send(embed=embed)
                else:
                    # Play first track, add rest to queue
                    first_track = valid_tracks[0]
                    for track in valid_tracks[1:]:
                        player.queue.put(track)
                    
                    await player.play(first_track)
                    
                    if len(valid_tracks) > 1:
                        embed = discord.Embed(
                            title="📋 Đang phát Playlist",
                            description=f"**{playlist_name}**",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Số bài", value=f"{len(valid_tracks)} bài", inline=True)
                        embed.add_field(name="Tổng thời gian", value=total_duration_str, inline=True)
                        await ctx.send(embed=embed)
            
            else:
                # Single track (hoặc list with 1 track)
                track = tracks[0] if isinstance(tracks, list) else tracks
                
                # Validate track
                is_valid, reason = is_valid_track(
                    title=track.title,
                    duration_ms=track.length,
                    is_stream=track.is_stream
                )
                
                if not is_valid:
                    return await ctx.send(reason)
                
                # Add to queue or play
                if player.playing:
                    # Xóa prefetch autoplay nếu có (vì user đã add bài mới)
                    if ctx.guild and ctx.guild.id in self._next_autoplay:
                        del self._next_autoplay[ctx.guild.id]
                        logger.info(f"[PLAY] Guild {ctx.guild.id}: Xóa prefetch autoplay vì user add bài mới")
                    
                    player.queue.put(track)
                    position = len(player.queue)
                    embed = discord.Embed(
                        title="📝 Đã thêm vào queue",
                        description=f"**{track.title}**",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Vị trí", value=f"#{position}", inline=True)
                    embed.add_field(name="Thời lượng", value=self._format_duration(track.length), inline=True)
                    await ctx.send(embed=embed)
                else:
                    await player.play(track)
            
        except Exception as e:
            await ctx.send(f"❌ Lỗi khi tìm bài: {e}")
    
    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        """Skip bài hiện tại."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player or not player.playing:
            return await ctx.send("❌ Không có gì đang phát.")
        
        current_title = player.current.title if player.current else "Unknown"
        await player.skip()
        await ctx.send(f"⏭️ Đã skip: **{current_title}**")
    
    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Tạm dừng phát nhạc."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player or not player.playing:
            return await ctx.send("❌ Không có gì đang phát.")
        
        await player.pause(True)
        await ctx.send("⏸️ Đã tạm dừng")
    
    @commands.command(name="resume", aliases=["unpause"])
    async def resume(self, ctx: commands.Context):
        """Tiếp tục phát nhạc."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            return await ctx.send("❌ Bot không trong voice channel.")
        
        if not player.paused:
            return await ctx.send("❌ Nhạc không bị tạm dừng.")
        
        await player.pause(False)
        await ctx.send("▶️ Tiếp tục phát")
    
    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Dừng phát và xóa queue."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            return await ctx.send("❌ Bot không trong voice channel.")
        
        player.queue.clear()
        await player.stop()
        await player.disconnect()
        
        # Clear guild state
        if ctx.guild:
            guild_id = ctx.guild.id
            self._recent_ids.pop(guild_id, None)
            self._next_autoplay.pop(guild_id, None)
        
        await ctx.send("⏹️ Đã dừng và rời voice")
    
    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context, page: int = 1):
        """Xem danh sách bài chờ."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            return await ctx.send("❌ Bot không trong voice channel.")
        
        if not player.queue and not player.current:
            return await ctx.send("📭 Queue trống.")
        
        items_per_page = 10
        start = (page - 1) * items_per_page
        end = start + items_per_page
        
        queue_list = list(player.queue)
        total_pages = (len(queue_list) - 1) // items_per_page + 1 if queue_list else 1
        
        embed = discord.Embed(title="📜 Queue", color=discord.Color.blue())
        
        # Current track
        if player.current:
            embed.add_field(
                name="🎵 Đang phát",
                value=f"**{player.current.title}** - {self._format_duration(player.current.length)}",
                inline=False
            )
        
        # Queue items
        if queue_list:
            description = ""
            for i, track in enumerate(queue_list[start:end], start=start + 1):
                description += f"`{i}.` {track.title} - {self._format_duration(track.length)}\n"
            
            embed.add_field(name="Tiếp theo", value=description or "Trống", inline=False)
            embed.set_footer(text=f"Trang {page}/{total_pages} | Tổng: {len(queue_list)} bài")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int):
        """Xóa bài ở vị trí chỉ định khỏi queue."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player or not player.queue:
            return await ctx.send("❌ Queue trống.")
        
        if index < 1 or index > len(player.queue):
            return await ctx.send(f"❌ Index không hợp lệ. Chọn từ 1-{len(player.queue)}")
        
        # Convert to 0-based index
        queue_list = list(player.queue)
        removed = queue_list.pop(index - 1)
        
        # Rebuild queue
        player.queue.clear()
        for track in queue_list:
            player.queue.put(track)
        
        await ctx.send(f"🗑️ Đã xóa: **{removed.title}**")
    
    @commands.command(name="clear")
    async def clear(self, ctx: commands.Context):
        """Xóa toàn bộ queue (không dừng bài đang phát)."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player or not player.queue:
            return await ctx.send("❌ Queue đã trống.")
        
        count = len(player.queue)
        player.queue.clear()
        await ctx.send(f"🗑️ Đã xóa {count} bài khỏi queue")
    
    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Trộn ngẫu nhiên queue."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player or len(player.queue) < 2:
            return await ctx.send("❌ Cần ít nhất 2 bài trong queue để shuffle.")
        
        # Shuffle
        queue_list = list(player.queue)
        random.shuffle(queue_list)
        
        player.queue.clear()
        for track in queue_list:
            player.queue.put(track)
        
        await ctx.send(f"🔀 Đã trộn {len(queue_list)} bài")
    
    @commands.command(name="jump", aliases=["j", "skipto"])
    async def jump(self, ctx: commands.Context, index: int):
        """Nhảy đến bài ở vị trí chỉ định trong queue."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player or not player.queue:
            return await ctx.send("❌ Queue trống.")
        
        if index < 1 or index > len(player.queue):
            return await ctx.send(f"❌ Index không hợp lệ. Chọn từ 1-{len(player.queue)}")
        
        # Lấy danh sách queue hiện tại
        queue_list = list(player.queue)
        
        # Bài muốn nhảy đến
        target_track = queue_list[index - 1]
        
        # Xóa tất cả bài từ đầu đến trước bài đích
        skipped_count = index - 1
        remaining_tracks = queue_list[index:]  # Bao gồm bài đích ở vị trí 0
        
        # Rebuild queue với các bài còn lại (không bao gồm bài đích vì sẽ phát ngay)
        player.queue.clear()
        for track in remaining_tracks[1:]:  # Bỏ bài đích
            player.queue.put(track)
        
        # Phát bài đích
        await player.play(target_track)
        
        embed = discord.Embed(
            title="⏭️ Nhảy đến bài",
            description=f"**{target_track.title}**",
            color=discord.Color.orange()
        )
        if skipped_count > 0:
            embed.add_field(name="Đã bỏ qua", value=f"{skipped_count} bài", inline=True)
        embed.add_field(name="Còn lại", value=f"{len(remaining_tracks) - 1} bài", inline=True)
        await ctx.send(embed=embed)
    
    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        """Hiển thị bài đang phát với progress bar."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player or not player.current:
            return await ctx.send("❌ Không có gì đang phát.")
        
        track = player.current
        position = player.position
        duration = track.length
        
        progress_bar = self._create_progress_bar(position, duration)
        current_time = self._format_duration(position)
        total_time = self._format_duration(duration)
        
        embed = discord.Embed(
            title="🎵 Đang phát",
            description=f"**{track.title}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Channel", value=track.author, inline=True)
        embed.add_field(name="Tiến độ", value=f"`{progress_bar}`\n{current_time} / {total_time}", inline=False)
        
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="loop")
    async def loop(self, ctx: commands.Context, mode: str = None):
        """Đặt chế độ lặp: off/track/queue"""
        if not ctx.guild:
            return
        
        guild_id = ctx.guild.id
        
        if mode is None:
            current = self.get_loop_mode(guild_id)
            return await ctx.send(f"🔁 Loop hiện tại: **{current}**")
        
        mode = mode.lower()
        if mode not in ("off", "track", "queue"):
            return await ctx.send("❌ Chế độ không hợp lệ. Dùng: `off`, `track`, hoặc `queue`")
        
        self.loop_mode[guild_id] = mode
        
        emoji = {"off": "➡️", "track": "🔂", "queue": "🔁"}
        await ctx.send(f"{emoji[mode]} Loop: **{mode}**")
    
    @commands.command(name="autoplay", aliases=["ap"])
    async def autoplay(self, ctx: commands.Context, setting: str = None):
        """Bật/tắt autoplay: on/off/status"""
        if not ctx.guild:
            return
        
        guild_id = ctx.guild.id
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if setting is None or setting.lower() == "status":
            status = "ON" if self.get_autoplay(guild_id) else "OFF"
            return await ctx.send(f"🔄 Autoplay: **{status}**")
        
        setting = setting.lower()
        if setting == "on":
            self.autoplay_enabled[guild_id] = True
            # Disable built-in, use custom
            if player:
                player.autoplay = wavelink.AutoPlayMode.disabled
            await ctx.send("🔄 Autoplay: **ON** (Smart Recommend)")
        elif setting == "off":
            self.autoplay_enabled[guild_id] = False
            if player:
                player.autoplay = wavelink.AutoPlayMode.disabled
            await ctx.send("🔄 Autoplay: **OFF**")
        else:
            await ctx.send("❌ Dùng: `on`, `off`, hoặc `status`")


    @commands.command(name="settings")
    async def settings(self, ctx: commands.Context):
        """Xem cấu hình hiện tại."""
        if not ctx.guild:
            return
        
        guild_id = ctx.guild.id
        
        autoplay = "ON" if self.get_autoplay(guild_id) else "OFF"
        loop = self.get_loop_mode(guild_id)
        max_dur = MAX_DURATION_SECONDS // 60
        
        embed = discord.Embed(title="⚙️ Cấu hình", color=discord.Color.dark_gray())
        embed.add_field(name="Autoplay", value=autoplay, inline=True)
        embed.add_field(name="Loop", value=loop, inline=True)
        embed.add_field(name="Max Duration", value=f"{max_dur} phút", inline=True)
        embed.add_field(name="Volume", value=f"{DEFAULT_VOLUME}%", inline=True)
        embed.add_field(name="Idle Timeout", value=f"{IDLE_TIMEOUT_SECONDS // 60} phút", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, vol: int = None):
        """Điều chỉnh âm lượng (0-100)."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            return await ctx.send("❌ Bot không trong voice channel.")
        
        if vol is None:
            return await ctx.send(f"🔊 Âm lượng: **{player.volume}%**")
        
        vol = min(max(vol, 0), 100)
        await player.set_volume(vol)
        await ctx.send(f"🔊 Âm lượng: **{vol}%**")
    
    @commands.command(name="musichelp", aliases=["mhelp", "huongdan"])
    async def help_command(self, ctx: commands.Context):
        """Hiển thị hướng dẫn sử dụng bot."""
        embed = discord.Embed(
            title="🎵 Đài Phát Thanh - Hướng Dẫn",
            description="Bot phát nhạc YouTube với **Autoplay thông minh**!\n\n*Prefix: `p` (ví dụ: `pplay`, `pskip`)*",
            color=discord.Color.blue()
        )
        
        # Phát nhạc
        embed.add_field(
            name="🎶 **Phát Nhạc**",
            value=(
                "`pplay <tên/url>` - Phát hoặc thêm vào queue\n"
                "`pskip` - Skip bài hiện tại\n"
                "`ppause` / `presume` - Tạm dừng / Tiếp tục\n"
                "`pstop` - Dừng + xóa queue"
            ),
            inline=False
        )
        
        # Queue
        embed.add_field(
            name="📋 **Queue**",
            value=(
                "`pqueue` - Xem danh sách chờ\n"
                "`premove <số>` - Xóa bài khỏi queue\n"
                "`pclear` - Xóa toàn bộ queue\n"
                "`pshuffle` - Trộn ngẫu nhiên queue"
            ),
            inline=False
        )
        
        # Thông tin & Điều khiển
        embed.add_field(
            name="ℹ️ **Thông Tin**",
            value=(
                "`pnowplaying` - Bài đang phát + progress\n"
                "`pvolume [0-100]` - Điều chỉnh âm lượng\n"
                "`psettings` - Xem cấu hình hiện tại"
            ),
            inline=True
        )
        
        # Loop & Autoplay
        embed.add_field(
            name="🔄 **Lặp & Autoplay**",
            value=(
                "`ploop <off/track/queue>` - Chế độ lặp\n"
                "`pautoplay <on/off>` - Bật/tắt autoplay"
            ),
            inline=True
        )
        
        # Tips
        embed.add_field(
            name="💡 **Mẹo**",
            value=(
                "• Autoplay sẽ tự tìm bài tiếp theo khi queue trống\n"
                "• Sử dụng thuật toán YouTube Mix để gợi ý\n"
                "• Bot tự rời khi không còn ai trong voice"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made with ❤️ | Prefix: p")
        
        await ctx.send(embed=embed)
    
    # ==================== VOICE STATE EVENTS ====================
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Tự động rời voice khi không còn ai (trừ bot)."""
        # Chỉ xử lý khi ai đó rời voice channel
        if before.channel is None:
            return
        
        # Kiểm tra nếu channel cũ có bot trong đó
        guild = before.channel.guild
        player: wavelink.Player = guild.voice_client  # type: ignore
        
        if not player or not player.channel:
            return
        
        # Kiểm tra nếu đây là channel mà bot đang ở
        if player.channel.id != before.channel.id:
            return
        
        # Đếm số người thật trong channel (không tính bot)
        human_members = [m for m in before.channel.members if not m.bot]
        
        if len(human_members) == 0:
            logger.info(f"[ALONE] Guild {guild.id}: Không còn ai trong voice, rời sau 30s...")
            
            # Đợi 30 giây trước khi rời (trong trường hợp ai đó quay lại)
            await asyncio.sleep(30)
            
            # Kiểm tra lại sau 30s
            if player.channel:
                current_members = [m for m in player.channel.members if not m.bot]
                if len(current_members) == 0 and player.connected:
                    player.queue.clear()
                    if player.playing:
                        await player.stop()
                    await player.disconnect()
                    
                    if hasattr(player, 'text_channel') and player.text_channel:
                        await player.text_channel.send("👋 Rời voice vì không còn ai nghe.")
                    
                    logger.info(f"[ALONE] Guild {guild.id}: Đã rời voice")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))

