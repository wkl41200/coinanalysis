import ccxt
import requests
from datetime import datetime
import time
import threading
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============ YOUR TELEGRAM INFO ============
TELEGRAM_BOT_TOKEN = "7973108719:AAEkvnSwANsi7gWvju3qmPXKTWZqwWLpdRQ"
TELEGRAM_CHAT_ID = "282333505"

# ============ STRATEGY SETTINGS ============
EXTREME_LOW_FUNDING = 0.00003
PRICE_BUFFER_PCT = 0.03

# ============ TIMING SETTINGS ============
CHECK_INTERVAL_MINUTES = 30
COOLDOWN_MINUTES = 60

# ============ GLOBAL VARIABLES (for tracking) ============
bot_start_time = datetime.now()
last_check_time = None
next_check_time = None
signals_today = []
latest_market_data = {}

# ============ SEND TELEGRAM MESSAGE (one-way alert) ============
def send_telegram(message):
    """Send alert to your Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

# ============ CHECK FOR SIGNAL ============
def check_signal():
    """Check if LONG signal exists"""
    global last_check_time, next_check_time, signals_today, latest_market_data
    
    try:
        last_check_time = datetime.now()
        
        print(f"\n{'='*70}")
        print(f"🔍 Checking at {last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print('='*70)
        
        # Get Binance data
        exchange = ccxt.binance()
        
        # Get funding rate
        funding_data = exchange.fetch_funding_rate('BTC/USDT:USDT')
        current_funding = funding_data['fundingRate']
        
        # Get OHLC data
        candles = exchange.fetch_ohlcv('BTC/USDT', '4h', limit=25)
        current_price = candles[-1][4]
        past_closes = [bar[4] for bar in candles[:-1]]
        low_24 = min(past_closes)
        
        # Store latest market data (for /market command)
        latest_market_data = {
            'price': current_price,
            'funding': current_funding,
            'low_24': low_24,
            'threshold': low_24 * (1 + PRICE_BUFFER_PCT),
            'time': last_check_time
        }
        
        print(f"\n📊 Market Data:")
        print(f"   BTC Price: ${current_price:,.2f}")
        print(f"   Funding: {current_funding:.6f} ({current_funding*100:.4f}%)")
        print(f"   24-bar Low: ${low_24:,.2f}")
        print(f"   Entry Threshold: ${low_24 * 1.03:,.2f}")
        
        # Check conditions
        funding_ok = current_funding <= EXTREME_LOW_FUNDING
        price_ok = current_price <= low_24 * (1 + PRICE_BUFFER_PCT)
        
        print(f"\n🎯 Signal Check:")
        print(f"   {'✅' if funding_ok else '❌'} Funding ≤ 0.00003")
        print(f"   {'✅' if price_ok else '❌'} Price ≤ 103% of low")
        
        # SIGNAL DETECTED!
        if funding_ok and price_ok:
            print("\n🚨 SIGNAL DETECTED!")
            
            stop_loss = current_price * 0.97
            take_profit = current_price * 1.045
            
            # Store signal (for /signals command)
            signals_today.append({
                'time': last_check_time,
                'price': current_price,
                'funding': current_funding
            })
            
            alert = f"""
🚨 LONG SIGNAL DETECTED! 🚨

💰 Entry: ${current_price:,.2f}
🛑 Stop Loss: ${stop_loss:,.2f} (-3%)
🎯 Take Profit: ${take_profit:,.2f} (+4.5%)

📊 Position: $2,000 (2x leverage)
⏰ Time: {last_check_time.strftime('%H:%M:%S UTC')}

⚡ ACTION REQUIRED:
1. Open Binance Futures
2. LONG BTC/USDT
3. Enter position: $2,000
4. Set SL: ${stop_loss:,.2f}
5. Set TP: ${take_profit:,.2f}
"""
            send_telegram(alert)
            print("✅ Alert sent!")
            return True
        else:
            print("\n❌ No signal yet")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

# ============ TELEGRAM COMMAND HANDLERS ============

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    uptime = datetime.now() - bot_start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    last_check_str = "Never" if last_check_time is None else f"{int((datetime.now() - last_check_time).total_seconds() / 60)} min ago"
    next_check_str = "Calculating..." if next_check_time is None else next_check_time.strftime('%H:%M:%S UTC')
    
    # Count today's signals
    today = datetime.now().date()
    today_count = len([s for s in signals_today if s['time'].date() == today])
    
    message = f"""🤖 BOT STATUS

✅ Online: {hours}h {minutes}m
⏰ Last check: {last_check_str}
⏱️ Next check: {next_check_str}

