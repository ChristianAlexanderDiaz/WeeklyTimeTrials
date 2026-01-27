"""
Base command class for the MKW Time Trial Bot.

This module provides the BaseCommand class that all bot commands inherit from.
It implements common functionality like error handling, validation, and
database operations to follow DRY (Don't Repeat Yourself) principles.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import discord
from discord import app_commands, Interaction

from ..database.connection import db_manager
from ..utils.validators import ValidationError, InputValidator
from ..utils.formatters import EmbedFormatter
from ..utils.user_utils import UserManager
from ..config.settings import settings

logger = logging.getLogger(__name__)


class CommandError(Exception):
    """Base exception for command execution errors."""
    pass


class BaseCommand(ABC):
    """
    Abstract base class for all bot commands.
    
    This class provides common functionality for command validation,
    error handling, database operations, and response formatting.
    All bot commands should inherit from this class.
    """
    
    def __init__(self):
        """Initialize the base command."""
        self.name = self.__class__.__name__.lower()
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
    
    @abstractmethod
    async def execute(self, interaction: Interaction, **kwargs) -> None:
        """
        Execute the command logic.
        
        This method must be implemented by all command subclasses.
        It contains the main logic for the command execution.
        
        Args:
            interaction: Discord interaction object
            **kwargs: Command-specific arguments
        """
        pass
    
    async def handle_command(self, interaction: Interaction, **kwargs) -> None:
        """
        Main entry point for command execution with error handling.
        
        This method wraps the execute() method with comprehensive error
        handling, logging, and user feedback. It should be called by
        the Discord command handlers.
        
        Args:
            interaction: Discord interaction object
            **kwargs: Command-specific arguments
        """
        try:
            # Validate that the interaction is from a guild
            guild_id = self._validate_guild_interaction(interaction)
            
            # Log command execution
            self.logger.info(
                f"Executing {self.name} command for user {interaction.user.id} "
                f"in guild {guild_id}"
            )
            
            # Execute the command
            await self.execute(interaction, **kwargs)
            
            self.logger.info(f"Successfully executed {self.name} command")
            
        except ValidationError as e:
            # Handle validation errors with user-friendly messages
            await self._send_validation_error(interaction, str(e))
            self.logger.warning(f"Validation error in {self.name}: {e}")
            
        except CommandError as e:
            # Handle command-specific errors
            await self._send_command_error(interaction, str(e))
            self.logger.error(f"Command error in {self.name}: {e}")
            
        except Exception as e:
            # Handle unexpected errors
            await self._send_unexpected_error(interaction)
            self.logger.error(f"Unexpected error in {self.name}: {e}", exc_info=True)
    
    def _validate_guild_interaction(self, interaction: Interaction) -> int:
        """
        Validate that the interaction is from a guild and return guild ID.
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            int: Guild ID
            
        Raises:
            ValidationError: If interaction is not from a guild
        """
        return InputValidator.validate_guild_interaction(interaction)
    
    def _validate_user_interaction(self, interaction: Interaction) -> int:
        """
        Validate interaction and return user ID.
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            int: User ID
            
        Raises:
            ValidationError: If user information is unavailable
        """
        return InputValidator.validate_user_interaction(interaction)
    
    async def _send_validation_error(self, interaction: Interaction, message: str) -> None:
        """
        Send a validation error response to the user.
        
        Args:
            interaction: Discord interaction object
            message: Error message to display
        """
        embed = EmbedFormatter.create_error_embed(
            "Invalid Input",
            message
        )
        await self._send_response(interaction, embed=embed, ephemeral=True)
    
    async def _send_command_error(self, interaction: Interaction, message: str) -> None:
        """
        Send a command error response to the user.
        
        Args:
            interaction: Discord interaction object
            message: Error message to display
        """
        embed = EmbedFormatter.create_error_embed(
            "Command Failed",
            message
        )
        await self._send_response(interaction, embed=embed, ephemeral=True)
    
    async def _send_unexpected_error(self, interaction: Interaction) -> None:
        """
        Send an unexpected error response to the user.
        
        Args:
            interaction: Discord interaction object
        """
        embed = EmbedFormatter.create_error_embed(
            "Cynical you braindead fuck 🤡",
            "The bot had a little fucky wucky and had an absoulte howler!",
            "If this keeps happening, make sure to ping Cynical 'wanker' because he probably broke something again. 💀"
        )
        await self._send_response(interaction, embed=embed, ephemeral=True)
    
    async def _send_response(self, interaction: Interaction, 
                           content: Optional[str] = None,
                           embed: Optional[discord.Embed] = None,
                           ephemeral: bool = False) -> None:
        """
        Send a response to the Discord interaction.
        
        Handles both initial responses and follow-ups depending on
        whether the interaction has already been responded to.
        
        Args:
            interaction: Discord interaction object
            content: Text content to send
            embed: Embed to send
            ephemeral: Whether the response should be ephemeral (private)
        """
        try:
            if interaction.response.is_done():
                # Interaction already responded to, send follow-up
                await interaction.followup.send(
                    content=content,
                    embed=embed,
                    ephemeral=ephemeral
                )
            else:
                # Send initial response
                await interaction.response.send_message(
                    content=content,
                    embed=embed,
                    ephemeral=ephemeral
                )
        except Exception as e:
            self.logger.error(f"Failed to send response: {e}")
    
    def _execute_query(self, query: str, params: tuple = (), fetch: bool = True) -> List[Dict[str, Any]]:
        """
        Execute a database query with error handling.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch results
            
        Returns:
            List of dictionaries representing query results
            
        Raises:
            CommandError: If database operation fails
        """
        try:
            return db_manager.execute_query(query, params, fetch)
        except Exception as e:
            self.logger.error(f"Database query failed: {e}")
            raise CommandError("Database operation failed. Please try again.")
    
    def _execute_transaction(self, operations: List[tuple]) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple queries in a transaction with error handling.
        
        Args:
            operations: List of (query, params) tuples
            
        Returns:
            List of results for each query
            
        Raises:
            CommandError: If transaction fails
        """
        try:
            return db_manager.execute_transaction(operations)
        except Exception as e:
            self.logger.error(f"Database transaction failed: {e}")
            raise CommandError("Database operation failed. Please try again.")
    
    async def _get_active_trial_by_track(self, guild_id: int, track_name: str) -> Optional[Dict[str, Any]]:
        """
        Get active trial information for a specific track.
        
        Args:
            guild_id: Discord guild ID
            track_name: Track name to search for
            
        Returns:
            Trial data dictionary or None if not found
            
        Raises:
            CommandError: If database operation fails
        """
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
                status
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND track_name = %s 
                AND status = 'active'
            LIMIT 1
        """
        
        results = self._execute_query(query, (guild_id, track_name))
        return results[0] if results else None
    
    async def _get_trial_by_track(self, guild_id: int, track_name: str) -> Optional[Dict[str, Any]]:
        """
        Get trial information for a specific track (any status).
        
        Args:
            guild_id: Discord guild ID
            track_name: Track name to search for
            
        Returns:
            Most recent trial data for the track or None if not found
        """
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
                status
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND track_name = %s
            ORDER BY trial_number DESC
            LIMIT 1
        """
        
        results = self._execute_query(query, (guild_id, track_name))
        return results[0] if results else None
    
    async def _get_user_time_for_trial(self, trial_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a user's current time for a trial.
        
        Args:
            trial_id: Trial ID
            user_id: Discord user ID
            
        Returns:
            User's time data or None if no time submitted
        """
        query = """
            SELECT 
                id,
                time_ms,
                submitted_at,
                updated_at
            FROM player_times 
            WHERE trial_id = %s 
                AND user_id = %s
        """
        
        results = self._execute_query(query, (trial_id, user_id))
        return results[0] if results else None
    
    async def _get_leaderboard_data(self, trial_id: int, trial_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get leaderboard data for a trial with medal calculations.
        
        Args:
            trial_id: Trial ID
            trial_data: Trial information including goal times

        Returns:
            List of player times with rankings and medal information
        """
        gold_ms = trial_data.get('gold_time_ms')
        silver_ms = trial_data.get('silver_time_ms')
        bronze_ms = trial_data.get('bronze_time_ms')

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

        return self._execute_query(query, (gold_ms, silver_ms, bronze_ms, gold_ms, silver_ms, bronze_ms, trial_id))
    
    async def _get_next_trial_number(self, guild_id: int) -> int:
        """
        Get the next trial number for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Next sequential trial number
        """
        query = """
            SELECT COALESCE(MAX(trial_number), 0) + 1 as next_trial_number
            FROM weekly_trials 
            WHERE guild_id = %s
        """
        
        results = self._execute_query(query, (guild_id,))
        return results[0]['next_trial_number']
    
    async def _count_active_trials(self, guild_id: int) -> int:
        """
        Count the number of active trials for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Number of active trials
        """
        query = """
            SELECT COUNT(*) as active_count
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND status = 'active'
        """
        
        results = self._execute_query(query, (guild_id,))
        return results[0]['active_count']


class AutocompleteCommand(BaseCommand):
    """
    Extended base class for commands that need autocomplete functionality.
    
    This class adds support for Discord slash command autocomplete,
    specifically for track names in the MKW time trial bot.
    """
    
    @abstractmethod
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Handle autocomplete for command parameters.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices
        """
        pass