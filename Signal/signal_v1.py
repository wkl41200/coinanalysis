import ccxt
import requests
from datetime import datetime

# ============ YOUR TELEGRAM INFO ============
TELEGRAM_BOT_TOKEN = "7973108719:AAEkvnSwANsi7gWvju3qmPXKTWZqwWLpdRQ"
TELEGRAM_CHAT_ID = "282333505"

# ============ STRATEGY SETTINGS ============
EXTREME_LOW_FUNDING = 0.00003
PRICE_BUFFER_PCT = 0.03

# ============ SEND TELEGRAM MESSAGE ============
def send_telegram(message):
    """Send alert to your Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
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
            return True
        else:
            print("\n❌ No signal yet")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

# ============ MAIN ============
if __name__ == "__main__":
    print("🤖 Trading Alert Bot")
    print("="*70)
    
    # Test Telegram first
    print("\n📱 Testing Telegram...")
    if send_telegram("🧪 Test: Your alert bot is working! ✅"):
        print("✅ Telegram working!")
        
        # Check for signal
        check_signal()
        
        print("\n✅ Done!")
    else:
        print("❌ Telegram failed")