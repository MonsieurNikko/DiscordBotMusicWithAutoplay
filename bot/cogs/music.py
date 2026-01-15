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
from bot.recommender import recommender, TrackInfo
from bot.filters import is_valid_track, filter_search_results


class Music(commands.Cog):
    """Music commands for playing YouTube audio."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Per-guild state
        self.autoplay_enabled: dict[int, bool] = {}  # Default: True
        self.loop_mode: dict[int, str] = {}  # "off", "track", "queue"
        self.last_recommendations: dict[int, list] = {}  # For paddrec
        self._idle_tasks: dict[int, asyncio.Task] = {}
    
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
        
        # Record to recommender for learning
        track_info = TrackInfo(
            video_id=track.identifier,
            title=track.title,
            channel=track.author,
            duration_ms=track.length
        )
        recommender.learn(guild_id, track_info)
        
        # Send now playing message
        if hasattr(player, 'text_channel') and player.text_channel:
            embed = self._create_now_playing_embed(track)
            await player.text_channel.send(embed=embed)
        
        # Cancel idle timer
        if guild_id in self._idle_tasks:
            self._idle_tasks[guild_id].cancel()
        
        # If this is the last song in queue and autoplay is on, show what's next
        if not player.queue and self.get_autoplay(guild_id):
            await self._show_last_song_notice(player, track)
    
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
        if payload.reason not in ("finished", "FINISHED"):
            logger.debug(f"[SKIP] Guild {guild_id}: Ignoring track end (reason: {payload.reason})")
            return
        
        logger.info(f"[FINISHED] Guild {guild_id}: Track finished naturally, checking next action...")
        
        # Handle loop modes
        loop = self.get_loop_mode(guild_id)
        if loop == "track" and payload.track:
            logger.info(f"[LOOP_TRACK] Guild {guild_id}: Replaying same track")
            await player.play(payload.track)
            return
        
        # Check if queue has more tracks
        if player.queue:
            next_track = player.queue.get()
            logger.info(f"[QUEUE] Guild {guild_id}: Playing next from queue: '{next_track.title}'")
            await player.play(next_track)
            return
        
        # Wavelink AutoPlayMode.enabled handles autoplay automatically via auto_queue
        # Check if there's a track in auto_queue (from Wavelink's recommendations)
        if self.get_autoplay(guild_id):
            logger.info(f"[AUTOPLAY] Guild {guild_id}: Autoplay enabled, auto_queue has {len(player.auto_queue) if player.auto_queue else 0} tracks")
            if player.auto_queue:
                # Wavelink will automatically play from auto_queue
                # Just notify the user
                if hasattr(player, 'text_channel') and player.text_channel:
                    next_in_auto = player.auto_queue.peek() if hasattr(player.auto_queue, 'peek') else None
                    if next_in_auto:
                        logger.info(f"[AUTOPLAY] Guild {guild_id}: Next recommendation: '{next_in_auto.title}'")
                        embed = discord.Embed(
                            title="🔄 Autoplay (YouTube Recommendation)",
                            description=f"Tiếp theo: **{next_in_auto.title}**",
                            color=discord.Color.purple()
                        )
                        await player.text_channel.send(embed=embed)
                return
            else:
                # Wavelink auto_queue is empty, use our custom autoplay as fallback
                logger.warning(f"[AUTOPLAY] Guild {guild_id}: auto_queue is empty, trying custom autoplay...")
                await self._do_autoplay(player)
                return
        else:
            logger.info(f"[AUTOPLAY_OFF] Guild {guild_id}: Autoplay is disabled")
        
        # No autoplay or no tracks available, start idle timer
        logger.info(f"[IDLE] Guild {guild_id}: Starting idle timer ({IDLE_TIMEOUT_SECONDS}s)")
        self._start_idle_timer(player)
    
    async def _do_autoplay(self, player: wavelink.Player):
        """Find and play next track based on recommendations."""
        if not player.guild:
            return
        
        guild_id = player.guild.id
        
        # Get last played track for seed
        history = recommender._guild_history.get(guild_id, [])
        if not history:
            logger.warning(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: No history, cannot recommend")
            return
        
        last_track = history[-1]
        logger.info(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: Finding songs similar to '{last_track.title}'")
        
        # Build search queries - prioritize artist/song name
        queries = []
        
        # Extract artist from title (pattern: "Artist - Song")
        if ' - ' in last_track.title:
            artist = last_track.title.split(' - ')[0].strip()
            queries.append(f"{artist} music")
            queries.append(f"{artist} songs")
        
        # Use channel name as artist fallback
        if last_track.channel:
            queries.append(f"{last_track.channel} music")
        
        # Add genre-based queries from recommender
        genre_queries = recommender.build_queries(guild_id, last_track.title)
        queries.extend(genre_queries)
        
        # Limit to 5 queries
        queries = queries[:5]
        logger.info(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: Search queries: {queries}")
        
        recent_ids = recommender.get_recent_ids(guild_id)
        
        # Try each query
        for query in queries:
            try:
                logger.debug(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: Searching '{query}'")
                results = await wavelink.Playable.search(f"ytsearch:{query}")
                if not results:
                    logger.debug(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: No results for '{query}'")
                    continue
                
                logger.debug(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: Got {len(results)} results")
                
                # Filter results
                valid = filter_search_results(results[:10], recent_ids)
                if not valid:
                    logger.debug(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: All results filtered out")
                    continue
                
                # Score and pick
                scored = []
                for track in valid:
                    score = recommender.score_candidate(
                        guild_id, 
                        track.title, 
                        track.author
                    )
                    scored.append((track, score))
                
                # Sort by score, pick from top 3 with weighted random
                scored.sort(key=lambda x: x[1], reverse=True)
                top = scored[:3]
                
                if top:
                    weights = [max(s[1], 1) for s in top]
                    chosen = random.choices(top, weights=weights, k=1)[0][0]
                    
                    logger.info(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: Selected '{chosen.title}' from query '{query}'")
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
                logger.error(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: Error searching '{query}': {e}")
                continue
        
        # Failed to find next track
        logger.warning(f"[CUSTOM_AUTOPLAY] Guild {guild_id}: All queries failed, no track found")
        if hasattr(player, 'text_channel') and player.text_channel:
            await player.text_channel.send("🔇 Autoplay: Không tìm được bài phù hợp.")
        
        self._start_idle_timer(player)
    
    async def _show_last_song_notice(self, player: wavelink.Player, current_track: wavelink.Playable):
        """Show notice when playing the last song in queue, with autoplay preview."""
        if not player.guild:
            return
        
        guild_id = player.guild.id
        
        try:
            # Get the next autoplay track - try auto_queue first
            next_track = None
            
            if player.auto_queue:
                next_track = player.auto_queue.peek() if hasattr(player.auto_queue, 'peek') else None
            
            # If auto_queue is empty, pre-fetch using our custom search
            if not next_track:
                next_track = await self._prefetch_next_autoplay(guild_id, current_track)
            
            if hasattr(player, 'text_channel') and player.text_channel:
                if next_track:
                    embed = discord.Embed(
                        title="🎵 Bài cuối trong Queue",
                        description=(
                            f"Đang phát bài cuối: **{current_track.title}**\n\n"
                            f"⏭️ **Autoplay tiếp theo:** {next_track.title}"
                        ),
                        color=discord.Color.orange()
                    )
                    if hasattr(next_track, 'thumb') and next_track.thumb:
                        embed.set_thumbnail(url=next_track.thumb)
                else:
                    embed = discord.Embed(
                        title="🎵 Bài cuối trong Queue",
                        description=(
                            f"Đang phát bài cuối: **{current_track.title}**\n\n"
                            f"⏭️ **Autoplay** đang bật - sẽ tự tìm bài khi hết."
                        ),
                        color=discord.Color.orange()
                    )
                
                await player.text_channel.send(embed=embed)
                logger.info(f"[LAST_SONG] Guild {guild_id}: Playing last song, next autoplay: '{next_track.title if next_track else 'TBD'}'")
                
        except Exception as e:
            logger.error(f"[LAST_SONG] Guild {guild_id}: Error showing last song notice: {e}")
    
    async def _prefetch_next_autoplay(self, guild_id: int, current_track: wavelink.Playable) -> wavelink.Playable | None:
        """Pre-fetch the next autoplay track without playing it."""
        try:
            # Build search queries based on current track
            queries = []
            
            # Extract artist from title
            if ' - ' in current_track.title:
                artist = current_track.title.split(' - ')[0].strip()
                queries.append(f"{artist} music")
            
            # Use author as fallback
            if current_track.author:
                queries.append(f"{current_track.author} music")
            
            # Add genre queries
            genre_queries = recommender.build_queries(guild_id, current_track.title)
            queries.extend(genre_queries[:2])
            
            recent_ids = recommender.get_recent_ids(guild_id)
            
            # Try first query only for speed
            for query in queries[:2]:
                results = await wavelink.Playable.search(f"ytsearch:{query}")
                if not results:
                    continue
                
                valid = filter_search_results(results[:5], recent_ids)
                if valid:
                    return valid[0]  # Return first valid track
            
            return None
        except Exception as e:
            logger.error(f"[PREFETCH] Guild {guild_id}: Error prefetching: {e}")
            return None
    
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
                # Use Wavelink's built-in autoplay for better YouTube recommendations
                if self.get_autoplay(ctx.guild.id):
                    player.autoplay = wavelink.AutoPlayMode.enabled
                else:
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
            
            track = tracks[0]
            
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
            recommender.clear_guild(ctx.guild.id)
        
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
            # Enable Wavelink's built-in autoplay for better YouTube recommendations
            if player:
                player.autoplay = wavelink.AutoPlayMode.enabled
            await ctx.send("🔄 Autoplay: **ON** (sử dụng YouTube recommendations)")
        elif setting == "off":
            self.autoplay_enabled[guild_id] = False
            if player:
                player.autoplay = wavelink.AutoPlayMode.disabled
            await ctx.send("🔄 Autoplay: **OFF**")
        else:
            await ctx.send("❌ Dùng: `on`, `off`, hoặc `status`")
    
    @commands.command(name="recommend", aliases=["rec"])
    async def recommend(self, ctx: commands.Context, count: int = 5):
        """Xem danh sách gợi ý dựa trên bài đang/vừa phát."""
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not ctx.guild:
            return
        
        guild_id = ctx.guild.id
        count = min(max(count, 1), 10)  # Clamp 1-10
        
        # Get seed from current or history
        seed_title = None
        if player and player.current:
            seed_title = player.current.title
        else:
            history = recommender._guild_history.get(guild_id, [])
            if history:
                seed_title = history[-1].title
        
        if not seed_title:
            return await ctx.send("❌ Chưa có bài nào được phát để gợi ý.")
        
        # Get recommendations
        queries = recommender.build_queries(guild_id, seed_title)
        recent_ids = recommender.get_recent_ids(guild_id)
        
        recommendations = []
        for query in queries:
            try:
                results = await wavelink.Playable.search(f"ytsearch:{query}")
                if results:
                    valid = filter_search_results(results[:5], recent_ids)
                    for track in valid:
                        if track.identifier not in [r.identifier for r in recommendations]:
                            recommendations.append(track)
                            if len(recommendations) >= count:
                                break
            except Exception:
                continue
            
            if len(recommendations) >= count:
                break
        
        if not recommendations:
            return await ctx.send("❌ Không tìm được gợi ý phù hợp.")
        
        # Store for paddrec
        self.last_recommendations[guild_id] = recommendations
        
        # Build response
        embed = discord.Embed(title="💡 Gợi ý cho bạn", color=discord.Color.gold())
        description = ""
        for i, track in enumerate(recommendations, 1):
            duration = self._format_duration(track.length)
            description += f"`{i}.` **{track.title}** - {duration}\n"
        
        embed.description = description
        embed.set_footer(text="Dùng paddrec <số> để thêm vào queue")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="addrec")
    async def addrec(self, ctx: commands.Context, index: int):
        """Thêm bài từ danh sách gợi ý vào queue."""
        if not ctx.guild:
            return
        
        guild_id = ctx.guild.id
        
        recommendations = self.last_recommendations.get(guild_id, [])
        if not recommendations:
            return await ctx.send("❌ Chưa chạy `precommend`. Hãy chạy trước!")
        
        if index < 1 or index > len(recommendations):
            return await ctx.send(f"❌ Chọn số từ 1-{len(recommendations)}")
        
        track = recommendations[index - 1]
        
        player: wavelink.Player = ctx.voice_client  # type: ignore
        
        if not player:
            # Check if user is in voice
            if not ctx.author.voice:
                return await ctx.send("❌ Bạn phải vào voice channel!")
            
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            player.text_channel = ctx.channel  # type: ignore
            await player.set_volume(DEFAULT_VOLUME)
        
        if player.playing:
            player.queue.put(track)
            await ctx.send(f"📝 Đã thêm: **{track.title}**")
        else:
            await player.play(track)
    
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
                "`pautoplay <on/off>` - Bật/tắt autoplay\n"
                "`precommend` - Xem gợi ý\n"
                "`paddrec <số>` - Thêm gợi ý vào queue"
            ),
            inline=True
        )
        
        # Tips
        embed.add_field(
            name="💡 **Mẹo**",
            value=(
                "• Autoplay sẽ tự tìm bài tiếp theo khi queue trống\n"
                "• Bot học từ bài bạn nghe để gợi ý chính xác hơn\n"
                "• Dùng URL YouTube để phát bài cụ thể"
            ),
            inline=False
        )
        
        embed.set_footer(text="Made with ❤️ | Prefix: p")
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
