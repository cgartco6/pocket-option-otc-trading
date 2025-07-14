import requests
import time
import json

class PocketOptionAPI:
    BASE_URL = "https://api.pocketoption.com"
    
    def __init__(self, email, password, api_key):
        self.email = email
        self.password = password
        self.api_key = api_key
        self.session = requests.Session()
        self.ssid = None
        self._authenticate()
        
    def _authenticate(self):
        """Authenticate and get session ID"""
        endpoint = f"{self.BASE_URL}/api/auth/login"
        payload = {
            "email": self.email,
            "password": self.password,
            "api_key": self.api_key
        }
        response = self.session.post(endpoint, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                self.ssid = data.get('ssid')
                self.session.headers.update({'Authorization': f'Bearer {self.ssid}'})
                print("Authentication successful")
            else:
                raise Exception(f"Authentication failed: {data.get('
