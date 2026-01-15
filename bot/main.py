"""
Discord Music Bot - Main Entry Point
"""
import asyncio
import logging
import discord
from discord.ext import commands
import wavelink

from bot.config import (
    DISCORD_TOKEN,
    COMMAND_PREFIX,
    LAVALINK_HOST,
    LAVALINK_PORT,
    LAVALINK_PASSWORD,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('bot')


class MusicBot(commands.Bot):
    """Custom bot class with wavelink integration."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            case_insensitive=True,  # pPLAY, PPLAY, pplay all work
        )
    
    def _get_prefix(self, bot, message: discord.Message) -> list[str]:
        """Return command prefixes (case-insensitive handled by Bot)."""
        return [COMMAND_PREFIX]
    
    async def setup_hook(self) -> None:
        """Called when bot is starting up."""
        # Connect to Lavalink
        node = wavelink.Node(
            uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}",
            password=LAVALINK_PASSWORD,
        )
        await wavelink.Pool.connect(nodes=[node], client=self, cache_capacity=100)
        logger.info(f"Connected to Lavalink at {LAVALINK_HOST}:{LAVALINK_PORT}")
        
        # Load cogs
        await self.load_extension("bot.cogs.music")
        logger.info("Loaded music cog")
    
    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # Set activity
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{COMMAND_PREFIX}play"
        )
        await self.change_presence(activity=activity)
    
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """Called when Lavalink node is ready."""
        logger.info(f"Wavelink node ready: {payload.node.identifier}")
    
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Global error handler."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Thiếu tham số: `{error.param.name}`")
            return
        
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Tham số không hợp lệ: {error}")
            return
        
        # Log unexpected errors
        logger.error(f"Command error in {ctx.command}: {error}", exc_info=error)
        await ctx.send("❌ Đã xảy ra lỗi. Vui lòng thử lại.")


async def main():
    """Main entry point."""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not found in environment!")
        return
    
    bot = MusicBot()
    
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
