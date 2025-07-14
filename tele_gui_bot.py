import sys
import time
import schedule
from PyQt5.QtWidgets import (QApplication, QMainWindow, QSystemTrayIcon, 
                             QMenu, QLabel, QVBoxLayout, QWidget, QListWidget,
                             QPushButton, QHBoxLayout, QStatusBar)
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from telegram import Bot
from telegram.error import TelegramError
from pocket_option_api import PocketOptionAPI
from enhanced_signals import EnhancedSignalGenerator
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, FALLBACK_INSTRUMENTS

class SignalWorker(QThread):
    signal_detected = pyqtSignal(str, str)  # instrument, signal
    status_update = pyqtSignal(str)
    
    def __init__(self, signal_gen, instruments):
        super().__init__()
        self.signal_gen = signal_gen
        self.instruments = instruments
        self.active = True
        
    def run(self):
        while self.active:
            try:
                for instrument in self.instruments:
                    if not self.active:
                        return
                    
                    self.status_update.emit(f"Checking {instrument}...")
                    signal = self.signal_gen.generate_signal(instrument)
                    
                    if signal != 'HOLD':
                        self.signal_detected.emit(instrument, signal)
                        self.status_update.emit(f"Signal found: {instrument} {signal}")
                    else:
                        self.status_update.emit(f"No signal for {instrument}")
                    
                    time.sleep(5)  # Brief pause between instruments
                
                time.sleep(30)  # Main cycle delay
            except Exception as e:
                self.status_update.emit(f"⚠️ Worker error: {str(e)}")
                time.sleep(60)
    
    def stop(self):
        self.active = False

class TradingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OTC Signal Master")
        self.setGeometry(100, 100, 800, 600)
        
        try:
            self.api = PocketOptionAPI()
            self.telegram_bot = Bot(token=TELEGRAM_TOKEN)
            self.signal_gen = EnhancedSignalGenerator(self.api)
            self.instruments = self.api.get_otc_instruments() or FALLBACK_INSTRUMENTS
            self.signals = []
            self.worker = None
            
            self.init_ui()
            self.init_tray()
            self.init_status_bar()
            self.start_signal_worker()
            
            # Schedule daily reload
            schedule.every().day.at("00:00").do(self.reload_previous_day)
            
        except Exception as e:
            self.show_error(f"Initialization failed: {str(e)}")
    
    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Title
        title = QLabel("OTC Trading Signal System")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #2c3e50;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Instruments
        instruments_label = QLabel(f"Monitoring: {', '.join(self.instruments[:5])}")
        instruments_label.setFont(QFont("Arial", 10))
        instruments_label.setStyleSheet("color: #34495e;")
        main_layout.addWidget(instruments_label)
        
        # Signal list
        self.signal_list = QListWidget()
        self.signal_list.setFont(QFont("Consolas", 10))
        self.signal_list.setStyleSheet("""
            QListWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        main_layout.addWidget(self.signal_list)
        
        # Button panel
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ Start Monitoring")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.start_btn.clicked.connect(self.start_signal_worker)
        button_layout.addWidget(self.start_btn)
        
        stop_btn = QPushButton("⏹ Stop Monitoring")
        stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        stop_btn.clicked.connect(self.stop_signal_worker)
        button_layout.addWidget(stop_btn)
        
        reload_btn = QPushButton("🔄 Reload Data")
        reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        reload_btn.clicked.connect(self.reload_previous_day)
        button_layout.addWidget(reload_btn)
        
        main_layout.addLayout(button_layout)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
    
    def init_status_bar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setFont(QFont("Arial", 9))
        self.status_bar.showMessage("System ready")
        self.setStatusBar(self.status_bar)
    
    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(QIcon("assets/signal_icon.ico"), self)
        tray_menu = QMenu()
        
        show_action = tray_menu.addAction("📊 Show Dashboard")
        show_action.triggered.connect(self.show)
        
        exit_action = tray_menu.addAction("🚪 Exit")
        exit_action.triggered.connect(self.close_app)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_activated)
    
    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
    
    def start_signal_worker(self):
        if self.worker and self.worker.isRunning():
            return
            
        self.worker = SignalWorker(self.signal_gen, self.instruments[:5])
        self.worker.signal_detected.connect(self.process_signal)
        self.worker.status_update.connect(self.status_bar.showMessage)
        self.worker.start()
        self.start_btn.setText("🟢 Monitoring...")
        self.start_btn.setEnabled(False)
    
    def stop_signal_worker(self):
        if self.worker:
            self.worker.stop()
            self.worker.quit()
            self.worker.wait()
            self.start_btn.setText("▶ Start Monitoring")
            self.start_btn.setEnabled(True)
            self.status_bar.showMessage("Monitoring stopped")
    
    def reload_previous_day(self):
        self.status_bar.showMessage("Reloading historical data...")
        try:
            self.signal_gen.load_previous_day()
            self.status_bar.showMessage("Historical data reloaded")
        except Exception as e:
            self.status_bar.showMessage(f"⚠️ Reload error: {str(e)}")
    
    def process_signal(self, instrument, signal):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        signal_text = f"[{timestamp}] {instrument}: {signal}"
        
        # Add to GUI
        self.signals.insert(0, signal_text)
        self.signal_list.clear()
        self.signal_list.addItems(self.signals[:20])
        
        # Send to Telegram
        try:
            self.telegram_bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"🚀 OTC SIGNAL\n{signal_text}\n#PocketOption #OTC"
            )
        except TelegramError as e:
            self.status_bar.showMessage(f"⚠️ Telegram error: {str(e)}")
        
        # System tray notification
        self.tray_icon.showMessage(
            "OTC Signal Alert",
            f"{instrument}: {signal}",
            QSystemTrayIcon.Information,
            5000
        )
    
    def show_error(self, message):
        error_label = QLabel(f"❌ {message}")
        error_label.setFont(QFont("Arial", 12))
        error_label.setStyleSheet("color: #e74c3c;")
        error_label.setAlignment(Qt.AlignCenter)
        
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(error_label)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
    
    def close_app(self):
        self.stop_signal_worker()
        QApplication.quit()
    
    def closeEvent(self, event):
        self.stop_signal_worker()
        self.tray_icon.hide()
        event.accept()

class ScheduleTimer(QTimer):
    def __init__(self):
        super().__init__()
        self.timeout.connect(self.run_schedules)
    
    def run_schedules(self):
        schedule.run_pending()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Schedule timer
    timer = ScheduleTimer()
    timer.start(60000)  # Check every minute
    
    window = TradingDashboard()
    window.show()
    sys.exit(app.exec_())
