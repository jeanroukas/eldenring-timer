import sys
import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QGroupBox, QListWidget, QProgressBar, 
                             QFormLayout, QGridLayout)
from PyQt6.QtCore import QTimer, Qt

class StateInspectorWindow(QMainWindow):
    def __init__(self, state_service):
        super().__init__()
        self.state_service = state_service
        self.setWindowTitle("ER Timer - State Inspector")
        self.setMinimumSize(500, 600)
        
        # Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        self.setup_ui()
        
        # Refresh Timer (500ms)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500)

    def setup_ui(self):
        # 1. Game State Group
        self.grp_game = QGroupBox("Game State")
        full_layout = QHBoxLayout(self.grp_game)
        
        # Left Col
        col1 = QFormLayout()
        self.lbl_phase = QLabel("Unknown")
        self.lbl_runes = QLabel("0")
        self.lbl_level = QLabel("1")
        col1.addRow("Phase:", self.lbl_phase)
        col1.addRow("Runes:", self.lbl_runes)
        col1.addRow("Level:", self.lbl_level)
        
        # Right Col
        col2 = QFormLayout()
        self.lbl_merchant = QLabel("0")
        self.lbl_death = QLabel("0")
        self.lbl_black_screen = QLabel("No")
        self.lbl_black_screen.setStyleSheet("color: gray; font-weight: bold;")
        col2.addRow("Spent:", self.lbl_merchant)
        col2.addRow("Desths:", self.lbl_death)
        col2.addRow("Black Screen:", self.lbl_black_screen)
        
        full_layout.addLayout(col1)
        full_layout.addLayout(col2)
        self.main_layout.addWidget(self.grp_game)
        
        # 2. OCR Engine Group
        self.grp_ocr = QGroupBox("OCR Engine & Logic")
        ocr_layout = QGridLayout(self.grp_ocr)
        
        ocr_layout.addWidget(QLabel("Next Scan (Cooldown):"), 0, 0)
        self.bar_cooldown = QProgressBar()
        self.bar_cooldown.setRange(0, 60)
        self.bar_cooldown.setFormat("%v s")
        ocr_layout.addWidget(self.bar_cooldown, 0, 1)
        
        ocr_layout.addWidget(QLabel("OCR Mode:"), 1, 0)
        self.lbl_ocr_mode = QLabel("Normal")
        ocr_layout.addWidget(self.lbl_ocr_mode, 1, 1)
        
        ocr_layout.addWidget(QLabel("Last Text:"), 2, 0)
        self.lbl_last_text = QLabel("-")
        self.lbl_last_text.setStyleSheet("color: blue;")
        ocr_layout.addWidget(self.lbl_last_text, 2, 1)
        
        ocr_layout.addWidget(QLabel("Buffers:"), 3, 0)
        self.lbl_buffers = QLabel("Trigger: 0 | Consensus: 0")
        ocr_layout.addWidget(self.lbl_buffers, 3, 1)
        
        self.main_layout.addWidget(self.grp_ocr)
        
        # 3. Doubts / Warnings Log
        self.grp_log = QGroupBox("Doubts / Warnings Log")
        log_layout = QVBoxLayout(self.grp_log)
        self.list_log = QListWidget()
        log_layout.addWidget(self.list_log)
        self.main_layout.addWidget(self.grp_log)
        
    def update_ui(self):
        if not self.state_service: return
        
        debug_data = self.state_service.get_debug_state()
        vision_data = debug_data.get("vision", {})
        
        # Update Game State
        self.lbl_phase.setText(f"{debug_data.get('phase')} ({debug_data.get('phase_index')})")
        
        runes = debug_data.get('runes', 0)
        pending_loss = debug_data.get('pending_loss', 0)
        runes_text = f"{runes}"
        if pending_loss > 0:
            runes_text += f" (LOST? {pending_loss})"
        self.lbl_runes.setText(runes_text)
        
        self.lbl_level.setText(str(debug_data.get('level', 1)))
        self.lbl_merchant.setText(str(debug_data.get('spent_merchants', 0)))
        self.lbl_death.setText(str(debug_data.get('death_count', 0)))
        
        bs = debug_data.get('black_screen', {})
        if bs.get('active'):
            dur = bs.get('duration', 0)
            self.lbl_black_screen.setText(f"YES ({dur:.1f}s)")
            self.lbl_black_screen.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_black_screen.setText("NO")
            self.lbl_black_screen.setStyleSheet("color: gray;")
            
        # Update OCR State
        rem = vision_data.get("cooldown_remaining", 0)
        self.bar_cooldown.setValue(int(rem))
        if rem > 0:
            self.bar_cooldown.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else:
            self.bar_cooldown.setStyleSheet("QProgressBar::chunk { background-color: green; }")
            
        mode_text = "High Performance"
        if vision_data.get("is_low_power_mode"):
            mode_text = "Low Power (Noise Throttle)"
            self.lbl_ocr_mode.setStyleSheet("color: orange;")
        elif rem > 0:
            mode_text = "Cooldown (Paused)"
            self.lbl_ocr_mode.setStyleSheet("color: red;")
        else:
            self.lbl_ocr_mode.setStyleSheet("color: green;")
        self.lbl_ocr_mode.setText(mode_text)
        
        last_conf = vision_data.get("last_conf", 0)
        self.lbl_last_text.setText(f"'{vision_data.get('last_text', '')}' ({int(last_conf)}%)")
        
        self.lbl_buffers.setText(f"Trigger: {debug_data.get('buffer_size')} | Consensus: {debug_data.get('level_consensus')}")
        
        # Update Log
        current_rows = self.list_log.count()
        warnings = debug_data.get("recent_warnings", [])
        
        # Simple Logic: Clear and refill if different length or naive check
        # Since it's a small window (20 items), full refresh is fine
        self.list_log.clear()
        for w in reversed(warnings): # Show newest top
            self.list_log.addItem(w)
