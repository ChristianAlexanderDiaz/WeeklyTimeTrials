# Mario Kart World Time Trial Discord Bot 🏁

A Discord bot for managing weekly time trial challenges for all 30 Mario Kart World tracks. Features automatic leaderboards, medal achievements, and comprehensive time tracking.

## Features ✨

- **30 Mario Kart World Tracks**: Complete track database with autocomplete
- **Weekly Time Trials**: Create challenges with gold/silver/bronze goal times
- **Automatic Leaderboards**: Real-time rankings with medal indicators
- **Time Improvement Tracking**: Only accepts faster times, shows improvement
- **Multiple Concurrent Trials**: Support for 1-2 simultaneous challenges
- **Smart Autocomplete**: Context-aware track suggestions for each command
- **Automatic Expiration**: Trials automatically expire after set duration
- **Production Ready**: Comprehensive error handling and logging

## Commands 🎮

### User Commands

- `/save <track> <time>` - Submit your time for an active trial
  - Example: `/save track:Rainbow Road time:2:23.640`
  - Only shows tracks with active trials in autocomplete
  - Rejects slower times than your current best

- `/leaderboard <track>` - View the leaderboard for any trial
  - Example: `/leaderboard track:Mario Circuit`
  - Shows all participants with rankings and medals
  - Works for active, expired, and ended trials

- `/remove-time <track>` - Remove your time from an active trial
  - Example: `/remove-time track:Rainbow Road`
  - Only shows tracks where you have submitted times
  - Only works for active trials

- `/active` - View all currently active time trials
  - Shows overview of all ongoing challenges
  - Displays participant counts and fastest times

### Admin Commands

- `/set-challenge <track> <gold> <silver> <bronze> <duration>` - Create a new trial
  - Example: `/set-challenge track:Rainbow Road gold_time:2:20.000 silver_time:2:25.000 bronze_time:2:30.000 duration_days:7`
  - Maximum 2 concurrent trials per server
  - Gold time must be ≤ silver time ≤ bronze time

- `/end-challenge <track>` - Manually end an active trial
  - Example: `/end-challenge track:Rainbow Road`
  - Shows final statistics and participant count
  - Trial becomes read-only

## Time Format ⏱️

- **Input Format**: MM:SS.mmm (e.g., "2:23.640")
- **Range**: 0:00.000 to 9:59.999
- **Precision**: Millisecond accuracy for precise rankings
- **Leading Zeros**: Optional for minutes (both "2:23.640" and "02:23.640" work)

## Setup & Installation 🚀

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Discord Bot Token

### Environment Variables

Create a `.env` file with:

```env
BOT_TOKEN=your_discord_bot_token_here
DATABASE_URL=postgresql://username:password@host:port/database_name
DEBUG=false
```

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd WeeklyTimeTrials
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the bot**
   ```bash
   python -m src.bot
   ```

### Railway Deployment

This bot is optimized for Railway deployment:

1. **Connect your GitHub repository to Railway**

2. **Add environment variables in Railway dashboard:**
   - `BOT_TOKEN`: Your Discord bot token
   - `DATABASE_URL`: Will be auto-provided by Railway PostgreSQL

3. **Deploy:**
   - Railway will automatically detect the Python project
   - Uses `Procfile` for startup command
   - Provisions PostgreSQL database automatically

### Discord Bot Setup

1. **Create Discord Application**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create new application and bot
   - Copy bot token for environment variables

