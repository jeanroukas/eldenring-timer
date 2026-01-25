from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QFontMetrics, QPainterPath

class DraggableWindow(QMainWindow):
    position_changed = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        # Window Flags: Frameless, Always on Top, Tool (no taskbar icon), Transparent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.old_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if self.old_pos: # Only if we were dragging
            self.old_pos = None
            self.position_changed.emit(self.x(), self.y())
        else:
             # Even if just a click, if old_pos was cleared properly we might want to ensure we reset but here we just clear.
             # Wait, mouseRelease comes after drag. 
             pass
        # Always emit position on release if we want to be sure, or only if moved. 
        # Simpler: just emit self.pos()
        self.old_pos = None
        self.position_changed.emit(self.x(), self.y())

class ModernOverlay(DraggableWindow):
    def __init__(self):
        super().__init__()
        
        # Initial Geometry (Top Right) - Default
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry.width() - 650, 20, 600, 150)
        
        self.text = "Waiting..."
        self.is_recording = False
        self.score = 0
        
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
        
        # Positioning: Right Aligned with padding
        rect = self.rect()
        text_width = metrics.horizontalAdvance(display_text)
        x = rect.width() - text_width - 20
        y = 60 # Vertical center-ish
        
        # Draw Outline
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

class RunCountOverlay(DraggableWindow):
    def __init__(self):
        super().__init__()
        
        # Initial Geometry (Top Left) - Default
        self.setGeometry(20, 20, 300, 150)
        
        self.runs_text = "Next Level: -- runs"
        
    def set_run_count(self, count):
        self.runs_text = f"Next Level: {count} runs"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Standard Font Setup
        font = QFont("Helvetica", 12) # Smaller font
        font.setBold(True)
        painter.setFont(font)
        
        # Text Positioning: Top Left, 20px padding
        x = 20
        y = 30
        
        # Draw Text
        path = QPainterPath()
        path.addText(x, y, font, self.runs_text)
        
        # Outline
        painter.setPen(QPen(QColor(0, 0, 0, 255), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        # Fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 255))
        painter.drawPath(path)
        
        # Graph Placeholder
        # Draw a box below the text
        graph_rect_y = y + 10
        graph_rect_h = 60
        graph_rect_w = 200
        
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.drawRect(x, graph_rect_y, graph_rect_w, graph_rect_h)
        
        # Draw a dummy curve
        painter.setPen(QPen(QColor(0, 255, 0, 255), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Simple sine-ish wave
        curve_path = QPainterPath()
        curve_path.moveTo(x, graph_rect_y + graph_rect_h / 2)
        for i in range(1, graph_rect_w, 5):
            # Just a sine wave visual
            import math
            offset_y = math.sin(i * 0.1) * 20
            curve_path.lineTo(x + i, graph_rect_y + graph_rect_h / 2 + offset_y)
            
        painter.drawPath(curve_path)
