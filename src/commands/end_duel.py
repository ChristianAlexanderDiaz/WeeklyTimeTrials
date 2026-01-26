"""
End duel command for the MKW Time Trial Bot.

This command allows users to manually end an active duel.
"""

from typing import List
import logging
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import ValidationError
from ..utils.duel_formatters import DuelFormatter
from ..utils.duel_manager import DuelManager
from ..utils.user_utils import get_display_name

logger = logging.getLogger(__name__)


class EndDuelCommand(AutocompleteCommand):
    """
    Command to manually end an active duel.

    This command handles:
    - Finding active duels for the user
    - Determining final winner
    - Updating duel status to 'completed'
    - Displaying final results
    """

    async def execute(self, interaction: Interaction, challenge_number: int) -> None:
        """
        Execute the end duel command.

        Args:
            interaction: Discord interaction object
            challenge_number: Challenge number to end
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)

        # Get the active duel
        duel_data = await self._get_active_duel(guild_id, user_id, challenge_number)
        if not duel_data:
            raise CommandError(
                f"No active duel found with challenge #{challenge_number}. "
                f"Use `/end-duel` autocomplete to see your active duels."
            )

        # Verify user is a participant
        if user_id not in [duel_data['creator_user_id'], duel_data['opponent_user_id']]:
            raise CommandError("You can only end duels you're participating in.")

        challenge_id = duel_data['id']

        # Determine winner
        winner_user_id = DuelManager.determine_winner(challenge_id)

        # Complete the duel
        await self._complete_duel(challenge_id, winner_user_id)

        # Get times for both participants
        creator_time = DuelManager.get_user_time_for_duel(
            challenge_id,
            duel_data['creator_user_id']
        )
        opponent_time = DuelManager.get_user_time_for_duel(
            challenge_id,
            duel_data['opponent_user_id']
        )

        creator_time_ms = creator_time['time_ms'] if creator_time else None
        opponent_time_ms = opponent_time['time_ms'] if opponent_time else None

        # Get display names
        creator_name = await get_display_name(duel_data['creator_user_id'], interaction.guild)
        opponent_name = await get_display_name(duel_data['opponent_user_id'], interaction.guild)

        # Update duel_data with completion status
        duel_data['status'] = 'completed'
        duel_data['winner_user_id'] = winner_user_id

        # Create results embed
        embed = DuelFormatter.create_duel_results_embed(
            duel_data=duel_data,
            creator_name=creator_name,
            opponent_name=opponent_name,
            creator_time_ms=creator_time_ms,
            opponent_time_ms=opponent_time_ms,
            winner_user_id=winner_user_id
        )

        # Notify both participants
        try:
            other_user_id = (duel_data['opponent_user_id'] if user_id == duel_data['creator_user_id']
                           else duel_data['creator_user_id'])
            other_user = await interaction.guild.fetch_member(other_user_id)
            await self._send_response(
                interaction,
                content=f"{other_user.mention}, the duel has ended!",
                embed=embed,
                ephemeral=False
            )
        except Exception as e:
            logger.error(f"Error notifying other participant: {e}")
            await self._send_response(interaction, embed=embed, ephemeral=False)

    async def _get_active_duel(self, guild_id: int, user_id: int, challenge_number: int):
        """
        Get an active duel for the user by challenge number.

        Args:
            guild_id: Discord guild ID
            user_id: User ID (can be creator or opponent)
            challenge_number: Challenge number

        Returns:
            Duel data or None if not found
        """
        query = """
            SELECT
                id,
                challenge_number,
                guild_id,
                track_name,
                creator_user_id,
                opponent_user_id,
                status,
                start_date,
                end_date
            FROM challenges_1v1
            WHERE guild_id = %s
                AND challenge_number = %s
                AND (creator_user_id = %s OR opponent_user_id = %s)
                AND status = 'active'
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, challenge_number, user_id, user_id))
        return results[0] if results else None

    async def _complete_duel(self, challenge_id: int, winner_user_id: int) -> None:
        """
        Complete a duel by setting status to completed and recording winner.

        Args:
            challenge_id: Challenge ID
            winner_user_id: Winner's user ID (or None for tie)

        Raises:
            CommandError: If completion fails
        """
        query = """
            UPDATE challenges_1v1
            SET status = 'completed',
                winner_user_id = %s,
                end_date = CURRENT_TIMESTAMP
            WHERE id = %s
                AND status = 'active'
            RETURNING id
        """

        results = self._execute_query(query, (winner_user_id, challenge_id), fetch=True)
        if not results:
            raise CommandError("Failed to end duel. It may have already ended.")

    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for active duels.

        Shows duels where the user is a participant and status is active.

        Args:
            interaction: Discord interaction object
            current: Current user input

        Returns:
            List of autocomplete choices for active duels
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            user_id = self._validate_user_interaction(interaction)

            # Get active duels for this user
            active_duels = DuelManager.get_active_duels_for_user(user_id, guild_id)

            # Format as choices
            choices = []
            for duel in active_duels:
                # Get opponent name for display
                opponent_id = (duel['opponent_user_id'] if duel['creator_user_id'] == user_id
                              else duel['creator_user_id'])
                try:
                    opponent_name = await get_display_name(opponent_id, interaction.guild)
                except Exception:
                    opponent_name = f"User {opponent_id}"

                display = f"#{duel['challenge_number']} - vs {opponent_name} - {duel['track_name']}"

                # Filter based on current input
                if current and current.lower() not in display.lower():
                    continue

                choices.append(
                    app_commands.Choice(
                        name=display[:100],  # Discord limit
                        value=duel['challenge_number']
                    )
                )

            return choices[:25]  # Discord limit

        except Exception as e:
            logger.error(f"Autocomplete error: {e}")
            return []


# Command setup function for the main bot file
def setup_end_duel_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the end duel command with the Discord command tree.

    Args:
        tree: Discord app commands tree
    """
    end_duel_cmd = EndDuelCommand()

    @tree.command(
        name="end-duel",
        description="Manually end an active 1v1 duel and determine the winner"
    )
    @app_commands.describe(
        challenge_number="Select the duel to end (autocomplete shows your active duels)"
    )
    async def end_duel(interaction: Interaction, challenge_number: int):
        """
        Manually end an active 1v1 duel and determine the winner.

        Determines the winner based on fastest submitted time.
        If only one player submitted, they win by default.

        Examples:
        /end-duel challenge_number:1
        """
        await end_duel_cmd.handle_command(interaction, challenge_number=challenge_number)

    @end_duel.autocomplete('challenge_number')
    async def challenge_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[int]]:
        """Autocomplete for challenge_number parameter - shows active duels."""
        return await end_duel_cmd.autocomplete_callback(interaction, current)
