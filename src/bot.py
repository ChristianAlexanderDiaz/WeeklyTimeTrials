"""
Main bot file for the Mario Kart World Time Trial Discord Bot.

This is the entry point for the bot. It sets up the Discord client,
registers commands, and starts the bot with proper error handling.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from .config.settings import settings, validate_environment
from .events.on_ready import setup_events, BotEvents
from .commands.save_time import setup_save_command
from .commands.leaderboard import setup_leaderboard_command, setup_active_trials_command
from .commands.remove_time import setup_remove_time_command
from .commands.set_challenge import setup_set_challenge_command
from .commands.end_challenge import setup_end_challenge_command
from .commands.set_leaderboard_channel import setup_set_leaderboard_channel_command

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mkw_bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


class MKWTimeTrialBot(commands.Bot):
    """
    Main bot class for the Mario Kart World Time Trial Bot.
    
    This class extends discord.py's Bot class with custom functionality
    for managing time trial challenges and database operations.
    """
    
    def __init__(self):
        """Initialize the bot with required intents and settings."""
        
        # Configure intents (permissions for bot to access certain data)
        intents = discord.Intents.default()
        intents.message_content = False  # We only use slash commands
        intents.guilds = True  # Need to access guild information
        intents.guild_messages = False  # Not reading messages
        
        super().__init__(
            command_prefix='!',  # Not used since we only have slash commands
            intents=intents,
            help_command=None,  # Disable default help command
            case_insensitive=True,
            description="Mario Kart World Time Trial Bot"
        )
        
        self.events_handler: Optional[BotEvents] = None
    
    async def setup_hook(self) -> None:
        """
        Set up the bot after logging in but before connecting to the gateway.
        
        This method is called automatically by discord.py and is used to
        register commands and set up event handlers.
        """
        logger.info("Setting up bot...")
        
        try:
            # Set up event handlers
            self.events_handler = setup_events(self)
            
            # Register all slash commands
            await self._register_commands()
            
            # Sync commands with Discord (this can take a few minutes to propagate)
            logger.info("Syncing commands with Discord...")
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
            
        except Exception as e:
            logger.error(f"Error during bot setup: {e}", exc_info=True)
            raise
    
    async def _register_commands(self) -> None:
        """
        Register all slash commands with the bot.
        
        This method calls the setup functions for each command module
        to register them with the Discord command tree.
        """
        logger.info("Registering slash commands...")
        
        # User commands
        setup_save_command(self.tree)
        setup_leaderboard_command(self.tree)
        setup_active_trials_command(self.tree)
        setup_remove_time_command(self.tree)
        
        # Admin commands (no restrictions as specified)
        setup_set_challenge_command(self.tree)
        setup_end_challenge_command(self.tree)
        setup_set_leaderboard_channel_command(self.tree)
        
        logger.info("All commands registered successfully")
    
    async def on_error(self, event: str, *args, **kwargs) -> None:
        """
        Handle general bot errors.
        
        Args:
            event: The event that caused the error
            *args: Event arguments
            **kwargs: Event keyword arguments
        """
        logger.error(f"Error in event {event}", exc_info=True)
    
    async def close(self) -> None:
        """
        Clean up resources when the bot shuts down.
        
        This method ensures proper cleanup of database connections
        and background tasks before the bot exits.
        """
        logger.info("Bot is shutting down...")
        
        if self.events_handler:
            await self.events_handler.shutdown()
        
        await super().close()


def setup_signal_handlers(bot: MKWTimeTrialBot) -> None:
    """
    Set up signal handlers for graceful shutdown.
    
    Args:
        bot: Bot instance to shut down gracefully
    """
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main() -> None:
    """
    Main entry point for the bot.
    
    This function validates the environment, creates the bot instance,
    sets up signal handlers, and starts the bot.
    """
    try:
        # Validate environment configuration
        logger.info("Validating environment configuration...")
        validate_environment()
        
        # Create bot instance
        logger.info("Creating bot instance...")
        bot = MKWTimeTrialBot()
        
        # Set up signal handlers for graceful shutdown
        setup_signal_handlers(bot)
        
        # Start the bot
        logger.info("Starting Mario Kart World Time Trial Bot...")
        await bot.start(settings.BOT_TOKEN)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    """
    Entry point when running the bot directly.
    
    This allows the bot to be started with: python -m src.bot
    """
    try:
        # Check Python version
        if sys.version_info < (3, 8):
            print("Error: Python 3.8 or higher is required")
            sys.exit(1)
        
        # Run the bot
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)