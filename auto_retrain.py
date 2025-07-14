import schedule
import time
import joblib
import numpy as np
import pandas as pd
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from pocket_option_api import PocketOptionAPI

# Replace with your credentials
POCKET_EMAIL = "your_email@pocketoption.com"
POCKET_PASSWORD = "your_password"
POCKET_API_KEY = "your_api_key"

class ModelRetrainer:
    def __init__(self, api_client):
        self.api = api_client
        self.instruments = api_client.get_otc_instruments()[:5]
        
    def fetch_training_data(self):
        """Fetch and prepare training data"""
        all_data = []
        
        for instrument in self.instruments:
            try:
                # Get 1000 1-minute candles
                data = self.api.get_historical_data(instrument, interval=60, count=1000)
                if not data:
                    continue
                    
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close'])
                df = self.calculate_features(df)
                
                # Create labels (1: price increased next candle, 0: decreased)
                df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
                all_data.append(df.dropna())
            except Exception as e:
                print(f"Error fetching data for {instrument}: {str(e)}")
                continue
            
        if not all_data:
            return pd.DataFrame()
        return pd.concat(all_data)
    
    def calculate_features(self, df):
        """Feature engineering for training data"""
        if len(df) < 20:
            return df
            
        # Price features
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(10).std().fillna(0)
        
        # Technical indicators
        # RSI
        diff = df['close'].diff()
        gain = diff.where(diff > 0, 0)
        loss = -diff.where(diff < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs)).fillna(50)
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(14).mean().fillna(method='bfill')
        
        return df.dropna()
    
    def build_model(self, input_shape):
        """Create LSTM model architecture"""
        model = Sequential([
            LSTM(128, return_sequences=True, input_shape=input_shape),
            Dropout(0.3),
            LSTM(64, return_sequences=False),
            Dropout(0.3),
            Dense(32, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def retrain_model(self):
        """Full retraining workflow"""
        print("Starting model retraining...")
        try:
            # Fetch and prepare data
            data = self.fetch_training_data()
            if len(data) == 0:
                print("No data available for retraining")
                return False
                
            features = data[['rsi', 'macd', 'atr', 'volatility']]
            targets = data['target']
            
            # Scale features
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)
            joblib.dump(scaler, 'scaler.pkl')
            
            # Reshape for LSTM
            X = scaled_features.reshape((scaled_features.shape[0], 1, scaled_features.shape[1]))
            
            # Split data
            X_train, X_val, y_train, y_val = train_test_split(
                X, targets, test_size=0.2, shuffle=False
            )
            
            # Build and train model
            model = self.build_model((X_train.shape[1], X_train.shape[2]))
            model.fit(
                X_train, y_train,
                epochs=50,
                batch_size=64,
                validation_data=(X_val, y_val),
                verbose=1
            )
            
            # Validate model
            val_loss, val_acc = model.evaluate(X_val, y_val, verbose=0)
            print(f"Validation accuracy: {val_acc:.2%}, Loss: {val_loss:.4f}")
            
            # Save if performance is acceptable
            if val_acc > 0.75:
                model.save('otc_model.h5')
                print("Model successfully updated")
                return True
                
            print("Model performance below threshold - keeping previous version")
            return False
            
        except Exception as e:
            print(f"Retraining failed: {str(e)}")
            return False

def main():
    # Initialize API client
    api_client = PocketOptionAPI(POCKET_EMAIL, POCKET_PASSWORD, POCKET_API_KEY)
    retrainer = ModelRetrainer(api_client)
    
    # Initial retraining
    print("Performing initial model training...")
    if retrainer.retrain_model():
        print("Initial training successful")
    else:
        print("Initial training failed")
    
    # Schedule daily retraining at market close
    schedule.every().day.at("23:00").do(retrainer.retrain_model)
    
    print("Retrainer started. Waiting for scheduled retraining...")
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour

if __name__ == "__main__":
    main()
