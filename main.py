import requests
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from telegram import Bot
from telegram.error import TelegramError
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
import asyncio
import time
import logging
from keep_alive import keep_alive
keep_alive()
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ottieni le prime 250 criptovalute da CoinGecko
def get_all_coins():
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1"
    data = requests.get(url).json()
    coins = [coin['id'] for coin in data]
    return coins

# Ottieni dati storici di un coin
def get_price_history(coin_id, days=30):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
    data = requests.get(url).json()
    prices = data['prices']
    df = pd.DataFrame(prices, columns=["timestamp", "close"])
    df['close'] = df['close'].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Genera segnale tecnico
def generate_signal(coin_id):
    try:
        df = get_price_history(coin_id, days=30)
    except:
        return None

    if len(df) < 21:
        return None

    ema_short = EMAIndicator(df['close'], window=9).ema_indicator()
    ema_long = EMAIndicator(df['close'], window=21).ema_indicator()
    rsi = RSIIndicator(df['close'], window=14).rsi()

    last_close = df['close'].iloc[-1]
    last_ema_short = ema_short.iloc[-1]
    last_ema_long = ema_long.iloc[-1]
    last_rsi = rsi.iloc[-1]

    signal_type = None
    if last_ema_short > last_ema_long and last_rsi < 70:
        signal_type = "LONG"
    elif last_ema_short < last_ema_long and last_rsi > 30:
        signal_type = "SHORT"

    if signal_type:
        stop_loss = last_close * (0.98 if signal_type=="LONG" else 1.02)
        take_profit_1 = last_close * (1.02 if signal_type=="LONG" else 0.98)
        take_profit_2 = last_close * (1.04 if signal_type=="LONG" else 0.96)
        take_profit_3 = last_close * (1.06 if signal_type=="LONG" else 0.94)

        return {
            "symbol": coin_id.upper(),
            "type": signal_type,
            "entry": last_close,
            "stop_loss": stop_loss,
            "take_profits": [take_profit_1, take_profit_2, take_profit_3]
        }
    return None

# Invia segnale su Telegram
async def send_signal(signal):
    message = f"""
📊 Segnale: {signal['symbol']}
💹 Tipo: {signal['type']}
💰 Entry: {signal['entry']:.2f}
⛔ Stop Loss: {signal['stop_loss']:.2f}
🎯 Take Profit 1: {signal['take_profits'][0]:.2f}
🎯 Take Profit 2: {signal['take_profits'][1]:.2f}
🎯 Take Profit 3: {signal['take_profits'][2]:.2f}
"""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        async with bot:
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            logger.info("Segnale inviato con successo")
    except TelegramError as e:
        logger.error(f"Errore nell'invio del messaggio: {e}")

# Job periodico
async def job():
    print("Controllo segnali...")
    coins = get_all_coins()
    for coin in coins:
        signal = generate_signal(coin)
        if signal:
            await send_signal(signal)

# Loop principale 
async def main():
    while True:
        try:
            await job()
            print("Controllo completato. Prossimo controllo tra 1 ora...")
        except Exception as e:
            logger.error(f"Errore durante il controllo: {e}")
        
        # Aspetta 1 ora (3600 secondi)
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
