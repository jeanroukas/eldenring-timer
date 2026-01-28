from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QGroupBox, QPushButton, QComboBox
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from src.ui.region_selector import RegionSelector
import cv2
import numpy as np

class OCRTunerWindow(QWidget):
    update_image_signal = pyqtSignal(str, object, float) # name, cv_image, conf

    def __init__(self, vision_service, parent=None):
        super().__init__(parent)
        self.vision_service = vision_service
        
        # Register Image Callback
        self.vision_service.set_debug_image_callback(self.receive_image)
        self.update_image_signal.connect(self.display_image)

        self.setWindowTitle("OCR Tuner (Runes/Level)")
        self.setGeometry(100, 100, 300, 450)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        
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

        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
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
        
        layout.addStretch()

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
        # Start with QImage based on data
        # Note: image.data must be kept alive, but here we likely copy via QPixmap
        q_img = QImage(image.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
        
        # Scale for visibility
        pixmap = QPixmap.fromImage(q_img)
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
