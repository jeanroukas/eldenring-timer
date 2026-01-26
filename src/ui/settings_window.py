import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QCheckBox, QTabWidget, QLabel, 
                             QSlider, QFormLayout, QGroupBox, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from src.services.base_service import IConfigService, IDatabaseService, IAudioService
from src.utils.startup_manager import StartupManager
import random

class SettingsWindow(QMainWindow):
    def __init__(self, config_service: IConfigService, db_service: IDatabaseService = None, audio_service: IAudioService = None):
        super().__init__()
        self.config_service = config_service
        self.db_service = db_service
        self.audio_service = audio_service
        self.setWindowTitle("Elden Ring Timer Settings")
        self.setMinimumSize(400, 300)

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tabs
        self.setup_general_tab()
        self.setup_capture_tab()
        self.setup_ocr_tab()
        if self.db_service:
            self.setup_stats_tab()

        # Footer Buttons
        footer = QHBoxLayout()
        self.btn_save = QPushButton("Save & Close")
        self.btn_save.clicked.connect(self.save_and_close)
        footer.addStretch()
        footer.addWidget(self.btn_save)
        main_layout.addLayout(footer)

    def setup_general_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.chk_debug_logs = QCheckBox("Enable Debug Logs")
        self.chk_debug_logs.setChecked(self.config_service.get("debug_mode", False))
        
        self.chk_save_images = QCheckBox("Save Debug Images")
        self.chk_save_images.setChecked(self.config_service.get("save_debug_images", False))

        self.chk_training_data = QCheckBox("Collect Training Data (Raw)")
        self.chk_training_data.setChecked(self.config_service.get("save_raw_samples", True))

        self.chk_auto_hibernate = QCheckBox("Mode Auto-Hibernation (Activé = Pause si jeu absent)")
        self.chk_auto_hibernate.setChecked(self.config_service.get("auto_hibernate", True))
        
        self.chk_run_at_startup = QCheckBox("Démarrer avec Windows")
        self.chk_run_at_startup.setChecked(StartupManager.is_enabled())

        audio_group = QGroupBox("Audio (TTS)")
        audio_layout = QVBoxLayout(audio_group)

        self.chk_audio_enabled = QCheckBox("Activer les annonces vocales")
        self.chk_audio_enabled.setChecked(self.config_service.get("audio_enabled", True))
        
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.slider_volume = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(int(self.config_service.get("audio_volume", 50)))
        volume_layout.addWidget(self.slider_volume)
        self.lbl_volume_val = QLabel(f"{self.slider_volume.value()}%")
        volume_layout.addWidget(self.lbl_volume_val)
        self.slider_volume.valueChanged.connect(self.on_volume_changed)

        # Speed Slider
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Vitesse:"))
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(50, 300) # pyttsx3 rate
        self.slider_speed.setValue(int(self.config_service.get("audio_rate", 165)))
        speed_layout.addWidget(self.slider_speed)
        self.lbl_speed_val = QLabel(str(self.slider_speed.value()))
        speed_layout.addWidget(self.lbl_speed_val)
        self.slider_speed.valueChanged.connect(self.on_speed_changed)

        # Device Selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Sortie:"))
        self.combo_device = QComboBox()
        self.populate_audio_devices()
        device_layout.addWidget(self.combo_device)
        self.combo_device.currentIndexChanged.connect(self.on_device_changed)

        # Voice Selection
        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel("Voix:"))
        self.combo_voice = QComboBox()
        self.populate_audio_voices()
        voice_layout.addWidget(self.combo_voice)
        self.combo_voice.currentIndexChanged.connect(self.on_voice_changed)

        self.btn_test_audio = QPushButton("Test Audio (Random)")
        self.btn_test_audio.clicked.connect(self.test_audio)
        
        audio_layout.addWidget(self.chk_audio_enabled)
        audio_layout.addLayout(volume_layout)
        audio_layout.addLayout(speed_layout)
        audio_layout.addLayout(device_layout)
        audio_layout.addLayout(voice_layout)
        audio_layout.addWidget(self.btn_test_audio)

        layout.addRow(self.chk_debug_logs)
        layout.addRow(self.chk_save_images)
        layout.addRow(self.chk_training_data)
        layout.addRow(self.chk_auto_hibernate)
        layout.addRow(self.chk_run_at_startup)
        layout.addWidget(audio_group)

        self.tabs.addTab(tab, "General")

    def setup_capture_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        layout.addWidget(QLabel("Capture region is currently set via the 'Select Region' button."))
        
        self.btn_select_region = QPushButton("Select Timer Region")
        # Note: self.select_region will be provided by a callback or delegate
        layout.addWidget(self.btn_select_region)
        
        self.btn_select_level_region = QPushButton("Select Level Region")
        layout.addWidget(self.btn_select_level_region)
        
        self.btn_select_runes_region = QPushButton("Select Runes Region")
        layout.addWidget(self.btn_select_runes_region)

        self.btn_select_runes_icon_region = QPushButton("Select Runes Icon Region")
        layout.addWidget(self.btn_select_runes_icon_region)

        self.btn_select_char_region = QPushButton("Select Main Menu Region (Auto-Reset)")
        layout.addWidget(self.btn_select_char_region)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Capture")

    def setup_ocr_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("OCR Sensitivity")
        form = QFormLayout(group)
        
        # Placeholder for real sliders if we add them to config
        self.lbl_info = QLabel("OCR parameters are currently managed automatically by the Vision Engine.")
        form.addRow(self.lbl_info)
        
        layout.addWidget(group)
        layout.addStretch()
        layout.addWidget(group)
        layout.addStretch()
        self.tabs.addTab(tab, "OCR")

    def setup_stats_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        stats = self.db_service.get_stats()
        
        if not stats:
            layout.addRow(QLabel("No statistics available."))
        else:
            layout.addRow("Total Runs:", QLabel(str(stats.get("total_runs", 0))))
            layout.addRow("Victories:", QLabel(str(stats.get("victories", 0))))
            layout.addRow("Win Rate:", QLabel(stats.get("win_rate", "N/A")))
            layout.addRow("Avg Duration:", QLabel(stats.get("avg_duration", "N/A")))
            
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(lambda: self.refresh_stats(layout))
        layout.addRow(btn_refresh)
        
        self.tabs.addTab(tab, "Statistics")

    def refresh_stats(self, layout):
        # Clear layout rows (hacky for QFormLayout)
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()
            
        stats = self.db_service.get_stats()
        if not stats:
            layout.addRow(QLabel("No statistics available."))
        else:
            layout.addRow("Total Runs:", QLabel(str(stats.get("total_runs", 0))))
            layout.addRow("Victories:", QLabel(str(stats.get("victories", 0))))
            layout.addRow("Win Rate:", QLabel(stats.get("win_rate", "N/A")))
            layout.addRow("Avg Duration:", QLabel(stats.get("avg_duration", "N/A")))
            
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(lambda: self.refresh_stats(layout))
        layout.addRow(btn_refresh)

    
    def on_volume_changed(self, value):
        self.lbl_volume_val.setText(f"{value}%")
        self.config_service.set("audio_volume", value)
    
    def on_speed_changed(self, value):
        self.lbl_speed_val.setText(str(value))
        self.config_service.set("audio_rate", value)
        
    def populate_audio_devices(self):
        if not self.audio_service: return
        self.combo_device.blockSignals(True)
        self.combo_device.clear()
        
        # Add Default Option
        self.combo_device.addItem("Par défaut", "")
        
        devices = self.audio_service.get_devices()
        current_id = self.config_service.get("audio_device_id", "")
        
        selected_index = 0
        for i, (dev_id, desc) in enumerate(devices):
            self.combo_device.addItem(desc, dev_id)
            if dev_id == current_id:
                selected_index = i + 1 # +1 because of default item
                
        self.combo_device.setCurrentIndex(selected_index)
        self.combo_device.blockSignals(False)

    def on_device_changed(self, index):
        dev_id = self.combo_device.currentData()
        self.config_service.set("audio_device_id", dev_id if dev_id else "")
        if self.audio_service:
            self.audio_service.set_device(dev_id if dev_id else "")

    def populate_audio_voices(self):
        if not self.audio_service: return
        self.combo_voice.blockSignals(True)
        self.combo_voice.clear()
        
        # Add Default Option
        self.combo_voice.addItem("Automatique (Hortense / Fr)", "")
        
        voices = self.audio_service.get_voices()
        current_id = self.config_service.get("audio_voice_id", "")
        
        selected_index = 0
        for i, (v_id, name) in enumerate(voices):
            self.combo_voice.addItem(name, v_id)
            if v_id == current_id:
                selected_index = i + 1
                
        self.combo_voice.setCurrentIndex(selected_index)
        self.combo_voice.blockSignals(False)

    def on_voice_changed(self, index):
        v_id = self.combo_voice.currentData()
        self.config_service.set("audio_voice_id", v_id if v_id else "")
        if self.audio_service:
            self.audio_service.set_voice(v_id if v_id else "")

    def on_volume_changed(self, value):
        self.lbl_volume_val.setText(f"{value}%")
        self.config_service.set("audio_volume", value)
        # Note: AudioService observes config, so it updates automatically
        
    def test_audio(self):
        if not self.audio_service: return
        
        phrases = [
            "La zone se refermera dans 4 minutes 30 secondes",
            "Fermeture de la zone dans 2 minutes",
            "Fermeture de la zone dans 1 minute",
            "Dans 30 secondes",
            "5 secondes",
            "La zone se referme",
            "Victoire !"
        ]
        phrase = random.choice(phrases)
        self.audio_service.announce(phrase)

    def save_and_close(self):
        # Update config service
        self.config_service.set("debug_mode", self.chk_debug_logs.isChecked())
        self.config_service.set("save_debug_images", self.chk_save_images.isChecked())
        self.config_service.set("save_raw_samples", self.chk_training_data.isChecked())
        self.config_service.set("auto_hibernate", self.chk_auto_hibernate.isChecked())
        self.config_service.set("audio_enabled", self.chk_audio_enabled.isChecked())
        self.config_service.set("audio_volume", self.slider_volume.value())
        
        # Handle Windows startup
        if self.chk_run_at_startup.isChecked():
            StartupManager.enable()
        else:
            StartupManager.disable()
        
        self.config_service.save()
        self.close()
