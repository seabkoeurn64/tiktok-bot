import os
import requests
import telebot
import time
import json
from urllib.parse import urlparse
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 TikTok Bot is Running - Server Version!"

@app.route('/health')
def health():
    return "✅ Bot is Healthy!"

BOT_TOKEN = "8368595880:AAGLfrmsJ1tHub8lrLnBZovU3HoD5Rk4SDw"
bot = telebot.TeleBot(BOT_TOKEN)

# Store bot statistics
BOT_STATS = {
    'total_downloads': 0,
    'total_users': set(),
    'start_time': time.time()
}

def save_stats():
    """Save statistics to file"""
    try:
        stats_to_save = BOT_STATS.copy()
        stats_to_save['total_users'] = list(stats_to_save['total_users'])
        with open('bot_stats.json', 'w') as f:
            json.dump(stats_to_save, f)
    except:
        pass

def load_stats():
    """Load statistics from file"""
    global BOT_STATS
    try:
        with open('bot_stats.json', 'r') as f:
            loaded_stats = json.load(f)
            loaded_stats['total_users'] = set(loaded_stats['total_users'])
            BOT_STATS.update(loaded_stats)
    except:
        pass

def simple_tiktok_download(url):
    """Simple TikTok download using multiple APIs"""
    apis = [
        f"https://www.tikwm.com/api/?url={url}",
        f"https://api.tikmate.app/api/lookup?url={url}",
    ]
    
    for api_url in apis:
        try:
            response = requests.get(api_url, timeout=10)
            data = response.json()
            
            if 'play' in str(data):
                video_url = data['data']['play']
                return video_url
            elif 'url' in str(data):
                video_url = data['url']
                return video_url
        except:
            continue
    return None

@bot.message_handler(commands=['start', 'help'])
def start(message):
    # Add user to statistics
    BOT_STATS['total_users'].add(message.from_user.id)
    save_stats()
    
    help_text = """
🤖 **TikTok Download Bot - Server Version**

📥 **វិធីប្រើ:**
1. ចូល TikTok App
2. ចុច Share លើ video
3. ចុច Copy Link
4. ផ្ញើ Link មក bot នេះ

🔗 **ឧទាហរណ៍:**
https://www.tiktok.com/@username/video/123456789

🏠 **Hosted on Render.com**
📞 **Owner:** @koeurn65
    """
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['stats'])
def show_stats(message):
    """Show bot statistics"""
    uptime_seconds = time.time() - BOT_STATS['start_time']
    uptime_str = time.strftime("%Hh %Mm %Ss", time.gmtime(uptime_seconds))
    
    stats_text = f"""
📊 **ស្ថិតិ Bot**

👥 អ្នកប្រើសរុប: {len(BOT_STATS['total_users'])}
📥 Downloads សរុប: {BOT_STATS['total_downloads']}
⏱️ ពេលដំណើរការ: {uptime_str}
📞 **Owner:** @koeurn65
    """
    bot.reply_to(message, stats_text)

@bot.message_handler(func=lambda m: True)
def handle(message):
    url = message.text.strip()
    
    if 'tiktok.com' not in url:
        bot.reply_to(message, "❌ សូមផ្ញើ TikTok URL ត្រឹមត្រូវ!")
        return
    
    # Add user to statistics
    BOT_STATS['total_users'].add(message.from_user.id)
    
    bot.send_chat_action(message.chat.id, 'typing')
    msg = bot.reply_to(message, "🔄 កំពុង process...")
    
    try:
        video_url = simple_tiktok_download(url)
        
        if not video_url:
            bot.edit_message_text(
                "❌ មិនអាច download បាន!",
                message.chat.id,
                msg.message_id
            )
            return
        
        bot.edit_message_text(
            "📥 កំពុង download video...",
            message.chat.id,
            msg.message_id
        )
        
        video_response = requests.get(video_url, timeout=30)
        video_data = video_response.content
        
        bot.edit_message_text(
            "📤 កំពុង upload...",
            message.chat.id,
            msg.message_id
        )
        
        bot.send_video(message.chat.id, video_data, timeout=60)
        
        # Update statistics
        BOT_STATS['total_downloads'] += 1
        save_stats()
        
        bot.edit_message_text(
            "✅ Download បានរួចរាល់!",
            message.chat.id,
            msg.message_id
        )
        
    except Exception as e:
        error_msg = f"❌ មាន error: {str(e)}"
        try:
            bot.edit_message_text(
                error_msg,
                message.chat.id,
                msg.message_id
            )
        except:
            bot.reply_to(message, error_msg)

def run_bot():
    """Run the bot with better error handling"""
    print("🤖 Starting TikTok Bot...")
    load_stats()
    
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"🔄 Attempt {retry_count + 1} to start bot...")
            
            # Use different polling parameters to avoid conflicts
            bot.infinity_polling(
                timeout=30, 
                long_polling_timeout=30,
                allowed_updates=['message', 'callback_query']
            )
            
        except Exception as e:
            print(f"❌ Bot error: {e}")
            retry_count += 1
            
            if "409" in str(e) or "Conflict" in str(e):
                print("🔄 Conflict detected - waiting longer before retry...")
                time.sleep(30)  # Wait longer for conflict resolution
            else:
                print("🔄 Other error - waiting 10 seconds...")
                time.sleep(10)
            
            if retry_count >= max_retries:
                print("❌ Max retries reached. Bot stopped.")
                break

if __name__ == "__main__":
    # Start web server in thread
    def run_web():
        app.run(host='0.0.0.0', port=5000, debug=False)
    
    web_thread = Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()
    
    # Start bot with better error handling
    run_bot()