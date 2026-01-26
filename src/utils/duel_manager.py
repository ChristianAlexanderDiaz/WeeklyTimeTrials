"""
Duel manager utility for the MKW Time Trial Bot.

This module provides helper functions for managing 1v1 duels,
including winner determination, duel retrieval, and challenge numbering.
"""

from typing import Optional, List, Dict, Any
import logging

from ..database.connection import db_manager

logger = logging.getLogger(__name__)


class DuelManager:
    """
    Manager class for 1v1 duel operations.

    Provides helper methods for retrieving duel data, determining winners,
    and managing challenge numbers.
    """

    @staticmethod
    def get_pending_duels_for_user(user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get all pending duel invitations for a user (where they are the opponent).

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID

        Returns:
            List of pending duel data dictionaries
        """
        query = """
            SELECT
                id,
                challenge_number,
                track_name,
                creator_user_id,
                opponent_user_id,
                status,
                created_at,
                end_date
            FROM challenges_1v1
            WHERE guild_id = %s
                AND opponent_user_id = %s
                AND status = 'pending'
            ORDER BY created_at DESC
        """

        try:
            results = db_manager.execute_query(query, (guild_id, user_id))
            return results
        except Exception as e:
            logger.error(f"Error getting pending duels: {e}")
            return []

    @staticmethod
    def get_active_duels_for_user(user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get all active duels for a user (as either creator or opponent).

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID

        Returns:
            List of active duel data dictionaries
        """
        query = """
            SELECT
                id,
                challenge_number,
                track_name,
                creator_user_id,
                opponent_user_id,
                status,
                start_date,
                end_date
            FROM challenges_1v1
            WHERE guild_id = %s
                AND (creator_user_id = %s OR opponent_user_id = %s)
                AND status = 'active'
            ORDER BY created_at DESC
        """

        try:
            results = db_manager.execute_query(query, (guild_id, user_id, user_id))
            return results
        except Exception as e:
            logger.error(f"Error getting active duels: {e}")
            return []

    @staticmethod
    def get_all_duels_for_user(user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get all duels for a user (any status, as either creator or opponent).

        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID

        Returns:
            List of duel data dictionaries
        """
        query = """
            SELECT
                id,
                challenge_number,
                track_name,
                creator_user_id,
                opponent_user_id,
                status,
                created_at,
                accepted_at,
                start_date,
                end_date,
                winner_user_id
            FROM challenges_1v1
            WHERE guild_id = %s
                AND (creator_user_id = %s OR opponent_user_id = %s)
            ORDER BY created_at DESC
        """

        try:
            results = db_manager.execute_query(query, (guild_id, user_id, user_id))
            return results
        except Exception as e:
            logger.error(f"Error getting all duels: {e}")
            return []

    @staticmethod
    def get_duel_display_name(duel_data: Dict[str, Any], creator_name: str, opponent_name: str) -> str:
        """
        Generate a display name for a duel.

        Args:
            duel_data: Duel information dictionary
            creator_name: Creator's display name
            opponent_name: Opponent's display name

        Returns:
            Formatted duel display name (e.g., "Michel vs Kramer - Rainbow Road")
        """
        track_name = duel_data['track_name']
        # Truncate names if too long
        creator_short = creator_name[:10] if len(creator_name) > 10 else creator_name
        opponent_short = opponent_name[:10] if len(opponent_name) > 10 else opponent_name

        return f"{creator_short} vs {opponent_short} - {track_name}"

    @staticmethod
    def determine_winner(challenge_id: int) -> Optional[int]:
        """
        Determine the winner of a duel based on submitted times.

        Args:
            challenge_id: Challenge ID

        Returns:
            Winner's user_id, or None if tie or no submissions
        """
        query = """
            SELECT user_id, time_ms
            FROM challenge_1v1_times
            WHERE challenge_id = %s
            ORDER BY time_ms ASC
            LIMIT 2
        """

        try:
            results = db_manager.execute_query(query, (challenge_id,))

            if len(results) == 0:
                # No submissions
                return None
            elif len(results) == 1:
                # Only one submission - win by default
                return results[0]['user_id']
            else:
                # Both submitted - check for tie
                if results[0]['time_ms'] == results[1]['time_ms']:
                    return None  # Tie
                else:
                    return results[0]['user_id']  # Fastest wins
        except Exception as e:
            logger.error(f"Error determining winner: {e}")
            return None

    @staticmethod
    def get_next_challenge_number(guild_id: int) -> int:
        """
        Get the next sequential challenge number for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            Next challenge number to use
        """
        query = """
            SELECT COALESCE(MAX(challenge_number), 0) + 1 as next_number
            FROM challenges_1v1
            WHERE guild_id = %s
        """

        try:
            results = db_manager.execute_query(query, (guild_id,))
            if results:
                return results[0]['next_number']
            else:
                return 1
        except Exception as e:
            logger.error(f"Error getting next challenge number: {e}")
            return 1

    @staticmethod
    def get_duel_by_id(challenge_id: int) -> Optional[Dict[str, Any]]:
        """
        Get duel information by challenge ID.

        Args:
            challenge_id: Challenge ID

        Returns:
            Duel data dictionary or None if not found
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
                accepted_at,
                start_date,
                end_date,
                winner_user_id
            FROM challenges_1v1
            WHERE id = %s
            LIMIT 1
        """

        try:
            results = db_manager.execute_query(query, (challenge_id,))
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Error getting duel by ID: {e}")
            return None

    @staticmethod
    def get_duel_times(challenge_id: int) -> List[Dict[str, Any]]:
        """
        Get all submitted times for a duel.

        Args:
            challenge_id: Challenge ID

        Returns:
            List of time submission dictionaries, sorted by time (fastest first)
        """
        query = """
            SELECT
                id,
                user_id,
                time_ms,
                submitted_at,
                updated_at
            FROM challenge_1v1_times
            WHERE challenge_id = %s
            ORDER BY time_ms ASC
        """

        try:
            results = db_manager.execute_query(query, (challenge_id,))
            return results
        except Exception as e:
            logger.error(f"Error getting duel times: {e}")
            return []

    @staticmethod
    def get_user_time_for_duel(challenge_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a user's submitted time for a specific duel.

        Args:
            challenge_id: Challenge ID
            user_id: Discord user ID

        Returns:
            Time submission data or None if not found
        """
        query = """
            SELECT
                id,
                user_id,
                time_ms,
                submitted_at,
                updated_at
            FROM challenge_1v1_times
            WHERE challenge_id = %s
                AND user_id = %s
            LIMIT 1
        """

        try:
            results = db_manager.execute_query(query, (challenge_id, user_id))
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Error getting user time for duel: {e}")
            return None

    @staticmethod
    def get_opponent_user_id(challenge_id: int, user_id: int) -> Optional[int]:
        """
        Get the opponent's user ID for a duel.

        Args:
            challenge_id: Challenge ID
            user_id: Current user's ID

        Returns:
            Opponent's user_id or None if not found
        """
        query = """
            SELECT creator_user_id, opponent_user_id
            FROM challenges_1v1
            WHERE id = %s
            LIMIT 1
        """

        try:
            results = db_manager.execute_query(query, (challenge_id,))
            if results:
                duel = results[0]
                if duel['creator_user_id'] == user_id:
                    return duel['opponent_user_id']
                else:
                    return duel['creator_user_id']
            return None
        except Exception as e:
            logger.error(f"Error getting opponent user ID: {e}")
            return None
