"""
Duel time save command for the MKW Time Trial Bot.

This command allows users to submit times for active 1v1 duels.
"""

from typing import List, Dict
import logging
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.time_parser import TimeParser
from ..utils.duel_formatters import DuelFormatter
from ..utils.duel_manager import DuelManager
from ..utils.user_utils import get_display_name

logger = logging.getLogger(__name__)


class DuelTimeSaveCommand(AutocompleteCommand):
    """
    Command to submit a time for an active 1v1 duel.

    This command handles:
    - Time format validation
    - Finding active duels for the user
    - Allowing multiple improvements
    - Pinging opponent with Tesla-style messages
    - Auto-determining winner when both submit
    """

    async def execute(self, interaction: Interaction, challenge_number: int, time: str) -> None:
        """
        Execute the duel time save command.

        Args:
            interaction: Discord interaction object
            challenge_number: Challenge number (from autocomplete)
            time: Time string in MM:SS.mmm format
        """
        guild_id = self._validate_guild_interaction(interaction)
        user_id = self._validate_user_interaction(interaction)

        # Validate and parse the time input
        try:
            time_ms = InputValidator.validate_time_input(time)
        except ValidationError as e:
            raise ValidationError(f"Invalid time format: {e}")

        # Get the active duel
        duel_data = await self._get_active_duel(guild_id, user_id, challenge_number)
        if not duel_data:
            raise CommandError(
                f"No active duel found with challenge #{challenge_number}. "
                f"Use `/dueltimesave` autocomplete to see your active duels."
            )

        # Verify user is a participant
        if user_id not in [duel_data['creator_user_id'], duel_data['opponent_user_id']]:
            raise CommandError("You are not a participant in this duel.")

        challenge_id = duel_data['id']

        # Check if user already has a time
        existing_time = DuelManager.get_user_time_for_duel(challenge_id, user_id)

        is_improvement = False
        previous_time_ms = None

        if existing_time:
            previous_time_ms = existing_time['time_ms']
            # Allow improvements (no restriction like weekly trials)
            is_improvement = time_ms < previous_time_ms

        # Save the time
        await self._save_duel_time(challenge_id, user_id, time_ms, is_improvement)

        # Get display names
        submitter_name = await get_display_name(user_id, interaction.guild)
        opponent_id = DuelManager.get_opponent_user_id(challenge_id, user_id)
        opponent_name = await get_display_name(opponent_id, interaction.guild)

        # Create submission embed
        embed = DuelFormatter.create_duel_time_submission_embed(
            duel_data=duel_data,
            submitter_name=submitter_name,
            time_ms=time_ms,
            is_improvement=is_improvement,
            previous_time_ms=previous_time_ms
        )

        # Check if both users have submitted times
        all_times = DuelManager.get_duel_times(challenge_id)
        both_submitted = len(all_times) >= 2

        if both_submitted:
            # Determine winner and complete the duel
            winner_user_id = DuelManager.determine_winner(challenge_id)
            await self._complete_duel(challenge_id, winner_user_id)

            # Send completion message
            await self._send_response(interaction, embed=embed, ephemeral=False)
        else:
            # Send submission confirmation and ping opponent with Tesla-style taunt
            time_str = TimeParser.format_time(time_ms)
            taunt_message = DuelFormatter.create_tesla_taunt_message(
                opponent_name=opponent_name,
                submitter_name=submitter_name,
                time_str=time_str
            )

            try:
                opponent_user = await interaction.guild.fetch_member(opponent_id)
                await self._send_response(
                    interaction,
                    content=f"{opponent_user.mention}",
                    embed=embed,
                    ephemeral=False
                )
                # Send taunt as follow-up
                await interaction.followup.send(content=taunt_message, ephemeral=False)
            except Exception as e:
                logger.error(f"Error pinging opponent: {e}")
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

    async def _save_duel_time(self, challenge_id: int, user_id: int, time_ms: int,
                             is_update: bool) -> None:
        """
        Save or update a user's time for a duel.

        Args:
            challenge_id: Challenge ID
            user_id: Discord user ID
            time_ms: Time in milliseconds
            is_update: Whether this is updating an existing time

        Raises:
            CommandError: If save fails
        """
        if is_update:
            # Update existing time
            query = """
                UPDATE challenge_1v1_times
                SET time_ms = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE challenge_id = %s
                    AND user_id = %s
                RETURNING id
            """
            params = (time_ms, challenge_id, user_id)
        else:
            # Insert new time
            query = """
                INSERT INTO challenge_1v1_times (challenge_id, user_id, time_ms)
                VALUES (%s, %s, %s)
                RETURNING id
            """
            params = (challenge_id, user_id, time_ms)

        results = self._execute_query(query, params, fetch=True)
        if not results:
            raise CommandError("Failed to save time. Please try again.")

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
            raise CommandError("Failed to complete duel.")

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
def setup_dueltimesave_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the duel time save command with the Discord command tree.

    Args:
        tree: Discord app commands tree
    """
    duel_time_cmd = DuelTimeSaveCommand()

    @tree.command(
        name="dueltimesave",
        description="Submit your time for an active 1v1 duel"
    )
    @app_commands.describe(
        challenge_number="Select the duel (autocomplete shows your active duels)",
        time="Your time in MM:SS.mmm format (e.g., '2:23.640')"
    )
    async def dueltimesave(interaction: Interaction, challenge_number: int, time: str):
        """
        Submit your time for an active 1v1 duel.

        Examples:
        /dueltimesave challenge_number:1 time:2:23.640
        /dueltimesave challenge_number:2 time:1:45.123
        """
        await duel_time_cmd.handle_command(
            interaction,
            challenge_number=challenge_number,
            time=time
        )

    @dueltimesave.autocomplete('challenge_number')
    async def challenge_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[int]]:
        """Autocomplete for challenge_number parameter - shows active duels."""
        return await duel_time_cmd.autocomplete_callback(interaction, current)