2. **Set Bot Permissions**
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`

3. **Invite Bot to Server**
   - Use the generated invite URL
   - Ensure bot has necessary permissions in your server

## Database Schema 🗄️

### Tables

**weekly_trials**
- Stores trial information, goal times, and status
- Sequential trial numbering for "Weekly Time Trial #N" format
- Automatic expiration based on end_date

**player_times**
- Stores user time submissions with millisecond precision
- Foreign key relationship to trials
- Unique constraint prevents duplicate submissions per user/trial

**Indexes**
- Optimized for leaderboard queries and user lookups
- Composite indexes for common query patterns

### Data Flow

1. Admin creates trial → `weekly_trials` record
2. Users submit times → `player_times` records  
3. Leaderboards generated → JOIN queries with rankings
4. Trials expire → Background task updates status
5. Cleanup → Old expired trials auto-deleted

## Architecture 🏗️

### Technology Stack

- **Language**: Python 3.11+
- **Discord Library**: discord.py
- **Database**: PostgreSQL with raw SQL queries
- **Deployment**: Railway platform
- **Environment**: Docker-compatible with Nixpacks

### Design Patterns

- **Command Pattern**: Base command class with common functionality
- **Factory Pattern**: Command setup functions for modularity
- **Observer Pattern**: Event handlers for bot lifecycle
- **Repository Pattern**: Database operations abstracted in base class

### Code Organization

```
src/
├── commands/          # Slash command implementations
├── database/          # Database connection and schema
├── utils/            # Shared utilities (time parsing, validation)
├── config/           # Environment and settings management
├── events/           # Bot event handlers
└── bot.py           # Main application entry point
```

## Development 🛠️

### Key Design Decisions

- **Raw SQL over ORM**: Direct SQL experience for learning
- **No admin restrictions**: Anyone can create trials (configurable)
- **Dynamic username resolution**: Don't store usernames, resolve from Discord
- **Millisecond precision**: Accurate time comparison and ranking
- **Smart autocomplete**: Context-aware suggestions for better UX

### Testing

Manual testing checklist:

- [ ] All commands register and respond
- [ ] Autocomplete works for all parameters
- [ ] Error messages are user-friendly
- [ ] Database operations handle edge cases
- [ ] Background tasks run correctly
- [ ] Deployment works on Railway

### Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with comprehensive testing
4. Update documentation if needed
5. Submit pull request

## Usage Examples 📝

### Creating a Weekly Challenge

```
/set-challenge track:Rainbow Road gold_time:2:20.000 silver_time:2:25.000 bronze_time:2:30.000 duration_days:7
```

### Submitting Times

```
/save track:Rainbow Road time:2:23.640
/save track:Mario Circuit time:1:45.123
```

### Viewing Results

```
/leaderboard track:Rainbow Road
/active
```

### Managing Trials

```
/end-challenge track:Rainbow Road
/remove-time track:Mario Circuit
```

## Track List 🏎️

All 30 Mario Kart World tracks are supported:

- Mario Bros. Circuit
- Crown City
- Whistlestop Summit
- DK Spaceport
- Desert Hills
- Shy Guy Bazaar
- Wario Stadium
- Airship Fortress
- DK Pass
- Starview Peak
- Sky-High Sundae
- Wario Shipyard
- Koopa Troopa Beach
- Faraway Oasis
- Peach Stadium
- Peach Beach
- Salty Salty Speedway
- Dino Dino Jungle
- Great ? Block Ruins
- Cheep Cheep Falls
- Dandelion Depths
- Boo Cinema
- Dry Bones Burnout
- Moo Moo Meadows
- Choco Mountain
- Toad's Factory
- Bowser's Castle
- Acorn Heights
- Mario Circuit
- Rainbow Road

## Troubleshooting 🔧

### Common Issues

**Bot not responding to commands**
- Verify bot token is correct
- Ensure bot has proper permissions in server
- Check bot is online in Discord

**Database connection errors**
- Verify DATABASE_URL format is correct
- Ensure PostgreSQL database is accessible
- Check Railway database service status

**Commands not appearing**
- Allow up to 1 hour for Discord to sync commands globally
- Try kicking and re-inviting the bot
- Check bot permissions include `applications.commands`

**Time format errors**
- Use MM:SS.mmm format (e.g., "2:23.640")
- Ensure time is within 0:00.000 to 9:59.999 range
- Check for typos in time input

### Logs

Bot logs are written to both console and `mkw_bot.log` file:
- INFO level for normal operations
- ERROR level for issues requiring attention
- DEBUG level when DEBUG=true in environment

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.

## Support 💬

For support or questions:
- Check the troubleshooting section above
- Review logs for error details
- Create an issue in the GitHub repository
- Ensure your environment meets the requirements

---

**Happy racing! 🏁**