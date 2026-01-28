from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QGroupBox, 
                             QPushButton, QComboBox, QTabWidget, QFormLayout, QDoubleSpinBox, QSpinBox, QCheckBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from src.ui.region_selector import RegionSelector
from src.utils.startup_manager import StartupManager
import cv2
import numpy as np
import random

class OCRTunerWindow(QMainWindow):
    update_image_signal = pyqtSignal(str, object, float) # name, cv_image, conf

    def __init__(self, vision_service, config_service, db_service=None, audio_service=None, state_service=None, parent=None):
        super().__init__(parent)
        self.vision_service = vision_service
        self.config_service = config_service
        self.db_service = db_service
        self.audio_service = audio_service
        self.state_service = state_service

        
        # Register Image Callback
        self.vision_service.set_debug_image_callback(self.receive_image)
        self.update_image_signal.connect(self.display_image)

        self.setWindowTitle("Elden Ring Nightreign Timer - Settings (F9)")
        self.setGeometry(100, 100, 500, 600)
        # self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool) # Removed Tool to allow Alt-Tab

        
        # Local State for profiles
        self.profiles = {
            "Runes": {"scale": 1.0, "gamma": 1.9, "thresh": 255, "dilate": 0, "psm": 7, "mode": "Digits", "padding": 20},
            "Level": {"scale": 4.0, "gamma": 0.6, "thresh": 160, "dilate": 1, "psm": 7, "mode": "Digits", "padding": 20},
            "Day":   {"scale": 1.0, "gamma": 0.5, "thresh": 180, "dilate": 0, "psm": 6, "mode": "Custom", "padding": 20}
        }
        # Try to load from vision service config if available
        if self.vision_service.engine:
             saved = self.vision_service.engine.ocr_params
             for k, v in saved.items():
                 if k in self.profiles:
                     self.profiles[k].update(v)
                     
        self.current_profile = "Runes"
        self.sliders = {} # Key -> (Slider, Label)
        self.selectors = {} # Key -> Combo

        # Styles
        self.setStyleSheet("""
            QWidget { background-color: #222; color: #EEE; font-family: 'Segoe UI'; }
            QGroupBox { border: 1px solid #555; margin-top: 10px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QSlider::handle:horizontal { background: #E6C200; width: 14px; border-radius: 7px; margin: -5px 0; }
            QSlider::groove:horizontal { height: 4px; background: #444; border-radius: 2px; }
            QComboBox { background: #333; border: 1px solid #555; padding: 5px; color: #E6C200; font-weight: bold; }
        """)

        
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Setup Tabs
        self.setup_tuner_tab()
        self.setup_general_tab()
        self.setup_curve_tab()
        self.setup_capture_tab()
        self.setup_simulation_tab()
        if self.db_service:
            self.setup_stats_tab()
            
    def setup_simulation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        title = QLabel("GRAPH & EVENT SIMULATION")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007bff; margin-bottom: 10px;")
        layout.addWidget(title)
        
        info = QLabel("Use these to test UI markers without waiting for a full run.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #AAA; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(info)

        # Markers Group
        group = QGroupBox("Graph Markers")
        vbox = QVBoxLayout()
        
        btn_shrink = QPushButton("Simulate 'End Shrink 1.1'")
        btn_shrink.clicked.connect(lambda: self.simulate_event("SHRINK", "End Shrink 1.1"))
        vbox.addWidget(btn_shrink)
        
        btn_boss = QPushButton("Simulate 'Boss 1'")
        btn_boss.clicked.connect(lambda: self.simulate_event("BOSS", "Boss 1"))
        vbox.addWidget(btn_boss)
        
        btn_death = QPushButton("Simulate 'Death'")
        btn_death.clicked.connect(lambda: self.simulate_event("DEATH", ""))
        vbox.addWidget(btn_death)
        
        group.setLayout(vbox)
        layout.addWidget(group)
        layout.addStretch()
        
        # ADD TAB TO THE WIDGET
        self.tabs.addTab(tab, "Simulate")

    def simulate_event(self, evt_type, details):
        if not self.state_service or not self.state_service.session:
            print("Simulation failed: StateService or Session not available.")
            return
            
        import time
        self.state_service.session.graph_events.append({
            "t": time.time(),
            "type": evt_type,
            "details": details
        })
        print(f"Simulated {evt_type} event added.")
        # Trigger UI Update
        if hasattr(self.state_service, "update_runes_display"):
            self.state_service.update_runes_display(self.state_service.session.current_run_level)

    def setup_tuner_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Title (Moved inside tab)
        title = QLabel("REAL-TIME OCR TUNER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #E6C200; margin-bottom: 5px;")
        layout.addWidget(title)

        
        # Profile Selector
        hbox_profile = QHBoxLayout()
        hbox_profile.addWidget(QLabel("Target Profile:"))
        self.combo_profile = QComboBox()
        self.combo_profile.addItems(["Runes", "Level", "Day"])
        self.combo_profile.currentTextChanged.connect(self.change_profile)
        hbox_profile.addWidget(self.combo_profile)
        
        # Save Button
        btn_save = QPushButton("Save Config")
        btn_save.setFixedWidth(80)
        btn_save.clicked.connect(self.save_profiles)
        btn_save.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
        btn_save.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
        hbox_profile.addWidget(btn_save)
        
        # Redefine Area Button
        self.btn_redefine = QPushButton("Redefine Area")
        self.btn_redefine.clicked.connect(self.start_redefine)
        self.btn_redefine.setStyleSheet("background-color: #6610f2; color: white;")
        hbox_profile.addWidget(self.btn_redefine)

        layout.addLayout(hbox_profile)
        
        # --- ADVANCED OCR SETTINGS ---
        group_adv = QGroupBox("Advanced OCR Settings")
        vbox_adv = QVBoxLayout()
        
        # PSM
        hbox_psm = QHBoxLayout()
        hbox_psm.addWidget(QLabel("Layout (PSM):"))
        self.combo_psm = QComboBox()
        self.combo_psm.addItem("Single Line (7)", 7)
        self.combo_psm.addItem("Single Block (6)", 6)
        self.combo_psm.addItem("Single Char (10)", 10)
        self.combo_psm.addItem("Sparse Text (11)", 11)
        self.combo_psm.currentIndexChanged.connect(lambda: self.on_combo_change("psm", self.combo_psm))
        hbox_psm.addWidget(self.combo_psm)
        vbox_adv.addLayout(hbox_psm)
        self.selectors["psm"] = self.combo_psm
        
        # Mode
        hbox_mode = QHBoxLayout()
        hbox_mode.addWidget(QLabel("Analysis Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Digits", "Alphanumeric", "Uppercase", "Custom"])
        self.combo_mode.currentTextChanged.connect(lambda t: self.on_combo_change("mode", self.combo_mode))
        hbox_mode.addWidget(self.combo_mode)
        vbox_adv.addLayout(hbox_mode)
        self.selectors["mode"] = self.combo_mode
        
        group_adv.setLayout(vbox_adv)
        layout.addWidget(group_adv)

        # --- LIVE PREVIEW ---
        group_preview = QGroupBox("Live OCR Preview")
        vbox_prev = QVBoxLayout()
        self.preview_label = QLabel("No Signal")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setStyleSheet("background-color: #222; border: 1px solid #555;") # Grey background to see black padding
        vbox_prev.addWidget(self.preview_label)
        
        self.conf_label = QLabel("Comparaison: --%")
        self.conf_label.setStyleSheet("color: #AAA; font-size: 11px;")
        self.conf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox_prev.addWidget(self.conf_label)
        
        group_preview.setLayout(vbox_prev)
        layout.addWidget(group_preview)

        # Scale Control
        group_scale = self.create_slider_group("scale", "Scale (Zoom)", 1, 60, self.profiles["Runes"]["scale"] * 10, "x{:.1f}")
        layout.addWidget(group_scale)

        # Gamma Control
        group_gamma = self.create_slider_group("gamma", "Gamma (Contrast)", 1, 30, self.profiles["Runes"]["gamma"] * 10, "{:.1f}")
        layout.addWidget(group_gamma)

        # Threshold Control
        group_thresh = self.create_slider_group("thresh", "Threshold (B/W)", 0, 255, self.profiles["Runes"]["thresh"], "{:.0f}")
        layout.addWidget(group_thresh)

        # Dilation Control
        group_dilate = self.create_slider_group("dilate", "Dilate (Thickness)", 0, 5, self.profiles["Runes"]["dilate"], "{:.0f}")
        layout.addWidget(group_dilate)
        
        # Padding Control
        group_padding = self.create_slider_group("padding", "Padding (Border)", 0, 100, self.profiles["Runes"]["padding"], "{:.0f}")
        layout.addWidget(group_padding)
        
        # --- DATA COLLECTION ---
        group_capture = QGroupBox("Training Data Collection")
        vbox_cap = QVBoxLayout()
        
        btn_cap_level = QPushButton("Capture LEVEL Sample")
        btn_cap_level.clicked.connect(lambda: self.capture("Level", btn_cap_level))
        
        btn_cap_runes = QPushButton("Capture RUNES Sample")
        btn_cap_runes.clicked.connect(lambda: self.capture("Runes", btn_cap_runes))
        
        btn_cap_day = QPushButton("Capture DAY Sample")
        btn_cap_day.clicked.connect(lambda: self.capture("Day", btn_cap_day))
        
        vbox_cap.addWidget(btn_cap_level)
        vbox_cap.addWidget(btn_cap_runes)
        vbox_cap.addWidget(btn_cap_day)
        
        group_capture.setLayout(vbox_cap)
        layout.addWidget(group_capture)
        
        layout.addWidget(group_capture)
        layout.addStretch()
        self.tabs.addTab(tab, "OCR Tuner")

    # --- SETTINGS TABS ---

    def setup_general_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.chk_debug_logs = QCheckBox("Enable Debug Logs")
        self.chk_debug_logs.setChecked(self.config_service.get("debug_mode", False))
        
        self.chk_save_images = QCheckBox("Save Debug Images")
        self.chk_save_images.setChecked(self.config_service.get("save_debug_images", False))

        self.chk_training_data = QCheckBox("Collect Training Data (Raw)")
        self.chk_training_data.setChecked(self.config_service.get("save_raw_samples", True))

        self.chk_auto_hibernate = QCheckBox("Mode Auto-Hibernation")
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

        self.btn_test_audio = QPushButton("Test Audio (Random)")
        self.btn_test_audio.clicked.connect(self.test_audio)
        
        audio_layout.addWidget(self.chk_audio_enabled)
        audio_layout.addLayout(volume_layout)
        audio_layout.addWidget(self.btn_test_audio)
        
        # Save Button for General Tab
        btn_save_gen = QPushButton("Sauvegarder les Paramètres")
        btn_save_gen.clicked.connect(self.save_general_settings)
        
        layout.addRow(self.chk_debug_logs)
        layout.addRow(self.chk_save_images)
        layout.addRow(self.chk_training_data)
        layout.addRow(self.chk_auto_hibernate)
        layout.addRow(self.chk_run_at_startup)
        layout.addWidget(audio_group)
        layout.addRow(btn_save_gen)

        self.tabs.addTab(tab, "General")

    def setup_curve_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        nr_config = self.config_service.get("nr_config", {})
        
        self.spin_snowball_d1 = QDoubleSpinBox()
        self.spin_snowball_d1.setRange(1.0, 3.0)
        self.spin_snowball_d1.setSingleStep(0.01)
        self.spin_snowball_d1.setValue(nr_config.get("snowball_d1", 1.35))
        layout.addRow("Snowball Day 1:", self.spin_snowball_d1)
        
        self.spin_snowball_d2 = QDoubleSpinBox()
        self.spin_snowball_d2.setRange(1.0, 3.0)
        self.spin_snowball_d2.setSingleStep(0.01)
        self.spin_snowball_d2.setValue(nr_config.get("snowball_d2", 1.15))
        layout.addRow("Snowball Day 2:", self.spin_snowball_d2)
        
        self.spin_goal = QSpinBox()
        self.spin_goal.setRange(100000, 2000000)
        self.spin_goal.setSingleStep(1000)
        self.spin_goal.setValue(nr_config.get("goal", 512936))
        layout.addRow("Total Runes Goal:", self.spin_goal)
        
        btn_save_curve = QPushButton("Sauvegarder Courbe")
        btn_save_curve.clicked.connect(self.save_curve_settings)
        layout.addRow(btn_save_curve)
        
        self.tabs.addTab(tab, "Ideal Curve")

    def setup_capture_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.btn_select_region = QPushButton("Select Timer Region")
        # Logic to be connected in main
        layout.addWidget(self.btn_select_region)
        self.btn_select_level_region = QPushButton("Select Level Region")
        layout.addWidget(self.btn_select_level_region)
        self.btn_select_runes_region = QPushButton("Select Runes Region")
        layout.addWidget(self.btn_select_runes_region)
        self.btn_select_runes_icon_region = QPushButton("Select Runes Icon Region")
        layout.addWidget(self.btn_select_runes_icon_region)
        self.btn_select_char_region = QPushButton("Select Main Menu Region")
        layout.addWidget(self.btn_select_char_region)
        layout.addStretch()
        self.tabs.addTab(tab, "Capture Areas")

    def setup_stats_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.stats_layout_container = layout
        self.refresh_stats()
        self.tabs.addTab(tab, "Statistics")

    def refresh_stats(self):
        # Clear existing
        while self.stats_layout_container.count():
             item = self.stats_layout_container.takeAt(0)
             if item.widget(): item.widget().deleteLater()
             
        stats = self.db_service.get_stats()
        if not stats:
            self.stats_layout_container.addRow(QLabel("No statistics available."))
        else:
            self.stats_layout_container.addRow("Total Runs:", QLabel(str(stats.get("total_runs", 0))))
            self.stats_layout_container.addRow("Victories:", QLabel(str(stats.get("victories", 0))))
            self.stats_layout_container.addRow("Win Rate:", QLabel(stats.get("win_rate", "N/A")))
             
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_stats)
        self.stats_layout_container.addRow(btn_refresh)

    def on_volume_changed(self, value):
        self.lbl_volume_val.setText(f"{value}%")
        self.config_service.set("audio_volume", value)

    def test_audio(self):
        if self.audio_service:
            self.audio_service.announce("Test Audio OK")

    def save_general_settings(self):
        self.config_service.set("debug_mode", self.chk_debug_logs.isChecked())
        self.config_service.set("save_debug_images", self.chk_save_images.isChecked())
        self.config_service.set("save_raw_samples", self.chk_training_data.isChecked())
        self.config_service.set("auto_hibernate", self.chk_auto_hibernate.isChecked())
        self.config_service.set("audio_enabled", self.chk_audio_enabled.isChecked())
        
        if self.chk_run_at_startup.isChecked(): StartupManager.enable()
        else: StartupManager.disable()
        
        self.config_service.save()
        
    def save_curve_settings(self):
        nr_config = self.config_service.get("nr_config", { "duration": 1680, "goal": 512936 })
        nr_config["snowball_d1"] = self.spin_snowball_d1.value()
        nr_config["snowball_d2"] = self.spin_snowball_d2.value()
        nr_config["goal"] = self.spin_goal.value()
        self.config_service.set("nr_config", nr_config)
        self.config_service.save()

    def change_profile(self, new_profile):
        self.current_profile = new_profile
        params = self.profiles[new_profile]
        
        # Block signals to avoid re-triggering updates during ui switch
        self.blockSignals(True)
        self.update_slider_ui("scale", params["scale"] * 10)
        self.update_slider_ui("gamma", params["gamma"] * 10)
        self.update_slider_ui("thresh", params["thresh"])
        self.update_slider_ui("dilate", params["dilate"])
        self.update_slider_ui("padding", params["padding"])
        
        # Sync combos
        self.sync_combos(params)
        
        self.blockSignals(False)

    def sync_combos(self, params):
        # find index for psm
        psm_val = params.get("psm", 7)
        idx = self.combo_psm.findData(psm_val)
        if idx >= 0: self.combo_psm.setCurrentIndex(idx)
        
        # find text for mode
        mode_val = params.get("mode", "Digits")
        self.combo_mode.setCurrentText(mode_val)

    def on_combo_change(self, key, combo):
        if self.signalsBlocked(): return
        val = combo.currentData() if hasattr(combo, 'currentData') and combo.currentData() is not None else combo.currentText()
        if val is None: val = combo.currentText()
        
        self.profiles[self.current_profile][key] = val
        self.vision_service.set_ocr_param(self.current_profile, key, val)

    def start_redefine(self):
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self.on_region_selected)
        self.selector.show()
        
    def on_region_selected(self, rect):
        # Use new specialized method
        if hasattr(self.vision_service, "set_region_tuner"):
            self.vision_service.set_region_tuner(self.current_profile, rect)
        else:
            # Fallback legacy
            self.vision_service.set_region(self.current_profile, rect)
            
        print(f"OCRTuner: Redefined {self.current_profile} area to {rect}")
        
    def update_slider_ui(self, key, slider_val):
        if key in self.sliders:
            slider, label = self.sliders[key]
            slider.blockSignals(True)
            slider.setValue(int(slider_val))
            slider.blockSignals(False)
            
            # Update label text
            # Dirty re-calc of visual val
            is_float = key in ["scale", "gamma"]
            display_val = slider_val / 10.0 if is_float else slider_val
            fmt = "x{:.1f}" if key == "scale" else "{:.1f}" if key == "gamma" else "{:.0f}"
            label.setText(fmt.format(display_val))

    def create_slider_group(self, key, label_text, min_val, max_val, default_val, format_str):
        group = QGroupBox(label_text)
        vbox = QVBoxLayout()
        
        hbox = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(int(default_val))
        
        is_float = key in ["scale", "gamma"]
        display_val = default_val / 10.0 if is_float else default_val
        val_label = QLabel(format_str.format(display_val))
        val_label.setFixedWidth(40)
        val_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.sliders[key] = (slider, val_label)
        
        slider.valueChanged.connect(lambda v: self.on_slider_change(key, v, val_label, format_str, is_float))
        
        hbox.addWidget(slider)
        hbox.addWidget(val_label)
        vbox.addLayout(hbox)
        group.setLayout(vbox)
        
        return group

    def on_slider_change(self, key, value, label_widget, format_str, is_float_x10):
        real_val = value / 10.0 if is_float_x10 else value
        label_widget.setText(format_str.format(real_val))
        
        # update local state
        self.profiles[self.current_profile][key] = real_val
        
        # send to service
        self.vision_service.set_ocr_param(self.current_profile, key, real_val)

    def receive_image(self, name: str, image: np.ndarray, conf: float):
        """Called from Background Thread."""
        self.update_image_signal.emit(name, image, conf)

    def display_image(self, name: str, image: np.ndarray, conf: float):
        """Called on Main Thread."""
        # Only show the currently selected profile
        if name != self.current_profile:
            return
            
        # Update Conf
        self.conf_label.setText(f"Confiance: {conf:.1f}%")
        if conf > 80:
            self.conf_label.setStyleSheet("color: #0F0; font-weight: bold;")
        elif conf > 50:
             self.conf_label.setStyleSheet("color: #FA0; font-weight: bold;")
        else:
             self.conf_label.setStyleSheet("color: #F00; font-weight: bold;")

        if image is None: return
        
        # Convert CV2 (Gray/Binary) to QImage
        h, w = image.shape
        bytes_per_line = w
        
        # --- PADDING DEBUG ---
        current_params = self.profiles.get(self.current_profile, {})
        padding = int(current_params.get("padding", 0))
        if name == "Day":
            print(f"[TUNER DEBUG] Day Image Rx: {w}x{h}, Padding: {padding}, Rect: {w-2*padding}x{h-2*padding}")
        # ---------------------
        
        # Start with QImage based on data
        # Note: image.data must be kept alive, but here we likely copy via QPixmap
        q_img = QImage(image.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
        
        # Scale for visibility
        pixmap = QPixmap.fromImage(q_img)
        
        # --- PADDING VISUALIZATION ---
        # Draw a red rectangle to show the effective area after padding
        from PyQt6.QtGui import QPainter, QPen, QColor
        current_params = self.profiles.get(self.current_profile, {})
        padding = int(current_params.get("padding", 0))
        
        if padding > 0:
            painter = QPainter(pixmap)
            pen = QPen(QColor(255, 0, 0)) # Red
            pen.setWidth(2)
            painter.setPen(pen)
            
            # Rect is (x, y, w, h)
            # We want to show what remains, so we draw the inner rect
            rect_w = w - (padding * 2)
            rect_h = h - (padding * 2)
            
            if rect_w > 0 and rect_h > 0:
                painter.drawRect(padding, padding, rect_w, rect_h)
            painter.end()

        if w < 100:
             pixmap = pixmap.scaled(w * 2, h * 2, Qt.AspectRatioMode.KeepAspectRatio)
        
        self.preview_label.setPixmap(pixmap)

    def capture(self, category, btn):
        self.vision_service.capture_training_sample(category)
        # Visual feedback
        original_text = btn.text()
        btn.setText("Capturé !")
        btn.setStyleSheet("background-color: #28a745; color: white;")
        QTimer.singleShot(1000, lambda: self._reset_btn(btn, original_text))
        
    def _reset_btn(self, btn, text):
        btn.setText(text)
        btn.setStyleSheet("")

    def save_profiles(self):
        """Persist current settings to config."""
        # For now, we assume VisionService has a save method or we implement it
        # Actually, best way is to dump self.profiles to config service via vision service
        try:
            self.vision_service.save_ocr_profiles(self.profiles)
            # Visual feedback on save button (trickier since we created it locally)
            # Just print for now or use a status label if we had one.
            # Ideally btn_save should be a class member.
        except Exception as e:
            print(f"Failed to save profile: {e}")

    def showEvent(self, event):
        self.vision_service.set_tuning_active(True)
        super().showEvent(event)

    def closeEvent(self, event):
        self.vision_service.set_tuning_active(False)
        super().closeEvent(event)
