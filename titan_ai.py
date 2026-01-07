import json
import yfinance as yf
import pandas as pd
import numpy as np
import os
import sys
from xgboost import XGBClassifier
import warnings

warnings.filterwarnings('ignore')

CONFIG_FILE = "/home/ubuntu/titan_config.json"
APPROVED_FILE = "/home/ubuntu/titan_approved.json"

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    except: return {}

def train_and_predict(ticker, cfg):
    try:
        df = yf.download(ticker, period="60d", interval="1h", progress=False)
        if len(df) < 50: return 0
        
        # FIX FOR MULTIINDEX
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df['SMA'] = df['Close'].rolling(20).mean()
        df['Std'] = df['Close'].rolling(20).std()
        df['Lower'] = df['SMA'] - (df['Std'] * cfg['dev'])
        
        df['Dist_Lower'] = (df['Close'] - df['Lower']) / df['Close']
        df['Volatility'] = df['Std'] / df['Close']
        df['Momentum'] = df['Close'].pct_change().rolling(5).mean()
        df['Vol_Spike'] = df['Volume'] / df['Volume'].rolling(20).mean()
        df = df.dropna()
        
        # LABELING
        targets = []
        lower = df['SMA'] - (df['Std'] * cfg['dev'])
        upper = df['SMA'] + (df['Std'] * cfg['dev'])
        
        for i in range(len(df)-5):
            if df['Low'].iloc[i] <= lower.iloc[i]:
                entry = df['Close'].iloc[i]
                target = df['SMA'].iloc[i] if cfg['exit'] == 'MEDIAN' else upper.iloc[i]
                stop = entry * (1 - cfg['trail_pct'])
                win = 0
                for j in range(1, 6):
                    if i+j >= len(df): break
                    if df['High'].iloc[i+j] >= target: win = 1; break
                    if df['Low'].iloc[i+j] <= stop: win = 0; break
                targets.append(win)
            else:
                targets.append(0)
        
        y = pd.Series(targets, index=df.index[:-5])
        X = df[['Dist_Lower', 'Volatility', 'Momentum', 'Vol_Spike']].iloc[:-5]
        y = y.reindex(X.index).fillna(0)
        
        if len(X) < 10: return 0
        
        model = XGBClassifier(eval_metric='logloss')
        model.fit(X, y)
        
        last_row = X.iloc[[-1]]
        return model.predict_proba(last_row)[0][1]
        
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return 0

def run_ai():
    print("🤖 TITAN AI STARTING...")
    cfg = load_config()
    approved = {}
    
    for t, c in cfg.items():
        prob = train_and_predict(t, c)
        print(f"   {t}: {prob*100:.1f}% Win Prob")
        # THRESHOLD: 30% (Lowered slightly since market is closed)
        if prob > 0.30:
            approved[t] = c
            
    with open(APPROVED_FILE, 'w') as f:
        json.dump(approved, f, indent=2)
    print(f"✅ Approved {len(approved)} assets.")

if __name__ == "__main__":
    run_ai()
