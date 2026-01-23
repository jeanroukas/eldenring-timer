import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QCheckBox, QTabWidget, QLabel, 
                             QSlider, QFormLayout, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal
from src.services.base_service import IConfigService, IDatabaseService

class SettingsWindow(QMainWindow):
    def __init__(self, config_service: IConfigService, db_service: IDatabaseService = None):
        super().__init__()
        self.config_service = config_service
        self.db_service = db_service
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

        self.chk_hdr_mode = QCheckBox("HDR Mode (WGC Capture)")
        self.chk_hdr_mode.setChecked(self.config_service.get("hdr_mode", False))

        self.chk_training_data = QCheckBox("Collect Training Data (Raw)")
        self.chk_training_data.setChecked(self.config_service.get("save_raw_samples", True))

        self.chk_auto_hibernate = QCheckBox("Masquer le timer si le jeu n'est pas lancé")
        self.chk_auto_hibernate.setChecked(self.config_service.get("auto_hibernate", True))

        layout.addRow(self.chk_debug_logs)
        layout.addRow(self.chk_save_images)
        layout.addRow(self.chk_hdr_mode)
        layout.addRow(self.chk_training_data)
        layout.addRow(self.chk_auto_hibernate)

        self.tabs.addTab(tab, "General")

    def setup_capture_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        layout.addWidget(QLabel("Capture region is currently set via the 'Select Region' button."))
        
        self.btn_select_region = QPushButton("Select Screen Region")
        # Note: self.select_region will be provided by a callback or delegate
        layout.addWidget(self.btn_select_region)
        
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

    def save_and_close(self):
        # Update config service
        self.config_service.set("debug_mode", self.chk_debug_logs.isChecked())
        self.config_service.set("save_debug_images", self.chk_save_images.isChecked())
        self.config_service.set("hdr_mode", self.chk_hdr_mode.isChecked())
        self.config_service.set("save_raw_samples", self.chk_training_data.isChecked())
        self.config_service.set("auto_hibernate", self.chk_auto_hibernate.isChecked())
        
        self.config_service.save()
        self.close()
