"""
PostgreSQL database connection management for the MKW Time Trial Bot.

This module provides connection pooling, transaction management, and 
raw SQL query execution using psycopg2. All queries use parameterized
statements to prevent SQL injection.
"""

import asyncio
import logging
import psycopg2
import psycopg2.pool
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple
from psycopg2.extras import RealDictCursor

from ..config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages PostgreSQL connections and provides query execution methods.
    
    This class uses a connection pool for efficient database access and
    provides methods for executing raw SQL queries with proper error handling.
    """
    
    def __init__(self):
        self._pool: Optional[psycopg2.pool.SimpleConnectionPool] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize the database connection pool.
        
        Creates a connection pool with multiple connections for concurrent access.
        This should be called once when the bot starts up.
        
        Raises:
            psycopg2.Error: If database connection fails
        """
        if self._initialized:
            return
        
        try:
            db_config = settings.get_database_config()
            
            # Create connection pool with 5-20 connections
            self._pool = psycopg2.pool.SimpleConnectionPool(
                minconn=5,
                maxconn=20,
                **db_config
            )
            
            # Test the connection by getting a connection directly from pool
            test_conn = None
            try:
                test_conn = self._pool.getconn()
                if test_conn is None:
                    raise RuntimeError("Failed to get test connection from pool")
                
                with test_conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    if result[0] != 1:
                        raise Exception("Database connection test failed")
            finally:
                if test_conn:
                    self._pool.putconn(test_conn)
            
            # Mark as initialized only after successful test
            self._initialized = True
            logger.info("✓ Database connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"✗ Failed to initialize database: {e}")
            raise
    
    def close(self) -> None:
        """
        Close all database connections in the pool.
        
        This should be called when the bot shuts down to properly
        clean up database connections.
        """
        if self._pool:
            self._pool.closeall()
            self._pool = None
            self._initialized = False
            logger.info("Database connection pool closed")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for getting a database connection from the pool.
        
        Automatically returns the connection to the pool when done.
        Handles connection errors and ensures proper cleanup.
        
        Yields:
            psycopg2.connection: Database connection
            
        Example:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM weekly_trials")
                    results = cursor.fetchall()
        """
        if not self._initialized or not self._pool:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        conn = None
        try:
            conn = self._pool.getconn()
            if conn is None:
                raise RuntimeError("Failed to get connection from pool")
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def execute_query(self, query: str, params: Tuple = (), fetch: bool = True) -> List[Dict[str, Any]]:
        """
        Execute a SQL query with parameters and return results.
        
        Args:
            query: SQL query string with %s placeholders for parameters
            params: Tuple of parameters to substitute in the query
            fetch: Whether to fetch and return results (False for INSERT/UPDATE/DELETE)
            
        Returns:
            List of dictionaries representing rows (empty list if fetch=False)
            
        Example:
            # SELECT query
            results = db.execute_query(
                "SELECT * FROM weekly_trials WHERE status = %s", 
                ('active',)
            )
            
            # INSERT query  
            db.execute_query(
                "INSERT INTO player_times (trial_id, user_id, time_ms) VALUES (%s, %s, %s)",
                (trial_id, user_id, time_ms),
                fetch=False
            )
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(query, params)
                    
                    if fetch:
                        rows = cursor.fetchall()
                        # Convert RealDictRow to regular dict
                        return [dict(row) for row in rows]
                    else:
                        conn.commit()
                        return []
                        
                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Query execution failed: {e}")
                    logger.error(f"Query: {query}")
                    logger.error(f"Parameters: {params}")
                    raise
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """
        Execute the same query with multiple parameter sets.
        
        Useful for batch INSERT operations. All operations are executed
        in a single transaction for consistency.
        
        Args:
            query: SQL query string with %s placeholders
            params_list: List of parameter tuples
            
        Example:
            db.execute_many(
                "INSERT INTO player_times (trial_id, user_id, time_ms) VALUES (%s, %s, %s)",
                [
                    (1, 12345, 143000),
                    (1, 67890, 145000),
                    (1, 11111, 147000)
                ]
            )
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.executemany(query, params_list)
                    conn.commit()
                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Batch query execution failed: {e}")
                    raise
    
    def execute_transaction(self, operations: List[Tuple[str, Tuple]]) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple queries in a single transaction.
        
        All queries succeed together or all fail together (ACID compliance).
        This is useful for operations that need to maintain data consistency.
        
        Args:
            operations: List of (query, params) tuples
            
        Returns:
            List of results for each query (empty list for non-SELECT queries)
            
        Example:
            results = db.execute_transaction([
                ("UPDATE weekly_trials SET status = %s WHERE id = %s", ('ended', trial_id)),
                ("SELECT * FROM player_times WHERE trial_id = %s", (trial_id,))
            ])
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    results = []
                    
                    for query, params in operations:
                        cursor.execute(query, params)
                        
                        # Check if this is a SELECT query by looking for results
                        try:
                            rows = cursor.fetchall()
                            results.append([dict(row) for row in rows])
                        except psycopg2.ProgrammingError:
                            # No results to fetch (INSERT/UPDATE/DELETE)
                            results.append([])
                    
                    conn.commit()
                    return results
                    
                except psycopg2.Error as e:
                    conn.rollback()
                    logger.error(f"Transaction failed: {e}")
                    raise


# Global database manager instance
db_manager = DatabaseManager()


async def initialize_database() -> None:
    """
    Initialize the database connection and create tables if needed.
    
    This function should be called once when the bot starts up.
    It will create all necessary tables if they don't exist.
    """
    await db_manager.initialize()
    
    # Read and execute the schema file to create tables
    try:
        with open('sql/schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # Execute schema creation (this is idempotent - safe to run multiple times)
        db_manager.execute_query(schema_sql, fetch=False)
        logger.info("✓ Database schema initialized successfully")
        
    except FileNotFoundError:
        logger.warning("Schema file not found - assuming tables already exist")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        raise


async def close_database() -> None:
    """
    Close database connections when the bot shuts down.
    
    This ensures proper cleanup of database resources.
    """
    db_manager.close()