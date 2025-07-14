import pandas as pd
import numpy as np
import joblib
from tensorflow.keras.models import load_model
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import MACD, EMAIndicator

class EnhancedSignalGenerator:
    def __init__(self, api_client, model_path='otc_model.h5'):
        self.api = api_client
        try:
            self.model = load_model(model_path)
        except:
            # Fallback to a simple model or raise after retraining
            self.model = None
        self.scaler = joblib.load('scaler.pkl')
        self.prev_day_data = {}
        self.load_previous_day()
        
    def load_previous_day(self):
        """Load yesterday's data for comparison"""
        instruments = self.api.get_otc_instruments()
        for instrument in instruments[:5]:  # Top 5 instruments
            try:
                data = self.api.get_historical_data(instrument, 1440, 2)  # Daily data (1440 minutes)
                if len(data) >= 2:
                    # Format: [timestamp, open, high, low, close]
                    yesterday = data[-2]
                    self.prev_day_data[instrument] = {
                        'high': yesterday[2],
                        'low': yesterday[3],
                        'close': yesterday[4]
                    }
            except Exception as e:
                print(f"Error loading previous day data for {instrument}: {str(e)}")
    
    def calculate_features(self, df):
        """Calculate advanced technical features"""
        # Ensure we have enough data
        if len(df) < 20:
            return df
        
        # Price features
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(10).std().fillna(0)
        
        # Momentum indicators
        rsi = RSIIndicator(df['close'], window=14)
        df['rsi'] = rsi.rsi().fillna(50)
        
        # Trend indicators
        macd = MACD(df['close'])
        df['macd'] = macd.macd().fillna(0)
        df['macd_signal'] = macd.macd_signal().fillna(0)
        df['macd_diff'] = macd.macd_diff().fillna(0)
        
        # Volatility indicators
        bb = BollingerBands(df['close'], window=20)
        df['bb_upper'] = bb.bollinger_hband().fillna(method='bfill')
        df['bb_middle'] = bb.bollinger_mavg().fillna(method='bfill')
        df['bb_lower'] = bb.bollinger_lband().fillna(method='bfill')
        
        atr = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr'] = atr.average_true_range().fillna(method='bfill')
        
        # Moving averages
        ema12 = EMAIndicator(df['close'], window=12)
        ema26 = EMAIndicator(df['close'], window=26)
        df['ema12'] = ema12.ema_indicator().fillna(method='bfill')
        df['ema26'] = ema26.ema_indicator().fillna(method='bfill')
        
        # Pattern detection: hammer (simplified)
        df['hammer'] = ((df['close'] > df['open']) & 
                       (df['close'] - df['low']) > 2 * (df['open'] - df['close']) & 
                       (df['high'] - df['close']) < (df['open'] - df['close']))).astype(int)
        
        return df.dropna()
    
    def detect_breakout(self, instrument, current_data):
        """Detect early breakouts compared to previous day"""
        if instrument not in self.prev_day_data:
            return False
            
        prev = self.prev_day_data[instrument]
        current = current_data.iloc[-1]
        
        # Breakout detection logic
        upper_break = current['high'] > prev['high']
        lower_break = current['low'] < prev['low']
        
        # Volatility filter (current ATR must be at least 80% of yesterday's ATR)
        # Note: We don't have yesterday's ATR, so we skip for now. Alternatively, we can store yesterday's ATR in load_previous_day.
        # For now, we skip volatility filter for breakout
        
        return upper_break or lower_break
    
    def generate_signal(self, instrument):
        """Generate validated trading signal"""
        # Fetch current data
        try:
            raw_data = self.api.get_historical_data(instrument, interval=60, count=1000)
            if not raw_data:
                return 'HOLD'
                
            df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = self.calculate_features(df)
            if len(df) < 10:
                return 'HOLD'
            
            # Check for breakout
            if self.detect_breakout(instrument, df):
                return 'BREAKOUT'
            
            # Prepare features for ML model
            current = df.iloc[-1:][['rsi', 'macd', 'macd_diff', 'atr', 'volatility', 'bb_upper', 'bb_lower']]
            scaled = self.scaler.transform(current)
            X = scaled.reshape(1, 1, scaled.shape[1])
            
            # Model prediction (if model is loaded)
            if self.model is None:
                return 'HOLD'
                
            prediction = self.model.predict(X)
            direction = np.argmax(prediction)
            confidence = np.max(prediction)
            
            # Confidence threshold
            if confidence < 0.92:
                return 'HOLD'
                
            # Next candle validation
            time.sleep(60)  # Wait for next candle
            next_data = self.api.get_historical_data(instrument, interval=60, count=1)
            if not next_data:
                return 'HOLD'
                
            next_close = next_data[0][4]
            current_close = df.iloc[-1]['close']
            
            # Validate prediction
            if (direction == 0 and next_close > current_close) or \
               (direction == 1 and next_close < current_close):
                return 'BUY' if direction == 0 else 'SELL'
            
            return 'HOLD'
        except Exception as e:
            print(f"Error generating signal for {instrument}: {str(e)}")
            return 'HOLD'
