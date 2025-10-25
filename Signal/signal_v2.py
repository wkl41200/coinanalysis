import ccxt
import requests
from datetime import datetime
import time  # ← NEW: For making the script wait between checks

# ============ YOUR TELEGRAM INFO ============
TELEGRAM_BOT_TOKEN = "7973108719:AAEkvnSwANsi7gWvju3qmPXKTWZqwWLpdRQ"
TELEGRAM_CHAT_ID = "282333505"

# ============ STRATEGY SETTINGS ============
EXTREME_LOW_FUNDING = 0.00003
PRICE_BUFFER_PCT = 0.03

# ============ TIMING SETTINGS ============
CHECK_INTERVAL_MINUTES = 30  # How often to check for signals (30 minutes)
COOLDOWN_MINUTES = 60        # Wait 60 minutes after sending an alert before checking again

# ============ SEND TELEGRAM MESSAGE ============
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
    try:
        print(f"\n{'='*70}")
        print(f"🔍 Checking at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print('='*70)
        
        # Get Binance data (no API keys needed!)
        exchange = ccxt.binance()
        
        # Get funding rate
        funding_data = exchange.fetch_funding_rate('BTC/USDT:USDT')
        current_funding = funding_data['fundingRate']
        
        # Get OHLC data
        candles = exchange.fetch_ohlcv('BTC/USDT', '4h', limit=25)
        current_price = candles[-1][4]
        past_closes = [bar[4] for bar in candles[:-1]]
        low_24 = min(past_closes)
        
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
            
            alert = f"""
🚨 LONG SIGNAL DETECTED! 🚨

💰 Entry: ${current_price:,.2f}
🛑 Stop Loss: ${stop_loss:,.2f} (-3%)
🎯 Take Profit: ${take_profit:,.2f} (+4.5%)

📊 Position: $2,000 (2x leverage)
⏰ Time: {datetime.now().strftime('%H:%M:%S UTC')}

⚡ ACTION REQUIRED:
1. Open Binance Futures
2. LONG BTC/USDT
3. Enter position: $2,000
4. Set SL: ${stop_loss:,.2f}
5. Set TP: ${take_profit:,.2f}
"""
            send_telegram(alert)
            print("✅ Alert sent!")
            return True  # Signal was detected
        else:
            print("\n❌ No signal yet")
            return False  # No signal
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

# ============ MAIN LOOP (NEW!) ============
def run_continuous():
    """
    Main function that runs forever.
    Checks for signals every 30 minutes.
    After sending an alert, waits 60 minutes before checking again.
    """
    print("🤖 Trading Alert Bot - CONTINUOUS MODE")
    print("="*70)
    print(f"⏰ Checking every {CHECK_INTERVAL_MINUTES} minutes")
    print(f"🔕 Cooldown after alert: {COOLDOWN_MINUTES} minutes")
    print("="*70)
    
    # Test Telegram first
    print("\n📱 Testing Telegram...")
    if not send_telegram("🧪 Test: Your continuous alert bot is starting! ✅"):
        print("❌ Telegram failed - please check your bot token and chat ID")
        return
    
    print("✅ Telegram working!")
    print("\n🔄 Starting continuous monitoring...")
    print("   (Press Ctrl+C to stop)\n")
    
    # Main loop - runs forever
    while True:
        try:
            # Check for signal
            signal_detected = check_signal()
            
            # If signal was detected, wait longer (cooldown period)
            if signal_detected:
                wait_minutes = COOLDOWN_MINUTES
                print(f"\n⏸️  Cooldown: Waiting {wait_minutes} minutes before next check...")
            else:
                wait_minutes = CHECK_INTERVAL_MINUTES
                print(f"\n⏸️  Waiting {wait_minutes} minutes until next check...")
            
            # Show countdown
            wait_seconds = wait_minutes * 60
            next_check_time = datetime.now().timestamp() + wait_seconds
            next_check_str = datetime.fromtimestamp(next_check_time).strftime('%H:%M:%S')
            print(f"   Next check at: {next_check_str}")
            
            # Sleep (wait) for the specified time
            time.sleep(wait_seconds)
            
        except KeyboardInterrupt:
            # User pressed Ctrl+C to stop
            print("\n\n⛔ Stopping bot... Goodbye!")
            break
            
        except Exception as e:
            # If there's an error, wait 5 minutes and try again
            print(f"\n❌ Unexpected error: {e}")
            print("⏸️  Waiting 5 minutes before retrying...")
            time.sleep(300)  # 5 minutes = 300 seconds

# ============ START HERE ============
if __name__ == "__main__":
    run_continuous()