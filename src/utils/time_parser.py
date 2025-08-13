"""
Time parsing and validation utilities for the MKW Time Trial Bot.

This module handles conversion between time formats:
- User input: "2:23.640" or "02:23.640" (MM:SS.mmm)
- Storage: milliseconds as integer (143640)
- Display: "2:23.640" (MM:SS.mmm with proper formatting)

Time range supported: 0:00.000 to 9:59.999
"""

import re
from typing import Optional, Tuple


class TimeFormatError(Exception):
    """Raised when time format validation fails."""
    pass


class TimeParser:
    """
    Handles time format validation, parsing, and conversion.
    
    This class provides static methods for working with Mario Kart World
    time trial times in MM:SS.mmm format.
    """
    
    # Regular expression for time format validation
    # Matches: M:SS.mmm or MM:SS.mmm where M=0-9, SS=00-59, mmm=000-999
    TIME_REGEX = re.compile(r'^([0-9]):([0-5]\d)\.(\d{3})$')
    
    # Time constraints (in milliseconds)
    MIN_TIME_MS = 0        # 0:00.000
    MAX_TIME_MS = 599999   # 9:59.999
    
    @staticmethod
    def parse_time(time_str: str) -> int:
        """
        Parse a time string and convert to milliseconds.
        
        Args:
            time_str: Time in format "M:SS.mmm" or "MM:SS.mmm"
                     Examples: "2:23.640", "0:45.123", "9:59.999"
        
        Returns:
            int: Time in milliseconds
            
        Raises:
            TimeFormatError: If time format is invalid or out of range
            
        Example:
            >>> TimeParser.parse_time("2:23.640")
            143640
            >>> TimeParser.parse_time("0:45.123") 
            45123
        """
        if not isinstance(time_str, str):
            raise TimeFormatError("Time must be a string")
        
        time_str = time_str.strip()
        
        # Validate format using regex
        match = TimeParser.TIME_REGEX.match(time_str)
        if not match:
            raise TimeFormatError(
                f"Invalid time format: '{time_str}'. "
                f"Expected format: M:SS.mmm (e.g., '2:23.640')"
            )
        
        # Extract components
        minutes_str, seconds_str, milliseconds_str = match.groups()
        
        try:
            minutes = int(minutes_str)
            seconds = int(seconds_str)
            milliseconds = int(milliseconds_str)
        except ValueError:
            raise TimeFormatError(f"Invalid numeric values in time: '{time_str}'")
        
        # Convert to total milliseconds
        total_ms = (minutes * 60 * 1000) + (seconds * 1000) + milliseconds
        
        # Validate range
        if total_ms < TimeParser.MIN_TIME_MS:
            raise TimeFormatError(f"Time too small: '{time_str}' (minimum: 0:00.000)")
        
        if total_ms > TimeParser.MAX_TIME_MS:
            raise TimeFormatError(f"Time too large: '{time_str}' (maximum: 9:59.999)")
        
        return total_ms
    
    @staticmethod
    def format_time(milliseconds: int) -> str:
        """
        Convert milliseconds back to MM:SS.mmm format for display.
        
        Args:
            milliseconds: Time in milliseconds
            
        Returns:
            str: Formatted time string (e.g., "2:23.640")
            
        Raises:
            TimeFormatError: If milliseconds value is invalid
            
        Example:
            >>> TimeParser.format_time(143640)
            "2:23.640"
            >>> TimeParser.format_time(45123)
            "0:45.123"
        """
        if not isinstance(milliseconds, int):
            raise TimeFormatError("Milliseconds must be an integer")
        
        if milliseconds < TimeParser.MIN_TIME_MS:
            raise TimeFormatError(f"Invalid time: {milliseconds}ms (minimum: {TimeParser.MIN_TIME_MS}ms)")
        
        if milliseconds > TimeParser.MAX_TIME_MS:
            raise TimeFormatError(f"Invalid time: {milliseconds}ms (maximum: {TimeParser.MAX_TIME_MS}ms)")
        
        # Convert milliseconds to components
        total_seconds = milliseconds // 1000
        ms_remainder = milliseconds % 1000
        
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        # Format as M:SS.mmm (no leading zero for minutes)
        return f"{minutes}:{seconds:02d}.{ms_remainder:03d}"
    
    @staticmethod
    def validate_time_string(time_str: str) -> bool:
        """
        Check if a time string is valid without raising exceptions.
        
        Args:
            time_str: Time string to validate
            
        Returns:
            bool: True if valid, False otherwise
            
        Example:
            >>> TimeParser.validate_time_string("2:23.640")
            True
            >>> TimeParser.validate_time_string("invalid")
            False
        """
        try:
            TimeParser.parse_time(time_str)
            return True
        except TimeFormatError:
            return False
    
    @staticmethod
    def compare_times(time1_ms: int, time2_ms: int) -> str:
        """
        Compare two times and return a human-readable difference.
        
        Args:
            time1_ms: First time in milliseconds
            time2_ms: Second time in milliseconds
            
        Returns:
            str: Formatted difference (e.g., "+0:01.234" or "-0:00.500")
            
        Example:
            >>> TimeParser.compare_times(143640, 142000)
            "+0:01.640"
            >>> TimeParser.compare_times(142000, 143640)  
            "-0:01.640"
        """
        diff_ms = time1_ms - time2_ms
        
        if diff_ms == 0:
            return "±0:00.000"
        
        sign = "+" if diff_ms > 0 else "-"
        abs_diff = abs(diff_ms)
        
        diff_formatted = TimeParser.format_time(abs_diff)
        return f"{sign}{diff_formatted}"
    
    @staticmethod
    def get_time_improvement(old_time_ms: int, new_time_ms: int) -> Optional[str]:
        """
        Calculate time improvement when a user submits a faster time.
        
        Args:
            old_time_ms: Previous time in milliseconds
            new_time_ms: New time in milliseconds
            
        Returns:
            str: Improvement message if new time is faster, None otherwise
            
        Example:
            >>> TimeParser.get_time_improvement(143640, 142000)
            "Improved by 0:01.640!"
            >>> TimeParser.get_time_improvement(142000, 143640)
            None
        """
        if new_time_ms >= old_time_ms:
            return None
        
        improvement_ms = old_time_ms - new_time_ms
        improvement_str = TimeParser.format_time(improvement_ms)
        return f"Improved by {improvement_str}!"
    
    @staticmethod
    def parse_goal_times(gold_str: str, silver_str: str, bronze_str: str) -> Tuple[int, int, int]:
        """
        Parse and validate goal times for a new challenge.
        
        Ensures that gold <= silver <= bronze for logical medal requirements.
        
        Args:
            gold_str: Gold medal time string
            silver_str: Silver medal time string  
            bronze_str: Bronze medal time string
            
        Returns:
            Tuple[int, int, int]: (gold_ms, silver_ms, bronze_ms)
            
        Raises:
            TimeFormatError: If any time is invalid or ordering is wrong
            
        Example:
            >>> TimeParser.parse_goal_times("2:20.000", "2:25.000", "2:30.000")
            (140000, 145000, 150000)
        """
        # Parse all three times
        gold_ms = TimeParser.parse_time(gold_str)
        silver_ms = TimeParser.parse_time(silver_str)
        bronze_ms = TimeParser.parse_time(bronze_str)
        
        # Validate ordering (gold should be fastest)
        if not (gold_ms <= silver_ms <= bronze_ms):
            raise TimeFormatError(
                f"Invalid goal time ordering. Expected: gold ≤ silver ≤ bronze. "
                f"Got: {TimeParser.format_time(gold_ms)} ≤ "
                f"{TimeParser.format_time(silver_ms)} ≤ "
                f"{TimeParser.format_time(bronze_ms)}"
            )
        
        return gold_ms, silver_ms, bronze_ms


