"""
Formatting utilities for Discord embeds and leaderboard displays.

This module provides functions for creating consistently formatted
Discord embeds, leaderboards, and other display elements.
"""

import discord
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .time_parser import TimeParser, get_medal_emoji
from .user_utils import UserManager


class EmbedFormatter:
    """
    Creates standardized Discord embeds for the MKW Time Trial Bot.
    
    This class provides methods for creating consistent, well-formatted
    embeds for various bot responses including leaderboards, confirmations,
    and error messages.
    """
    
    # Color constants for different embed types
    COLOR_SUCCESS = 0x00ff00  # Green
    COLOR_ERROR = 0xff0000    # Red
    COLOR_WARNING = 0xffaa00  # Orange
    COLOR_INFO = 0x0099ff     # Blue
    COLOR_LEADERBOARD = 0x4B0082  # Indigo
    COLOR_TRIAL = 0x800080    # Purple
    
    @staticmethod
    def create_leaderboard_embed(trial_data: Dict[str, Any], 
                               leaderboard_data: List[Dict[str, Any]],
                               user_display_names: Dict[int, str]) -> discord.Embed:
        """
        Create a formatted leaderboard embed.
        
        Args:
            trial_data: Trial information (number, track, goal times, etc.)
            leaderboard_data: List of player times with rankings
            user_display_names: Mapping of user_id -> display_name
            
        Returns:
            discord.Embed: Formatted leaderboard embed
        """
        trial_number = trial_data['trial_number']
        track_name = trial_data['track_name']
        status = trial_data.get('status', 'active')
        
        # Create embed title with status emoji
        status_emoji = ""
        if status == 'active':
            status_emoji = " 🟢"
        elif status == 'expired':
            status_emoji = " 🟡"
        elif status == 'ended':
            status_emoji = " 🔴"
        
        title = f"🏁 Weekly Time Trial #{trial_number} - {track_name}{status_emoji}"
        
        # Build the description with leaderboard and goal times
        description_parts = []
        
        # Add leaderboard content
        if not leaderboard_data:
            description_parts.append("No times submitted yet. Be the first to set a time!")
        else:
            leaderboard_text = EmbedFormatter._format_leaderboard_positions(
                leaderboard_data, user_display_names
            )
            description_parts.append(leaderboard_text)
        
        # Add spacing between leaderboard and goal times
        
        # Add goal times (without header)
        goal_times_text = EmbedFormatter._format_goal_times(
            trial_data['gold_time_ms'],
            trial_data['silver_time_ms'], 
            trial_data['bronze_time_ms']
        )
        description_parts.append(goal_times_text)
        
        embed = discord.Embed(
            title=title,
            description="\n\n".join(description_parts),
            color=EmbedFormatter.COLOR_LEADERBOARD,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.set_footer(text="Use /weeklytimesave to submit your time!")
        return embed
    
    @staticmethod
    def _format_leaderboard_positions(leaderboard_data: List[Dict[str, Any]],
                                    user_display_names: Dict[int, str]) -> str:
        """
        Format the leaderboard positions for display.
        
        Args:
            leaderboard_data: List of player times with rankings
            user_display_names: Mapping of user_id -> display_name
            
        Returns:
            str: Formatted leaderboard text
        """
        lines = []
        
        for row in leaderboard_data:
            rank = row['rank']
            user_id = row['user_id']
            time_ms = row['time_ms']
            medal = row.get('medal', 'none')
            
            # Get display name
            display_name = user_display_names.get(user_id, f"User {user_id}")
            display_name = UserManager.truncate_display_name(display_name, 16)
            
            # Format time
            time_str = TimeParser.format_time(time_ms)
            
            # Get medal emoji (to show after time if achieved)
            medal_emoji = ""
            if medal == 'gold':
                medal_emoji = " 🥇"
            elif medal == 'silver':
                medal_emoji = " 🥈"
            elif medal == 'bronze':
                medal_emoji = " 🥉"
            
            # Always use consistent numbering for rank
            rank_display = f"{rank}. "
            
            lines.append(f"{rank_display}{display_name} - {time_str}{medal_emoji}")
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_goal_times(gold_ms: int, silver_ms: int, bronze_ms: int) -> str:
        """
        Format goal times for display.
        
        Args:
            gold_ms: Gold medal time in milliseconds
            silver_ms: Silver medal time in milliseconds
            bronze_ms: Bronze medal time in milliseconds
            
        Returns:
            str: Formatted goal times text
        """
        gold_str = TimeParser.format_time(gold_ms)
        silver_str = TimeParser.format_time(silver_ms)
        bronze_str = TimeParser.format_time(bronze_ms)
        
        return f"🥇 **{gold_str}**  •  🥈 **{silver_str}**  •  🥉 **{bronze_str}**"
    
    @staticmethod
    def create_time_submission_embed(trial_data: Dict[str, Any], 
                                   time_ms: int,
                                   is_improvement: bool = False,
                                   improvement_text: Optional[str] = None,
                                   medal_achieved: Optional[str] = None) -> discord.Embed:
        """
        Create an embed for successful time submission.
        
        Args:
            trial_data: Trial information
            time_ms: Submitted time in milliseconds
            is_improvement: Whether this is an improvement over previous time
            improvement_text: Text describing the improvement
            medal_achieved: Medal level achieved ('gold', 'silver', 'bronze', or None)
            
        Returns:
            discord.Embed: Formatted submission confirmation embed
        """
        trial_number = trial_data['trial_number']
        track_name = trial_data['track_name']
        time_str = TimeParser.format_time(time_ms)
        
        if is_improvement:
            # Ultra minimal format for improvements
            title = f"🏁 {track_name} Improvement"
            
            # Build description with new time, medal, and improvement
            description_parts = []
            
            # Medal emoji if achieved
            medal_emoji = ""
            if medal_achieved:
                medal_emoji = {"gold": " 🥇", "silver": " 🥈", "bronze": " 🥉"}.get(medal_achieved, "")
            
            # Improvement amount (extract from improvement_text)
            improvement_amount = ""
            if improvement_text:
                # Extract the time improvement (e.g., "Improved by 0:00.401!")
                import re
                match = re.search(r'(\d+:\d+\.\d+)', improvement_text)
                if match:
                    improvement_amount = f" (-{match.group(1)})"
            
            description = f"New time: {time_str}{medal_emoji}{improvement_amount}"
            
            embed = discord.Embed(
                title=title,
                description=description,
                color=EmbedFormatter.COLOR_SUCCESS,
                timestamp=datetime.now(timezone.utc)
            )
        else:
            # Regular submission format (keep existing for non-improvements)
            title = "⏱️ Time Submitted!"
            
            embed = discord.Embed(
                title=title,
                color=EmbedFormatter.COLOR_SUCCESS,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Main submission info
            embed.add_field(
                name="🏁 Challenge",
                value=f"Weekly Time Trial #{trial_number}\n**{track_name}**",
                inline=True
            )
            
            embed.add_field(
                name="⏰ Your Time",
                value=f"**{time_str}**",
                inline=True
            )
            
            # Medal achievement
            if medal_achieved:
                medal_emoji = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(medal_achieved, "")
                embed.add_field(
                    name="🏆 Medal Earned",
                    value=f"{medal_emoji} **{medal_achieved.upper()}**",
                    inline=True
                )
        
        embed.set_footer(text="Use /leaderboard to see your ranking!")
        return embed
    
    @staticmethod
    def create_trial_created_embed(trial_data: Dict[str, Any]) -> discord.Embed:
        """
        Create an embed for successful trial creation.
        
        Args:
            trial_data: New trial information
            
        Returns:
            discord.Embed: Formatted trial creation embed
        """
        trial_number = trial_data['trial_number']
        track_name = trial_data['track_name']
        
        embed = discord.Embed(
            title="🏁 New Time Trial Created!",
            description=f"**Weekly Time Trial #{trial_number} - {track_name}**",
            color=EmbedFormatter.COLOR_TRIAL,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Goal times
        goal_times_text = EmbedFormatter._format_goal_times(
            trial_data['gold_time_ms'],
            trial_data['silver_time_ms'],
            trial_data['bronze_time_ms']
        )
        embed.add_field(
            name="🎯 Goal Times",
            value=goal_times_text,
            inline=True
        )
        
        # Duration info
        if 'end_date' in trial_data and trial_data['end_date']:
            embed.add_field(
                name="⏰ Duration",
                value=f"Ends: <t:{int(trial_data['end_date'].timestamp())}:F>",
                inline=True
            )
        
        embed.add_field(
            name="🎮 How to Participate",
            value="Use `/weeklytimesave` command to submit your time!",
            inline=False
        )
        
        embed.set_footer(text="Good luck, racers!")
        return embed
    
    @staticmethod
    def create_error_embed(title: str, description: str, 
                         details: Optional[str] = None) -> discord.Embed:
        """
        Create a standardized error embed.
        
        Args:
            title: Error title
            description: Error description
            details: Optional additional details
            
        Returns:
            discord.Embed: Formatted error embed
        """
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=EmbedFormatter.COLOR_ERROR,
            timestamp=datetime.now(timezone.utc)
        )
        
        if details:
            embed.add_field(
                name="Details",
                value=details,
                inline=False
            )
        
        return embed
    
    @staticmethod
    def create_success_embed(title: str, description: str,
                           details: Optional[str] = None) -> discord.Embed:
        """
        Create a standardized success embed.
        
        Args:
            title: Success title
            description: Success description  
            details: Optional additional details
            
        Returns:
            discord.Embed: Formatted success embed
        """
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=EmbedFormatter.COLOR_SUCCESS,
            timestamp=datetime.now(timezone.utc)
        )
        
        if details:
            embed.add_field(
                name="Details",
                value=details,
                inline=False
            )
        
        return embed
    
    @staticmethod
    def create_info_embed(title: str, description: str,
                        fields: Optional[List[Dict[str, Any]]] = None) -> discord.Embed:
        """
        Create a standardized info embed.
        
        Args:
            title: Info title
            description: Info description
            fields: Optional list of fields to add
            
        Returns:
            discord.Embed: Formatted info embed
        """
        embed = discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=EmbedFormatter.COLOR_INFO,
            timestamp=datetime.now(timezone.utc)
        )
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', 'Field'),
                    value=field.get('value', 'No value'),
                    inline=field.get('inline', False)
                )
        
        return embed


