#!/usr/bin/env python3
"""
Test script for the Mario Kart World Time Trial Bot.

This script performs basic validation of the bot components without
requiring a Discord connection. It tests imports, basic functionality,
and catches obvious configuration issues.
"""

import sys
import os
import asyncio
from typing import List, Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports() -> List[str]:
    """Test that all modules can be imported successfully."""
    errors = []
    
    try:
        from src.config.settings import settings, validate_environment
        print("✓ Config module imported successfully")
    except Exception as e:
        errors.append(f"Config import failed: {e}")
    
    try:
        from src.utils.time_parser import TimeParser, TimeFormatError
        print("✓ Time parser module imported successfully")
    except Exception as e:
        errors.append(f"Time parser import failed: {e}")
    
    try:
        from src.utils.track_data import TrackManager, get_all_tracks
        print("✓ Track data module imported successfully")
    except Exception as e:
        errors.append(f"Track data import failed: {e}")
    
    try:
        from src.utils.validators import InputValidator, ValidationError
        print("✓ Validators module imported successfully")
    except Exception as e:
        errors.append(f"Validators import failed: {e}")
    
    try:
        from src.utils.formatters import EmbedFormatter
        print("✓ Formatters module imported successfully")
    except Exception as e:
        errors.append(f"Formatters import failed: {e}")
    
    try:
        from src.commands.base import BaseCommand
        print("✓ Base command module imported successfully")
    except Exception as e:
        errors.append(f"Base command import failed: {e}")
    
    try:
        from src.database.connection import DatabaseManager
        print("✓ Database connection module imported successfully")
    except Exception as e:
        errors.append(f"Database connection import failed: {e}")
    
    return errors

def test_time_parser() -> List[str]:
    """Test time parsing functionality."""
    errors = []
    
    try:
        from src.utils.time_parser import TimeParser, TimeFormatError
        
        # Test valid time parsing
        test_cases = [
            ("2:23.640", 143640),
            ("0:45.123", 45123),
            ("9:59.999", 599999),
            ("1:00.000", 60000)
        ]
        
        for time_str, expected_ms in test_cases:
            try:
                result = TimeParser.parse_time(time_str)
                if result != expected_ms:
                    errors.append(f"Time parsing error: {time_str} -> {result}, expected {expected_ms}")
                else:
                    print(f"✓ Time parsing: {time_str} -> {result}ms")
            except Exception as e:
                errors.append(f"Time parsing failed for {time_str}: {e}")
        
        # Test time formatting
        for time_str, ms_value in test_cases:
            try:
                formatted = TimeParser.format_time(ms_value)
                if formatted != time_str:
                    errors.append(f"Time formatting error: {ms_value} -> {formatted}, expected {time_str}")
                else:
                    print(f"✓ Time formatting: {ms_value}ms -> {formatted}")
            except Exception as e:
                errors.append(f"Time formatting failed for {ms_value}: {e}")
        
        # Test invalid time parsing
        invalid_cases = ["invalid", "10:00.000", "2:60.000", "-1:00.000", "2:23"]
        for invalid_time in invalid_cases:
            try:
                TimeParser.parse_time(invalid_time)
                errors.append(f"Should have failed parsing: {invalid_time}")
            except TimeFormatError:
                print(f"✓ Correctly rejected invalid time: {invalid_time}")
            except Exception as e:
                errors.append(f"Unexpected error for {invalid_time}: {e}")
                
    except Exception as e:
        errors.append(f"Time parser test setup failed: {e}")
    
    return errors

def test_track_data() -> List[str]:
    """Test track data functionality."""
    errors = []
    
    try:
        from src.utils.track_data import TrackManager, get_all_tracks
        
        # Test track list
        tracks = get_all_tracks()
        if len(tracks) != 30:
            errors.append(f"Expected 30 tracks, got {len(tracks)}")
        else:
            print(f"✓ Track list contains {len(tracks)} tracks")
        
        # Test specific tracks exist
        required_tracks = ["Rainbow Road", "Mario Circuit", "Bowser's Castle"]
        for track in required_tracks:
            if track not in tracks:
                errors.append(f"Missing required track: {track}")
            else:
                print(f"✓ Found required track: {track}")
        
        # Test track validation
        if not TrackManager.is_valid_track("Rainbow Road"):
            errors.append("Rainbow Road should be valid")
        else:
            print("✓ Track validation working")
        
        if TrackManager.is_valid_track("Invalid Track"):
            errors.append("Invalid Track should not be valid")
        else:
            print("✓ Invalid track correctly rejected")
        
        # Test track search
        mario_tracks = TrackManager.search_tracks("mario")
        if len(mario_tracks) == 0:
            errors.append("Should find tracks containing 'mario'")
        else:
            print(f"✓ Found {len(mario_tracks)} tracks containing 'mario'")
            
    except Exception as e:
        errors.append(f"Track data test failed: {e}")
    
    return errors

