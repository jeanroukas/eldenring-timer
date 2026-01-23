from PyQt6.QtWidgets import QWidget, QRubberBand, QApplication, QLabel
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QBrush
import sys

class RegionSelector(QWidget):
    region_selected = pyqtSignal(dict) # Signals region dictionary

    def __init__(self):
        super().__init__()
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        
        # Window Setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        
        # Instructions
        self.label = QLabel("Click and drag to select region. Press ESC to cancel.", self)
        self.label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 10px; border-radius: 5px; font-size: 16px;")
        self.label.adjustSize()
        # Center label roughly
        screen_geo = QApplication.primaryScreen().geometry()
        self.label.move((screen_geo.width() - self.label.width()) // 2, 100)

        # Overlay color (dimmed background)
        self.overlay_color = QColor(0, 0, 0, 100) 

    def paintEvent(self, event):
        # We can implement custom painting if QRubberBand isn't styled enough, 
        # but standard QRubberBand is usually sufficient for "snip" tools.
        # Alternatively, paint the whole screen dim, and leave the selection clear.
        # For simplicity/performance, let's stick to base widget transparency + RubberBand.
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.globalPosition().toPoint()
            self.rubber_band.setGeometry(QRect(self.start_point, self.start_point))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if not self.start_point.isNull():
            self.rubber_band.setGeometry(QRect(self.start_point, event.globalPosition().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.rubber_band.geometry()
            
            # Normalize to screen coordinates if needed, but widget is fullscreen so mapFromGlobal is implied identity mostly?
            # self.start_point was global.
            
            if rect.width() > 10 and rect.height() > 10:
                region = {
                    "top": rect.top(),
                    "left": rect.left(),
                    "width": rect.width(),
                    "height": rect.height()
                }
                self.region_selected.emit(region)
                self.close()
            else:
                self.rubber_band.hide()
                self.start_point = QPoint()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
