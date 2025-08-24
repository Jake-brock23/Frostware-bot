import discord
from discord.ext import commands
import asyncio
import os
import logging
import json
import time
from flask import Flask, render_template, jsonify
from threading import Thread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration - Set these as environment variables on Render
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ROLE_ID = int(os.getenv('ADMIN_ROLE_ID', '0'))
ESSENTIAL_ROLE_ID = int(os.getenv('ESSENTIAL_ROLE_ID', '0'))
PRIME_ROLE_ID = int(os.getenv('PRIME_ROLE_ID', '0'))

if not BOT_TOKEN:
    logger.error("BOT_TOKEN environment variable is required!")
    exit(1)

# Bot setup - Fixed for discord.py 1.7.3
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='&', intents=intents)

# Permission management
permitted_users = set()
user_timeouts = {}

def parse_duration(duration_str):
    """Parse duration string to seconds"""
    if duration_str.lower() == 'inf' or duration_str.lower() == 'infinite':
        return float('inf')
    
    try:
        if duration_str.endswith('m'):
            return int(duration_str[:-1]) * 60
        elif duration_str.endswith('h'):
            return int(duration_str[:-1]) * 3600
        elif duration_str.endswith('d'):
            return int(duration_str[:-1]) * 86400
        else:
            return int(duration_str) * 60  # Default to minutes
    except ValueError:
        return None

def is_admin(user):
    """Check if user has admin role"""
    return any(role.id == ADMIN_ROLE_ID for role in user.roles)

def has_essential_role(user):
    """Check if user has Essential role"""
    return any(role.id == ESSENTIAL_ROLE_ID for role in user.roles)

def has_prime_role(user):
    """Check if user has Prime role"""
    return any(role.id == PRIME_ROLE_ID for role in user.roles)

def is_permitted(user):
    """Check if user is permitted to use the bot"""
    return (is_admin(user) or 
            has_essential_role(user) or 
            has_prime_role(user) or 
            user.id in permitted_users)

async def unauthorized_message(ctx):
    """Send unauthorized access message"""
    embed = discord.Embed(
        title="🔒 Access Denied", 
        description="You don't have permission to use this command.",
        color=0xe74c3c
    )
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    """Bot startup event"""
    if bot.user:
        logger.info(f"Frostware Utility Bot logged in as {bot.user.name} (ID: {bot.user.id})")
        logger.info(f"Bot is in {len(bot.guilds)} guilds")
        
        # Set bot status
        activity = discord.Activity(type=discord.ActivityType.watching, name="for &help")
        await bot.change_presence(activity=activity)
        
        # Update status for web app
        update_bot_status()

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Arguments",
            description=f"Missing required argument: `{error.param.name}`\nUse `&help {ctx.command.name}` for usage info.",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
    else:
        logger.error(f"Command error: {error}")

