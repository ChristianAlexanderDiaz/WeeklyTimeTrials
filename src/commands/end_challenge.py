"""
End challenge command for the MKW Time Trial Bot.

This command allows users to manually end an active weekly trial challenge
before its scheduled expiration time.
"""

from typing import List, Optional, Dict, Any
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import ValidationError
from ..utils.formatters import EmbedFormatter


class EndChallengeCommand(AutocompleteCommand):
    """
    Command to manually end an active weekly time trial challenge.
    
    This command handles:
    - Trial number validation
    - Finding active trials by trial number
    - Updating trial status to 'ended'
    - Sending confirmation with final leaderboard info
    """
    
    async def execute(self, interaction: Interaction, trial_number: int) -> None:
        """
        Execute the end challenge command.
        
        Args:
            interaction: Discord interaction object
            trial_number: Trial number to end (from weekly_trials.trial_number)
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)
        
        # Validate trial number
        if trial_number <= 0:
            raise ValidationError("Trial number must be a positive integer")
        
        # Get active trial by trial number
        trial_data = await self._get_active_trial_by_number(guild_id, trial_number)
        if not trial_data:
            raise CommandError(
                f"No active trial found with number **{trial_number}**. "
                f"Use `/active` to see current active trials."
            )
        
        trial_id = trial_data['id']
        trial_number = trial_data['trial_number']
        
        # Get final statistics before ending
        final_stats = await self._get_trial_final_stats(trial_id)
        
        # End the trial
        await self._end_trial_by_number(guild_id, trial_number)
        
        # Create success response with final stats
        embed = await self._create_trial_ended_embed(
            trial_data, final_stats, interaction.guild
        )
        
        await self._send_response(interaction, embed=embed, ephemeral=False)
    
    async def _get_active_trial_by_number(self, guild_id: int, trial_number: int) -> Optional[Dict[str, Any]]:
        """
        Get active trial by trial number.
        
        Args:
            guild_id: Discord guild ID
            trial_number: Trial number to find
            
        Returns:
            Trial data if found and active, None otherwise
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
                AND trial_number = %s 
                AND status = 'active'
            LIMIT 1
        """
        
        results = self._execute_query(query, (guild_id, trial_number))
        return results[0] if results else None
    
    async def _end_trial_by_number(self, guild_id: int, trial_number: int) -> None:
        """
        End an active trial by setting status to 'ended'.
        
        Args:
            guild_id: Discord guild ID
            trial_number: Trial number to end
            
        Raises:
            CommandError: If ending fails
        """
        query = """
            UPDATE weekly_trials 
            SET status = 'ended', 
                end_date = CURRENT_TIMESTAMP 
            WHERE guild_id = %s 
                AND trial_number = %s 
                AND status = 'active'
            RETURNING id, trial_number, track_name
        """
        
        results = self._execute_query(query, (guild_id, trial_number), fetch=True)
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
        """No autocomplete needed for trial number input."""
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
        description="Manually end an active weekly time trial challenge by trial number"
    )
    @app_commands.describe(
        trial_number="Trial number to end (use /active to see current trial numbers)"
    )
    async def end_challenge(interaction: Interaction, trial_number: int):
        """
        Manually end an active weekly time trial challenge by trial number.
        
        This immediately stops accepting new time submissions for the trial
        and sets it to 'ended' status. The leaderboard remains viewable.
        
        Examples:
        /end-challenge trial_number:1
        /end-challenge trial_number:2
        
        Note:
        - Use /active to see current active trial numbers
        - Only active trials can be ended manually
        - Once ended, the trial becomes read-only
        - A new trial can be created for the same track afterwards
        """
        await end_cmd.handle_command(interaction, trial_number=trial_number)