import os
import json
import sqlite3
import asyncio
import aiohttp
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telethon import TelegramClient, events
from telethon.tl.types import MessageEntityMentionName
import logging

# Configuration
BOT_TOKEN = "8512809899:AAGRwfvkiEMma6GtHvOEKMR0Uy6rYlyZ194"
API_ID = 38128029  # Get from my.telegram.org
API_HASH = "b33c76f4468f79c192472d226d3e59fc"
OTP_GROUP_ID = -1003773115636  # Your OTP group chat ID

# Initialize bot
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('otp_bot.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        joined_date TEXT,
        is_active INTEGER DEFAULT 1,
        total_requests INTEGER DEFAULT 0,
        last_request TEXT
    )''')
    
    # Numbers table
    c.execute('''CREATE TABLE IF NOT EXISTS numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country_code TEXT,
        country_name TEXT,
        flag TEXT,
        number TEXT,
        service TEXT,
        is_available INTEGER DEFAULT 1,
        added_date TEXT,
        last_used TEXT
    )''')
    
    # Services table
    c.execute('''CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_name TEXT UNIQUE,
        is_active INTEGER DEFAULT 1
    )''')
    
    # OTP cache table
    c.execute('''CREATE TABLE IF NOT EXISTS otp_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT,
        otp_code TEXT,
        service TEXT,
        timestamp TEXT,
        is_sent INTEGER DEFAULT 0
    )''')
    
    # Admin table
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        role TEXT DEFAULT 'admin'
    )''')
    
    # Insert sample data
    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0] == 0:
        sample_services = [
            ('WhatsApp', 1),
            ('Telegram', 1),
            ('Facebook', 1),
            ('Instagram', 1),
            ('Google', 1)
        ]
        c.executemany("INSERT INTO services (service_name, is_active) VALUES (?, ?)", sample_services)
    
    c.execute("SELECT COUNT(*) FROM numbers")
    if c.fetchone()[0] == 0:
        sample_numbers = [
            ('+1', 'USA', '🇺🇸', '+1234567890', 'WhatsApp'),
            ('+1', 'USA', '🇺🇸', '+1234567891', 'Telegram'),
            ('+44', 'UK', '🇬🇧', '+44789012345', 'Facebook'),
            ('+91', 'India', '🇮🇳', '+919876543210', 'Instagram'),
            ('+86', 'China', '🇨🇳', '+86123456789', 'Google'),
            ('+55', 'Brazil', '🇧🇷', '+55123456789', 'WhatsApp'),
            ('+49', 'Germany', '🇩🇪', '+49123456789', 'Telegram')
        ]
        c.executemany("INSERT INTO numbers (country_code, country_name, flag, number, service) VALUES (?, ?, ?, ?, ?)", sample_numbers)
    
    # Insert sample admin
    c.execute("SELECT COUNT(*) FROM admins")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO admins (user_id) VALUES (?)", (5853022053,))
    
    conn.commit()
    conn.close()

# Helper functions
def get_db_connection():
    return sqlite3.connect('otp_bot.db')

