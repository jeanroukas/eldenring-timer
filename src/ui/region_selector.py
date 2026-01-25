from PyQt6.QtWidgets import QWidget, QRubberBand, QApplication, QLabel
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QBrush, QPainter
import sys

class RegionSelector(QWidget):
    region_selected = pyqtSignal(dict) # Signals region dictionary

    def __init__(self):
        super().__init__()
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        
        # Window Setup
        # Window Setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        
        # Geometry: Cover all screens
        total_rect = QRect()
        for screen in QApplication.screens():
            total_rect = total_rect.united(screen.geometry())
            
        self.setGeometry(total_rect)

        # Instructions
        self.label = QLabel("Click and drag to select region. Press ESC to cancel.", self)
        self.label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 10px; border-radius: 5px; font-size: 16px;")
        self.label.adjustSize()
        # Center label roughly on primary screen
        screen_geo = QApplication.primaryScreen().geometry()
        # Map to local coordinates if the window spans multiple monitors? 
        # Window is at (total_rect.x, total_rect.y). We need relative pos.
        label_x = (screen_geo.width() - self.label.width()) // 2 + screen_geo.x() - total_rect.x()
        label_y = 100 + screen_geo.y() - total_rect.y()
        self.label.move(label_x, label_y)

        # Overlay color (dimmed background)
        self.overlay_color = QColor(0, 0, 0, 100) 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.overlay_color)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.globalPosition().toPoint()
            # Map global cursor position to widget coordinates
            local_pos = self.mapFromGlobal(self.start_point)
            self.rubber_band.setGeometry(QRect(local_pos, local_pos))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if not self.start_point.isNull():
            current_pos = event.globalPosition().toPoint()
            # Map both start and current positions to local coordinates
            local_start = self.mapFromGlobal(self.start_point)
            local_current = self.mapFromGlobal(current_pos)
            self.rubber_band.setGeometry(QRect(local_start, local_current).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self.rubber_band.geometry()
            
            # For the OUTPUT region, we usually want GLOBAL coordinates (for mss/bettercam)
            # self.start_point was set from globalPosition(), so it's ALREADY global.
            # But we need the width/height from the rubberband (which is local).
            
            # Let's reconstruct the Global Rect from the Global Points
            # This avoids mapFromGlobal/mapToGlobal round trip issues if DPI is weird.
            global_end = event.globalPosition().toPoint()
            global_rect = QRect(self.start_point, global_end).normalized()
            
            if global_rect.width() > 10 and global_rect.height() > 10:
                # Apply DPI Scaling to match physical pixels (ImageGrab)
                ratio = self.devicePixelRatio()
                
                region = {
                    "top": int(global_rect.top() * ratio),
                    "left": int(global_rect.left() * ratio),
                    "width": int(global_rect.width() * ratio),
                    "height": int(global_rect.height() * ratio)
                }
                self.region_selected.emit(region)
                self.close()
            else:
                self.rubber_band.hide()
                self.start_point = QPoint()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
