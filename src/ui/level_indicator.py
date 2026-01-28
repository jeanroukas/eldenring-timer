from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen
import time

class LevelIndicatorOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        # Window Flags: Frameless, Always on Top, Tool (no taskbar icon), Transparent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput # Click through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # State
        self.lvl = 1
        self.pot = 1
        self.region = [0, 0, 100, 100]
        
        # Animation Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50) # 20 FPS for animation
        
        # Start hidden
        self.setGeometry(0, 0, 1, 1)

    def set_data(self, lvl, pot, region):
        self.lvl = lvl
        self.pot = pot
        self.region = region
        
        # If no level up, hide or shrink
        if self.pot <= self.lvl:
             if self.isVisible():
                 self.setGeometry(0, 0, 1, 1)
                 self.hide()
        else:
             # Handle dict or list region
             if isinstance(region, dict):
                 rx, ry, rw, rh = region.get("left", 0), region.get("top", 0), region.get("width", 100), region.get("height", 100)
             else:
                 rx, ry, rw, rh = region
                 
             cx = rx + rw // 2
             cy = ry + rh // 2
             
             size = 600  # Increased from 400 for larger neon circles
             if self.geometry().width() != size:
                 self.setGeometry(cx - size // 2, cy - size // 2, size, size)
             
             if not self.isVisible():
                 self.show()
             self.update()

    def paintEvent(self, event):
        if self.pot <= self.lvl: return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Concentric Circles
        count = self.pot - self.lvl
        # Safety cap
        count = min(count, 10)
        
        center = QPoint(self.width() // 2, self.height() // 2)
        
        # NEON EFFECT: Larger circles with gradient glow
        # Base Radius - INCREASED for better visibility
        base_radius = 100  # Was 60
        spacing = 35  # Was 20 - more space between circles
        
        # Pulsing Animation (Smooth, more dramatic)
        pulse = (abs(time.time() % 1.2 - 0.6) / 0.6) * 15  # Was 10
        
        for i in range(count):
            radius = base_radius + (i * spacing) + pulse
            
            # NEON GRADIENT: Draw multiple overlapping circles for glow effect
            # Outer glow (very transparent, wide)
            for glow_layer in range(3):
                glow_offset = (3 - glow_layer) * 8  # 24px, 16px, 8px
                glow_alpha = 30 + (glow_layer * 20)  # 30, 50, 70
                
                # Bright cyan-blue neon color
                color_glow = QColor(100, 200, 255, glow_alpha)
                pen_glow = QPen(color_glow, 12 - (glow_layer * 3))  # 12px, 9px, 6px
                painter.setPen(pen_glow)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(center, int(radius + glow_offset), int(radius + glow_offset))
            
            # Main bright circle (core neon)
            alpha = max(80, 255 - (i * 30))  # Brighter base alpha
            color_core = QColor(80, 180, 255, alpha)  # Bright electric blue
            pen_core = QPen(color_core, 8)  # Thick core
            painter.setPen(pen_core)
            painter.drawEllipse(center, int(radius), int(radius))
            
            # Inner highlight (white-ish center for neon effect)
            color_highlight = QColor(200, 230, 255, alpha // 2)
            pen_highlight = QPen(color_highlight, 3)
            painter.setPen(pen_highlight)
            painter.drawEllipse(center, int(radius - 2), int(radius - 2))
