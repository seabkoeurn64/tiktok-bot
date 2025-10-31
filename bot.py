import os
import requests
import telebot
import time
import json
import re
from flask import Flask, request
from waitress import serve
from collections import defaultdict

# -----------------------------
# Flask App
# -----------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 TikTok Bot is Running - Production Version!"

@app.route('/health')
def health():
    stats = {
        'status': 'healthy',
        'total_downloads': BOT_STATS['total_downloads'],
        'total_users': len(BOT_STATS['total_users']),
        'uptime_seconds': time.time() - BOT_STATS['start_time']
    }
    return json.dumps(stats)

# -----------------------------
# Bot Config
# -----------------------------
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8368595880:AAGLfrmsJ1tHub8lrLnBZovU3HoD5Rk4SDw')
bot = telebot.TeleBot(BOT_TOKEN)

# Your Render URL
WEBHOOK_URL_BASE = "https://tiktok-bot-781w.onrender.com"
WEBHOOK_URL_PATH = "/webhook/"

# -----------------------------
# Stats & Rate Limiting
# -----------------------------
BOT_STATS = {
    'total_downloads': 0,
    'total_users': set(),
    'start_time': time.time()
}

USER_COOLDOWN = defaultdict(float)
COOLDOWN_TIME = 30  # seconds

def save_stats():
    try:
        stats_to_save = BOT_STATS.copy()
        stats_to_save['total_users'] = list(stats_to_save['total_users'])
        with open('bot_stats.json', 'w') as f:
            json.dump(stats_to_save, f)
    except Exception as e:
        print(f"Error saving stats: {e}")

def load_stats():
    global BOT_STATS
    try:
        with open('bot_stats.json', 'r') as f:
            loaded_stats = json.load(f)
            loaded_stats['total_users'] = set(loaded_stats['total_users'])
            BOT_STATS.update(loaded_stats)
    except FileNotFoundError:
        print("No existing stats file found, starting fresh")
    except Exception as e:
        print(f"Error loading stats: {e}")

# -----------------------------
# URL Validation
# -----------------------------
def is_valid_tiktok_url(url):
    tiktok_patterns = [
        r'https?://(www\.)?tiktok\.com/.*/video/\d+',
        r'https?://vm\.tiktok\.com/\w+',
        r'https?://vt\.tiktok\.com/\w+',
        r'https?://(www\.)?tiktok\.com/t/\w+',
        r'https?://(www\.)?tiktok\.com/@[^/]+/video/\d+'
    ]
    
    return any(re.match(pattern, url) for pattern in tiktok_patterns)

