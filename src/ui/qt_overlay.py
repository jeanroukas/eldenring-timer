from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QFontMetrics, QPainterPath

class ModernOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Window Flags: Frameless, Always on Top, Tool (no taskbar icon), Transparent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Initial Geometry (Top Right)
        # We'll set a default, but it can be moved.
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry.width() - 650, 20, 600, 150)
        
        self.text = "Waiting..."
        self.is_recording = False
        self.score = 0
        
        # Drag Logic
        self.old_pos = None

    def set_text(self, text):
        self.text = text
        self.update() # Trigger repaint

    def set_score(self, score):
        self.score = score
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Font Setup
        font = QFont("Helvetica", 24)
        font.setBold(True)
        painter.setFont(font)
        
        metrics = QFontMetrics(font)
        
        # Text to draw
        display_text = self.text
        if self.is_recording and not display_text.startswith("🔴") and not display_text.startswith("Waiting"):
             # Optional: Add recording dot if not present (logic might vary)
             pass 

        # Positioning: Right Aligned with padding
        rect = self.rect()
        text_width = metrics.horizontalAdvance(display_text)
        x = rect.width() - text_width - 20
        y = 60 # Vertical center-ish
        
        # Draw Outline (Simulated with multiple draws or QPainterPath)
        # Using QPainterPath is cleaner for outlines but expensive-ish. 
        # Simple offset draw is fine for this.
        outline_color = QColor(0, 0, 0, 255)
        text_color = QColor(255, 255, 255, 255)
        
        path = QPainterPath()
        path.addText(x, y, font, display_text)
        
        # Stroke (Outline)
        pen = QPen(outline_color)
        pen.setWidth(4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        # Fill (Text)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(text_color)
        painter.drawPath(path)

        # Draw Score (Small text below)
        if self.score > 0:
            score_text = f"Accuracy: {int(self.score)}%"
            score_font = QFont("Helvetica", 12)
            score_font.setBold(True)
            painter.setFont(score_font)
            
            score_metrics = QFontMetrics(score_font)
            score_width = score_metrics.horizontalAdvance(score_text)
            sx = rect.width() - score_width - 20
            sy = y + 40 # 40px below main timer
            
            score_path = QPainterPath()
            score_path.addText(sx, sy, score_font, score_text)
            
            # Outline
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(score_path)
            
            # Fill
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(170, 170, 170, 255)) # Silver/Gray
            painter.drawPath(score_path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
