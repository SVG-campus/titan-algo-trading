import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
import time
import os
import sys
import json
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "/home/ubuntu/titan_logs"
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
log_filename = os.path.join(LOG_DIR, "titan_trade_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        TimedRotatingFileHandler(log_filename, when="W0", interval=1, backupCount=52)
    ]
)
logger = logging.getLogger()

API_KEY = os.environ.get('ALPACA_KEY')
API_SECRET = os.environ.get('ALPACA_SECRET')
BASE_URL = "https://paper-api.alpaca.markets"
APPROVED_FILE = "/home/ubuntu/titan_approved.json" 

def load_config():
    try:
        with open(APPROVED_FILE, 'r') as f: return json.load(f)
    except: return {}

def get_data(api, ticker):
    try:
        bars = api.get_bars(ticker, tradeapi.TimeFrame.Minute, limit=100).df
        if bars.empty: return None
        return bars.resample('5Min').agg({'close': 'last'}).dropna()
    except: return None

def run_titan():
    logger.info("🚀 TITAN V10 AI-TRADER STARTING...")
    api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')
    ASSET_CONFIG = load_config()
    
    while True:
        try:
            # Reload Approved List every 15 mins (in case AI runs update)
            if datetime.now().minute % 15 == 0: ASSET_CONFIG = load_config()
            
            try:
                if not api.get_clock().is_open:
                    logger.info("💤 Market Closed.")
                    time.sleep(900); continue
            except: pass

            account = api.get_account()
            bp = float(account.buying_power)
            
            candidates = []
            for ticker, cfg in ASSET_CONFIG.items():
                df = get_data(api, ticker)
                if df is None: continue
                
                sma = df['close'].rolling(20).mean().iloc[-1]
                std = df['close'].rolling(20).std().iloc[-1]
                lower = sma - (std * cfg['dev'])
                
                if df['close'].iloc[-1] <= lower:
                    candidates.append({'ticker': ticker, 'score': cfg.get('score', 0)})
            
            # ALL IN EXECUTION (If Buying Power > $500)
            if candidates and bp > 500:
                best = sorted(candidates, key=lambda x: x['score'], reverse=True)[0]
                t = best['ticker']
                qty = int((bp * 0.95) / df['close'].iloc[-1]) 
                
                if qty > 0:
                    api.submit_order(symbol=t, qty=qty, side='buy', type='market', time_in_force='day')
                    logger.info(f"🚀 ALL-IN BUY: {t} ({qty} shares)")
                    time.sleep(10)
            
            time.sleep(60)
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run_titan()
