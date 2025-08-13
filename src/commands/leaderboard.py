"""
Leaderboard command for the MKW Time Trial Bot.

This command displays the leaderboard for a specific track's weekly trial,
showing all participants ranked by their times with medal indicators.
"""

from typing import List, Dict, Any
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter
from ..utils.user_utils import bulk_get_display_names


class LeaderboardCommand(AutocompleteCommand):
    """
    Command to display the leaderboard for a weekly trial.
    
    This command handles:
    - Track name validation with autocomplete
    - Finding trials (active or inactive)
    - Fetching leaderboard data with rankings
    - Resolving user display names
    - Formatting leaderboard embed
    """
    
    async def execute(self, interaction: Interaction, track: str) -> None:
        """
        Execute the leaderboard command.
        
        Args:
            interaction: Discord interaction object
            track: Track name (validated via autocomplete)
        """
        guild_id = self._validate_guild_interaction(interaction)
        
        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)
        
        # Get trial for this track (any status - active, expired, or ended)
        trial_data = await self._get_trial_by_track(guild_id, track_name)
        if not trial_data:
            raise CommandError(
                f"No trial found for **{track_name}**. "
                f"Ask an admin to create a challenge for this track!"
            )
        
        trial_id = trial_data['id']
        
        # Get leaderboard data
        leaderboard_data = await self._get_leaderboard_data(trial_id, trial_data)
        
        # Get user display names for all participants
        user_ids = [row['user_id'] for row in leaderboard_data]
        user_display_names = {}
        
        if user_ids:
            user_display_names = await bulk_get_display_names(user_ids, interaction.guild)
        
        # Create leaderboard embed
        embed = EmbedFormatter.create_leaderboard_embed(
            trial_data=trial_data,
            leaderboard_data=leaderboard_data,
            user_display_names=user_display_names
        )
        
        # Send response (not ephemeral - everyone can see leaderboards)
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.
        
        Shows all tracks that have trials (active or inactive) to allow
        viewing historical leaderboards.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices for tracks with trials
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            
            # Get tracks that have any trials (not just active)
            trial_tracks = await self._get_trial_track_names(guild_id)
            
            # Filter tracks based on user input
            if current:
                current_lower = current.lower()
                filtered_tracks = [
                    track for track in trial_tracks
                    if current_lower in track.lower()
                ]
            else:
                filtered_tracks = trial_tracks
            
            # Limit to 25 choices (Discord limit)
            filtered_tracks = filtered_tracks[:25]
            
            return [
                app_commands.Choice(name=track, value=track)
                for track in filtered_tracks
            ]
            
        except Exception as e:
            self.logger.error(f"Autocomplete error: {e}")
            # Fallback to all tracks if database query fails
            return [
                app_commands.Choice(name=choice['name'], value=choice['value'])
                for choice in get_track_autocomplete_choices(current)[:25]
            ]
    
    async def _get_trial_track_names(self, guild_id: int) -> List[str]:
        """
        Get list of track names that have any trials (active or inactive).
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of track names with trials, ordered by most recent
        """
        query = """
            SELECT DISTINCT track_name
            FROM weekly_trials 
            WHERE guild_id = %s
            ORDER BY track_name
        """
        
        try:
            results = self._execute_query(query, (guild_id,))
            return [row['track_name'] for row in results]
        except Exception:
            # Fallback to empty list if query fails
            return []


