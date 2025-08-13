"""
Input validation utilities for the MKW Time Trial Bot.

This module provides validation functions for user inputs,
Discord interactions, and data integrity checks.
"""

import re
from typing import Optional, List, Any
from discord import Interaction

from .time_parser import TimeParser, TimeFormatError


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """
    Provides validation methods for various user inputs.
    
    This class contains static methods for validating different types
    of data that users can input through Discord commands.
    """
    
    @staticmethod
    def validate_time_input(time_str: str) -> int:
        """
        Validate and parse a time input from user.
        
        Args:
            time_str: Time string input by user
            
        Returns:
            int: Parsed time in milliseconds
            
        Raises:
            ValidationError: If time format is invalid
            
        Example:
            >>> InputValidator.validate_time_input("2:23.640")
            143640
        """
        if not time_str or not isinstance(time_str, str):
            raise ValidationError("Time cannot be empty")
        
        time_str = time_str.strip()
        
        if not time_str:
            raise ValidationError("Time cannot be empty")
        
        try:
            return TimeParser.parse_time(time_str)
        except TimeFormatError as e:
            raise ValidationError(str(e))
    
    @staticmethod
    def validate_track_name(track_name: str, valid_tracks: List[str]) -> str:
        """
        Validate that a track name is in the list of valid MKW tracks.
        
        Args:
            track_name: Track name input by user
            valid_tracks: List of valid track names
            
        Returns:
            str: Validated track name
            
        Raises:
            ValidationError: If track name is invalid
        """
        if not track_name or not isinstance(track_name, str):
            raise ValidationError("Track name cannot be empty")
        
        track_name = track_name.strip()
        
        if not track_name:
            raise ValidationError("Track name cannot be empty")
        
        if track_name not in valid_tracks:
            raise ValidationError(
                f"'{track_name}' is not a valid Mario Kart World track. "
                f"Please select from the autocomplete list."
            )
        
        return track_name
    
    @staticmethod
    def validate_duration_days(duration: int) -> int:
        """
        Validate challenge duration in days.
        
        Args:
            duration: Number of days for challenge
            
        Returns:
            int: Validated duration
            
        Raises:
            ValidationError: If duration is invalid
        """
        if not isinstance(duration, int):
            try:
                duration = int(duration)
            except (ValueError, TypeError):
                raise ValidationError("Duration must be a number")
        
        if duration < 1:
            raise ValidationError("Duration must be at least 1 day")
        
        if duration > 30:
            raise ValidationError("Duration cannot exceed 30 days")
        
        return duration
    
    @staticmethod
    def validate_guild_interaction(interaction: Interaction) -> int:
        """
        Validate that interaction is from a guild (server) and return guild ID.
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            int: Guild ID
            
        Raises:
            ValidationError: If interaction is not from a guild
        """
        if not interaction.guild:
            raise ValidationError("This command can only be used in a server")
        
        return interaction.guild.id
    
    @staticmethod
    def validate_user_interaction(interaction: Interaction) -> int:
        """
        Validate interaction and return user ID.
        
        Args:
            interaction: Discord interaction object
            
        Returns:
            int: User ID
            
        Raises:
            ValidationError: If user information is unavailable
        """
        if not interaction.user:
            raise ValidationError("Unable to identify user")
        
        return interaction.user.id
    
    @staticmethod
    def validate_goal_times(gold: str, silver: str, bronze: str) -> tuple[int, int, int]:
        """
        Validate and parse goal times for a new challenge.
        
        Args:
            gold: Gold medal time string
            silver: Silver medal time string
            bronze: Bronze medal time string
            
        Returns:
            tuple: (gold_ms, silver_ms, bronze_ms) in milliseconds
            
        Raises:
            ValidationError: If any goal time is invalid
        """
        try:
            return TimeParser.parse_goal_times(gold, silver, bronze)
        except TimeFormatError as e:
            raise ValidationError(f"Invalid goal times: {e}")
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 100) -> str:
        """
        Sanitize string input by removing harmful characters and limiting length.
        
        Args:
            input_str: String to sanitize
            max_length: Maximum allowed length
            
        Returns:
            str: Sanitized string
            
        Raises:
            ValidationError: If string is too long after sanitization
        """
        if not isinstance(input_str, str):
            raise ValidationError("Input must be a string")
        
        # Remove control characters and excessive whitespace
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', input_str)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        if len(sanitized) > max_length:
            raise ValidationError(f"Input too long (max {max_length} characters)")
        
        return sanitized


