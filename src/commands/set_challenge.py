"""
Set challenge command for the MKW Time Trial Bot.

This command allows users to create new weekly time trial challenges
with specified goal times and duration.
"""

from datetime import datetime, timedelta, timezone
from typing import List
import logging
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter
from ..config.settings import settings

logger = logging.getLogger(__name__)


class SetChallengeCommand(AutocompleteCommand):
    """
    Command to create a new weekly time trial challenge.
    
    This command handles:
    - Track name validation with autocomplete
    - Goal time validation and ordering
    - Duration validation
    - Checking concurrent trial limits
    - Creating the trial in database
    - Sending confirmation
    """
    
    async def execute(self, interaction: Interaction, track: str, gold_time: str, 
                     silver_time: str, bronze_time: str, duration_days: int) -> None:
        """
        Execute the set challenge command.
        
        Args:
            interaction: Discord interaction object
            track: Track name (validated via autocomplete)
            gold_time: Gold medal goal time in MM:SS.mmm format
            silver_time: Silver medal goal time in MM:SS.mmm format
            bronze_time: Bronze medal goal time in MM:SS.mmm format
            duration_days: Challenge duration in days
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)
        
        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)
        
        # Validate goal times
        try:
            gold_ms, silver_ms, bronze_ms = InputValidator.validate_goal_times(
                gold_time, silver_time, bronze_time
            )
        except ValidationError as e:
            raise ValidationError(e)
        
        # Validate duration
        try:
            duration = InputValidator.validate_duration_days(duration_days)
        except ValidationError as e:
            raise ValidationError(e)
        
        # Check if there's already an active trial for this track
        existing_trial = await self._get_active_trial_by_track(guild_id, track_name)
        if existing_trial:
            raise CommandError(
                f"There's already an active trial for **{track_name}** "
                f"(Trial #{existing_trial['trial_number']}). End it first using "
                f"`/end-challenge {track_name}` before creating a new one."
            )
        
        # Check concurrent trial limit
        active_count = await self._count_active_trials(guild_id)
        if active_count >= settings.MAX_CONCURRENT_TRIALS:
            raise CommandError(
                f"Maximum of {settings.MAX_CONCURRENT_TRIALS} concurrent trials allowed. "
                f"End an existing trial before creating a new one."
            )
        
        # Calculate end date
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=duration)
        
        # Get next trial number
        trial_number = await self._get_next_trial_number(guild_id)
        
        # Create the trial
        trial_data = await self._create_trial(
            guild_id=guild_id,
            trial_number=trial_number,
            track_name=track_name,
            gold_ms=gold_ms,
            silver_ms=silver_ms,
            bronze_ms=bronze_ms,
            end_date=end_date
        )
        
        # Create live leaderboard message
        from ..utils.leaderboard_manager import create_live_leaderboard
        
        try:
            leaderboard_message = await create_live_leaderboard(trial_data, interaction.channel)
            if leaderboard_message:
                logger.info(f"Created live leaderboard for trial #{trial_number}")
            else:
                logger.warning(f"Failed to create live leaderboard for trial #{trial_number}")
        except Exception as e:
            # Don't fail the command if leaderboard creation fails
            logger.error(f"Error creating live leaderboard: {e}")
        
        # Create success response
        embed = EmbedFormatter.create_trial_created_embed(trial_data)
        
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def _create_trial(self, guild_id: int, trial_number: int, track_name: str,
                          gold_ms: int, silver_ms: int, bronze_ms: int, 
                          end_date: datetime) -> dict:
        """
        Create a new trial in the database.
        
        Args:
            guild_id: Discord guild ID
            trial_number: Sequential trial number
            track_name: Track name
            gold_ms: Gold medal time in milliseconds
            silver_ms: Silver medal time in milliseconds  
            bronze_ms: Bronze medal time in milliseconds
            end_date: When the trial ends
            
        Returns:
            Created trial data
            
        Raises:
            CommandError: If creation fails
        """
        query = """
            INSERT INTO weekly_trials (
                trial_number, 
                track_name, 
                gold_time_ms, 
                silver_time_ms, 
                bronze_time_ms, 
                end_date, 
                guild_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, trial_number, track_name, gold_time_ms, silver_time_ms, bronze_time_ms, start_date, end_date
        """
        
        params = (trial_number, track_name, gold_ms, silver_ms, bronze_ms, end_date, guild_id)
        results = self._execute_query(query, params, fetch=True)
        
        if not results:
            raise CommandError("Failed to create trial. Please try again.")
        
        return results[0]
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.
        
        Shows all MKW tracks, prioritizing those without active trials.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices for all tracks
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            
            # Get tracks with active trials to deprioritize them
            active_tracks = await self._get_active_track_names(guild_id)
            all_tracks = TrackManager.get_all_tracks()
            
            # Prioritize tracks without active trials
            available_tracks = [track for track in all_tracks if track not in active_tracks]
            busy_tracks = [track for track in all_tracks if track in active_tracks]
            
            # Combine lists (available first, then busy)
            prioritized_tracks = available_tracks + busy_tracks
            
            # Filter based on user input
            if current:
                current_lower = current.lower()
                filtered_tracks = [
                    track for track in prioritized_tracks
                    if current_lower in track.lower()
                ]
            else:
                filtered_tracks = prioritized_tracks
            
            # Limit to 25 choices (Discord limit)
            filtered_tracks = filtered_tracks[:25]
            
            return [
                app_commands.Choice(name=track, value=track)
                for track in filtered_tracks
            ]
            
        except Exception as e:
            self.logger.error(f"Autocomplete error: {e}")
            # Fallback to all tracks
            return [
                app_commands.Choice(name=choice['name'], value=choice['value'])
                for choice in get_track_autocomplete_choices(current)[:25]
            ]
    
    async def _get_active_track_names(self, guild_id: int) -> List[str]:
        """
        Get list of track names that have active trials.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of track names with active trials
        """
        query = """
            SELECT DISTINCT track_name
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND status = 'active'
        """
        
        try:
            results = self._execute_query(query, (guild_id,))
            return [row['track_name'] for row in results]
        except Exception:
            return []


# Command setup function for the main bot file
def setup_set_challenge_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the set challenge command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    set_cmd = SetChallengeCommand()
    
    @tree.command(
        name="set-challenge",
        description="Create a new weekly time trial challenge"
    )
    @app_commands.describe(
        track="Select the track for the challenge",
        gold_time="Gold medal goal time (MM:SS.mmm format, e.g., '2:20.000')",
        silver_time="Silver medal goal time (MM:SS.mmm format, e.g., '2:25.000')",
        bronze_time="Bronze medal goal time (MM:SS.mmm format, e.g., '2:30.000')",
        duration_days="Challenge duration in days (1-30)"
    )
    async def set_challenge(interaction: Interaction, track: str, gold_time: str, 
                           silver_time: str, bronze_time: str, duration_days: int):
        """
        Create a new weekly time trial challenge.
        
        Sets up a new challenge with goal times for gold, silver, and bronze medals.
        The challenge will automatically expire after the specified duration.
        
        Examples:
        /set-challenge track:Rainbow Road gold_time:2:20.000 silver_time:2:25.000 bronze_time:2:30.000 duration_days:7
        /set-challenge track:Mario Circuit gold_time:1:40.000 silver_time:1:45.000 bronze_time:1:50.000 duration_days:14
        
        Requirements:
        - Gold time must be faster than or equal to silver time
        - Silver time must be faster than or equal to bronze time
        - Duration must be between 1-30 days
        - Maximum 2 concurrent active trials per server
        """
        await set_cmd.handle_command(
            interaction, 
            track=track, 
            gold_time=gold_time, 
            silver_time=silver_time,
            bronze_time=bronze_time, 
            duration_days=duration_days
        )
    
    @set_challenge.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - prioritizes tracks without active trials."""
        return await set_cmd.autocomplete_callback(interaction, current)