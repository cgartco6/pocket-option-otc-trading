import sys
import time
import schedule
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSystemTrayIcon, 
                             QMenu, QLabel, QVBoxLayout, QWidget, QListWidget,
                             QPushButton, QHBoxLayout)
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from telegram import Bot, BotCommand
from telegram.error import TelegramError
from pocket_option_api import PocketOptionAPI
from enhanced_signals import EnhancedSignalGenerator

# Replace with your credentials
POCKET_EMAIL = "your_email@pocketoption.com"
POCKET_PASSWORD = "your_password"
POCKET_API_KEY = "your_api_key"
TELEGRAM_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

class SignalChecker(QThread):
    signal_detected = pyqtSignal(str, str)  # instrument, signal
    
    def __init__(self, signal_gen, instruments):
        super().__init__()
        self.signal_gen = signal_gen
        self.instruments = instruments
        self.running = True
        
    def run(self):
        while self.running:
            for instrument in self.instruments:
                signal = self.signal_gen.generate_signal(instrument)
                if signal != 'HOLD':
                    self.signal_detected.emit(instrument, signal)
            time.sleep(30)  # Check every 30 seconds
    
    def stop(self):
        self.running = False

class TradingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            # Initialize API client
            self.api = PocketOptionAPI(POCKET_EMAIL, POCKET_PASSWORD, POCKET_API_KEY)
            self.telegram_bot = Bot(token=TELEGRAM_TOKEN)
            self.telegram_bot.get_me()
            self.signal_gen = EnhancedSignalGenerator(self.api)
            self.instruments = self.api.get_otc_instruments()[:5]  # Top 5 instruments
            self.signals = []
            
            self.init_ui()
            self.init_tray()
            self.start_signal_checker()
            
            # Schedule daily reload of previous day data
            schedule.every().day.at("00:00").do(self.signal_gen.load_previous_day)
            
        except Exception as e:
            print(f"Initialization failed: {str(e)}")
            sys.exit(1)
        
    def init_ui(self):
        self.setWindowTitle("OTC Signal Master")
        self.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Title
        title = QLabel("Real-Time OTC Signals")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Instruments
        instruments_label = QLabel(f"Instruments: {', '.join(self.instruments)}")
        instruments_label.setFont(QFont("Arial", 10))
        main_layout.addWidget(instruments_label)
        
        # Signal list
        self.signal_list = QListWidget()
        self.signal_list.setFont(QFont("Consolas", 10))
        main_layout.addWidget(self.signal_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_signal_checker)
        button_layout.addWidget(self.start_button)
        
        stop_button = QPushButton("Stop Monitoring")
        stop_button.clicked.connect(self.stop_signal_checker)
        button_layout.addWidget(stop_button)
        
        main_layout.addLayout(button_layout)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(QIcon("signal_icon.ico"), self)
        tray_menu = QMenu()
        
        show_action = tray_menu.addAction("Show Dashboard")
        show_action.triggered.connect(self.show)
        
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(self.close_app)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_activated)
        
    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            
    def start_signal_checker(self):
        if hasattr(self, 'signal_thread') and self.signal_thread.isRunning():
            return
            
        self.signal_thread = SignalChecker(self.signal_gen, self.instruments)
        self.signal_thread.signal_detected.connect(self.process_signal)
        self.signal_thread.start()
        self.start_button.setText("Monitoring...")
        self.start_button.setEnabled(False)
        
    def stop_signal_checker(self):
        if hasattr(self, 'signal_thread'):
            self.signal_thread.stop()
            self.signal_thread.quit()
            self.start_button.setText("Start Monitoring")
            self.start_button.setEnabled(True)
    
    def process_signal(self, instrument, signal):
        """Process and display valid signals"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        signal_text = f"[{timestamp}] {instrument}: {signal}"
        
        # Add to GUI
        self.signals.insert(0, signal_text)
        self.signal_list.clear()
        self.signal_list.addItems(self.signals[:20])  # Show last 20 signals
        
        # Send to Telegram
        try:
            self.telegram_bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"🚀 OTC SIGNAL\n{signal_text}\n#PocketOption #OTC"
            )
        except TelegramError as e:
            print(f"Telegram send error: {str(e)}")
        
        # System tray notification
        self.tray_icon.showMessage(
            "OTC Signal Alert",
            f"{instrument}: {signal}",
            QSystemTrayIcon.Information,
            5000
        )
    
    def close_app(self):
        self.stop_signal_checker()
        QApplication.quit()
        
    def closeEvent(self, event):
        self.tray_icon.hide()
        event.accept()

# Timer for scheduled tasks
class ScheduleTimer(QTimer):
    def __init__(self):
        super().__init__()
        self.timeout.connect(self.run_schedules)
        
    def run_schedules(self):
        schedule.run_pending()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Schedule timer
    timer = ScheduleTimer()
    timer.start(60000)  # Check every minute
    
    window = TradingDashboard()
    window.show()
    sys.exit(app.exec_())