class DatabaseValidator:
    """
    Provides validation methods for database operations.
    
    This class contains static methods for validating data
    before database operations to ensure data integrity.
    """
    
    @staticmethod
    def validate_trial_data(trial_data: dict) -> dict:
        """
        Validate trial data before database insertion.
        
        Args:
            trial_data: Dictionary containing trial information
            
        Returns:
            dict: Validated trial data
            
        Raises:
            ValidationError: If trial data is invalid
        """
        required_fields = ['trial_number', 'track_name', 'gold_time_ms', 
                          'silver_time_ms', 'bronze_time_ms', 'guild_id']
        
        for field in required_fields:
            if field not in trial_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate trial number
        if not isinstance(trial_data['trial_number'], int) or trial_data['trial_number'] < 1:
            raise ValidationError("Trial number must be a positive integer")
        
        # Validate track name
        if not isinstance(trial_data['track_name'], str) or not trial_data['track_name'].strip():
            raise ValidationError("Track name must be a non-empty string")
        
        # Validate goal times
        for time_field in ['gold_time_ms', 'silver_time_ms', 'bronze_time_ms']:
            if not isinstance(trial_data[time_field], int) or trial_data[time_field] < 0:
                raise ValidationError(f"{time_field} must be a non-negative integer")
        
        # Validate time ordering
        if not (trial_data['gold_time_ms'] <= trial_data['silver_time_ms'] <= trial_data['bronze_time_ms']):
            raise ValidationError("Goal times must be in order: gold ≤ silver ≤ bronze")
        
        # Validate guild ID
        if not isinstance(trial_data['guild_id'], int) or trial_data['guild_id'] <= 0:
            raise ValidationError("Guild ID must be a positive integer")
        
        return trial_data
    
    @staticmethod
    def validate_time_submission(submission_data: dict) -> dict:
        """
        Validate time submission data before database insertion.
        
        Args:
            submission_data: Dictionary containing submission information
            
        Returns:
            dict: Validated submission data
            
        Raises:
            ValidationError: If submission data is invalid
        """
        required_fields = ['trial_id', 'user_id', 'time_ms']
        
        for field in required_fields:
            if field not in submission_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate trial ID
        if not isinstance(submission_data['trial_id'], int) or submission_data['trial_id'] <= 0:
            raise ValidationError("Trial ID must be a positive integer")
        
        # Validate user ID
        if not isinstance(submission_data['user_id'], int) or submission_data['user_id'] <= 0:
            raise ValidationError("User ID must be a positive integer")
        
        # Validate time
        if not isinstance(submission_data['time_ms'], int) or submission_data['time_ms'] <= 0:
            raise ValidationError("Time must be a positive integer (milliseconds)")
        
        # Validate time range
        if not (TimeParser.MIN_TIME_MS <= submission_data['time_ms'] <= TimeParser.MAX_TIME_MS):
            raise ValidationError(f"Time out of valid range ({TimeParser.MIN_TIME_MS}-{TimeParser.MAX_TIME_MS}ms)")
        
        return submission_data


def create_error_embed(title: str, description: str, color: int = 0xff0000) -> dict:
    """
    Create a standardized error embed for Discord responses.
    
    Args:
        title: Error title
        description: Error description
        color: Embed color (default: red)
        
    Returns:
        dict: Discord embed data
    """
    return {
        "title": f"❌ {title}",
        "description": description,
        "color": color
    }


def create_success_embed(title: str, description: str, color: int = 0x00ff00) -> dict:
    """
    Create a standardized success embed for Discord responses.
    
    Args:
        title: Success title
        description: Success description
        color: Embed color (default: green)
        
    Returns:
        dict: Discord embed data
    """
    return {
        "title": f"✅ {title}",
        "description": description,
        "color": color
    }


def create_info_embed(title: str, description: str, color: int = 0x0099ff) -> dict:
    """
    Create a standardized info embed for Discord responses.
    
    Args:
        title: Info title
        description: Info description
        color: Embed color (default: blue)
        
    Returns:
        dict: Discord embed data
    """
    return {
        "title": f"ℹ️ {title}",
        "description": description,
        "color": color
    }