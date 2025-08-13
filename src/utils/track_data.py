"""
Mario Kart World track data and utilities.

This module contains the complete list of all 30 Mario Kart World tracks
and provides utilities for track name validation and autocomplete functionality.
"""

from typing import List, Optional


# Complete list of all 30 Mario Kart World tracks
# This list is used for autocomplete functionality and validation
MKW_TRACKS: List[str] = [
    "Mario Bros. Circuit",
    "Crown City", 
    "Whistlestop Summit",
    "DK Spaceport",
    "Desert Hills",
    "Shy Guy Bazaar",
    "Wario Stadium",
    "Airship Fortress",
    "DK Pass",
    "Starview Peak",
    "Sky-High Sundae",
    "Wario Shipyard",
    "Koopa Troopa Beach",
    "Faraway Oasis",
    "Peach Stadium",
    "Peach Beach",
    "Salty Salty Speedway",
    "Dino Dino Jungle",
    "Great ? Block Ruins",
    "Cheep Cheep Falls",
    "Dandelion Depths",
    "Boo Cinema",
    "Dry Bones Burnout",
    "Moo Moo Meadows",
    "Choco Mountain",
    "Toad's Factory",
    "Bowser's Castle",
    "Acorn Heights",
    "Mario Circuit",
    "Rainbow Road"
]


