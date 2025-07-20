import pandas as pd
import numpy as np
import joblib
import time
import os
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import MACD
from tensorflow.keras.models import load_model
from pocket_option_api import PocketOptionAPI
from config import FALLBACK_INSTRUMENTS

class EnhancedSignalGenerator:
    def _init_(self, api_client):
        self.api = api_client
        self.prev_day_data = {}
        self.model = self._load_model()
        self.scaler = self._load_scaler()
        self.load_previous_day()
    
    def _load_model(self):
        try:
            return load_model('otc_model.h5')
        except:
            print("⚠ Model load failed - using fallback strategy")
            return None
    
    def _load_scaler(self):
        try:
            return joblib.load('scaler.pkl')
        except:
            print("⚠ Scaler load failed - using default scaling")
            return None
    
    def load_previous_day(self):
        instruments = self.api.get_otc_instruments() or FALLBACK_INSTRUMENTS
        for instrument in instruments[:5]:
            try:
                data = self.api.get_historical_data(instrument, 1440, 2)
                if len(data) >= 2:
                    self.prev_day_data[instrument] = {
                        'high': data[-2][2],
                        'low': data[-2][3],
                        'close': data[-2][4]
                    }
            except Exception as e:
                print(f"⚠ Previous day load error for {instrument}: {str(e)}")
    
    def calculate_features(self, df):
        try:
            # Basic features
            df['returns'] = df['close'].pct_change()
            df['volatility'] = df['returns'].rolling(10).std().fillna(0)
            
            # RSI
            rsi = RSIIndicator(df['close'], window=14)
            df['rsi'] = rsi.rsi().fillna(50)
            
            # MACD
            macd = MACD(df['close'])
            df['macd'] = macd.macd().fillna(0)
            df['macd_signal'] = macd.macd_signal().fillna(0)
            df['macd_diff'] = macd.macd_diff().fillna(0)
            
            # Bollinger Bands
            bb = BollingerBands(df['close'], window=20)
            df['bb_upper'] = bb.bollinger_hband().fillna(method='bfill')
            df['bb_middle'] = bb.bollinger_mavg().fillna(method='bfill')
            df['bb_lower'] = bb.bollinger_lband().fillna(method='bfill')
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            
            # ATR
            atr = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
            df['atr'] = atr.average_true_range().fillna(method='bfill')
            
            # Price relationships
            df['close_vs_high'] = df['close'] / df['high'].rolling(5).max()
            df['close_vs_low'] = df['close'] / df['low'].rolling(5).min()
            
            return df.dropna()
        except Exception as e:
            print(f"⚠ Feature calculation error: {str(e)}")
            return df
    
    def detect_breakout(self, instrument, current_candle):
        if instrument not in self.prev_day_data:
            return False
        
        prev = self.prev_day_data[instrument]
        upper_break = current_candle['high'] > prev['high']
        lower_break = current_candle['low'] < prev['low']
        
        return upper_break or lower_break
    
    def generate_signal(self, instrument):
        try:
            # Fetch data
            raw_data = self.api.get_historical_data(instrument, count=100)
            if not raw_data:
                return 'HOLD'
            
            # Create DataFrame
            df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close'])
            df = self.calculate_features(df)
            
            if len(df) < 10:
                return 'HOLD'
            
            # Current candle data
            current_candle = df.iloc[-1].to_dict()
            
            # Breakout detection
            if self.detect_breakout(instrument, current_candle):
                return 'BREAKOUT'
            
            # ML signal generation
            if self.model and self.scaler:
                features = df.iloc[-1][['rsi', 'macd', 'macd_diff', 'atr', 'volatility', 'bb_width']]
                scaled = self.scaler.transform([features])
                X = scaled.reshape(1, 1, scaled.shape[1])
                
                prediction = self.model.predict(X, verbose=0)
                direction = np.argmax(prediction)
                confidence = np.max(prediction)
                
                if confidence < 0.92:
                    return 'HOLD'
                
                # Next candle validation
                time.sleep(60)  # Wait for next candle
                next_data = self.api.get_historical_data(instrument, count=1)
                if not next_data:
                    return 'HOLD'
                
                next_close = next_data[0][4]
                current_close = current_candle['close']
                
                if (direction == 0 and next_close > current_close) or \
                   (direction == 1 and next_close < current_close):
                    return 'BUY' if direction == 0 else 'SELL'
            
            return 'HOLD'
        except Exception as e:
            print(f"⚠ Signal generation error: {str(e)}")
            return 'HOLD'
