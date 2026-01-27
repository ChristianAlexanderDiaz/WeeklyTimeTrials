"""
Update category command for the MKW Time Trial Bot.

This command allows admins to change the category (shrooms/shroomless) of an
existing challenge after it has been created.
"""

from typing import List, Optional, Dict, Any
import logging
import discord
from discord import app_commands, Interaction

from .base import AutocompleteCommand, CommandError
from ..utils.validators import InputValidator, ValidationError
from ..utils.formatters import EmbedFormatter

logger = logging.getLogger(__name__)


class UpdateCategoryCommand(AutocompleteCommand):
    """
    Command to update the category of an existing trial.

    This command handles:
    - Trial number validation
    - Finding active trials by trial number
    - Updating category in database
    - Updating live leaderboard message with new category
    - Sending confirmation
    """

    async def execute(self, interaction: Interaction, trial_number: int, category: str) -> None:
        """
        Execute the update category command.

        Args:
            interaction: Discord interaction object
            trial_number: Trial number to update
            category: New category ('shrooms' or 'shroomless')
        """
        guild_id = self._validate_guild_interaction(interaction)

        # Validate trial number
        if trial_number <= 0:
            raise ValidationError("Trial number must be a positive integer")

        # Validate category
        category = InputValidator.validate_category(category)

        # Get trial by trial number (any status - can update active or ended)
        trial_data = await self._get_trial_by_number(guild_id, trial_number)
        if not trial_data:
            raise CommandError(
                f"No trial found with number **{trial_number}**. "
                f"Use `/active` to see current active trials."
            )

        trial_id = trial_data['id']
        old_category = trial_data.get('category', 'shrooms')

        # Check if category is already set to the requested value
        if old_category == category:
            raise CommandError(
                f"Trial #{trial_number} is already set to **{category}** category. "
                f"No changes needed."
            )

        # Check if there's already an active trial for this track with the new category
        track_name = trial_data['track_name']
        existing_trial = await self._get_active_trial_by_track_and_category(
            guild_id, track_name, category
        )
        if existing_trial and existing_trial['id'] != trial_id:
            raise CommandError(
                f"Cannot change to **{category}** category because there's already "
                f"an active {category} trial for **{track_name}** "
                f"(Trial #{existing_trial['trial_number']}). End that trial first."
            )

        # Update the category in database
        await self._update_trial_category(trial_id, category)

        # Update live leaderboard message if it exists
        from ..utils.leaderboard_manager import update_live_leaderboard

        leaderboard_updated = False
        try:
            # Refresh trial data with new category
            updated_trial_data = await self._get_trial_by_number(guild_id, trial_number)
            if updated_trial_data:
                leaderboard_updated = await update_live_leaderboard(updated_trial_data, interaction.guild)
                if leaderboard_updated:
                    logger.info(f"Updated live leaderboard for trial #{trial_number} with new category")
                else:
                    logger.warning(f"Failed to update live leaderboard for trial #{trial_number}")
        except Exception as e:
            # Don't fail the command if leaderboard update fails
            logger.error(f"Error updating live leaderboard: {e}")
            leaderboard_updated = False

        # Create success response
        embed = discord.Embed(
            title="✅ Category Updated",
            description=(
                f"**Weekly Time Trial #{trial_number} - {track_name}**\n\n"
                f"Category changed from **{old_category.title()}** to **{category.title()}**"
            ),
            color=EmbedFormatter.COLOR_SUCCESS
        )

        # Build what changed message conditionally based on leaderboard update success
        what_changed_parts = [f"• The trial category has been updated to **{category.title()}**"]
        if leaderboard_updated:
            what_changed_parts.append("• The live leaderboard has been updated with the new category")
        else:
            what_changed_parts.append("• Live leaderboard update failed (check logs)")
        what_changed_parts.append("• All existing times remain intact")

        embed.add_field(
            name="ℹ️ What Changed",
            value="\n".join(what_changed_parts),
            inline=False
        )

        embed.set_footer(text="Category updated successfully")

        await self._send_response(interaction, embed=embed, ephemeral=False)

    async def _get_trial_by_number(self, guild_id: int, trial_number: int) -> Optional[Dict[str, Any]]:
        """
        Get trial by trial number (any status).

        Args:
            guild_id: Discord guild ID
            trial_number: Trial number to find

        Returns:
            Trial data if found, None otherwise
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
                status,
                guild_id,
                leaderboard_channel_id,
                leaderboard_message_id
            FROM weekly_trials
            WHERE guild_id = %s
                AND trial_number = %s
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, trial_number))
        return results[0] if results else None

    async def _get_active_trial_by_track_and_category(
        self, guild_id: int, track_name: str, category: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get active trial for a specific track and category.

        Args:
            guild_id: Discord guild ID
            track_name: Track name
            category: Category to check

        Returns:
            Trial data if found, None otherwise
        """
        query = """
            SELECT
                id,
                trial_number,
                track_name,
                category
            FROM weekly_trials
            WHERE guild_id = %s
                AND track_name = %s
                AND category = %s
                AND status = 'active'
            LIMIT 1
        """

        results = self._execute_query(query, (guild_id, track_name, category))
        return results[0] if results else None

    async def _update_trial_category(self, trial_id: int, category: str) -> None:
        """
        Update the category of a trial in the database.

        Args:
            trial_id: Trial ID to update
            category: New category value

        Raises:
            CommandError: If update fails
        """
        query = """
            UPDATE weekly_trials
            SET category = %s
            WHERE id = %s
            RETURNING id, trial_number, track_name, category
        """

        results = self._execute_query(query, (category, trial_id), fetch=True)
        if not results:
            raise CommandError("Failed to update category. Please try again.")

    async def autocomplete_callback(self, interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
        """No autocomplete needed for trial number input."""
        return []


# Command setup function for the main bot file
def setup_update_category_command(tree: app_commands.CommandTree) -> None:
    """
    Set up the update category command with the Discord command tree.

    Args:
        tree: Discord app commands tree
    """
    update_cmd = UpdateCategoryCommand()

    @tree.command(
        name="update-category",
        description="Update the category (shrooms/shroomless) of an existing trial"
    )
    @app_commands.describe(
        trial_number="Trial number to update (use /active to see current trial numbers)",
        category="New category for the trial"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="Shrooms", value="shrooms"),
        app_commands.Choice(name="Shroomless", value="shroomless")
    ])
    async def update_category(interaction: Interaction, trial_number: int, category: str):
        """
        Update the category (shrooms/shroomless) of an existing trial.

        This changes the category in the database and updates the live
        leaderboard message to reflect the new category. All existing
        times remain intact.

        Examples:
        /update-category trial_number:1 category:shroomless
        /update-category trial_number:2 category:shrooms

        Notes:
        - Use /active to see current trial numbers
        - Cannot change to a category that already has an active trial for the same track
        - Works for both active and ended trials
        - Live leaderboard is automatically updated
        """
        await update_cmd.handle_command(interaction, trial_number=trial_number, category=category)
