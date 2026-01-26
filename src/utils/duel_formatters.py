"""
Duel formatters for creating Tesla-style engaging embeds.

This module provides functions for creating visually appealing and
engaging Discord embeds for the 1v1 duel system.
"""

import discord
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .time_parser import TimeParser


class DuelFormatter:
    """
    Formatter class for creating 1v1 duel embeds with Tesla-style engagement.
    """

    # Color constants
    COLOR_CHALLENGE = 0xFF6B00  # Orange - challenging/competitive
    COLOR_ACCEPTED = 0x00FF00   # Green - accepted/active
    COLOR_DECLINED = 0xFF0000   # Red - declined/cancelled
    COLOR_COMPLETED = 0x4B0082  # Indigo - completed
    COLOR_PENDING = 0xFFD700    # Gold - pending action

    @staticmethod
    def create_duel_invitation_embed(duel_data: Dict[str, Any], creator_name: str,
                                    opponent_name: str) -> discord.Embed:
        """
        Create an embed for a new duel invitation.

        Args:
            duel_data: Duel information
            creator_name: Creator's display name
            opponent_name: Opponent's display name

        Returns:
            Formatted invitation embed
        """
        challenge_number = duel_data['challenge_number']
        track_name = duel_data['track_name']
        end_date = duel_data.get('end_date')

        embed = discord.Embed(
            title="⚔️ 1v1 Duel Challenge!",
            description=f"**{creator_name}** has challenged **{opponent_name}** to a duel!",
            color=DuelFormatter.COLOR_CHALLENGE,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="🏁 Track",
            value=f"**{track_name}**",
            inline=True
        )

        embed.add_field(
            name="🔢 Challenge #",
            value=f"**{challenge_number}**",
            inline=True
        )

        if end_date:
            embed.add_field(
                name="⏰ Expires",
                value=f"<t:{int(end_date.timestamp())}:R>",
                inline=True
            )

        embed.add_field(
            name="📋 Next Steps",
            value=(
                f"**{opponent_name}**, you can:\n"
                f"• `/accept-duel` to accept the challenge\n"
                f"• `/decline-duel` to decline"
            ),
            inline=False
        )

        embed.set_footer(text="May the fastest racer win!")
        return embed

    @staticmethod
    def create_duel_accepted_embed(duel_data: Dict[str, Any], creator_name: str,
                                   opponent_name: str) -> discord.Embed:
        """
        Create an embed for when a duel is accepted.

        Args:
            duel_data: Duel information
            creator_name: Creator's display name
            opponent_name: Opponent's display name

        Returns:
            Formatted acceptance embed
        """
        challenge_number = duel_data['challenge_number']
        track_name = duel_data['track_name']
        end_date = duel_data.get('end_date')

        embed = discord.Embed(
            title="✅ Duel Accepted!",
            description=f"**{opponent_name}** has accepted the challenge from **{creator_name}**!",
            color=DuelFormatter.COLOR_ACCEPTED,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="🏁 Track",
            value=f"**{track_name}**",
            inline=True
        )

        embed.add_field(
            name="🔢 Challenge #",
            value=f"**{challenge_number}**",
            inline=True
        )

        if end_date:
            embed.add_field(
                name="⏰ Time Limit",
                value=f"<t:{int(end_date.timestamp())}:R>",
                inline=True
            )

        embed.add_field(
            name="🎮 How to Compete",
            value="Submit your times using `/dueltimesave`\nThe fastest time wins!",
            inline=False
        )

        embed.set_footer(text="Let the race begin!")
        return embed

    @staticmethod
    def create_duel_declined_embed(duel_data: Dict[str, Any], creator_name: str,
                                   opponent_name: str) -> discord.Embed:
        """
        Create an embed for when a duel is declined.

        Args:
            duel_data: Duel information
            creator_name: Creator's display name
            opponent_name: Opponent's display name

        Returns:
            Formatted decline embed
        """
        challenge_number = duel_data['challenge_number']
        track_name = duel_data['track_name']

        embed = discord.Embed(
            title="❌ Duel Declined",
            description=f"**{opponent_name}** has declined the challenge from **{creator_name}**.",
            color=DuelFormatter.COLOR_DECLINED,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="🏁 Track",
            value=f"**{track_name}**",
            inline=True
        )

        embed.add_field(
            name="🔢 Challenge #",
            value=f"**{challenge_number}**",
            inline=True
        )

        embed.set_footer(text="Maybe next time!")
        return embed

    @staticmethod
    def create_duel_time_submission_embed(duel_data: Dict[str, Any], submitter_name: str,
                                         time_ms: int, is_improvement: bool = False,
                                         previous_time_ms: Optional[int] = None) -> discord.Embed:
        """
        Create an embed for a time submission in a duel.

        Args:
            duel_data: Duel information
            submitter_name: Name of person who submitted
            time_ms: Submitted time in milliseconds
            is_improvement: Whether this is an improvement
            previous_time_ms: Previous time in milliseconds (if improvement)

        Returns:
            Formatted time submission embed
        """
        challenge_number = duel_data['challenge_number']
        track_name = duel_data['track_name']
        time_str = TimeParser.format_time(time_ms)

        if is_improvement and previous_time_ms:
            improvement_ms = previous_time_ms - time_ms
            improvement_str = TimeParser.format_time(improvement_ms)
            title = "🔥 Time Improved!"
            description = f"**{submitter_name}** improved their time by **{improvement_str}**!"
        else:
            title = "⏱️ Time Submitted!"
            description = f"**{submitter_name}** has posted a time!"

        embed = discord.Embed(
            title=title,
            description=description,
            color=DuelFormatter.COLOR_CHALLENGE,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="🏁 Track",
            value=f"**{track_name}**",
            inline=True
        )

        embed.add_field(
            name="⏰ Time",
            value=f"**{time_str}**",
            inline=True
        )

        embed.add_field(
            name="🔢 Challenge #",
            value=f"**{challenge_number}**",
            inline=True
        )

        embed.set_footer(text="Use /1v1-results to see current standings")
        return embed

    @staticmethod
    def create_duel_results_embed(duel_data: Dict[str, Any], creator_name: str,
                                  opponent_name: str, creator_time_ms: Optional[int],
                                  opponent_time_ms: Optional[int],
                                  winner_user_id: Optional[int]) -> discord.Embed:
        """
        Create an embed showing duel results.

        Args:
            duel_data: Duel information
            creator_name: Creator's display name
            opponent_name: Opponent's display name
            creator_time_ms: Creator's time in milliseconds (or None)
            opponent_time_ms: Opponent's time in milliseconds (or None)
            winner_user_id: Winner's user ID (or None for tie/incomplete)

        Returns:
            Formatted results embed
        """
        challenge_number = duel_data['challenge_number']
        track_name = duel_data['track_name']
        creator_user_id = duel_data['creator_user_id']
        opponent_user_id = duel_data['opponent_user_id']
        status = duel_data['status']

        # Determine result
        if status == 'completed':
            if winner_user_id is None:
                title = "🤝 Duel Tied!"
                description = "Both racers posted the same time - it's a tie!"
                color = DuelFormatter.COLOR_COMPLETED
            elif winner_user_id == creator_user_id:
                title = "🏆 Duel Complete!"
                description = f"**{creator_name}** wins the duel!"
                color = DuelFormatter.COLOR_COMPLETED
            else:
                title = "🏆 Duel Complete!"
                description = f"**{opponent_name}** wins the duel!"
                color = DuelFormatter.COLOR_COMPLETED
        elif status == 'active':
            title = "⚔️ Duel In Progress"
            description = "The battle continues..."
            color = DuelFormatter.COLOR_ACCEPTED
        else:
            title = "📊 Duel Results"
            description = f"Status: {status.title()}"
            color = DuelFormatter.COLOR_PENDING

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="🏁 Track",
            value=f"**{track_name}**",
            inline=True
        )

        embed.add_field(
            name="🔢 Challenge #",
            value=f"**{challenge_number}**",
            inline=True
        )

        # Add times
        creator_time_str = TimeParser.format_time(creator_time_ms) if creator_time_ms else "Not submitted"
        opponent_time_str = TimeParser.format_time(opponent_time_ms) if opponent_time_ms else "Not submitted"

        # Add winner indicator
        creator_indicator = ""
        opponent_indicator = ""
        if winner_user_id == creator_user_id:
            creator_indicator = " 🏆"
        elif winner_user_id == opponent_user_id:
            opponent_indicator = " 🏆"

        embed.add_field(
            name=f"👤 {creator_name}{creator_indicator}",
            value=f"**{creator_time_str}**",
            inline=True
        )

        embed.add_field(
            name=f"👤 {opponent_name}{opponent_indicator}",
            value=f"**{opponent_time_str}**",
            inline=True
        )

        # Add margin of victory if both submitted
        if creator_time_ms and opponent_time_ms and creator_time_ms != opponent_time_ms:
            margin = abs(creator_time_ms - opponent_time_ms)
            margin_str = TimeParser.format_time(margin)
            embed.add_field(
                name="📏 Margin",
                value=f"**{margin_str}**",
                inline=True
            )

        if status == 'active':
            embed.set_footer(text="Use /dueltimesave to submit your time")
        else:
            embed.set_footer(text="Duel completed")

        return embed

    @staticmethod
    def create_tesla_taunt_message(opponent_name: str, submitter_name: str, time_str: str) -> str:
        """
        Create a Tesla-style engaging taunt message.

        Args:
            opponent_name: Opponent's display name
            submitter_name: Submitter's display name
            time_str: Formatted time string

        Returns:
            Taunt message string
        """
        taunts = [
            f"🔥 {opponent_name}, {submitter_name} just posted a time of **{time_str}**!\n\n"
            f"You're not going to let {submitter_name} beat you, right? 😏\n\n"
            f"Submit your time with `/dueltimesave` to defend your honor!",

            f"⚡ {opponent_name}, {submitter_name} threw down a **{time_str}**!\n\n"
            f"Think you can do better? 🏁\n\n"
            f"Use `/dueltimesave` to accept the challenge!",

            f"🎮 {opponent_name}, {submitter_name} just set a **{time_str}**!\n\n"
            f"Your move! ⚔️\n\n"
            f"Show them what you've got with `/dueltimesave`!",

            f"🏎️ {opponent_name}, {submitter_name} posted **{time_str}**!\n\n"
            f"The gauntlet has been thrown! 🧤\n\n"
            f"Submit your time with `/dueltimesave` to prove you're faster!",

            f"💨 {opponent_name}, {submitter_name} clocked in at **{time_str}**!\n\n"
            f"Are you going to take that? 😤\n\n"
            f"Time to respond with `/dueltimesave`!"
        ]

        return random.choice(taunts)

    @staticmethod
    def create_duel_cancelled_embed(duel_data: Dict[str, Any], creator_name: str,
                                   opponent_name: str) -> discord.Embed:
        """
        Create an embed for when a duel is cancelled.

        Args:
            duel_data: Duel information
            creator_name: Creator's display name
            opponent_name: Opponent's display name

        Returns:
            Formatted cancellation embed
        """
        challenge_number = duel_data['challenge_number']
        track_name = duel_data['track_name']

        embed = discord.Embed(
            title="🚫 Duel Cancelled",
            description=f"**{creator_name}** has cancelled the challenge against **{opponent_name}**.",
            color=DuelFormatter.COLOR_DECLINED,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="🏁 Track",
            value=f"**{track_name}**",
            inline=True
        )

        embed.add_field(
            name="🔢 Challenge #",
            value=f"**{challenge_number}**",
            inline=True
        )

        embed.set_footer(text="Challenge withdrawn")
        return embed
