"""
Guild settings management for the MKW Time Trial Bot.

This module handles server-specific bot configuration and preferences,
such as default leaderboard channels and other per-server settings.
"""

import logging
from typing import Optional, Dict, Any
import discord

from ..database.connection import db_manager

logger = logging.getLogger(__name__)


class GuildSettingsManager:
    """
    Manages server-specific bot settings and preferences.
    
    This class provides methods for storing and retrieving guild-specific
    configuration, such as default leaderboard channels.
    """
    
    @staticmethod
    async def set_leaderboard_channel(guild_id: int, channel_id: int) -> bool:
        """
        Set the default leaderboard channel for a guild.
        
        Args:
            guild_id: Discord guild ID
            channel_id: Discord channel ID for leaderboards
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use UPSERT (INSERT ... ON CONFLICT) to handle both new and existing records
            query = """
                INSERT INTO guild_settings (guild_id, leaderboard_channel_id, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (guild_id) 
                DO UPDATE SET 
                    leaderboard_channel_id = EXCLUDED.leaderboard_channel_id,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            db_manager.execute_query(query, (guild_id, channel_id), fetch=False)
            
            logger.info(f"Set leaderboard channel for guild {guild_id} to channel {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set leaderboard channel: {e}")
            return False
    
    @staticmethod
    async def get_leaderboard_channel(guild_id: int) -> Optional[int]:
        """
        Get the default leaderboard channel for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Channel ID if set, None if not configured
        """
        try:
            query = """
                SELECT leaderboard_channel_id 
                FROM guild_settings 
                WHERE guild_id = %s
            """
            
            results = db_manager.execute_query(query, (guild_id,))
            if results and results[0]['leaderboard_channel_id']:
                return results[0]['leaderboard_channel_id']
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get leaderboard channel: {e}")
            return None
    
    @staticmethod
    async def remove_leaderboard_channel(guild_id: int) -> bool:
        """
        Remove the leaderboard channel setting for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                UPDATE guild_settings 
                SET leaderboard_channel_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = %s
            """
            
            db_manager.execute_query(query, (guild_id,), fetch=False)
            
            logger.info(f"Removed leaderboard channel setting for guild {guild_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove leaderboard channel: {e}")
            return False
    
    @staticmethod
    async def get_all_settings(guild_id: int) -> Optional[Dict[str, Any]]:
        """
        Get all settings for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary of settings, or None if no settings exist
        """
        try:
            query = """
                SELECT 
                    guild_id,
                    leaderboard_channel_id,
                    created_at,
                    updated_at
                FROM guild_settings 
                WHERE guild_id = %s
            """
            
            results = db_manager.execute_query(query, (guild_id,))
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"Failed to get guild settings: {e}")
            return None


class LeaderboardChannelResolver:
    """
    Helper class to resolve which channel should be used for leaderboard messages.
    """
    
    @staticmethod
    async def get_leaderboard_channel(guild: discord.Guild, 
                                     fallback_channel: discord.TextChannel) -> discord.TextChannel:
        """
        Get the appropriate channel for posting leaderboard messages.
        
        Args:
            guild: Discord guild object
            fallback_channel: Channel to use if no preference is set
            
        Returns:
            Channel to use for leaderboard (either saved preference or fallback)
        """
        try:
            # Check if guild has a saved leaderboard channel preference
            saved_channel_id = await GuildSettingsManager.get_leaderboard_channel(guild.id)
            
            if saved_channel_id:
                # Try to get the saved channel
                saved_channel = guild.get_channel(saved_channel_id)
                
                if saved_channel and isinstance(saved_channel, discord.TextChannel):
                    # Verify bot has necessary permissions
                    permissions = saved_channel.permissions_for(guild.me)
                    if permissions.send_messages and permissions.embed_links:
                        logger.info(f"Using saved leaderboard channel: {saved_channel.name}")
                        return saved_channel
                    else:
                        logger.warning(
                            f"Bot lacks permissions in saved channel {saved_channel.name}, "
                            f"falling back to current channel"
                        )
                else:
                    logger.warning(
                        f"Saved leaderboard channel {saved_channel_id} not found, "
                        f"falling back to current channel"
                    )
            
            # Use fallback channel
            logger.info(f"Using fallback channel: {fallback_channel.name}")
            return fallback_channel
            
        except Exception as e:
            logger.error(f"Error resolving leaderboard channel: {e}")
            return fallback_channel


# Convenience functions for easy importing
async def set_leaderboard_channel(guild_id: int, channel_id: int) -> bool:
    """Set the default leaderboard channel for a guild."""
    return await GuildSettingsManager.set_leaderboard_channel(guild_id, channel_id)

async def get_leaderboard_channel(guild_id: int) -> Optional[int]:
    """Get the default leaderboard channel for a guild."""
    return await GuildSettingsManager.get_leaderboard_channel(guild_id)

async def resolve_leaderboard_channel(guild: discord.Guild, 
                                    fallback_channel: discord.TextChannel) -> discord.TextChannel:
    """Resolve which channel to use for leaderboard messages."""
    return await LeaderboardChannelResolver.get_leaderboard_channel(guild, fallback_channel)