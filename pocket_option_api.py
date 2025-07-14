import requests
import time
import json
import os
from config import POCKET_EMAIL, POCKET_PASSWORD, POCKET_API_KEY

class PocketOptionAPI:
    BASE_URL = "https://api.pocketoption.com"
    
    def __init__(self):
        self.email = POCKET_EMAIL
        self.password = POCKET_PASSWORD
        self.api_key = POCKET_API_KEY
        self.session = requests.Session()
        self.ssid = None
        self._authenticate()
        
    def _authenticate(self):
        endpoint = f"{self.BASE_URL}/api/auth/login"
        payload = {
            "email": self.email,
            "password": self.password,
            "api_key": self.api_key
        }
        try:
            response = self.session.post(endpoint, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                self.ssid = data.get('ssid')
                self.session.headers.update({'Authorization': f'Bearer {self.ssid}'})
                print("✅ PocketOption authentication successful")
            else:
                raise Exception(f"Authentication failed: {data.get('message')}")
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            self._handle_auth_error()
    
    def _handle_auth_error(self):
        """Attempt re-authentication with backoff"""
        for attempt in range(3):
            wait_time = (attempt + 1) * 10
            print(f"⚠️ Retrying authentication in {wait_time} seconds...")
            time.sleep(wait_time)
            try:
                response = self.session.post(
                    f"{self.BASE_URL}/api/auth/login",
                    json={
                        "email": self.email,
                        "password": self.password,
                        "api_key": self.api_key
                    },
                    timeout=15
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        self.ssid = data.get('ssid')
                        self.session.headers.update({'Authorization': f'Bearer {self.ssid}'})
                        print("✅ Re-authentication successful")
                        return
            except Exception:
                pass
        raise Exception("🔴 Critical: Failed to authenticate after multiple attempts")
    
    def get_otc_instruments(self):
        endpoint = f"{self.BASE_URL}/api/v2/instruments"
        try:
            response = self.session.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                return [item['name'] for item in data['data'] if 'otc' in item['name'].lower()]
            raise Exception(f"Instruments error: {data.get('message')}")
        except Exception as e:
            print(f"⚠️ Instruments error: {str(e)}")
            return ['BTC/USD', 'ETH/USD', 'EUR/USD', 'GBP/USD']  # Fallback
    
    def get_historical_data(self, instrument, interval=60, count=1000):
        endpoint = f"{self.BASE_URL}/api/chart/history"
        payload = {
            "symbol": instrument,
            "resolution": interval,
            "count": count
        }
        try:
            response = self.session.post(endpoint, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get('candles', [])
        except Exception as e:
            print(f"⚠️ Data fetch error for {instrument}: {str(e)}")
            return []
    
    def place_trade(self, instrument, amount, direction, duration=1):
        endpoint = f"{self.BASE_URL}/api/v2/binary-options/open"
        payload = {
            "symbol": instrument,
            "amount": str(amount),
            "direction": direction.lower(),
            "duration": duration,
            "duration_unit": "m"
        }
        try:
            response = self.session.post(endpoint, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            print(f"⚠️ Trade execution error: {str(e)}")
            return {'success': False, 'message': str(e)}