# -----------------------------
# TikTok Downloader
# -----------------------------
def enhanced_tiktok_download(url):
    apis = [
        f"https://www.tikwm.com/api/?url={url}",
        f"https://api.tikmate.app/api/lookup?url={url}",
        f"https://api16-normal-c-useast1a.tiktokv.com/aweme/v1/feed/?aweme_id={url}",
    ]
    
    for api_url in apis:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(api_url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Check different response formats
            if data.get('data', {}).get('play'):
                return data['data']['play']
            elif data.get('url'):
                return data['url']
            elif data.get('success') and data.get('video_url'):
                return data['video_url']
            elif data.get('aweme_list') and len(data['aweme_list']) > 0:
                video_url = data['aweme_list'][0].get('video', {}).get('play_addr', {}).get('url_list', [None])[0]
                if video_url:
                    return video_url
                    
        except requests.exceptions.RequestException as e:
            print(f"API {api_url} failed: {e}")
            continue
        except json.JSONDecodeError:
            print(f"Invalid JSON from {api_url}")
            continue
        except Exception as e:
            print(f"Unexpected error with {api_url}: {e}")
            continue
            
    return None

def download_video(video_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.tiktok.com/'
        }
        response = requests.get(video_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # Check file size (Telegram limit is 50MB)
        content_length = int(response.headers.get('content-length', 0))
        if content_length > 45 * 1024 * 1024:  # 45MB with some buffer
            return None, "File too large (max 45MB)"
            
        video_data = b''
        for chunk in response.iter_content(chunk_size=8192):
            video_data += chunk
            if len(video_data) > 47 * 1024 * 1024:  # Stop if approaching limit
                return None, "File too large"
                
        return video_data, None
        
    except requests.exceptions.RequestException as e:
        return None, f"Download failed: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

# -----------------------------
# Bot Handlers
# -----------------------------
@bot.message_handler(commands=['start', 'help'])
def start(message):
    BOT_STATS['total_users'].add(message.from_user.id)
    save_stats()
    help_text = """
🤖 TikTok Download Bot

📥 Use this bot:
1. Open TikTok
2. Copy video link
3. Send it to this bot

🔗 Supported URLs:
• https://www.tiktok.com/@user/video/123
• https://vm.tiktok.com/ABC123/
• https://vt.tiktok.com/XYZ456/

⚡ Commands:
/start - Show this help
/stats - Show bot statistics

📞 Owner: @koeurn65
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['stats'])
def show_stats(message):
    uptime_seconds = time.time() - BOT_STATS['start_time']
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    stats_text = f"""
📊 Bot Statistics

👥 Total Users: {len(BOT_STATS['total_users'])}
📥 Total Downloads: {BOT_STATS['total_downloads']}
⏱️ Uptime: {uptime_str}

⚡ Status: Running Smoothly
📞 Owner: @koeurn65
"""
    bot.reply_to(message, stats_text)

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    # Rate limiting check
    user_id = message.from_user.id
    current_time = time.time()
    
    if current_time - USER_COOLDOWN.get(user_id, 0) < COOLDOWN_TIME:
        remaining = int(COOLDOWN_TIME - (current_time - USER_COOLDOWN[user_id]))
        bot.reply_to(message, f"⏳ Please wait {remaining} seconds before your next download.")
        return
        
    USER_COOLDOWN[user_id] = current_time
    
    url = message.text.strip()
    
    # Validate TikTok URL
    if not is_valid_tiktok_url(url):
        bot.reply_to(message, """❌ Please send a valid TikTok URL!

🔗 Examples:
• https://www.tiktok.com/@user/video/123
• https://vm.tiktok.com/ABC123/
• https://vt.tiktok.com/XYZ456/

Make sure the link contains 'tiktok.com' and is a video link.""")
        return

    # Add user to stats
    BOT_STATS['total_users'].add(message.from_user.id)
    
    # Send processing message
    bot.send_chat_action(message.chat.id, 'typing')
    processing_msg = bot.reply_to(message, "🔄 Processing your TikTok video...")

    try:
        # Step 1: Get video URL
        bot.edit_message_text("🔍 Finding video source...", message.chat.id, processing_msg.message_id)
        video_url = enhanced_tiktok_download(url)
        
        if not video_url:
            bot.edit_message_text("❌ Could not download this video. The video might be private, removed, or the link is invalid.", message.chat.id, processing_msg.message_id)
            return

        # Step 2: Download video
        bot.edit_message_text("📥 Downloading video...", message.chat.id, processing_msg.message_id)
        video_data, error = download_video(video_url)
        
        if error:
            bot.edit_message_text(f"❌ {error}", message.chat.id, processing_msg.message_id)
            return

        # Step 3: Upload to Telegram
        bot.edit_message_text("📤 Uploading to Telegram...", message.chat.id, processing_msg.message_id)
        bot.send_chat_action(message.chat.id, 'upload_video')
        
        # Send video with caption
        bot.send_video(
            message.chat.id,
            video_data,
            caption="✅ Downloaded via @TikTokDownloaderBot\n📞 Owner: @koeurn65",
            timeout=60,
            supports_streaming=True
        )

        # Update stats
        BOT_STATS['total_downloads'] += 1
        save_stats()
        
        # Success message
        bot.edit_message_text("✅ Download completed! Enjoy your video! 🎬", message.chat.id, processing_msg.message_id)

    except Exception as e:
        error_msg = f"❌ An error occurred while processing your video:\n\n{str(e)}"
        try:
            bot.edit_message_text(error_msg, message.chat.id, processing_msg.message_id)
        except:
            bot.reply_to(message, error_msg)
        print(f"Error processing video: {e}")

# -----------------------------
# Webhook Setup
# -----------------------------
@app.route(WEBHOOK_URL_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Invalid content type', 400

def setup_webhook():
    """Set up webhook on application startup"""
    try:
        # Remove any existing webhook first
        bot.remove_webhook()
        time.sleep(2)
        
        # Set new webhook
        webhook_url = WEBHOOK_URL_BASE + WEBHOOK_URL_PATH
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set successfully: {webhook_url}")
        
        # Verify webhook info
        webhook_info = bot.get_webhook_info()
        print(f"📊 Webhook Info:")
        print(f"   URL: {webhook_info.url}")
        print(f"   Has Custom Certificate: {webhook_info.has_custom_certificate}")
        print(f"   Pending Update Count: {webhook_info.pending_update_count}")
        
    except Exception as e:
        print(f"❌ Webhook setup failed: {e}")

# -----------------------------
# Application Startup
# -----------------------------
if __name__ == "__main__":
    # Load previous stats
    load_stats()
    
    # Setup webhook
    setup_webhook()
    
    print("🤖 TikTok Bot Started Successfully!")
    print("🚀 Running in Webhook Mode")
    print(f"📊 Loaded Stats: {BOT_STATS['total_downloads']} downloads, {len(BOT_STATS['total_users'])} users")
    print("📍 Server running on port 5000")
    
    # Start Flask app using Waitress production server
    serve(app, host="0.0.0.0", port=5000, threads=4)