# Alternative leaderboard command that shows all active trials
class ActiveTrialsCommand(AutocompleteCommand):
    """
    Command to display all currently active trials and their leaderboards.
    
    This gives users an overview of all ongoing challenges.
    """
    
    async def execute(self, interaction: Interaction) -> None:
        """
        Execute the active trials overview command.
        
        Args:
            interaction: Discord interaction object
        """
        guild_id = self._validate_guild_interaction(interaction)
        
        # Get all active trials
        active_trials = await self._get_active_trials(guild_id)
        
        if not active_trials:
            embed = EmbedFormatter.create_info_embed(
                "No Active Trials",
                "There are currently no active time trials. Ask an admin to create one!"
            )
            await self._send_response(interaction, embed=embed, ephemeral=True)
            return
        
        # Create overview embed
        embed = await self._create_active_trials_embed(active_trials, interaction.guild)
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def _get_active_trials(self, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get all active trials for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of active trial data
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
                AND status = 'active'
            ORDER BY trial_number DESC
        """
        
        return self._execute_query(query, (guild_id,))
    
    async def _create_active_trials_embed(self, trials: List[Dict[str, Any]], guild) -> discord.Embed:
        """
        Create an embed showing all active trials.
        
        Args:
            trials: List of active trial data
            guild: Discord guild object
            
        Returns:
            Formatted embed with active trials overview
        """
        embed = discord.Embed(
            title="🏁 Active Time Trials",
            description=f"Currently **{len(trials)}** active trial(s)",
            color=EmbedFormatter.COLOR_INFO
        )
        
        for trial in trials:
            trial_id = trial['id']
            trial_number = trial['trial_number']
            track_name = trial['track_name']
            
            # Get participant count
            participant_count = await self._get_trial_participant_count(trial_id)
            
            # Get fastest time if any submissions
            fastest_time_str = "No times yet"
            if participant_count > 0:
                fastest_time_data = await self._get_fastest_time(trial_id, guild)
                if fastest_time_data:
                    fastest_time_str = f"{fastest_time_data['time_str']} by {fastest_time_data['username']}"
            
            field_value = (
                f"**Participants:** {participant_count}\n"
                f"**Fastest Time:** {fastest_time_str}\n"
                f"*Use `/leaderboard {track_name}` for full standings*"
            )
            
            embed.add_field(
                name=f"Trial #{trial_number} - {track_name}",
                value=field_value,
                inline=True
            )
        
        embed.set_footer(text="Use /weeklytimesave to submit your time!")
        return embed
    
    async def _get_trial_participant_count(self, trial_id: int) -> int:
        """
        Get the number of participants in a trial.
        
        Args:
            trial_id: Trial ID
            
        Returns:
            Number of participants
        """
        query = """
            SELECT COUNT(*) as participant_count
            FROM player_times 
            WHERE trial_id = %s
        """
        
        results = self._execute_query(query, (trial_id,))
        return results[0]['participant_count']
    
    async def _get_fastest_time(self, trial_id: int, guild) -> Dict[str, Any]:
        """
        Get the fastest time and user for a trial.
        
        Args:
            trial_id: Trial ID
            guild: Discord guild object for username resolution
            
        Returns:
            Dictionary with fastest time info
        """
        query = """
            SELECT 
                user_id,
                time_ms
            FROM player_times 
            WHERE trial_id = %s
            ORDER BY time_ms ASC
            LIMIT 1
        """
        
        results = self._execute_query(query, (trial_id,))
        if not results:
            return None
        
        from ..utils.time_parser import TimeParser
        from ..utils.user_utils import get_display_name
        
        result = results[0]
        time_str = TimeParser.format_time(result['time_ms'])
        
        # Resolve the actual username from Discord
        try:
            username = await get_display_name(result['user_id'], guild)
        except Exception:
            username = f"User {result['user_id']}"
        
        return {
            'time_str': time_str,
            'username': username,
            'user_id': result['user_id']
        }
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """This command doesn't use autocomplete."""
        return []


# Command setup functions for the main bot file
def setup_leaderboard_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the leaderboard command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    leaderboard_cmd = LeaderboardCommand()
    
    @tree.command(
        name="leaderboard",
        description="View the leaderboard for a weekly trial"
    )
    @app_commands.describe(
        track="Select the track to view leaderboard for"
    )
    async def leaderboard(interaction: Interaction, track: str):
        """
        View the leaderboard for a weekly trial.
        
        Shows all participants ranked by their times, with medals
        for those who achieved goal times.
        
        Examples:
        /leaderboard track:Rainbow Road
        /leaderboard track:Mario Circuit
        """
        await leaderboard_cmd.handle_command(interaction, track=track)
    
    @leaderboard.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows tracks with trials."""
        return await leaderboard_cmd.autocomplete_callback(interaction, current)


def setup_active_trials_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the active trials overview command.
    
    Args:
        tree: Discord app commands tree
    """
    active_cmd = ActiveTrialsCommand()
    
    @tree.command(
        name="active",
        description="View all currently active time trials"
    )
    async def active_trials(interaction: Interaction):
        """
        View all currently active time trials.
        
        Shows an overview of all ongoing challenges with participant
        counts and fastest times.
        """
        await active_cmd.handle_command(interaction)