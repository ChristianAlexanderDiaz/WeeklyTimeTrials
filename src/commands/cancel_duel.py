"""
Cancel duel command for the MKW Time Trial Bot.

This command allows creators to cancel their pending duel invitations.
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


class CancelDuelCommand(AutocompleteCommand):
    """
    Command to cancel a pending duel invitation.

    This command handles:
    - Finding pending duels created by the user
    - Validating duel selection
    - Updating duel status to 'expired' (or custom cancelled status)
    - Notifying the opponent
    """

    async def execute(self, interaction: Interaction, challenge_number: int) -> None:
        """
        Execute the cancel duel command.

        Args:
            interaction: Discord interaction object
            challenge_number: Challenge number to cancel
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)

        # Get the pending duel
        duel_data = await self._get_pending_duel_by_creator(guild_id, user_id, challenge_number)
        if not duel_data:
            raise CommandError(
                f"No pending duel found with challenge #{challenge_number} that you created. "
                f"Use `/cancel-duel` autocomplete to see your pending duels."
            )

        # Verify user is the creator
        if duel_data['creator_user_id'] != user_id:
            raise CommandError("You can only cancel duels that you created.")

        # Cancel the duel
        await self._cancel_duel(duel_data['id'])

        # Get display names
        creator_name = await get_display_name(duel_data['creator_user_id'], interaction.guild)
        opponent_name = await get_display_name(duel_data['opponent_user_id'], interaction.guild)

        # Create cancellation embed
        embed = DuelFormatter.create_duel_cancelled_embed(
            duel_data=duel_data,
            creator_name=creator_name,
            opponent_name=opponent_name
        )

        # Send response and notify opponent
        try:
            opponent = await interaction.guild.fetch_member(duel_data['opponent_user_id'])
            await self._send_response(
                interaction,
                content=f"{opponent.mention}, the challenge has been cancelled.",
                embed=embed,
                ephemeral=False
            )
        except Exception as e:
            logger.error(f"Error notifying opponent: {e}")
            await self._send_response(interaction, embed=embed, ephemeral=False)

    async def _get_pending_duel_by_creator(self, guild_id: int, creator_id: int, challenge_number: int):
        """
        Get a pending duel created by the user by challenge number.

        Args:
            guild_id: Discord guild ID
            creator_id: Creator's user ID
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
                end_date
            FROM challenges_1v1
            WHERE guild_id = %s
                AND creator_user_id = %s
                AND challenge_number = %s
                AND status = 'pending'
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, creator_id, challenge_number))
        return results[0] if results else None

    async def _cancel_duel(self, challenge_id: int) -> None:
        """
        Cancel a duel by updating its status to expired.

        Args:
            challenge_id: Challenge ID

        Raises:
            CommandError: If cancellation fails
        """
        query = """
            UPDATE challenges_1v1
            SET status = 'expired'
            WHERE id = %s
                AND status = 'pending'
            RETURNING id
        """

        results = self._execute_query(query, (challenge_id,), fetch=True)
        if not results:
            raise CommandError("Failed to cancel duel. It may have already been accepted or cancelled.")

    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for pending duels created by the user.

        Args:
            interaction: Discord interaction object
            current: Current user input

        Returns:
            List of autocomplete choices for pending duels
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            user_id = self._validate_user_interaction(interaction)

            # Get pending duels created by this user
            query = """
                SELECT
                    id,
                    challenge_number,
                    track_name,
                    opponent_user_id,
                    created_at
                FROM challenges_1v1
                WHERE guild_id = %s
                    AND creator_user_id = %s
                    AND status = 'pending'
                ORDER BY created_at DESC
            """

            pending_duels = self._execute_query(query, (guild_id, user_id))

            # Format as choices
            choices = []
            for duel in pending_duels:
                # Get opponent name for display
                try:
                    opponent_name = await get_display_name(duel['opponent_user_id'], interaction.guild)
                except Exception:
                    opponent_name = f"User {duel['opponent_user_id']}"

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
def setup_cancel_duel_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the cancel duel command with the Discord command tree.

    Args:
        tree: Discord app commands tree
    """
    cancel_duel_cmd = CancelDuelCommand()

    @tree.command(
        name="cancel-duel",
        description="Cancel a pending duel invitation you created"
    )
    @app_commands.describe(
        challenge_number="Select the duel to cancel (autocomplete shows your pending duels)"
    )
    async def cancel_duel(interaction: Interaction, challenge_number: int):
        """
        Cancel a pending duel invitation you created.

        Only works for pending duels. Active duels cannot be cancelled.

        Examples:
        /cancel-duel challenge_number:1
        """
        await cancel_duel_cmd.handle_command(interaction, challenge_number=challenge_number)

    @cancel_duel.autocomplete('challenge_number')
    async def challenge_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[int]]:
        """Autocomplete for challenge_number parameter - shows pending duels created by you."""
        return await cancel_duel_cmd.autocomplete_callback(interaction, current)
