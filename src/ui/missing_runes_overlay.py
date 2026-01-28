from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics
import time

class MissingRunesOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        # Window Flags: Frameless, Always on Top, Tool (no taskbar icon), Transparent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput  # Click through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # State
        self.missing = 0
        self.is_max = False
        self.region = [0, 0, 100, 100]
        self.level_cost = 1  # Cost to reach next level
        
        # Animation Timer for blink effect
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(50)  # 20 FPS
        
        # Start hidden
        self.setGeometry(0, 0, 1, 1)

    def set_data(self, missing, is_max, region, level_cost=1):
        self.missing = missing
        self.is_max = is_max
        self.region = region
        self.level_cost = max(1, level_cost)  # Avoid division by zero
        
        # Handle dict or list region
        if isinstance(region, dict):
            rx, ry, rw, rh = region.get("left", 0), region.get("top", 0), region.get("width", 100), region.get("height", 100)
        else:
            rx, ry, rw, rh = region
            
        # Position below the level region
        cx = rx + rw // 2
        cy = ry + rh + 120  # 120px below the region (was 20, +100px)
        
        width = 300
        height = 80
        
        if self.geometry().width() != width:
            self.setGeometry(cx - width // 2, cy, width, height)
        
        if not self.isVisible():
            self.show()
        self.update()

    def draw_text_with_shadow(self, painter, x, y, text, color, shadow_offset=2, shadow_alpha=120):
        """Draw text with a soft drop shadow for better visibility."""
        # Draw shadow
        shadow_color = QColor(0, 0, 0, shadow_alpha)
        painter.setPen(shadow_color)
        painter.drawText(x + shadow_offset, y + shadow_offset, text)
        
        # Draw main text
        painter.setPen(color)
        painter.drawText(x, y, text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Colors
        color_gold = QColor(212, 175, 55)
        color_amber = QColor(255, 195, 0)
        color_green = QColor(100, 255, 100)
        color_text_dim = QColor(180, 180, 180)
        
        w = self.width()
        h = self.height()
        center_x = w // 2
        
        # Label
        font_label = QFont("Cinzel", 10)
        painter.setFont(font_label)
        label_text = "MISSING TO LEVEL"
        tw_label = QFontMetrics(font_label).horizontalAdvance(label_text)
        self.draw_text_with_shadow(painter, center_x - tw_label // 2, 20, label_text, color_text_dim, 2, 120)
        
        # Value with BLINK effect when close to level up
        font_val = QFont("Cinzel", 28, QFont.Weight.Bold)
        painter.setFont(font_val)
        val_str = "MAX" if self.is_max else f"{self.missing:,}"
        val_color = color_gold if self.is_max else (color_green if self.missing <= 0 else color_amber)
        
        # Check if we should blink (missing < 10% of level cost)
        should_blink = not self.is_max and self.missing > 0 and self.missing < (self.level_cost * 0.1)
        
        if should_blink:
            # Blink animation: fade in/out using sine wave
            blink_speed = 3.0  # Hz
            alpha_factor = (abs(time.time() * blink_speed % 2.0 - 1.0))  # 0.0 to 1.0 and back
            alpha = int(100 + (155 * alpha_factor))  # Range: 100-255
            val_color.setAlpha(alpha)
        
        tw_val = QFontMetrics(font_val).horizontalAdvance(val_str)
        self.draw_text_with_shadow(painter, center_x - tw_val // 2, 55, val_str, val_color, 3, 140)
