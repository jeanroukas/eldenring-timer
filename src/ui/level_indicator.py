from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QRadialGradient, QBrush
import time

class LevelIndicatorOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # State
        self.lvl = 1
        self.pot = 1
        self.region = [0, 0, 100, 100]
        self._last_valid_cx = None
        self._last_valid_cy = None
        
        self._pulse_val = 0.0
        self._opacity = 0.0
        
        # Animation: Pulsing (Breathing)
        self.pulse_anim = QPropertyAnimation(self, b"pulse_val")
        self.pulse_anim.setDuration(2000)
        self.pulse_anim.setStartValue(0.0)
        self.pulse_anim.setEndValue(1.0)
        self.pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.pulse_anim.setLoopCount(-1)
        self.pulse_anim.start()

        # Animation: Opacity (Fade In/Out)
        self.fade_anim = QPropertyAnimation(self, b"opacity")
        self.fade_anim.setDuration(500)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Size (Fixed ultra-large canvas for glow)
        self.canvas_size = 600
        self.setGeometry(0, 0, 1, 1)

    @pyqtProperty(float)
    def pulse_val(self): return self._pulse_val
    @pulse_val.setter
    def pulse_val(self, v):
        self._pulse_val = v
        self.update()

    @pyqtProperty(float)
    def opacity(self): return self._opacity
    @opacity.setter
    def opacity(self, v):
        self._opacity = v
        self.update()

    def set_data(self, lvl, pot, region):
        self.lvl = lvl
        self.pot = pot
        
        target_opacity = 0.0
        if self.pot > self.lvl:
             target_opacity = 1.0
             
             # Handle region to find center
             if isinstance(region, dict):
                 rx, ry, rw, rh = region.get("left", 0), region.get("top", 0), region.get("width", 100), region.get("height", 100)
             else:
                 rx, ry, rw, rh = region
             
             # Only update position if region is "valid" (not full screen default [0,0,1920,1080] or tiny)
             # usually region is ~100-200px wide. If it's 0 or huge, it's invalid.
             is_valid = (20 < rw < 500)
             
             if is_valid:
                 self._last_valid_cx = rx + rw // 2
                 self._last_valid_cy = ry + rh // 2
             
             if self._last_valid_cx is not None:
                 size = self.canvas_size
                 # Update geometry if needed
                 if self.width() != size or abs(self.x() - (self._last_valid_cx - size//2)) > 5:
                     self.setGeometry(self._last_valid_cx - size // 2, self._last_valid_cy - size // 2, size, size)

        # Trigger Fade if state changed
        if target_opacity != self.fade_anim.endValue():
            self.fade_anim.stop()
            self.fade_anim.setEndValue(target_opacity)
            self.fade_anim.start()
            
            if target_opacity > 0 and not self.isVisible():
                self.show()

    def paintEvent(self, event):
        if self._opacity <= 0.01: return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)
        
        count = min(self.pot - self.lvl, 10)
        center = QPointF(self.width() / 2, self.height() / 2)
        
        # Base settings
        base_radius = 80
        spacing = 30
        
        # Pulse increases radius and decreases alpha slightly
        pulse_ext = self._pulse_val * 15
        
        for i in range(count):
            radius = base_radius + (i * spacing) + pulse_ext
            
            # 1. OUTER GLOW (Radial Gradient)
            glow_radius = radius + 30
            gradient = QRadialGradient(center, glow_radius)
            
            # Elden Ring Blue / Cyan mix
            color_inner = QColor(0, 150, 255, 60)
            color_outer = QColor(0, 80, 200, 0)
            
            gradient.setColorAt(radius / glow_radius, color_inner)
            gradient.setColorAt(1.0, color_outer)
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, int(glow_radius), int(glow_radius))
            
            # 2. CORE NEON LINE
            alpha = int(max(40, 200 - (i * 30)))
            core_color = QColor(100, 220, 255, alpha)
            
            # Subtle variation in thickness
            pen_width = 6 + (1.0 - self._pulse_val) * 2
            
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(core_color, pen_width))
            painter.drawEllipse(center, int(radius), int(radius))
            
            # 3. INNER HIGHLIGHT (Sharp White)
            highlight_color = QColor(255, 255, 255, alpha // 2)
            painter.setPen(QPen(highlight_color, 1.5))
            painter.drawEllipse(center, int(radius - 1), int(radius - 1))

