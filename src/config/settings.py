"""
Configuration settings for the Mario Kart World Time Trial Discord Bot.

This module handles environment variables and application configuration.
All sensitive data should be stored in environment variables.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()


class Settings:
    """
    Application settings loaded from environment variables.
    
    Attributes:
        BOT_TOKEN: Discord bot token for authentication
        DATABASE_URL: PostgreSQL connection string
        DEBUG: Enable debug logging and features
    """
    
    # Discord Bot Configuration
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    
    # Database Configuration
    DATABASE_URL: str = os.getenv('DATABASE_URL', '')
    
    # Application Configuration
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Time Trial Configuration
    MAX_CONCURRENT_TRIALS: int = 2  # Maximum number of active trials per guild
    EXPIRED_TRIAL_CLEANUP_DAYS: int = 3  # Days to keep expired trials before deletion
    
    # Time Format Configuration
    MIN_TIME_MS: int = 0  # 0:00.000
    MAX_TIME_MS: int = 599999  # 9:59.999
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate that all required configuration is present.
        
        Raises:
            ValueError: If required environment variables are missing
        """
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN environment variable is required")
        
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is required")
    
    @classmethod
    def get_database_config(cls) -> dict:
        """
        Parse DATABASE_URL into connection parameters.
        
        Returns:
            dict: Database connection parameters for psycopg2
            
        Example:
            postgresql://user:pass@host:port/dbname
            -> {
                'host': 'host',
                'port': port,
                'database': 'dbname', 
                'user': 'user',
                'password': 'pass'
            }
        """
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        # Parse PostgreSQL URL
        # Format: postgresql://user:password@host:port/database
        if cls.DATABASE_URL.startswith('postgresql://'):
            url = cls.DATABASE_URL[13:]  # Remove 'postgresql://'
        elif cls.DATABASE_URL.startswith('postgres://'):
            url = cls.DATABASE_URL[11:]  # Remove 'postgres://'
        else:
            raise ValueError("DATABASE_URL must start with postgresql:// or postgres://")
        
        # Split URL components
        if '@' in url:
            auth, host_db = url.split('@', 1)
            if ':' in auth:
                user, password = auth.split(':', 1)
            else:
                user, password = auth, ''
        else:
            raise ValueError("DATABASE_URL must include user@host format")
        
        if '/' in host_db:
            host_port, database = host_db.split('/', 1)
        else:
            raise ValueError("DATABASE_URL must include database name")
        
        if ':' in host_port:
            host, port_str = host_port.split(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError("DATABASE_URL port must be a number")
        else:
            host, port = host_port, 5432
        
        return {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }


# Global settings instance
settings = Settings()


def validate_environment() -> None:
    """
    Validate environment configuration on startup.
    
    This function should be called when the bot starts to ensure
    all required configuration is present before attempting to connect
    to Discord or the database.
    
    Raises:
        ValueError: If configuration validation fails
    """
    try:
        settings.validate()
        # Test database URL parsing
        settings.get_database_config()
        print("✓ Configuration validation passed")
    except ValueError as e:
        print(f"✗ Configuration validation failed: {e}")
        raise