📡 Health: All systems OK
🔔 Signals today: {today_count}
"""
    await update.message.reply_text(message)

async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /market command"""
    if not latest_market_data:
        await update.message.reply_text("⏳ No market data yet. Bot is starting...")
        return
    
    data = latest_market_data
    
    # Calculate if close to signal
    funding_ok = data['funding'] <= EXTREME_LOW_FUNDING
    price_ok = data['price'] <= data['threshold']
    
    status = "🟢 Ready to signal" if (funding_ok and price_ok) else "⚪ Waiting for setup"
    
    message = f"""📊 MARKET DATA

💰 BTC Price: ${data['price']:,.2f}

⚡ Funding Rate: {data['funding']:.6f}
📊 Funding %: {data['funding']*100:.4f}%
🎯 Long threshold: ≤ 0.00003

📍 24-bar Low: ${data['low_24']:,.2f}
📍 Entry Threshold: ${data['threshold']:,.2f}

{status}

⏰ Updated: {data['time'].strftime('%H:%M:%S UTC')}
"""
    await update.message.reply_text(message)

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /signals command"""
    today = datetime.now().date()
    today_signals = [s for s in signals_today if s['time'].date() == today]
    
    if not today_signals:
        message = """🎯 SIGNAL HISTORY

Today (Oct 24): No signals yet

Total today: 0 signals
"""
    else:
        message = f"🎯 SIGNAL HISTORY\n\nToday ({today.strftime('%b %d')}):\n"
        for sig in today_signals:
            message += f"  • {sig['time'].strftime('%H:%M')} UTC - LONG @ ${sig['price']:,.0f}\n"
        message += f"\nTotal today: {len(today_signals)} signals"
    
    await update.message.reply_text(message)

# ============ SIGNAL CHECKING LOOP (runs in separate thread) ============
def signal_checker_loop():
    """Main loop that checks for signals every 30 minutes"""
    global next_check_time
    
    while True:
        try:
            # Check for signal
            signal_detected = check_signal()
            
            # Determine wait time
            if signal_detected:
                wait_minutes = COOLDOWN_MINUTES
                print(f"\n⏸️  Cooldown: Waiting {wait_minutes} minutes before next check...")
            else:
                wait_minutes = CHECK_INTERVAL_MINUTES
                print(f"\n⏸️  Waiting {wait_minutes} minutes until next check...")
            
            # Calculate next check time
            wait_seconds = wait_minutes * 60
            next_check_time = datetime.fromtimestamp(datetime.now().timestamp() + wait_seconds)
            print(f"   Next check at: {next_check_time.strftime('%H:%M:%S')}")
            
            # Sleep
            time.sleep(wait_seconds)
            
        except Exception as e:
            print(f"\n❌ Error in signal checker: {e}")
            print("⏸️  Waiting 5 minutes before retrying...")
            time.sleep(300)

# ============ MAIN FUNCTION ============
def main():
    """Start both the signal checker and Telegram bot"""
    print("🤖 Trading Alert Bot - v3 WITH COMMANDS")
    print("="*70)
    print(f"⏰ Checking every {CHECK_INTERVAL_MINUTES} minutes")
    print(f"🔕 Cooldown after alert: {COOLDOWN_MINUTES} minutes")
    print("="*70)
    
    # Test Telegram
    print("\n📱 Testing Telegram...")
    if not send_telegram("🧪 Bot v3 starting with commands! Try /status, /market, /signals"):
        print("❌ Telegram failed - check your bot token and chat ID")
        return
    
    print("✅ Telegram working!")
    
    # Start signal checker in background thread
    print("\n🔄 Starting signal checker thread...")
    checker_thread = threading.Thread(target=signal_checker_loop, daemon=True)
    checker_thread.start()
    print("✅ Signal checker started!")
    
    # Start Telegram bot (command listener)
    print("\n🤖 Starting Telegram command listener...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("market", market_command))
    app.add_handler(CommandHandler("signals", signals_command))
    
    print("✅ Command listener ready!")
    print("\n📱 Available commands:")
    print("   /status  - Bot health and timing")
    print("   /market  - Current BTC price and funding")
    print("   /signals - Today's signal history")
    print("\n" + "="*70)
    print("✅ BOT FULLY OPERATIONAL!")
    print("="*70)
    
    # Run the bot (this blocks and keeps running)
    # Use run_polling() with asyncio in a way that doesn't conflict
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n\n⛔ Stopping bot... Goodbye!")

# ============ START HERE ============
if __name__ == "__main__":
    main()