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
            track: Track name with category (format: "track|category")
        """
        guild_id = self._validate_guild_interaction(interaction)

        # Parse track and category from pipe-separated value
        if '|' in track:
            track_name, category = track.split('|', 1)
        else:
            # Fallback for backwards compatibility or manual entry
            track_name = track
            category = 'shrooms'

        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track_name, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)

        # Validate category
        try:
            category = InputValidator.validate_category(category)
        except ValidationError as e:
            raise ValidationError(e)

        # Get trial for this track and category (any status - active, expired, or ended)
        trial_data = await self._get_trial_by_track_and_category(guild_id, track_name, category)
        if not trial_data:
            raise CommandError(
                f"No {category} trial found for **{track_name}**. "
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
        Provide autocomplete choices for track names with categories.

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

            # Get trials with track names and categories
            trials = await self._get_trials_with_category(guild_id)

            # Filter based on user input
            if current:
                current_lower = current.lower()
                filtered_trials = [
                    trial for trial in trials
                    if current_lower in trial['display'].lower()
                ]
            else:
                filtered_trials = trials

            # Limit to 25 choices (Discord limit)
            filtered_trials = filtered_trials[:25]

            return [
                app_commands.Choice(name=trial['display'], value=trial['value'])
                for trial in filtered_trials
            ]

        except Exception as e:
            self.logger.error(f"Autocomplete error: {e}")
            # Fallback to all tracks if database query fails
            return [
                app_commands.Choice(name=choice['name'], value=choice['value'])
                for choice in get_track_autocomplete_choices(current)[:25]
            ]
    
    async def _get_trials_with_category(self, guild_id: int) -> List[Dict[str, str]]:
        """
        Get list of trials with track names and categories (active or inactive).

        Args:
            guild_id: Discord guild ID

        Returns:
            List of dicts with 'display' (formatted) and 'value' (pipe-separated) keys
        """
        query = """
            SELECT DISTINCT track_name, category
            FROM weekly_trials
            WHERE guild_id = %s
            ORDER BY track_name, category
        """

        try:
            results = self._execute_query(query, (guild_id,))
            return [
                {
                    'display': f"{row['track_name']} ({row['category'].title()})",
                    'value': f"{row['track_name']}|{row['category']}"
                }
                for row in results
            ]
        except Exception:
            # Fallback to empty list if query fails
            return []

    async def _get_trial_by_track_and_category(self, guild_id: int, track_name: str, category: str) -> Any:
        """
        Get trial information for a specific track and category (any status).

        Args:
            guild_id: Discord guild ID
            track_name: Track name to search for
            category: Category to search for

        Returns:
            Most recent trial data for the track and category or None if not found
        """
        query = """
            SELECT
                id,
                trial_number,
                track_name,
                category,
                gold_time_ms,
                silver_time_ms,
                bronze_time_ms,
                start_date,
                end_date,
                status
            FROM weekly_trials
            WHERE guild_id = %s
                AND track_name = %s
                AND category = %s
            ORDER BY created_at DESC
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, track_name, category))
        return results[0] if results else None


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
        # Create title with count
        trial_count = len(trials)
        if trial_count == 1:
            title = "🏁 1 Active Time Trial"
        else:
            title = f"🏁 {trial_count} Active Time Trials"
        
        # Build description with just trial list (no redundant count text)
        description_parts = []
        
        if trials:
            for trial in trials:
                trial_number = trial['trial_number']
                track_name = trial['track_name']
                end_date = trial.get('end_date')
                
                # Format expiration info
                if end_date:
                    # Use Discord timestamp for automatic timezone handling
                    expire_text = f"Expires: <t:{int(end_date.timestamp())}:R>"
                else:
                    expire_text = "No expiration set"
                
                trial_line = f"**Trial #{trial_number} - {track_name}**\n{expire_text}"
                description_parts.append(trial_line)
        
        embed = discord.Embed(
            title=title,
            description="\n\n".join(description_parts) if description_parts else "No active trials right now.",
            color=EmbedFormatter.COLOR_INFO
        )
        
        embed.set_footer(text="Use /weeklytimesave to submit your time!")
        return embed
    
    
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