def is_admin(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def check_requirements(user_id):
    try:
        # Check channel join requirement
        channel_username = "https://t.me/otprether"  # Change this
        try:
            bot.loop.run_until_complete(
                bot.get_permissions(channel_username, user_id)
            )
            channel_ok = True
        except:
            channel_ok = False
        
        # Check group join requirement
        group_username = "https://t.me/+MgMOW9fAR5E1ZTE1"  # Change this
        try:
            bot.loop.run_until_complete(
                bot.get_permissions(group_username, user_id)
            )
            group_ok = True
        except:
            group_ok = False
        
        return channel_ok and group_ok
    except:
        return False

def get_available_numbers(service, country_code, limit=3):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT number, country_code, country_name, flag, service 
        FROM numbers 
        WHERE service = ? AND country_code = ? AND is_available = 1
        LIMIT ?
    """, (service, country_code, limit))
    numbers = c.fetchall()
    conn.close()
    return numbers

def update_user_request(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE users 
        SET total_requests = total_requests + 1,
            last_request = ?
        WHERE user_id = ?
    """, (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# OTP monitoring function
async def monitor_otp():
    while True:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            # Simulate OTP fetching from different sources
            # In production, you would integrate with actual OTP services
            current_time = datetime.now()
            
            # Get numbers that need OTP monitoring
            c.execute("SELECT number, service FROM numbers WHERE is_available = 1")
            numbers = c.fetchall()
            
            for number, service in numbers:
                # Simulate OTP retrieval (replace with actual API calls)
                # This is where you'd call your OTP service API
                otp_code = await fetch_otp_from_service(number, service)
                
                if otp_code:
                    # Store OTP in cache
                    c.execute("""
                        INSERT INTO otp_cache (number, otp_code, service, timestamp)
                        VALUES (?, ?, ?, ?)
                    """, (number, otp_code, service, current_time.isoformat()))
                    
                    # Send to OTP group
                    await bot.send_message(
                        OTP_GROUP_ID,
                        f"🔐 **New OTP Received!**\n\n"
                        f"📱 **Number:** `{number}`\n"
                        f"🛠 **Service:** {service}\n"
                        f"🔑 **OTP Code:** `{otp_code}`\n"
                        f"⏰ **Time:** {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    
                    logger.info(f"OTP {otp_code} sent for {number}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error in OTP monitoring: {e}")
        
        await asyncio.sleep(30)  # Refresh every 30 seconds

async def fetch_otp_from_service(number, service):
    """Simulate OTP fetching - Replace with actual API integration"""
    # This is where you'd implement actual OTP service API calls
    # Example for demonstration:
    import random
    import hashlib
    
    # Simulate OTP generation based on number and service
    # In production, you'd call actual OTP service APIs
    seed = f"{number}{service}{datetime.now().strftime('%Y%m%d%H%M')}"
    otp_hash = hashlib.md5(seed.encode()).hexdigest()
    otp = ''.join([c for c in otp_hash if c.isdigit()][:6])
    
    # 30% chance to return an OTP for demonstration
    if random.random() < 0.3:
        return otp
    return None

# Bot command handlers
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    username = event.sender.username or "No username"
    first_name = event.sender.first_name or "User"
    
    add_user(user_id, username, first_name)
    
    # Check join requirements
    if not check_requirements(user_id):
        keyboard = [[
            {"text": "✅ Join Channel", "url": "https://t.me/otprether"},
            {"text": "✅ Join Group", "url": "https://t.me/+MgMOW9fAR5E1ZTE1"}
        ], [
            {"text": "🔄 Check Status", "callback_data": "check_status"}
        ]]
        
        await event.respond(
            "⚠️ **Requirements Needed!**\n\n"
            "Please join our channel and group to use this bot:\n\n"
            "1️⃣ Join our Telegram Channel\n"
            "2️⃣ Join our Telegram Group\n\n"
            "After joining, click the 'Check Status' button.",
            buttons=keyboard,
            parse_mode='markdown'
        )
        return
    
    # Main menu
    keyboard = [[{"text": "📱 Get Number", "callback_data": "get_number"}]]
    
    await event.respond(
        f"✅ **Welcome {first_name}!**\n\n"
        "📱 **Virtual Number Bot**\n"
        "Get temporary numbers for OTP verification\n\n"
        "🔹 Click 'Get Number' to start\n"
        "🔹 Choose your service\n"
        "🔹 Select country\n"
        "🔹 Get numbers instantly\n\n"
        "**Status:** ✅ Active",
        buttons=keyboard,
        parse_mode='markdown'
    )

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    if data == "check_status":
        if check_requirements(user_id):
            await event.edit(
                "✅ **Verification Successful!**\n\n"
                "You have joined both channel and group.\n"
                "Click /start to access the bot.",
                parse_mode='markdown'
            )
        else:
            await event.answer("Please join both channel and group first!", alert=True)
    
    elif data == "get_number":
        if not check_requirements(user_id):
            await event.answer("Please complete requirements first!", alert=True)
            return
        
        # Show services
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT service_name FROM services WHERE is_active = 1")
        services = c.fetchall()
        conn.close()
        
        keyboard = []
        for service in services:
            keyboard.append([{"text": f"📱 {service[0]}", "callback_data": f"service_{service[0]}"}])
        keyboard.append([{"text": "« Back", "callback_data": "back_to_menu"}])
        
        await event.edit(
            "🎯 **Select Service**\n\n"
            "Choose the service you need OTP for:",
            buttons=keyboard,
            parse_mode='markdown'
        )
    
    elif data.startswith("service_"):
        service = data.replace("service_", "")
        
        # Show available countries
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT country_code, country_name, flag 
            FROM numbers 
            WHERE service = ? AND is_available = 1
        """, (service,))
        countries = c.fetchall()
        conn.close()
        
        if not countries:
            await event.answer(f"No numbers available for {service} yet!", alert=True)
            return
        
        keyboard = []
        for country in countries:
            keyboard.append([{
                "text": f"{country[2]} {country[1]} ({country[0]})",
                "callback_data": f"country_{service}_{country[0]}"
            }])
        keyboard.append([{"text": "« Back", "callback_data": "get_number"}])
        
        await event.edit(
            f"🌍 **Select Country for {service}**\n\n"
            "Choose a country:",
            buttons=keyboard,
            parse_mode='markdown'
        )
    
    elif data.startswith("country_"):
        parts = data.split("_")
        service = parts[1]
        country_code = parts[2]
        
        # Get numbers
        numbers = get_available_numbers(service, country_code)
        
        if not numbers:
            await event.answer("No numbers available! Try again later.", alert=True)
            return
        
        # Store in session
        if not hasattr(event, 'client'):
            event.client.current_numbers = numbers
            event.client.current_service = service
            event.client.current_country = country_code
        
        # Display numbers
        numbers_text = "📞 **Available Numbers:**\n\n"
        buttons = []
        
        for i, num in enumerate(numbers[:3], 1):
            number = num[0]
            flag = num[3]
            numbers_text += f"{i}. {flag} `{number}`\n"
            buttons.append([{"text": f"📋 Copy {number}", "callback_data": f"copy_{number}"}])
        
        buttons.append([
            {"text": "🔄 Refresh", "callback_data": f"refresh_{service}_{country_code}"},
            {"text": "💬 OTP Group", "url": "https://t.me/YOUR_OTP_GROUP"}
        ])
        buttons.append([{"text": "« Back", "callback_data": "get_number"}])
        
        update_user_request(user_id)
        
        await event.edit(
            numbers_text + "\n"
            "💡 **Instructions:**\n"
            "• Click on any number to copy\n"
            "• Use 'Refresh' for new numbers\n"
            "• Join OTP group to receive codes",
            buttons=buttons,
            parse_mode='markdown'
        )
    
    elif data.startswith("copy_"):
        number = data.replace("copy_", "")
        await event.answer(f"✅ Copied: {number}", alert=True)
    
    elif data.startswith("refresh_"):
        parts = data.split("_")
        service = parts[1]
        country_code = parts[2]
        
        # Get new numbers
        numbers = get_available_numbers(service, country_code)
        
        if not numbers:
            await event.answer("No new numbers available!", alert=True)
            return
        
        numbers_text = "🔄 **New Numbers Available:**\n\n"
        buttons = []
        
        for i, num in enumerate(numbers[:3], 1):
            number = num[0]
            flag = num[3]
            numbers_text += f"{i}. {flag} `{number}`\n"
            buttons.append([{"text": f"📋 Copy {number}", "callback_data": f"copy_{number}"}])
        
        buttons.append([
            {"text": "🔄 Refresh", "callback_data": f"refresh_{service}_{country_code}"},
            {"text": "💬 OTP Group", "url": "https://t.me/+MgMOW9fAR5E1ZTE1"}
        ])
        buttons.append([{"text": "« Back", "callback_data": "get_number"}])
        
        await event.edit(
            numbers_text + "\n"
            "💡 **New numbers generated!**",
            buttons=buttons,
            parse_mode='markdown'
        )
    
    elif data == "back_to_menu":
        keyboard = [[{"text": "📱 Get Number", "callback_data": "get_number"}]]
        await event.edit(
            "✅ **Main Menu**\n\n"
            "Click 'Get Number' to start",
            buttons=keyboard,
            parse_mode='markdown'
        )

# Admin commands
@bot.on(events.NewMessage(pattern='/admin'))
async def admin_panel(event):
    if not is_admin(event.sender_id):
        await event.respond("⛔ You are not authorized to use admin commands!")
        return
    
    keyboard = [
        [{"text": "📊 Statistics", "callback_data": "admin_stats"}],
        [{"text": "➕ Add Number", "callback_data": "admin_add_number"}],
        [{"text": "👥 User Management", "callback_data": "admin_users"}],
        [{"text": "🛠 Service Management", "callback_data": "admin_services"}],
        [{"text": "📨 Broadcast", "callback_data": "admin_broadcast"}]
    ]
    
    await event.respond(
        "🔧 **Admin Panel**\n\n"
        "Select an option:",
        buttons=keyboard,
        parse_mode='markdown'
    )

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    if not is_admin(event.sender_id):
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    active_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(total_requests) FROM users")
    total_requests = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM numbers WHERE is_available = 1")
    available_numbers = c.fetchone()[0]
    
    conn.close()
    
    stats_text = f"""
📊 **Bot Statistics**

👥 **Users:** {total_users}
✅ **Active Users:** {active_users}
📱 **Total Requests:** {total_requests}
🔢 **Available Numbers:** {available_numbers}

📈 **System Status:** 🟢 Online
    """
    
    await event.respond(stats_text, parse_mode='markdown')

# Broadcast function
@bot.on(events.NewMessage(pattern='/broadcast (.+)'))
async def broadcast_command(event):
    if not is_admin(event.sender_id):
        return
    
    message = event.pattern_match.group(1)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_active = 1")
    users = c.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await bot.send_message(user[0], f"📢 **Broadcast Message**\n\n{message}", parse_mode='markdown')
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await event.respond(f"✅ Broadcast complete!\n\n📨 Sent: {success}\n❌ Failed: {failed}")

# Start bot
async def main():
    init_db()
    logger.info("Bot started successfully!")
    
    # Start OTP monitoring
    asyncio.create_task(monitor_otp())
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    with bot:
        bot.loop.run_until_complete(main())