def format_time_with_medal(time_ms: int, gold_ms: int, silver_ms: int, bronze_ms: int) -> str:
    """
    Format a time with its corresponding medal emoji.
    
    Args:
        time_ms: Time in milliseconds
        gold_ms: Gold medal threshold
        silver_ms: Silver medal threshold
        bronze_ms: Bronze medal threshold
        
    Returns:
        str: Formatted time with medal emoji
    """
    time_str = TimeParser.format_time(time_ms)
    medal_emoji = get_medal_emoji(time_ms, gold_ms, silver_ms, bronze_ms)
    
    if medal_emoji:
        return f"{medal_emoji} {time_str}"
    else:
        return time_str


def format_rank_display(rank: int, total: int) -> str:
    """
    Format rank display for leaderboards.
    
    Args:
        rank: User's rank (1-based)
        total: Total number of participants
        
    Returns:
        str: Formatted rank string
    """
    ordinal_suffix = "th"
    if rank % 10 == 1 and rank % 100 != 11:
        ordinal_suffix = "st"
    elif rank % 10 == 2 and rank % 100 != 12:
        ordinal_suffix = "nd"
    elif rank % 10 == 3 and rank % 100 != 13:
        ordinal_suffix = "rd"
    
    return f"{rank}{ordinal_suffix} of {total}"