"""
Bot ready event handler for the MKW Time Trial Bot.

This module handles the bot's startup sequence, including database initialization,
command registration, and periodic maintenance tasks.
"""

import asyncio
import logging
from datetime import datetime, timezone
import discord

from ..database.connection import initialize_database, db_manager
from ..config.settings import validate_environment

logger = logging.getLogger(__name__)


class BotEvents:
    """
    Handles bot lifecycle events and background tasks.
    
    This class manages bot startup, shutdown, and periodic maintenance
    tasks like cleaning up expired trials.
    """
    
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.maintenance_task = None
    
    async def on_ready(self) -> None:
        """
        Handle bot ready event.
        
        This method is called when the bot successfully connects to Discord
        and is ready to start processing commands.
        """
        try:
            logger.info(f"Bot logged in as {self.bot.user} (ID: {self.bot.user.id})")
            
            # Validate environment configuration
            validate_environment()
            
            # Initialize database connection and schema
            await initialize_database()
            
            # Start background maintenance tasks
            await self._start_maintenance_tasks()
            
            # Log success
            logger.info("🚀 MKW Time Trial Bot is ready!")
            logger.info(f"Connected to {len(self.bot.guilds)} guild(s)")
            
            # Set bot status
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name="Mario Kart World time trials | /weeklytimesave"
            )
            await self.bot.change_presence(activity=activity)
            
        except Exception as e:
            logger.error(f"Error during bot startup: {e}", exc_info=True)
            raise
    
    async def on_disconnect(self) -> None:
        """Handle bot disconnect event."""
        logger.warning("Bot disconnected from Discord")
    
    async def on_resumed(self) -> None:
        """Handle bot resume event."""
        logger.info("Bot connection resumed")
    
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Handle bot joining a new guild.
        
        Args:
            guild: The guild the bot joined
        """
        logger.info(f"Bot joined guild: {guild.name} (ID: {guild.id})")
        
        # Send welcome message to the system channel if available
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            try:
                embed = discord.Embed(
                    title="🏁 Mario Kart World Time Trial Bot",
                    description=(
                        "Thanks for adding me to your server! I help manage weekly time trial challenges "
                        "for Mario Kart World tracks.\n\n"
                        "**Quick Start:**\n"
                        "• `/set-challenge` - Create a new time trial\n"
                        "• `/weeklytimesave` - Submit your time\n"
                        "• `/leaderboard` - View rankings\n"
                        "• `/active` - See all active trials\n\n"
                        "**Features:**\n"
                        "✅ 30 Mario Kart World tracks\n"
                        "✅ Automatic leaderboards with medals\n"
                        "✅ Time improvement tracking\n"
                        "✅ Multiple concurrent challenges\n"
                        "✅ Automatic trial expiration"
                    ),
                    color=0x4B0082
                )
                embed.set_footer(text="Use slash commands to get started!")
                await guild.system_channel.send(embed=embed)
            except Exception as e:
                logger.warning(f"Could not send welcome message to {guild.name}: {e}")
    
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """
        Handle bot being removed from a guild.
        
        Args:
            guild: The guild the bot was removed from
        """
        logger.info(f"Bot removed from guild: {guild.name} (ID: {guild.id})")
        
        # Optional: Clean up guild data (if desired)
        # For now, we'll keep the data in case they re-add the bot
    
    async def _start_maintenance_tasks(self) -> None:
        """
        Start background maintenance tasks.
        
        This includes periodic cleanup of expired trials and other
        database maintenance operations.
        """
        if self.maintenance_task and not self.maintenance_task.done():
            return  # Task already running
        
        self.maintenance_task = asyncio.create_task(self._maintenance_loop())
        logger.info("Started background maintenance tasks")
    
    async def _maintenance_loop(self) -> None:
        """
        Main maintenance loop that runs periodically.
        
        This task handles:
        - Marking expired trials as 'expired'
        - Cleaning up old expired trials
        - Database optimization (future)
        """
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._run_maintenance()
            except asyncio.CancelledError:
                logger.info("Maintenance task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(3600)
    
    async def _run_maintenance(self) -> None:
        """
        Run maintenance operations.

        This method performs database cleanup and maintenance tasks.
        """
        try:
            # Mark expired trials
            expired_count = await self._mark_expired_trials()
            if expired_count > 0:
                logger.info(f"Marked {expired_count} trials as expired")

            # Clean up old expired trials (after grace period)
            from ..config.settings import settings
            cleanup_count = await self._cleanup_old_trials(settings.EXPIRED_TRIAL_CLEANUP_DAYS)
            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} old expired trials")

            # Mark expired duels
            expired_duels_count = await self._mark_expired_duels()
            if expired_duels_count > 0:
                logger.info(f"Marked {expired_duels_count} duels as expired")

        except Exception as e:
            logger.error(f"Error during maintenance: {e}", exc_info=True)
    
    async def _mark_expired_trials(self) -> int:
        """
        Mark active trials as expired when their end_date is reached.
        
        Returns:
            Number of trials marked as expired
        """
        query = """
            UPDATE weekly_trials 
            SET status = 'expired' 
            WHERE status = 'active' 
                AND end_date IS NOT NULL 
                AND end_date < CURRENT_TIMESTAMP
            RETURNING id, trial_number, track_name, guild_id
        """
        
        try:
            results = db_manager.execute_query(query, fetch=True)
            
            # Log expired trials
            for trial in results:
                logger.info(
                    f"Trial #{trial['trial_number']} ({trial['track_name']}) "
                    f"in guild {trial['guild_id']} has expired"
                )
            
            return len(results)
            
        except Exception as e:
            logger.error(f"Error marking expired trials: {e}")
            return 0
    
    async def _cleanup_old_trials(self, cleanup_days: int) -> int:
        """
        Delete trials that have been expired for more than the cleanup period.

        Args:
            cleanup_days: Number of days after expiration to keep trials

        Returns:
            Number of trials cleaned up
        """
        query = """
            DELETE FROM weekly_trials
            WHERE status = 'expired'
                AND end_date < CURRENT_TIMESTAMP - INTERVAL '%s days'
            RETURNING id, trial_number, track_name, guild_id
        """

        try:
            # Note: This uses string formatting which is normally dangerous,
            # but cleanup_days is from config, not user input
            results = db_manager.execute_query(
                query.replace('%s', str(cleanup_days)),
                fetch=True
            )

            # Log cleaned up trials
            for trial in results:
                logger.info(
                    f"Cleaned up expired trial #{trial['trial_number']} "
                    f"({trial['track_name']}) from guild {trial['guild_id']}"
                )

            return len(results)

        except Exception as e:
            logger.error(f"Error cleaning up old trials: {e}")
            return 0

    async def _mark_expired_duels(self) -> int:
        """
        Handle expired duels when their end_date is reached.

        For active duels: Determines winner and marks as 'completed'
        For pending duels: Marks as 'expired'

        Returns:
            Number of duels processed
        """
        from ..utils.duel_manager import DuelManager

        # First, handle active duels - complete them with winner determination
        active_query = """
            SELECT id, challenge_number, guild_id
            FROM challenges_1v1
            WHERE status = 'active'
                AND end_date IS NOT NULL
                AND end_date < CURRENT_TIMESTAMP
        """

        # Then handle pending duels - just mark as expired
        pending_query = """
            UPDATE challenges_1v1
            SET status = 'expired'
            WHERE status = 'pending'
                AND end_date IS NOT NULL
                AND end_date < CURRENT_TIMESTAMP
            RETURNING id, challenge_number, guild_id
        """

        try:
            count = 0

            # Process active duels
            active_duels = db_manager.execute_query(active_query, fetch=True)
            for duel in active_duels:
                # Determine winner
                winner_user_id = DuelManager.determine_winner(duel['id'])

                # Complete the duel with winner
                complete_query = """
                    UPDATE challenges_1v1
                    SET status = 'completed',
                        winner_user_id = %s
                    WHERE id = %s
                """
                db_manager.execute_query(complete_query, (winner_user_id, duel['id']))

                logger.info(
                    f"Duel #{duel['challenge_number']} in guild {duel['guild_id']} "
                    f"completed (winner: {winner_user_id if winner_user_id else 'tie/no submissions'})"
                )
                count += 1

            # Process pending duels
            pending_duels = db_manager.execute_query(pending_query, fetch=True)
            for duel in pending_duels:
                logger.info(
                    f"Pending duel #{duel['challenge_number']} in guild {duel['guild_id']} has expired"
                )
                count += 1

            return count

        except Exception as e:
            logger.error(f"Error marking expired duels: {e}")
            return 0
    
    async def shutdown(self) -> None:
        """
        Clean shutdown of bot services.
        
        This method should be called when the bot is shutting down
        to properly close database connections and cancel tasks.
        """
        logger.info("Shutting down bot services...")
        
        # Cancel maintenance task
        if self.maintenance_task and not self.maintenance_task.done():
            self.maintenance_task.cancel()
            try:
                await self.maintenance_task
            except asyncio.CancelledError:
                pass
        
        # Close database connections
        from ..database.connection import close_database
        await close_database()
        
        logger.info("Bot shutdown complete")


def setup_events(bot: discord.Client) -> BotEvents:
    """
    Set up event handlers for the bot.
    
    Args:
        bot: Discord client instance
        
    Returns:
        BotEvents instance for manual control if needed
    """
    events = BotEvents(bot)
    
    # Register event handlers
    bot.event(events.on_ready)
    bot.event(events.on_disconnect)
    bot.event(events.on_resumed)
    bot.event(events.on_guild_join)
    bot.event(events.on_guild_remove)
    
    return events