def format_duration(duration_days: int) -> str:
    """
    Format challenge duration for display.
    
    Args:
        duration_days: Number of days
        
    Returns:
        str: Formatted duration string
        
    Example:
        >>> format_duration(7)
        "7 days"
        >>> format_duration(1)
        "1 day"
    """
    if duration_days == 1:
        return "1 day"
    else:
        return f"{duration_days} days"


def get_medal_emoji(time_ms: int, gold_ms: int, silver_ms: int, bronze_ms: int) -> str:
    """
    Get the appropriate medal emoji based on time performance.
    
    Args:
        time_ms: Submitted time in milliseconds
        gold_ms: Gold medal threshold in milliseconds
        silver_ms: Silver medal threshold in milliseconds
        bronze_ms: Bronze medal threshold in milliseconds
        
    Returns:
        str: Medal emoji ("🥇", "🥈", "🥉", or "" for no medal)
        
    Example:
        >>> get_medal_emoji(140000, 145000, 150000, 155000)
        "🥇"
        >>> get_medal_emoji(160000, 145000, 150000, 155000)
        ""
    """
    if time_ms <= gold_ms:
        return "🥇"
    elif time_ms <= silver_ms:
        return "🥈"
    elif time_ms <= bronze_ms:
        return "🥉"
    else:
        return ""