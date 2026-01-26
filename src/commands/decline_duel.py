"""
Decline duel command for the MKW Time Trial Bot.

This command allows users to decline a pending duel invitation.
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


class DeclineDuelCommand(AutocompleteCommand):
    """
    Command to decline a pending duel invitation.

    This command handles:
    - Finding pending duels for the user
    - Validating duel selection
    - Updating duel status to 'declined'
    - Notifying the creator
    """

    async def execute(self, interaction: Interaction, challenge_number: int) -> None:
        """
        Execute the decline duel command.

        Args:
            interaction: Discord interaction object
            challenge_number: Challenge number to decline
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)

        # Get the pending duel
        duel_data = await self._get_pending_duel(guild_id, user_id, challenge_number)
        if not duel_data:
            raise CommandError(
                f"No pending duel invitation found with challenge #{challenge_number}. "
                f"Use `/decline-duel` autocomplete to see your pending invitations."
            )

        # Verify user is the opponent
        if duel_data['opponent_user_id'] != user_id:
            raise CommandError("You can only decline duels where you are the challenged opponent.")

        # Decline the duel
        await self._decline_duel(duel_data['id'])

        # Get display names
        creator_name = await get_display_name(duel_data['creator_user_id'], interaction.guild)
        opponent_name = await get_display_name(duel_data['opponent_user_id'], interaction.guild)

        # Update duel_data with new status
        duel_data['status'] = 'declined'

        # Create decline embed
        embed = DuelFormatter.create_duel_declined_embed(
            duel_data=duel_data,
            creator_name=creator_name,
            opponent_name=opponent_name
        )

        # Send response and notify creator
        creator = await interaction.guild.fetch_member(duel_data['creator_user_id'])
        await self._send_response(
            interaction,
            content=f"{creator.mention}, your challenge has been declined.",
            embed=embed,
            ephemeral=False
        )

    async def _get_pending_duel(self, guild_id: int, user_id: int, challenge_number: int):
        """
        Get a pending duel for the user by challenge number.

        Args:
            guild_id: Discord guild ID
            user_id: User ID (should be opponent)
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
                AND opponent_user_id = %s
                AND challenge_number = %s
                AND status = 'pending'
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, user_id, challenge_number))
        return results[0] if results else None

    async def _decline_duel(self, challenge_id: int) -> None:
        """
        Decline a duel by updating its status.

        Args:
            challenge_id: Challenge ID

        Raises:
            CommandError: If decline fails
        """
        query = """
            UPDATE challenges_1v1
            SET status = 'declined'
            WHERE id = %s
                AND status = 'pending'
            RETURNING id
        """

        results = self._execute_query(query, (challenge_id,), fetch=True)
        if not results:
            raise CommandError("Failed to decline duel. It may have already been accepted or cancelled.")

    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for pending duels.

        Shows only duels where the user is the opponent and status is pending.

        Args:
            interaction: Discord interaction object
            current: Current user input

        Returns:
            List of autocomplete choices for pending duels
        """
        try:
            guild_id = self._validate_guild_interaction(interaction)
            user_id = self._validate_user_interaction(interaction)

            # Get pending duels for this user
            pending_duels = DuelManager.get_pending_duels_for_user(user_id, guild_id)

            # Format as choices
            choices = []
            for duel in pending_duels:
                # Get creator name for display
                try:
                    creator_name = await get_display_name(duel['creator_user_id'], interaction.guild)
                except Exception:
                    creator_name = f"User {duel['creator_user_id']}"

                display = f"#{duel['challenge_number']} - {creator_name} - {duel['track_name']}"

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
def setup_decline_duel_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the decline duel command with the Discord command tree.

    Args:
        tree: Discord app commands tree
    """
    decline_duel_cmd = DeclineDuelCommand()

    @tree.command(
        name="decline-duel",
        description="Decline a pending duel invitation"
    )
    @app_commands.describe(
        challenge_number="Select the duel to decline (autocomplete shows your pending invitations)"
    )
    async def decline_duel(interaction: Interaction, challenge_number: int):
        """
        Decline a pending duel invitation.

        Examples:
        /decline-duel challenge_number:1
        """
        await decline_duel_cmd.handle_command(interaction, challenge_number=challenge_number)

    @decline_duel.autocomplete('challenge_number')
    async def challenge_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[int]]:
        """Autocomplete for challenge_number parameter - shows pending invitations."""
        return await decline_duel_cmd.autocomplete_callback(interaction, current)
