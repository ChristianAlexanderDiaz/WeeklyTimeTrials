"""
Discord user utilities for the MKW Time Trial Bot.

This module provides functions for resolving Discord user information
and formatting user data for display in leaderboards and messages.
"""

import logging
from typing import Optional, Dict, Any
import discord
from discord import Guild, Member, User

logger = logging.getLogger(__name__)


class UserManager:
    """
    Manages Discord user information and display name resolution.
    
    This class provides methods for getting user display names,
    handling user lookups, and formatting user information for
    leaderboard displays.
    """
    
    @staticmethod
    async def get_display_name(user_id: int, guild: Guild) -> str:
        """
        Get the current display name for a user in a specific guild.
        
        This method attempts to fetch the user from the guild to get their
        current nickname or display name. If the user is no longer in the
        guild, it falls back to a generic display.
        
        Args:
            user_id: Discord user ID
            guild: Discord guild object
            
        Returns:
            str: User's display name, nickname, or fallback string
            
        Example:
            >>> await UserManager.get_display_name(123456789, guild)
            "CynicalGamer"  # Their server nickname
            >>> await UserManager.get_display_name(999999999, guild)  
            "User 999999999"  # User not found fallback
        """
        try:
            # Try to get the member from the guild (includes nickname)
            member = await guild.fetch_member(user_id)
            if member:
                # member.display_name returns nickname if set, otherwise global display name
                return member.display_name
                
        except discord.NotFound:
            # User is not in the guild anymore
            logger.debug(f"User {user_id} not found in guild {guild.id}")
        except discord.Forbidden:
            # Bot doesn't have permission to fetch member
            logger.warning(f"No permission to fetch user {user_id} in guild {guild.id}")
        except discord.HTTPException as e:
            # Other Discord API error
            logger.error(f"Error fetching user {user_id}: {e}")
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error fetching user {user_id}: {e}")
        
        # Try to get user from cache or API (no guild-specific info)
        try:
            user = await guild.get_or_fetch_user(user_id)
            if user:
                return user.display_name or user.name
        except Exception as e:
            logger.debug(f"Could not fetch user {user_id} from API: {e}")
        
        # Final fallback
        return f"User {user_id}"
    
    @staticmethod
    async def get_user_info(user_id: int, guild: Guild) -> Dict[str, Any]:
        """
        Get comprehensive user information for display purposes.
        
        Args:
            user_id: Discord user ID
            guild: Discord guild object
            
        Returns:
            dict: User information including display name, avatar, etc.
            
        Example:
            >>> await UserManager.get_user_info(123456789, guild)
            {
                "display_name": "CynicalGamer",
                "avatar_url": "https://cdn.discordapp.com/avatars/...",
                "is_in_guild": True,
                "is_bot": False
            }
        """
        user_info = {
            "display_name": f"User {user_id}",
            "avatar_url": None,
            "is_in_guild": False,
            "is_bot": False
        }
        
        try:
            # Try to get member first (guild-specific info)
            member = await guild.fetch_member(user_id)
            if member:
                user_info.update({
                    "display_name": member.display_name,
                    "avatar_url": member.display_avatar.url,
                    "is_in_guild": True,
                    "is_bot": member.bot
                })
                return user_info
                
        except discord.NotFound:
            pass  # User not in guild, try global lookup
        except Exception as e:
            logger.debug(f"Error fetching member {user_id}: {e}")
        
        try:
            # Try global user lookup
            user = await guild.get_or_fetch_user(user_id)
            if user:
                user_info.update({
                    "display_name": user.display_name or user.name,
                    "avatar_url": user.display_avatar.url,
                    "is_bot": user.bot
                })
                
        except Exception as e:
            logger.debug(f"Error fetching user {user_id}: {e}")
        
        return user_info
    
    @staticmethod
    async def bulk_get_display_names(user_ids: list[int], guild: Guild) -> Dict[int, str]:
        """
        Get display names for multiple users efficiently.
        
        This method fetches display names for multiple users and returns
        a mapping of user IDs to display names. Useful for leaderboards
        with many participants.
        
        Args:
            user_ids: List of Discord user IDs
            guild: Discord guild object
            
        Returns:
            dict: Mapping of user_id -> display_name
            
        Example:
            >>> await UserManager.bulk_get_display_names([123, 456, 789], guild)
            {123: "Alice", 456: "Bob", 789: "Charlie"}
        """
        display_names = {}
        
        # Process users in batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(user_ids), batch_size):
            batch = user_ids[i:i + batch_size]
            
            for user_id in batch:
                display_names[user_id] = await UserManager.get_display_name(user_id, guild)
        
        return display_names
    
    @staticmethod
    def format_user_mention(user_id: int, display_name: str) -> str:
        """
        Format a user for display with mention capability.
        
        Args:
            user_id: Discord user ID  
            display_name: User's display name
            
        Returns:
            str: Formatted user string with mention
            
        Example:
            >>> UserManager.format_user_mention(123456789, "CynicalGamer")
            "CynicalGamer (<@123456789>)"
        """
        return f"{display_name} (<@{user_id}>)"
    
    @staticmethod
    def format_user_simple(display_name: str) -> str:
        """
        Format a user for simple display without mention.
        
        Args:
            display_name: User's display name
            
        Returns:
            str: Simple formatted user string
            
        Example:
            >>> UserManager.format_user_simple("CynicalGamer")
            "CynicalGamer"
        """
        return display_name
    
    @staticmethod
    def truncate_display_name(display_name: str, max_length: int = 20) -> str:
        """
        Truncate display name if too long for leaderboard formatting.
        
        Args:
            display_name: User's display name
            max_length: Maximum length allowed
            
        Returns:
            str: Truncated display name with ellipsis if needed
            
        Example:
            >>> UserManager.truncate_display_name("VeryLongUsernameHere", 10)
            "VeryLon..."
        """
        if len(display_name) <= max_length:
            return display_name
        
        return display_name[:max_length-3] + "..."
    
    @staticmethod
    async def validate_user_permissions(interaction: discord.Interaction, 
                                      required_permissions: Optional[discord.Permissions] = None) -> bool:
        """
        Validate that a user has required permissions for admin commands.
        
        Args:
            interaction: Discord interaction object
            required_permissions: Required permissions (default: administrator)
            
        Returns:
            bool: True if user has required permissions
        """
        if not interaction.guild or not interaction.user:
            return False
        
        # Default to administrator permission
        if required_permissions is None:
            required_permissions = discord.Permissions(administrator=True)
        
        # Get member object to check permissions
        try:
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                member = await interaction.guild.fetch_member(interaction.user.id)
            
            return member.guild_permissions >= required_permissions
            
        except Exception as e:
            logger.error(f"Error checking permissions for user {interaction.user.id}: {e}")
            return False
    
    @staticmethod
    def is_bot_admin(user_id: int) -> bool:
        """
        Check if a user is a bot administrator (for future use).
        
        This could be expanded to check a database table of bot admins
        or use a configuration file for bot-specific permissions.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            bool: True if user is a bot admin
        """
        # For now, this is just a placeholder
        # In the future, this could check a database table or config file
        bot_admins = []  # Could be loaded from environment or database
        return user_id in bot_admins


async def get_display_name(user_id: int, guild: Guild) -> str:
    """
    Convenience function to get a user's display name.
    
    Args:
        user_id: Discord user ID
        guild: Discord guild object
        
    Returns:
        str: User's display name
    """
    return await UserManager.get_display_name(user_id, guild)


async def bulk_get_display_names(user_ids: list[int], guild: Guild) -> Dict[int, str]:
    """
    Convenience function to get multiple users' display names.
    
    Args:
        user_ids: List of Discord user IDs
        guild: Discord guild object
        
    Returns:
        dict: Mapping of user_id -> display_name
    """
    return await UserManager.bulk_get_display_names(user_ids, guild)