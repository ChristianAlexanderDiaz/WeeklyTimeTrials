"""
Duel results command for the MKW Time Trial Bot.

This command allows users to view the results/standings of their duels.
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


class DuelResultsCommand(AutocompleteCommand):
    """
    Command to view results of a 1v1 duel.

    This command handles:
    - Finding duels for the user (any status)
    - Showing current standings or final results
    - Displaying "win by default" if only one submitted
    """

    async def execute(self, interaction: Interaction, challenge_number: int) -> None:
        """
        Execute the duel results command.

        Args:
            interaction: Discord interaction object
            challenge_number: Challenge number to view results for
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)

        # Get the duel
        duel_data = await self._get_duel(guild_id, user_id, challenge_number)
        if not duel_data:
            raise CommandError(
                f"No duel found with challenge #{challenge_number}. "
                f"Use `/1v1-results` autocomplete to see your duels."
            )

        # Get times for both participants
        creator_time = DuelManager.get_user_time_for_duel(
            duel_data['id'],
            duel_data['creator_user_id']
        )
        opponent_time = DuelManager.get_user_time_for_duel(
            duel_data['id'],
            duel_data['opponent_user_id']
        )

        creator_time_ms = creator_time['time_ms'] if creator_time else None
        opponent_time_ms = opponent_time['time_ms'] if opponent_time else None

        # Get display names
        creator_name = await get_display_name(duel_data['creator_user_id'], interaction.guild)
        opponent_name = await get_display_name(duel_data['opponent_user_id'], interaction.guild)

        # Create results embed
        embed = DuelFormatter.create_duel_results_embed(
            duel_data=duel_data,
            creator_name=creator_name,
            opponent_name=opponent_name,
            creator_time_ms=creator_time_ms,
            opponent_time_ms=opponent_time_ms,
            winner_user_id=duel_data.get('winner_user_id')
        )

        await self._send_response(interaction, embed=embed, ephemeral=False)

    async def _get_duel(self, guild_id: int, user_id: int, challenge_number: int):
        """
        Get a duel for the user by challenge number (any status).

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
                created_at,
                accepted_at,
                start_date,
                end_date,
                winner_user_id
            FROM challenges_1v1
            WHERE guild_id = %s
                AND challenge_number = %s
                AND (creator_user_id = %s OR opponent_user_id = %s)
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, challenge_number, user_id, user_id))
        return results[0] if results else None

    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for all duels.

        Shows all duels where the user is a participant (any status).

        Args:
            interaction: Discord interaction object
            current: Current user input

        Returns:
            List of autocomplete choices for all duels
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            user_id = self._validate_user_interaction(interaction)

            # Get all duels for this user
            all_duels = DuelManager.get_all_duels_for_user(user_id, guild_id)

            # Format as choices
            choices = []
            for duel in all_duels:
                # Get opponent name for display
                opponent_id = (duel['opponent_user_id'] if duel['creator_user_id'] == user_id
                              else duel['creator_user_id'])
                try:
                    opponent_name = await get_display_name(opponent_id, interaction.guild)
                except Exception:
                    opponent_name = f"User {opponent_id}"

                status_emoji = {
                    'pending': '⏳',
                    'active': '⚔️',
                    'completed': '✅',
                    'declined': '❌',
                    'expired': '⏱️'
                }.get(duel['status'], '❓')

                display = f"{status_emoji} #{duel['challenge_number']} - vs {opponent_name} - {duel['track_name']}"

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
def setup_duel_results_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the duel results command with the Discord command tree.

    Args:
        tree: Discord app commands tree
    """
    results_cmd = DuelResultsCommand()

    @tree.command(
        name="1v1-results",
        description="View results and standings for a 1v1 duel"
    )
    @app_commands.describe(
        challenge_number="Select the duel to view (autocomplete shows all your duels)"
    )
    async def duel_results(interaction: Interaction, challenge_number: int):
        """
        View results and standings for a 1v1 duel.

        Shows current standings for active duels or final results for completed duels.

        Examples:
        /1v1-results challenge_number:1
        """
        await results_cmd.handle_command(interaction, challenge_number=challenge_number)

    @duel_results.autocomplete('challenge_number')
    async def challenge_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[int]]:
        """Autocomplete for challenge_number parameter - shows all duels."""
        return await results_cmd.autocomplete_callback(interaction, current)
