from PyQt6.QtWidgets import QMainWindow, QLabel, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer, QObject
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class OCRDebugWidget(QMainWindow):
    position_changed = pyqtSignal(str, int, int) # name, x, y

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        
        # Window Flags: Frameless, Tool, Always on Top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Default Size
        self.setGeometry(0, 0, 180, 40)
        
        # State
        self.text = "---"
        self.confidence = 0.0
        self.is_active = False # Visual flash
        self.last_update_time = 0
        self.burst_state = 'idle'  # New: 'idle', 'burst', 'validated', 'rejected'
        
        self.old_pos = None
        
        # Flash Timer
        self.flash_timer = QTimer()
        self.flash_timer.timeout.connect(self._turn_off_activity)
        self.flash_timer.setSingleShot(True)

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
        # Emit signal to save position
        self.position_changed.emit(self.name, self.x(), self.y())

    def update_state(self, text: str, conf: float, burst_state: str = 'idle'):
        self.text = text
        self.confidence = conf
        self.burst_state = burst_state
        self.is_active = True
        self.update()
        
        # Keep LED on for 200ms
        self.flash_timer.start(200)

    def _turn_off_activity(self):
        self.is_active = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        
        # Background (Black Glass)
        painter.setBrush(QColor(0, 0, 0, 220))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 5, 5)
        
        # LED 1: Confidence Indicator (Left)
        led1_x = 10
        led_y = h // 2
        led_size = 10
        
        led1_color = QColor(50, 50, 50) # Off (Grey)
        
        if self.is_active:
            if self.confidence > 80:
                led1_color = QColor(0, 255, 0) # Green (Good)
            elif self.confidence > 40:
                led1_color = QColor(255, 165, 0) # Orange (Uncertain)
            else:
                led1_color = QColor(255, 0, 0) # Red (Bad)
                
        painter.setBrush(led1_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(led1_x, led_y), led_size // 2, led_size // 2)
        
        # Glow Effect for LED 1
        if self.is_active:
            glow = QColor(led1_color)
            glow.setAlpha(80)
            painter.setBrush(glow)
            painter.drawEllipse(QPoint(led1_x, led_y), led_size, led_size)
        
        # LED 2: Burst State Indicator (Right of LED 1)
        led2_x = 24
        led2_color = QColor(80, 80, 80)  # Default: Dark Gray (idle)
        
        if self.burst_state == 'burst':
            led2_color = QColor(255, 165, 0)  # Orange (scanning)
        elif self.burst_state == 'validated':
            led2_color = QColor(0, 255, 0)  # Green (success)
        elif self.burst_state == 'rejected':
            led2_color = QColor(255, 0, 0)  # Red (failed)
        # else: idle = dark gray
        
        painter.setBrush(led2_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(led2_x, led_y), led_size // 2, led_size // 2)
        
        # Glow Effect for LED 2 (only if not idle)
        if self.burst_state != 'idle':
            glow2 = QColor(led2_color)
            glow2.setAlpha(80)
            painter.setBrush(glow2)
            painter.drawEllipse(QPoint(led2_x, led_y), led_size, led_size)

        # Label Text (Name + Raw)
        text_x = 40  # Moved right to accommodate 2 LEDs
        
        # Zone Name (Tiny, Top)
        painter.setFont(QFont("Arial", 7))
        painter.setPen(QColor(150, 150, 150))
        painter.drawText(text_x, 12, self.name.upper())
        
        # OCR Text (Main)
        painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255))
        
        display_text = self.text
        if not display_text: display_text = "<EMPTY>"
        
        # Truncate if too long
        fm = painter.fontMetrics()
        elided_text = fm.elidedText(display_text, Qt.TextElideMode.ElideRight, w - text_x - 5)
        
        painter.drawText(text_x, 30, elided_text)




class DebugOverlayManager(QObject):
    update_signal = pyqtSignal(str, str, float)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.widgets = {}
        self.positions = config.get("debug_overlay_positions", {})
        
        # Connect Signal (Runs on Main Thread)
        self.update_signal.connect(self._perform_update)
        
        # Zones to create by default
        self.create_widget("Runes")
        self.create_widget("Level")
        self.create_widget("Zone") # Day/Zone Text
        self.create_widget("Menu") # Main Menu
        self.create_widget("Reward") # Victory/Boss Banner

    def create_widget(self, name: str):
        widget = OCRDebugWidget(name)
        widget.position_changed.connect(self.save_position)
        
        # Load Position
        pos = self.positions.get(name, {"x": 100, "y": 100})
        widget.move(pos["x"], pos["y"])
        
        widget.show()
        self.widgets[name] = widget

    def save_position(self, name: str, x: int, y: int):
        self.positions[name] = {"x": x, "y": y}
        self.config["debug_overlay_positions"] = self.positions

    def update(self, name: str, text: str, conf: float):
        # This is called from Background Thread -> Emit Signal
        self.update_signal.emit(name, text, conf)

    def _perform_update(self, name: str, text: str, conf: float):
        # This runs on Main Thread
        if name in self.widgets:
            self.widgets[name].update_state(text, conf, burst_state='idle')

    def set_visible(self, visible: bool):
        for w in self.widgets.values():
            if visible: w.show()
            else: w.hide()
