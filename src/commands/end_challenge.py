"""
End challenge command for the MKW Time Trial Bot.

This command allows users to manually end an active weekly trial challenge
before its scheduled expiration time.
"""

from typing import List
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.formatters import EmbedFormatter


class EndChallengeCommand(AutocompleteCommand):
    """
    Command to manually end an active weekly time trial challenge.
    
    This command handles:
    - Track name validation with autocomplete
    - Finding active trials
    - Updating trial status to 'ended'
    - Sending confirmation with final leaderboard info
    """
    
    async def execute(self, interaction: Interaction, track: str) -> None:
        """
        Execute the end challenge command.
        
        Args:
            interaction: Discord interaction object
            track: Track name (validated via autocomplete)
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)
        
        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)
        
        # Get active trial for this track
        trial_data = await self._get_active_trial_by_track(guild_id, track_name)
        if not trial_data:
            raise CommandError(
                f"No active trial found for **{track_name}**. "
                f"Only active trials can be ended manually."
            )
        
        trial_id = trial_data['id']
        trial_number = trial_data['trial_number']
        
        # Get final statistics before ending
        final_stats = await self._get_trial_final_stats(trial_id)
        
        # End the trial
        await self._end_trial(guild_id, track_name)
        
        # Create success response with final stats
        embed = await self._create_trial_ended_embed(
            trial_data, final_stats, interaction.guild
        )
        
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def _end_trial(self, guild_id: int, track_name: str) -> None:
        """
        End an active trial by setting status to 'ended'.
        
        Args:
            guild_id: Discord guild ID
            track_name: Track name
            
        Raises:
            CommandError: If ending fails
        """
        query = """
            UPDATE weekly_trials 
            SET status = 'ended', 
                end_date = CURRENT_TIMESTAMP 
            WHERE guild_id = %s 
                AND track_name = %s 
                AND status = 'active'
            RETURNING id, trial_number, track_name
        """
        
        results = self._execute_query(query, (guild_id, track_name), fetch=True)
        if not results:
            raise CommandError("Failed to end trial. It may have already been ended.")
    
    async def _get_trial_final_stats(self, trial_id: int) -> dict:
        """
        Get final statistics for a trial before ending it.
        
        Args:
            trial_id: Trial ID
            
        Returns:
            Dictionary with final statistics
        """
        query = """
            SELECT 
                COUNT(*) as total_participants,
                MIN(time_ms) as fastest_time_ms,
                AVG(time_ms) as average_time_ms
            FROM player_times 
            WHERE trial_id = %s
        """
        
        results = self._execute_query(query, (trial_id,))
        stats = results[0] if results else {
            'total_participants': 0,
            'fastest_time_ms': None,
            'average_time_ms': None
        }
        
        # Get fastest user info if there are participants
        if stats['total_participants'] > 0 and stats['fastest_time_ms']:
            fastest_user_query = """
                SELECT user_id
                FROM player_times 
                WHERE trial_id = %s AND time_ms = %s
                LIMIT 1
            """
            fastest_results = self._execute_query(
                fastest_user_query, 
                (trial_id, stats['fastest_time_ms'])
            )
            stats['fastest_user_id'] = fastest_results[0]['user_id'] if fastest_results else None
        else:
            stats['fastest_user_id'] = None
        
        return stats
    
    async def _create_trial_ended_embed(self, trial_data: dict, final_stats: dict, guild) -> discord.Embed:
        """
        Create an embed announcing the trial has ended.
        
        Args:
            trial_data: Trial information
            final_stats: Final trial statistics
            guild: Discord guild object
            
        Returns:
            Formatted embed with trial end announcement
        """
        trial_number = trial_data['trial_number']
        track_name = trial_data['track_name']
        
        embed = discord.Embed(
            title="🏁 Trial Ended",
            description=f"**Weekly Time Trial #{trial_number} - {track_name}** has been manually ended.",
            color=EmbedFormatter.COLOR_WARNING
        )
        
        # Add final statistics
        total_participants = final_stats['total_participants']
        
        if total_participants > 0:
            from ..utils.time_parser import TimeParser
            from ..utils.user_utils import get_display_name
            
            fastest_time_str = TimeParser.format_time(final_stats['fastest_time_ms'])
            avg_time_str = TimeParser.format_time(int(final_stats['average_time_ms']))
            
            # Get fastest user's display name
            fastest_user_name = "Unknown User"
            if final_stats['fastest_user_id']:
                try:
                    fastest_user_name = await get_display_name(
                        final_stats['fastest_user_id'], guild
                    )
                except Exception:
                    fastest_user_name = f"User {final_stats['fastest_user_id']}"
            
            embed.add_field(
                name="📊 Final Statistics",
                value=(
                    f"**Participants:** {total_participants}\n"
                    f"**Fastest Time:** {fastest_time_str} by {fastest_user_name}\n"
                    f"**Average Time:** {avg_time_str}"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="📊 Final Statistics",
                value="No participants submitted times.",
                inline=False
            )
        
        embed.add_field(
            name="ℹ️ What's Next",
            value=(
                f"• Use `/leaderboard {track_name}` to view final standings\n"
                f"• This trial is now read-only\n"
                f"• A new trial can be created for this track"
            ),
            inline=False
        )
        
        embed.set_footer(text="Trial ended manually by admin")
        return embed
    
    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.
        
        Only shows tracks that have active trials that can be ended.
        
        Args:
            interaction: Discord interaction object
            current: Current user input
            
        Returns:
            List of autocomplete choices for tracks with active trials
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            
            # Get tracks with active trials
            active_tracks = await self._get_active_track_names(guild_id)
            
            # Filter tracks based on user input
            if current:
                current_lower = current.lower()
                filtered_tracks = [
                    track for track in active_tracks
                    if current_lower in track.lower()
                ]
            else:
                filtered_tracks = active_tracks
            
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
            ORDER BY track_name
        """
        
        try:
            results = self._execute_query(query, (guild_id,))
            return [row['track_name'] for row in results]
        except Exception:
            return []


# Command setup function for the main bot file
def setup_end_challenge_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the end challenge command with the Discord command tree.
    
    Args:
        tree: Discord app commands tree
    """
    end_cmd = EndChallengeCommand()
    
    @tree.command(
        name="end-challenge",
        description="Manually end an active weekly time trial challenge"
    )
    @app_commands.describe(
        track="Select the track with an active trial to end"
    )
    async def end_challenge(interaction: Interaction, track: str):
        """
        Manually end an active weekly time trial challenge.
        
        This immediately stops accepting new time submissions for the trial
        and sets it to 'ended' status. The leaderboard remains viewable.
        
        Examples:
        /end-challenge track:Rainbow Road
        /end-challenge track:Mario Circuit
        
        Note:
        - Only active trials can be ended manually
        - Once ended, the trial becomes read-only
        - A new trial can be created for the same track afterwards
        """
        await end_cmd.handle_command(interaction, track=track)
    
    @end_challenge.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter - shows only tracks with active trials."""
        return await end_cmd.autocomplete_callback(interaction, current)