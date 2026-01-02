# titan_live_ibkr.py
from ib_insync import *
import pandas as pd
import numpy as np
import datetime
import asyncio

# ==============================================================================
# ⚙️ CONFIG
# ==============================================================================
# Same Optimal Configs
ASSET_CONFIG = {
    'MIRA': {'dev': 1.5, 'sl': 0.05, 'exit': 'UPPER',  'trail': True,  'trail_ticks': 30, 'entry': 'CLOSE'},
    'CAMP': {'dev': 1.5, 'sl': 0.05, 'exit': 'MEDIAN', 'trail': True,  'trail_ticks': 25, 'entry': 'CLOSE'},
    'BENF': {'dev': 2.0, 'sl': 0.05, 'exit': 'MEDIAN', 'trail': True,  'trail_ticks': 20, 'entry': 'CLOSE'},
    'RCT':  {'dev': 1.5, 'sl': 0.05, 'exit': 'MEDIAN', 'trail': True,  'trail_ticks': 25, 'entry': 'CLOSE'},
    'DBGI': {'dev': 1.5, 'sl': 0.05, 'exit': 'MEDIAN', 'trail': True,  'trail_ticks': 20, 'entry': 'TOUCH'}
}

ACCOUNT_CASH = 1000000 # Paper Money
MAX_ALLOCATION = 0.20 # 20% per trade

# ==============================================================================
# 🔌 IBKR CONNECTION
# ==============================================================================
ib = IB()
try:
    # Connect to TWS (Port 7497 is default for Paper Trading)
    ib.connect('127.0.0.1', 7497, clientId=1)
    print("✅ CONNECTED TO IBKR TWS")
except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")
    print("   Make sure TWS is open and API is enabled in Settings -> API.")
    exit()

# ==============================================================================
# 🧠 TITAN LOGIC ENGINE
# ==============================================================================
async def run_strategy():
    print(f"🚀 TITAN ROBOT ACTIVE: Monitoring {len(ASSET_CONFIG)} Assets")
    
    # 1. Setup Contracts
    contracts = {}
    for ticker in ASSET_CONFIG.keys():
        c = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(c)
        contracts[ticker] = c
        # Request Data (5m bars to match strategy, keepUpToDate=True)
        ib.reqHistoricalData(c, endDateTime='', durationStr='1 D',
                             barSizeSetting='5 mins', whatToShow='TRADES', useRTH=True, keepUpToDate=True)
        print(f"   📡 Subscribed to {ticker}")

    # 2. Event Loop
    while True:
        await asyncio.sleep(60) # Check every minute
        
        current_positions = [p.contract.symbol for p in ib.positions()]
        
        for ticker, contract in contracts.items():
            bars = ib.bars(contract)
            if not bars: continue
            
            df = util.df(bars)
            cfg = ASSET_CONFIG[ticker]
            
            # Indicators
            df['Typical'] = (df['high'] + df['low'] + df['close']) / 3
            df['SMA'] = df['Typical'].rolling(20).mean()
            df['Std'] = df['Typical'].rolling(20).std()
            df['Upper'] = df['SMA'] + (df['Std'] * cfg['dev'])
            df['Lower'] = df['SMA'] - (df['Std'] * cfg['dev'])
            
            last = df.iloc[-1]
            
            # SIGNAL CHECK
            buy_signal = False
            if cfg['entry'] == 'TOUCH':
                if last['low'] <= last['Lower']: buy_signal = True
            else:
                if last['close'] <= last['Lower']: buy_signal = True
            
            # EXECUTION
            if buy_signal and ticker not in current_positions:
                print(f"🟢 BUY SIGNAL: {ticker} @ ${last['close']}")
                
                # Sizing
                qty = int((ACCOUNT_CASH * MAX_ALLOCATION) / last['close'])
                
                # Parent Order
                parent = Order()
                parent.action = 'BUY'
                parent.totalQuantity = qty
                parent.orderType = 'LMT'
                parent.lmtPrice = last['close'] # Limit at close
                parent.transmit = False # Wait for brackets
                
                # Take Profit
                target_price = last['SMA'] if cfg['exit'] == 'MEDIAN' else last['Upper']
                tp = Order()
                tp.action = 'SELL'
                tp.totalQuantity = qty
                tp.orderType = 'LMT'
                tp.lmtPrice = round(target_price, 2)
                tp.parentId = parent.orderId
                tp.transmit = True
                
                # Stop Loss (Choice: Trailing vs Fixed)
                if cfg['trail']:
                    sl = Order()
                    sl.action = 'SELL'
                    sl.totalQuantity = qty
                    sl.orderType = 'TRAIL'
                    sl.auxPrice = cfg['trail_ticks'] * 0.01 # Trailing amount
                    sl.parentId = parent.orderId
                    sl.transmit = True
                else:
                    sl = Order()
                    sl.action = 'SELL'
                    sl.totalQuantity = qty
                    sl.orderType = 'STP'
                    sl.auxPrice = round(last['close'] * (1 - cfg['sl']), 2)
                    sl.parentId = parent.orderId
                    sl.transmit = True
                
                # Send Bracket
                trades = ib.placeOrder(contract, parent)
                print(f"   🚀 ORDER SENT: {qty} Shares of {ticker}")

# Run
ib.run(run_strategy())
