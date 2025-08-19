"""
Set medal times command for the MKW Time Trial Bot.

This command allows users to add or update medal time requirements
for existing active time trial challenges.
"""

from typing import List, Optional
import logging
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter
from ..config.settings import settings

logger = logging.getLogger(__name__)


class SetMedalTimesCommand(AutocompleteCommand):
    """
    Command to set or update medal times for an active time trial challenge.
    
    This command handles:
    - Track name validation with autocomplete
    - Medal time validation and ordering
    - Updating existing active trials
    - Updating live leaderboard messages
    - Recalculating player medals
    """
    
    async def execute(self, interaction: Interaction, track: str, 
                     gold_time: Optional[str] = None, silver_time: Optional[str] = None, 
                     bronze_time: Optional[str] = None) -> None:
        """
        Execute the set medal times command.
        
        Args:
            interaction: Discord interaction object
            track: Track name (validated via autocomplete)
            gold_time: Gold medal goal time in MM:SS.mmm format (optional)
            silver_time: Silver medal goal time in MM:SS.mmm format (optional)
            bronze_time: Bronze medal goal time in MM:SS.mmm format (optional)
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)
        
        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)
        
        # Check if there's an active trial for this track
        trial_data = await self._get_active_trial_by_track(guild_id, track_name)
        if not trial_data:
            raise CommandError(
                f"No active trial found for **{track_name}**. "
                f"Use `/set-challenge` to create a new challenge first."
            )
        
        # Validate medal times (optional)
        try:
            gold_ms, silver_ms, bronze_ms = InputValidator.validate_goal_times(
                gold_time, silver_time, bronze_time
            )
        except ValidationError as e:
            raise ValidationError(e)
        
        # Determine the operation type
        removing_medals = all(time is None for time in [gold_ms, silver_ms, bronze_ms])
        adding_medals = not removing_medals
        
        # Get current medal times for comparison
        current_gold = trial_data.get('gold_time_ms')
        current_silver = trial_data.get('silver_time_ms')
        current_bronze = trial_data.get('bronze_time_ms')
        currently_has_medals = current_gold is not None
        
        # Update the trial with new medal times
        updated_trial_data = await self._update_trial_medal_times(
            trial_data['id'],
            gold_ms,
            silver_ms,
            bronze_ms
        )
        
        # Update live leaderboard if it exists
        from ..utils.leaderboard_manager import update_live_leaderboard
        try:
            await update_live_leaderboard(updated_trial_data['id'], interaction.guild)
            logger.info(f"Updated live leaderboard for trial #{trial_data['trial_number']} after medal time change")
        except Exception as e:
            # Don't fail the command if leaderboard update fails
            logger.error(f"Error updating live leaderboard after medal time change: {e}")
        
        # Create success response
        embed = self._create_medal_update_embed(
            updated_trial_data,
            removing_medals,
            currently_has_medals,
            (current_gold, current_silver, current_bronze),
            (gold_ms, silver_ms, bronze_ms)
        )
        
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def _update_trial_medal_times(self, trial_id: int, gold_ms: Optional[int], 
                                      silver_ms: Optional[int], bronze_ms: Optional[int]) -> dict:
        """
        Update medal times for a trial in the database.
        
        Args:
            trial_id: Trial ID to update
            gold_ms: Gold medal time in milliseconds (or None)
            silver_ms: Silver medal time in milliseconds (or None)
            bronze_ms: Bronze medal time in milliseconds (or None)
            
        Returns:
            Updated trial data
            
        Raises:
            CommandError: If update fails
        """
        query = """
            UPDATE weekly_trials 
            SET gold_time_ms = %s, silver_time_ms = %s, bronze_time_ms = %s
            WHERE id = %s
            RETURNING id, trial_number, track_name, gold_time_ms, silver_time_ms, bronze_time_ms, 
                     start_date, end_date, status, guild_id, leaderboard_channel_id, leaderboard_message_id
        """
        
        params = (gold_ms, silver_ms, bronze_ms, trial_id)
        results = self._execute_query(query, params, fetch=True)
        
        if not results:
            raise CommandError("Failed to update medal times. Please try again.")
        
        return results[0]
    
    def _create_medal_update_embed(self, trial_data: dict, removing_medals: bool, 
                                  currently_has_medals: bool, old_times: tuple, new_times: tuple) -> discord.Embed:
        """
        Create an embed for successful medal time update.
        
        Args:
            trial_data: Updated trial information
            removing_medals: Whether medals were removed
            currently_has_medals: Whether trial previously had medals
            old_times: Previous medal times (gold_ms, silver_ms, bronze_ms)
            new_times: New medal times (gold_ms, silver_ms, bronze_ms)
            
        Returns:
            discord.Embed: Formatted medal update embed
        """
        trial_number = trial_data['trial_number']
        track_name = trial_data['track_name']
        
        if removing_medals:
            # Removing medal requirements
            title = "🏁 Medal Requirements Removed"
            description = f"**Weekly Time Trial #{trial_number} - {track_name}**\n\nThis challenge no longer has medal requirements."
            color = EmbedFormatter.COLOR_WARNING
        else:
            # Adding or updating medal requirements
            if currently_has_medals:
                title = "🏆 Medal Times Updated"
                description = f"**Weekly Time Trial #{trial_number} - {track_name}**\n\nMedal requirements have been updated."
            else:
                title = "🏆 Medal Requirements Added"
                description = f"**Weekly Time Trial #{trial_number} - {track_name}**\n\nMedal requirements have been added to this challenge."
            color = EmbedFormatter.COLOR_SUCCESS
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        # Show new medal times if they exist
        if not removing_medals:
            goal_times_text = EmbedFormatter._format_goal_times(
                trial_data['gold_time_ms'],
                trial_data['silver_time_ms'],
                trial_data['bronze_time_ms']
            )
            embed.add_field(
                name="🎯 Medal Requirements",
                value=goal_times_text,
                inline=True
            )
        
        # Show what changed if updating existing medals
        if currently_has_medals and not removing_medals:
            from ..utils.time_parser import TimeParser
            
            changes = []
            old_gold, old_silver, old_bronze = old_times
            new_gold, new_silver, new_bronze = new_times
            
            if old_gold != new_gold:
                old_str = TimeParser.format_time(old_gold) if old_gold else "None"
                new_str = TimeParser.format_time(new_gold) if new_gold else "None"
                changes.append(f"🥇 Gold: {old_str} → {new_str}")
            
            if old_silver != new_silver:
                old_str = TimeParser.format_time(old_silver) if old_silver else "None"
                new_str = TimeParser.format_time(new_silver) if new_silver else "None"
                changes.append(f"🥈 Silver: {old_str} → {new_str}")
            
            if old_bronze != new_bronze:
                old_str = TimeParser.format_time(old_bronze) if old_bronze else "None"
                new_str = TimeParser.format_time(new_bronze) if new_bronze else "None"
                changes.append(f"🥉 Bronze: {old_str} → {new_str}")
            
            if changes:
                embed.add_field(
                    name="📝 Changes Made",
                    value="\n".join(changes),
                    inline=False
                )
        
        embed.add_field(
            name="📊 Effect",
            value="Live leaderboard has been updated with new medal requirements.",
            inline=False
        )
        
        embed.set_footer(text="Player medals have been recalculated based on new requirements!")
        return embed
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.
        
        Shows only tracks with active trials that can have their medal times updated.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices for tracks with active trials
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            
            # Get tracks with active trials
            active_trials = await self._get_active_trials(guild_id)
            active_track_names = [trial['track_name'] for trial in active_trials]
            
            # Filter based on user input
            if current:
                current_lower = current.lower()
                filtered_tracks = [
                    track for track in active_track_names
                    if current_lower in track.lower()
                ]
            else:
                filtered_tracks = active_track_names
            
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
    
    async def _get_active_trials(self, guild_id: int) -> List[dict]:
        """
        Get all active trials for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of active trial data
        """
        query = """
            SELECT id, trial_number, track_name, gold_time_ms, silver_time_ms, bronze_time_ms,
                   start_date, end_date, status, guild_id, leaderboard_channel_id, leaderboard_message_id
            FROM weekly_trials 
            WHERE guild_id = %s 
                AND status = 'active'
            ORDER BY trial_number DESC
        """
        
        try:
            results = self._execute_query(query, (guild_id,))
            return results
        except Exception:
            return []


# Command setup function for the main bot file
def setup_set_medal_times_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the set medal times command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    set_medal_cmd = SetMedalTimesCommand()
    
    @tree.command(
        name="set-medal-times",
        description="Add or update medal time requirements for an active challenge"
    )
    @app_commands.describe(
        track="Select the track with an active challenge",
        gold_time="Gold medal goal time (MM:SS.mmm format, e.g., '2:20.000') - optional",
        silver_time="Silver medal goal time (MM:SS.mmm format, e.g., '2:25.000') - optional",
        bronze_time="Bronze medal goal time (MM:SS.mmm format, e.g., '2:30.000') - optional"
    )
    async def set_medal_times(interaction: Interaction, track: str,
                             gold_time: str = None, silver_time: str = None, bronze_time: str = None):
        """
        Add or update medal time requirements for an active challenge.
        
        Sets medal requirements for challenges that were created without them,
        or updates existing medal requirements for active challenges.
        
        Examples:
        /set-medal-times track:"Rainbow Road" gold_time:2:20.000 silver_time:2:25.000 bronze_time:2:30.000
        /set-medal-times track:"Mario Circuit" (removes medal requirements)
        
        Requirements:
        - Challenge must be currently active
        - If medal times provided: Gold time must be faster than or equal to silver time, silver must be faster than bronze
        - Medal times must be all provided or all omitted
        - Updates live leaderboard automatically
        """
        await set_medal_cmd.handle_command(
            interaction, 
            track=track,
            gold_time=gold_time, 
            silver_time=silver_time,
            bronze_time=bronze_time
        )
    
    @set_medal_times.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows only tracks with active trials."""
        return await set_medal_cmd.autocomplete_callback(interaction, current)