class TrackManager:
    """
    Manages Mario Kart World track data and provides utility methods.
    
    This class provides methods for track validation, search, and
    autocomplete functionality for Discord slash commands.
    """
    
    @staticmethod
    def get_all_tracks() -> List[str]:
        """
        Get the complete list of all Mario Kart World tracks.
        
        Returns:
            List[str]: All 30 MKW track names
        """
        return MKW_TRACKS.copy()
    
    @staticmethod
    def is_valid_track(track_name: str) -> bool:
        """
        Check if a track name is valid.
        
        Args:
            track_name: Track name to validate
            
        Returns:
            bool: True if track name is valid, False otherwise
            
        Example:
            >>> TrackManager.is_valid_track("Rainbow Road")
            True
            >>> TrackManager.is_valid_track("Invalid Track")
            False
        """
        return track_name in MKW_TRACKS
    
    @staticmethod
    def search_tracks(query: str, limit: int = 25) -> List[str]:
        """
        Search for tracks matching a query string.
        
        This method performs case-insensitive partial matching
        and is useful for autocomplete functionality.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List[str]: List of matching track names
            
        Example:
            >>> TrackManager.search_tracks("mario")
            ["Mario Bros. Circuit", "Mario Circuit"]
            >>> TrackManager.search_tracks("beach")
            ["Koopa Troopa Beach", "Peach Beach"]
        """
        if not query:
            return MKW_TRACKS[:limit]
        
        query_lower = query.lower()
        matches = []
        
        # First, add exact matches (case-insensitive)
        for track in MKW_TRACKS:
            if track.lower() == query_lower:
                matches.append(track)
        
        # Then, add tracks that start with the query
        for track in MKW_TRACKS:
            if track.lower().startswith(query_lower) and track not in matches:
                matches.append(track)
        
        # Finally, add tracks that contain the query anywhere
        for track in MKW_TRACKS:
            if query_lower in track.lower() and track not in matches:
                matches.append(track)
        
        return matches[:limit]
    
    @staticmethod
    def get_track_autocomplete_choices(current: str) -> List[dict]:
        """
        Get autocomplete choices for Discord slash commands.
        
        Returns track names formatted for Discord autocomplete.
        Limits results to 25 as required by Discord API.
        
        Args:
            current: Current user input for autocomplete
            
        Returns:
            List[dict]: List of choice dictionaries for Discord
            
        Example:
            >>> TrackManager.get_track_autocomplete_choices("mario")
            [
                {"name": "Mario Bros. Circuit", "value": "Mario Bros. Circuit"},
                {"name": "Mario Circuit", "value": "Mario Circuit"}
            ]
        """
        matching_tracks = TrackManager.search_tracks(current, limit=25)
        
        return [
            {"name": track, "value": track}
            for track in matching_tracks
        ]
    
    @staticmethod
    def get_random_track() -> str:
        """
        Get a random track name.
        
        Useful for testing or challenge suggestions.
        
        Returns:
            str: Random track name
        """
        import random
        return random.choice(MKW_TRACKS)
    
    @staticmethod
    def get_track_categories() -> dict[str, List[str]]:
        """
        Get tracks organized by categories (for future use).
        
        This is a basic categorization that could be used for
        filtered autocomplete or themed challenges.
        
        Returns:
            dict: Track names organized by category
        """
        return {
            "Classic Mario": [
                "Mario Bros. Circuit",
                "Mario Circuit",
                "Peach Stadium", 
                "Peach Beach",
                "Bowser's Castle"
            ],
            "Nature/Outdoor": [
                "Moo Moo Meadows",
                "Choco Mountain",
                "Desert Hills",
                "Dandelion Depths",
                "Acorn Heights",
                "Starview Peak"
            ],
            "Industrial/City": [
                "Crown City",
                "Toad's Factory",
                "Wario Stadium",
                "Wario Shipyard",
                "DK Spaceport"
            ],
            "Adventure/Fantasy": [
                "Airship Fortress",
                "DK Pass",
                "Great ? Block Ruins",
                "Boo Cinema",
                "Sky-High Sundae",
                "Rainbow Road"
            ],
            "Beach/Water": [
                "Koopa Troopa Beach",
                "Peach Beach",
                "Cheep Cheep Falls",
                "Wario Shipyard"
            ],
            "Underground/Cave": [
                "Dry Bones Burnout",
                "Shy Guy Bazaar",
                "Whistlestop Summit"
            ],
            "Racing/Speed": [
                "Salty Salty Speedway",
                "Dino Dino Jungle",
                "Faraway Oasis"
            ]
        }
    
    @staticmethod
    def format_track_list(tracks: List[str], numbered: bool = True) -> str:
        """
        Format a list of tracks for display in Discord embeds.
        
        Args:
            tracks: List of track names to format
            numbered: Whether to number the tracks
            
        Returns:
            str: Formatted track list
            
        Example:
            >>> TrackManager.format_track_list(["Rainbow Road", "Mario Circuit"])
            "1. Rainbow Road\\n2. Mario Circuit"
        """
        if numbered:
            return "\n".join(f"{i+1}. {track}" for i, track in enumerate(tracks))
        else:
            return "\n".join(f"• {track}" for track in tracks)
    
    @staticmethod
    def validate_track_for_command(track_name: str) -> str:
        """
        Validate and normalize a track name for command usage.
        
        This method checks if the track is valid and returns it
        in the exact format stored in the database.
        
        Args:
            track_name: Track name to validate
            
        Returns:
            str: Validated track name
            
        Raises:
            ValueError: If track name is not valid
        """
        if not track_name or not isinstance(track_name, str):
            raise ValueError("Track name cannot be empty")
        
        track_name = track_name.strip()
        
        if not TrackManager.is_valid_track(track_name):
            raise ValueError(
                f"'{track_name}' is not a valid Mario Kart World track. "
                f"Please select from the autocomplete list."
            )
        
        return track_name


# Convenience functions for easy importing
def get_all_tracks() -> List[str]:
    """Get all MKW track names."""
    return TrackManager.get_all_tracks()


def is_valid_track(track_name: str) -> bool:
    """Check if a track name is valid."""
    return TrackManager.is_valid_track(track_name)


def search_tracks(query: str, limit: int = 25) -> List[str]:
    """Search for tracks matching a query."""
    return TrackManager.search_tracks(query, limit)


def get_track_autocomplete_choices(current: str) -> List[dict]:
    """Get autocomplete choices for Discord commands."""
    return TrackManager.get_track_autocomplete_choices(current)