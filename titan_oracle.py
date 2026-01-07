import yfinance as yf
import os

def check():
    try:
        vix = yf.Ticker("^VIX").history(period="5d")['Close'].iloc[-1]
        print(f"VIX: {vix}")
        
        if vix > 35:
            print("🔴 DANGER (VIX > 35). STOPPING.")
            os.system("sudo systemctl stop titan")
        else:
            print("🟢 SAFE. STARTING.")
            os.system("sudo systemctl start titan")
    except:
        os.system("sudo systemctl start titan")

if __name__ == "__main__":
    check()