@bot.command()
async def dm(ctx, user: discord.Member, *, message):
    """Send a direct message to a user (Admin only)"""
    if not is_admin(ctx.author):
        await unauthorized_message(ctx)
        return
    
    try:
        embed = discord.Embed(
            title="📨 Message from Server Staff",
            description=message,
            color=0x3498db
        )
        embed.set_footer(text=f"Sent from {ctx.guild.name}")
        
        await user.send(embed=embed)
        
        confirmation = discord.Embed(
            title="✅ Message Sent",
            description=f"Direct message sent to {user.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=confirmation)
        
    except discord.Forbidden:
        error_embed = discord.Embed(
            title="❌ Failed to Send",
            description=f"Cannot send DM to {user.mention}. They may have DMs disabled.",
            color=0xe74c3c
        )
        await ctx.send(embed=error_embed)

@bot.command()
async def whitelist(ctx, user: discord.Member, duration: str, plan: str):
    """Whitelist a user with Essential or Prime plan (Admin only)"""
    if not is_admin(ctx.author):
        await unauthorized_message(ctx)
        return
    
    if plan.lower() not in ['essential', 'prime']:
        embed = discord.Embed(
            title="❌ Invalid Plan",
            description="Plan must be either `essential` or `prime`",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
        return
    
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        embed = discord.Embed(
            title="❌ Invalid Duration",
            description="Use format: 5m, 2h, 1d, or inf",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
        return
    
    role_id = ESSENTIAL_ROLE_ID if plan.lower() == 'essential' else PRIME_ROLE_ID
    role = ctx.guild.get_role(role_id)
    
    if not role:
        embed = discord.Embed(
            title="❌ Role Not Found",
            description=f"Could not find {plan.title()} role",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
        return
    
    try:
        await user.add_roles(role)
        
        if duration_seconds != float('inf'):
            user_timeouts[user.id] = asyncio.create_task(
                remove_role_after_timeout(user, role, duration_seconds)
            )
            duration_text = duration
        else:
            duration_text = "permanent"
        
        embed = discord.Embed(
            title="✅ User Whitelisted",
            description=f"{user.mention} has been granted {plan.title()} access for {duration_text}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        
    except discord.Forbidden:
        embed = discord.Embed(
            title="❌ Permission Error",
            description="Bot doesn't have permission to assign roles",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

async def remove_role_after_timeout(user, role, duration):
    """Remove role after specified duration"""
    await asyncio.sleep(duration)
    try:
        await user.remove_roles(role)
        logger.info(f"Removed {role.name} from {user.name} after timeout")
    except discord.NotFound:
        logger.warning(f"User {user.name} not found when trying to remove role")
    except Exception as e:
        logger.error(f"Error removing role from {user.name}: {e}")
    finally:
        if user.id in user_timeouts:
            del user_timeouts[user.id]

@bot.command()
async def permit(ctx, user: discord.Member, duration: str):
    """Grant permission to use the bot (Admin only)"""
    if not is_admin(ctx.author):
        await unauthorized_message(ctx)
        return
    
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        embed = discord.Embed(
            title="❌ Invalid Duration",
            description="Use format: 5m, 2h, 1d, or inf",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
        return
    
    permitted_users.add(user.id)
    
    if duration_seconds != float('inf'):
        user_timeouts[user.id] = asyncio.create_task(
            remove_permit_after_timeout(user.id, duration_seconds)
        )
        duration_text = duration
    else:
        duration_text = "permanent"
    
    embed = discord.Embed(
        title="✅ Permission Granted",
        description=f"{user.mention} can now use bot commands for {duration_text}",
        color=0x2ecc71
    )
    await ctx.send(embed=embed)

async def remove_permit_after_timeout(user_id, duration):
    """Remove permit after specified duration"""
    await asyncio.sleep(duration)
    try:
        permitted_users.discard(user_id)
        logger.info(f"Removed permit for user {user_id} after timeout")
    finally:
        if user_id in user_timeouts:
            del user_timeouts[user_id]

@bot.command()
async def unpermit(ctx, user: discord.Member):
    """Revoke permission to use the bot (Admin only)"""
    if not is_admin(ctx.author):
        await unauthorized_message(ctx)
        return
    
    if user.id in permitted_users:
        permitted_users.discard(user.id)
        
        # Cancel timeout if exists
        if user.id in user_timeouts:
            user_timeouts[user.id].cancel()
            del user_timeouts[user.id]
        
        embed = discord.Embed(
            title="✅ Permission Revoked",
            description=f"Removed bot access for {user.mention}",
            color=0x2ecc71
        )
    else:
        embed = discord.Embed(
            title="❌ Not Permitted",
            description=f"{user.mention} was not in the permitted users list",
            color=0xe74c3c
        )
    
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx, command_name=None):
    """Display help information"""
    if command_name:
        # Show help for specific command
        command = bot.get_command(command_name)
        if command:
            embed = discord.Embed(
                title=f"Help: {command.name}",
                description=command.help or "No description available",
                color=0x3498db
            )
            embed.add_field(name="Usage", value=f"&{command.name} {command.signature}", inline=False)
        else:
            embed = discord.Embed(
                title="❌ Command Not Found",
                description=f"No command named '{command_name}' found",
                color=0xe74c3c
            )
    else:
        # Show general help
        embed = discord.Embed(
            title="🤖 Frostware Utility Bot",
            description="Advanced Discord utility bot with role-based permissions",
            color=0x3498db
        )
        
        admin_commands = [
            "`&dm <user> <message>` - Send direct message to user",
            "`&whitelist <user> <duration> <plan>` - Grant Essential/Prime access",
            "`&permit <user> <duration>` - Grant bot usage permission",
            "`&unpermit <user>` - Revoke bot usage permission"
        ]
        
        general_commands = [
            "`&ping` - Check bot latency",
            "`&help [command]` - Show this help message"
        ]
        
        embed.add_field(
            name="👑 Admin Commands",
            value="\n".join(admin_commands),
            inline=False
        )
        
        embed.add_field(
            name="🔧 General Commands", 
            value="\n".join(general_commands),
            inline=False
        )
        
        embed.add_field(
            name="⏰ Duration Format",
            value="`5m` (5 minutes), `2h` (2 hours), `1d` (1 day), `inf` (infinite)",
            inline=False
        )
    
    embed.set_footer(text="Duration examples: 5m (5 minutes), 2h (2 hours), 1d (1 day), inf (infinite)")
    
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    """Check bot latency"""
    if not is_permitted(ctx.author):
        await unauthorized_message(ctx)
        return
    
    embed = discord.Embed(
        title="🏓 Pong!",
        color=0x3498db
    )
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    await ctx.send(embed=embed)

def update_bot_status():
    """Update bot status in shared data"""
    try:
        status_data = {
            'online': bot.is_ready() if bot else False,
            'guilds': len(bot.guilds) if bot and bot.is_ready() else 1,
            'permitted_users': len(permitted_users),
            'latency': round(bot.latency * 1000) if bot and bot.is_ready() else 0
        }
        with open('bot_status.json', 'w') as f:
            json.dump(status_data, f)
    except Exception as e:
        logger.error(f"Error updating bot status: {e}")

def status_updater():
    """Background thread to update bot status periodically"""
    while True:
        time.sleep(30)  # Update every 30 seconds
        update_bot_status()

# Flask Web App
app = Flask(__name__)

def get_bot_status():
    """Get bot status from shared data file"""
    try:
        if os.path.exists('bot_status.json'):
            with open('bot_status.json', 'r') as f:
                return json.load(f)
    except:
        pass
    
    # Default status if file doesn't exist or can't be read
    return {
        'online': False,
        'guilds': 0,
        'permitted_users': 0,
        'latency': 0
    }

@app.route('/')
def home():
    """Main website page"""
    bot_status = get_bot_status()
    return render_template('index.html', bot_status=bot_status)

@app.route('/api/status')
def api_status():
    """API endpoint for real-time status updates"""
    return jsonify(get_bot_status())

@app.route('/health')
def health():
    """Health check endpoint for uptime monitoring"""
    bot_status = get_bot_status()
    return jsonify({
        "status": "alive" if bot_status['online'] else "offline", 
        "service": "frostware-utility-bot"
    })

def run_web_server():
    """Run the Flask web server"""
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

def start_web_app():
    """Start the web app in a separate thread"""
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("✅ Web server started")

if __name__ == "__main__":
    # Start web server
    start_web_app()
    
    # Start periodic status updates in background thread
    status_thread = Thread(target=status_updater, daemon=True)
    status_thread.start()
    
    # Run the Discord bot
    logger.info("Starting Frostware Utility Bot...")
    bot.run(BOT_TOKEN)iption=f"No command named '{command_name}' found",
                color=0xe74c3c
            )
    else:
        # Show general help
        embed = discord.Embed(
            title="🤖 Frostware Utility Bot",
            description="Advanced Discord utility bot with role-based permissions",
            color=0x3498db
        )
        
        admin_commands = [
            "`&dm <user> <message>` - Send direct message to user",
            "`&whitelist <user> <duration> <plan>` - Grant Essential/Prime access",
            "`&permit <user> <duration>` - Grant bot usage permission",
            "`&unpermit <user>` - Revoke bot usage permission"
        ]
        
        general_commands = [
            "`&ping` - Check bot latency",
            "`&help [command]` - Show this help message"
        ]
        
        embed.add_field(
            name="👑 Admin Commands",
            value="\n".join(admin_commands),
            inline=False
        )
        
        embed.add_field(
            name="🔧 General Commands", 
            value="\n".join(general_commands),
            inline=False
        )
        
        embed.add_field(
            name="⏰ Duration Format",
            value="`5m` (5 minutes), `2h` (2 hours), `1d` (1 day), `inf` (infinite)",
            inline=False
        )
    
    embed.set_footer(text="Duration examples: 5m (5 minutes), 2h (2 hours), 1d (1 day), inf (infinite)")
    
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    """Check bot latency"""
    if not is_permitted(ctx.author):
        await unauthorized_message(ctx)
        return
    
    embed = discord.Embed(
        title="🏓 Pong!",
        color=0x3498db
    )
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    await ctx.send(embed=embed)

def update_bot_status():
    """Update bot status in shared data"""
    try:
        status_data = {
            'online': bot.is_ready() if bot else False,
            'guilds': len(bot.guilds) if bot and bot.is_ready() else 1,
            'permitted_users': len(permitted_users),
            'latency': round(bot.latency * 1000) if bot and bot.is_ready() else 0
        }
        with open('bot_status.json', 'w') as f:
            json.dump(status_data, f)
    except Exception as e:
        logger.error(f"Error updating bot status: {e}")

def status_updater():
    """Background thread to update bot status periodically"""
    while True:
        time.sleep(30)  # Update every 30 seconds
        update_bot_status()

# Flask Web App
app = Flask(__name__)

def get_bot_status():
    """Get bot status from shared data file"""
    try:
        if os.path.exists('bot_status.json'):
            with open('bot_status.json', 'r') as f:
                return json.load(f)
    except:
        pass
    
    # Default status if file doesn't exist or can't be read
    return {
        'online': False,
        'guilds': 0,
        'permitted_users': 0,
        'latency': 0
    }

@app.route('/')
def home():
    """Main website page"""
    bot_status = get_bot_status()
    return render_template('index.html', bot_status=bot_status)

@app.route('/api/status')
def api_status():
    """API endpoint for real-time status updates"""
    return jsonify(get_bot_status())

@app.route('/health')
def health():
    """Health check endpoint for uptime monitoring"""
    bot_status = get_bot_status()
    return jsonify({
        "status": "alive" if bot_status['online'] else "offline", 
        "service": "frostware-utility-bot"
    })

def run_web_server():
    """Run the Flask web server"""
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

def start_web_app():
    """Start the web app in a separate thread"""
    web_thread = Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("✅ Web server started")

if __name__ == "__main__":
    # Start web server
    start_web_app()
    
    # Start periodic status updates in background thread
    status_thread = Thread(target=status_updater, daemon=True)
    status_thread.start()
    
    # Run the Discord bot
    logger.info("Starting Frostware Utility Bot...")
    bot.run(BOT_TOKEN)