def test_validators() -> List[str]:
    """Test validation functionality."""
    errors = []
    
    try:
        from src.utils.validators import InputValidator, ValidationError
        from src.utils.track_data import get_all_tracks
        
        # Test time validation
        try:
            result = InputValidator.validate_time_input("2:23.640")
            if result != 143640:
                errors.append(f"Time validation error: expected 143640, got {result}")
            else:
                print("✓ Time validation working")
        except Exception as e:
            errors.append(f"Time validation failed: {e}")
        
        # Test invalid time validation
        try:
            InputValidator.validate_time_input("invalid")
            errors.append("Should have failed on invalid time")
        except ValidationError:
            print("✓ Invalid time correctly rejected")
        except Exception as e:
            errors.append(f"Unexpected error for invalid time: {e}")
        
        # Test track validation
        tracks = get_all_tracks()
        try:
            result = InputValidator.validate_track_name("Rainbow Road", tracks)
            if result != "Rainbow Road":
                errors.append(f"Track validation error: expected 'Rainbow Road', got '{result}'")
            else:
                print("✓ Track validation working")
        except Exception as e:
            errors.append(f"Track validation failed: {e}")
        
        # Test invalid track validation
        try:
            InputValidator.validate_track_name("Invalid Track", tracks)
            errors.append("Should have failed on invalid track")
        except ValidationError:
            print("✓ Invalid track correctly rejected")
        except Exception as e:
            errors.append(f"Unexpected error for invalid track: {e}")
            
    except Exception as e:
        errors.append(f"Validators test failed: {e}")
    
    return errors

def test_database_schema() -> List[str]:
    """Test that database schema file is valid."""
    errors = []
    
    try:
        schema_path = "sql/schema.sql"
        if not os.path.exists(schema_path):
            errors.append(f"Schema file not found: {schema_path}")
        else:
            with open(schema_path, 'r') as f:
                schema_content = f.read()
            
            # Check for required tables
            required_tables = ["weekly_trials", "player_times", "bot_managers"]
            for table in required_tables:
                if f"CREATE TABLE {table}" not in schema_content:
                    errors.append(f"Missing table definition: {table}")
                else:
                    print(f"✓ Found table definition: {table}")
            
            # Check for indexes
            if "CREATE INDEX" not in schema_content:
                errors.append("No indexes found in schema")
            else:
                print("✓ Found index definitions")
                
    except Exception as e:
        errors.append(f"Schema validation failed: {e}")
    
    return errors

def test_configuration() -> List[str]:
    """Test configuration validation."""
    errors = []
    
    try:
        from src.config.settings import settings
        
        # Test that required settings are defined
        required_settings = ['BOT_TOKEN', 'DATABASE_URL', 'MAX_CONCURRENT_TRIALS']
        for setting in required_settings:
            if not hasattr(settings, setting):
                errors.append(f"Missing setting: {setting}")
            else:
                print(f"✓ Found setting: {setting}")
        
        # Test time constraints
        if settings.MIN_TIME_MS != 0:
            errors.append(f"MIN_TIME_MS should be 0, got {settings.MIN_TIME_MS}")
        else:
            print("✓ MIN_TIME_MS correct")
        
        if settings.MAX_TIME_MS != 599999:  # 9:59.999
            errors.append(f"MAX_TIME_MS should be 599999, got {settings.MAX_TIME_MS}")
        else:
            print("✓ MAX_TIME_MS correct")
            
    except Exception as e:
        errors.append(f"Configuration test failed: {e}")
    
    return errors

async def run_tests() -> None:
    """Run all tests and report results."""
    print("🏁 Mario Kart World Time Trial Bot - Test Suite")
    print("=" * 50)
    
    all_errors = []
    
    print("\n📦 Testing Imports...")
    all_errors.extend(test_imports())
    
    print("\n⏱️ Testing Time Parser...")
    all_errors.extend(test_time_parser())
    
    print("\n🏎️ Testing Track Data...")
    all_errors.extend(test_track_data())
    
    print("\n✅ Testing Validators...")
    all_errors.extend(test_validators())
    
    print("\n🗄️ Testing Database Schema...")
    all_errors.extend(test_database_schema())
    
    print("\n⚙️ Testing Configuration...")
    all_errors.extend(test_configuration())
    
    print("\n" + "=" * 50)
    if all_errors:
        print("❌ Tests Failed!")
        print(f"Found {len(all_errors)} error(s):")
        for i, error in enumerate(all_errors, 1):
            print(f"  {i}. {error}")
        sys.exit(1)
    else:
        print("✅ All tests passed!")
        print("Bot components are ready for deployment.")

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        sys.exit(1)