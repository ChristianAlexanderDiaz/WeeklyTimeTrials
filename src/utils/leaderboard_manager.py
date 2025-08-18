"""
Live leaderboard manager for the MKW Time Trial Bot.

This module handles the creation and updating of live leaderboard messages
that automatically refresh when users submit times, eliminating the need
to repeatedly run /leaderboard commands.
"""

import logging
from typing import Optional, Dict, Any, List, Union
import discord

from .formatters import EmbedFormatter
from .user_utils import bulk_get_display_names
from ..database.connection import db_manager

logger = logging.getLogger(__name__)


class LeaderboardManager:
    """
    Manages live auto-updating leaderboard messages.
    
    This class handles creating, updating, and maintaining Discord messages
    that show real-time leaderboards for active trials.
    """
    
    @staticmethod
    async def create_live_leaderboard(trial_data: Dict[str, Any], 
                                    channel: discord.TextChannel) -> Optional[discord.Message]:
        """
        Create a new live leaderboard message for a trial.
        
        Args:
            trial_data: Trial information from database
            channel: Discord channel to post the message in
            
        Returns:
            Discord message object if successful, None if failed
        """
        try:
            # Get current leaderboard data for the trial
            trial_id = trial_data['id']
            leaderboard_data = await LeaderboardManager._get_leaderboard_data(trial_id, trial_data)
            
            # Get user display names for all participants
            user_ids = [row['user_id'] for row in leaderboard_data]
            user_display_names = {}
            if user_ids:
                user_display_names = await bulk_get_display_names(user_ids, channel.guild)
            
            # Create leaderboard embed with actual current data
            embed = await LeaderboardManager._create_leaderboard_embed(
                trial_data, leaderboard_data, user_display_names
            )
            
            # Post the message
            message = await channel.send(embed=embed)
            
            # Store message ID in database
            await LeaderboardManager._update_leaderboard_message_id(
                trial_data['id'], channel.id, message.id
            )
            
            logger.info(
                f"Created live leaderboard message {message.id} in channel {channel.id} "
                f"for trial #{trial_data['trial_number']}"
            )
            
            return message
            
        except discord.Forbidden:
            logger.error(f"No permission to send messages in channel {channel.id}")
            return None
        except discord.HTTPException as e:
            logger.error(f"Failed to create leaderboard message: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating leaderboard: {e}")
            return None
    
    @staticmethod
    async def update_live_leaderboard(trial_data_or_id, guild: Optional[discord.Guild] = None) -> bool:
        """
        Update an existing live leaderboard message with current rankings.
        
        Args:
            trial_data_or_id: Either trial data dict or trial ID int
            guild: Discord guild object for user resolution (optional if trial_data provided)
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Handle both trial_data dict and trial_id int
            if isinstance(trial_data_or_id, dict):
                trial_data = trial_data_or_id
                trial_id = trial_data['id']
            else:
                trial_id = trial_data_or_id
                trial_data = await LeaderboardManager._get_trial_with_message_info(trial_id)
                if not trial_data:
                    logger.warning(f"Trial {trial_id} not found")
                    return False
            
            # Check if we have a leaderboard message to update
            if not trial_data.get('leaderboard_message_id'):
                logger.warning(f"No leaderboard message ID for trial {trial_id}")
                return False
            
            # Get current leaderboard data
            leaderboard_data = await LeaderboardManager._get_leaderboard_data(
                trial_id, trial_data
            )
            
            # Get user display names
            user_ids = [row['user_id'] for row in leaderboard_data]
            user_display_names = {}
            if user_ids:
                user_display_names = await bulk_get_display_names(user_ids, guild)
            
            # Create updated embed
            embed = await LeaderboardManager._create_leaderboard_embed(
                trial_data, leaderboard_data, user_display_names
            )
            
            # Get guild if not provided
            if not guild:
                from ..bot import bot_instance
                if bot_instance:
                    guild = bot_instance.get_guild(trial_data['guild_id'])
                if not guild:
                    logger.error(f"Guild {trial_data['guild_id']} not found")
                    return False
            
            # Get the message and update it
            channel = guild.get_channel(trial_data['leaderboard_channel_id'])
            if not channel:
                logger.error(f"Channel {trial_data['leaderboard_channel_id']} not found")
                return False
            
            try:
                message = await channel.fetch_message(trial_data['leaderboard_message_id'])
                await message.edit(embed=embed)
                
                logger.info(f"Updated live leaderboard for trial #{trial_data['trial_number']}")
                return True
                
            except discord.NotFound:
                # Message was deleted - create a new one
                logger.warning(f"Leaderboard message deleted, creating new one")
                new_message = await channel.send(embed=embed)
                
                # Update database with new message ID
                await LeaderboardManager._update_leaderboard_message_id(
                    trial_id, channel.id, new_message.id
                )
                return True
                
            except discord.Forbidden:
                logger.error(f"No permission to edit leaderboard message")
                return False
            except discord.HTTPException as e:
                logger.error(f"Failed to update leaderboard message: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error updating leaderboard: {e}")
            return False
    
    @staticmethod
    async def finalize_live_leaderboard(trial_id: int, guild: discord.Guild) -> bool:
        """
        Update a live leaderboard to show final results when trial ends.
        
        Args:
            trial_id: Database ID of the trial
            guild: Discord guild object
            
        Returns:
            True if finalization successful, False otherwise
        """
        # Same logic as update, but the trial status will be 'ended'
        # which will be reflected in the embed automatically
        return await LeaderboardManager.update_live_leaderboard(trial_id, guild)
    
    @staticmethod
    async def _get_trial_with_message_info(trial_id: int) -> Optional[Dict[str, Any]]:
        """Get trial data including leaderboard message information."""
        query = """
            SELECT 
                id,
                trial_number,
                track_name,
                gold_time_ms,
                silver_time_ms,
                bronze_time_ms,
                start_date,
                end_date,
                status,
                guild_id,
                leaderboard_channel_id,
                leaderboard_message_id
            FROM weekly_trials 
            WHERE id = %s
        """
        
        try:
            results = db_manager.execute_query(query, (trial_id,))
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to get trial data: {e}")
            return None
    
    @staticmethod
    async def _get_leaderboard_data(trial_id: int, trial_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get leaderboard data for a trial with medal calculations."""
        gold_ms = trial_data['gold_time_ms']
        silver_ms = trial_data['silver_time_ms']
        bronze_ms = trial_data['bronze_time_ms']
        
        query = """
            SELECT 
                ROW_NUMBER() OVER (ORDER BY time_ms ASC) as rank,
                user_id,
                time_ms,
                submitted_at,
                updated_at,
                CASE 
                    WHEN %s IS NOT NULL AND %s IS NOT NULL AND %s IS NOT NULL THEN
                        CASE 
                            WHEN time_ms <= %s THEN 'gold'
                            WHEN time_ms <= %s THEN 'silver'  
                            WHEN time_ms <= %s THEN 'bronze'
                            ELSE 'none'
                        END
                    ELSE 'none'
                END as medal
            FROM player_times 
            WHERE trial_id = %s
            ORDER BY time_ms ASC
        """
        
        try:
            return db_manager.execute_query(query, (gold_ms, silver_ms, bronze_ms, gold_ms, silver_ms, bronze_ms, trial_id))
        except Exception as e:
            logger.error(f"Failed to get leaderboard data: {e}")
            return []
    
    @staticmethod
    async def _create_leaderboard_embed(trial_data: Dict[str, Any], 
                                      leaderboard_data: List[Dict[str, Any]],
                                      user_display_names: Dict[int, str]) -> discord.Embed:
        """Create leaderboard embed using existing formatter."""
        return EmbedFormatter.create_leaderboard_embed(
            trial_data, leaderboard_data, user_display_names
        )
    
    @staticmethod
    async def _update_leaderboard_message_id(trial_id: int, 
                                           channel_id: int, 
                                           message_id: int) -> None:
        """Update the leaderboard message ID in the database."""
        query = """
            UPDATE weekly_trials 
            SET leaderboard_channel_id = %s,
                leaderboard_message_id = %s
            WHERE id = %s
        """
        
        try:
            db_manager.execute_query(query, (channel_id, message_id, trial_id), fetch=False)
            logger.debug(f"Updated leaderboard message ID for trial {trial_id}")
        except Exception as e:
            logger.error(f"Failed to update leaderboard message ID: {e}")
            raise


# Convenience functions for easy importing
async def create_live_leaderboard(trial_data: Dict[str, Any], 
                                channel: discord.TextChannel) -> Optional[discord.Message]:
    """Create a new live leaderboard message."""
    return await LeaderboardManager.create_live_leaderboard(trial_data, channel)

async def update_live_leaderboard(trial_data_or_id: Union[Dict[str, Any], int], guild: Optional[discord.Guild] = None) -> bool:
    """Update an existing live leaderboard message."""
    return await LeaderboardManager.update_live_leaderboard(trial_data_or_id, guild)

async def finalize_live_leaderboard(trial_id: int, guild: discord.Guild) -> bool:
    """Finalize a live leaderboard when trial ends."""
    return await LeaderboardManager.finalize_live_leaderboard(trial_id, guild)