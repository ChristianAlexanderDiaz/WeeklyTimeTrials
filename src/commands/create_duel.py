"""
Create duel command for the MKW Time Trial Bot.

This command allows users to challenge another user to a 1v1 duel.
"""

from datetime import datetime, timedelta, timezone
from typing import List
import logging
import discord
from discord import app_commands, Interaction, User

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.track_data import TrackManager, get_track_autocomplete_choices
from ..utils.duel_formatters import DuelFormatter
from ..utils.duel_manager import DuelManager
from ..utils.user_utils import get_display_name

logger = logging.getLogger(__name__)


class CreateDuelCommand(AutocompleteCommand):
    """
    Command to create a new 1v1 duel challenge.

    This command handles:
    - Track name validation with autocomplete
    - Opponent validation (different from creator)
    - Duration validation (1-30 days)
    - Creating the duel in database
    - Sending invitation to opponent
    """

    async def execute(self, interaction: Interaction, opponent: User, track: str,
                     duration_days: int = 7) -> None:
        """
        Execute the create duel command.

        Args:
            interaction: Discord interaction object
            opponent: Discord user to challenge
            track: Track name (validated via autocomplete)
            duration_days: Duel duration in days (default 7, max 30)
        """
        guild_id = self._validate_guild_interaction(interaction)
        creator_id = self._validate_user_interaction(interaction)

        # Validate opponent is different from creator
        if opponent.id == creator_id:
            raise ValidationError("You cannot challenge yourself to a duel!")

        # Validate opponent is not a bot
        if opponent.bot:
            raise ValidationError("You cannot challenge a bot to a duel!")

        # Validate track name
        try:
            track_name = InputValidator.validate_track_name(track, TrackManager.get_all_tracks())
        except ValidationError as e:
            raise ValidationError(e)

        # Validate duration
        if not isinstance(duration_days, int) or duration_days < 1:
            raise ValidationError("Duration must be at least 1 day")
        if duration_days > 30:
            raise ValidationError("Duration cannot exceed 30 days")

        # Calculate end date
        start_date = datetime.now(timezone.utc)
        end_date = start_date + timedelta(days=duration_days)

        # Get next challenge number
        challenge_number = DuelManager.get_next_challenge_number(guild_id)

        # Create the duel
        duel_data = await self._create_duel(
            guild_id=guild_id,
            challenge_number=challenge_number,
            track_name=track_name,
            creator_id=creator_id,
            opponent_id=opponent.id,
            end_date=end_date
        )

        # Get display names
        creator_name = await get_display_name(creator_id, interaction.guild)
        opponent_name = await get_display_name(opponent.id, interaction.guild)

        # Create invitation embed
        embed = DuelFormatter.create_duel_invitation_embed(
            duel_data=duel_data,
            creator_name=creator_name,
            opponent_name=opponent_name
        )

        # Send response and ping opponent
        await self._send_response(
            interaction,
            content=f"{opponent.mention}, you've been challenged!",
            embed=embed,
            ephemeral=False
        )

    async def _create_duel(self, guild_id: int, challenge_number: int, track_name: str,
                          creator_id: int, opponent_id: int, end_date: datetime) -> dict:
        """
        Create a new duel in the database.

        Args:
            guild_id: Discord guild ID
            challenge_number: Sequential challenge number
            track_name: Track name
            creator_id: Creator's Discord user ID
            opponent_id: Opponent's Discord user ID
            end_date: When the duel expires

        Returns:
            Created duel data

        Raises:
            CommandError: If creation fails
        """
        query = """
            INSERT INTO challenges_1v1 (
                challenge_number,
                guild_id,
                track_name,
                creator_user_id,
                opponent_user_id,
                end_date,
                status
            ) VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            RETURNING id, challenge_number, track_name, creator_user_id, opponent_user_id,
                      status, created_at, end_date
        """

        params = (challenge_number, guild_id, track_name, creator_id, opponent_id, end_date)
        results = self._execute_query(query, params, fetch=True)

        if not results:
            raise CommandError("Failed to create duel. Please try again.")

        return results[0]

    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """
        Provide autocomplete choices for track names.

        Args:
            interaction: Discord interaction object
            current: Current user input

        Returns:
            List of autocomplete choices for all tracks
        """
        return [
            app_commands.Choice(name=choice['name'], value=choice['value'])
            for choice in get_track_autocomplete_choices(current)[:25]
        ]


# Command setup function for the main bot file
def setup_create_duel_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the create duel command with the Discord command tree.

    Args:
        tree: Discord app commands tree
    """
    create_duel_cmd = CreateDuelCommand()

    @tree.command(
        name="create-duel",
        description="Challenge another user to a 1v1 time trial duel"
    )
    @app_commands.describe(
        opponent="The user you want to challenge",
        track="Select the track for the duel",
        duration_days="Duel duration in days (1-30, default: 7)"
    )
    async def create_duel(interaction: Interaction, opponent: User, track: str,
                         duration_days: int = 7):
        """
        Challenge another user to a 1v1 time trial duel.

        Examples:
        /create-duel opponent:@Kramer track:"Rainbow Road" duration_days:7
        /create-duel opponent:@Michel track:"Mario Circuit" duration_days:14
        """
        await create_duel_cmd.handle_command(
            interaction,
            opponent=opponent,
            track=track,
            duration_days=duration_days
        )

    @create_duel.autocomplete('track')
    async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for track parameter."""
        return await create_duel_cmd.autocomplete_callback(interaction, current)
