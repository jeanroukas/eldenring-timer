"""
Transaction History Widget - Draggable UI for displaying last 4 transactions

Matches the style of LED debug rectangles with drag-and-drop functionality.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush
import json


class TransactionHistoryWidget(QWidget):
    """
    Draggable widget displaying last 4 validated transactions.
    
    Style matches LED debug rectangles:
    - Dark semi-transparent background
    - White border
    - Colored text based on transaction type
    - Drag-and-drop with position persistence
    """
    
    def __init__(self, parent, config_service):
        super().__init__(parent)
        self.config = config_service
        self.transactions = []
        
        # Widget properties
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Drag-and-drop
        self.dragging = False
        self.drag_offset = QPoint()
        
        # Load saved position or use default
        saved_pos = self.config.get("transaction_history_position", {"x": 50, "y": 400})
        self.move(saved_pos["x"], saved_pos["y"])
        
        # Size
        self.setFixedSize(250, 120)
    
    def update_transactions(self, transaction_history):
        """Update the transaction list and repaint."""
        self.transactions = list(transaction_history)  # Convert deque to list
        self.update()
    
    def paintEvent(self, event):
        """Draw the transaction history widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background (dark semi-transparent)
        bg_color = QColor(20, 20, 20, 200)
        painter.fillRect(self.rect(), bg_color)
        
        # Border (white)
        border_color = QColor(255, 255, 255, 150)
        painter.setPen(QPen(border_color, 2))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
        
        # Title
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.drawText(10, 20, "TRANSACTIONS")
        
        # Transaction list
        y = 40
        painter.setFont(QFont("Consolas", 9))
        
        for entry in self.transactions:
            tx_type = entry.get("type", "")
            amount = entry.get("amount", 0)
            context = entry.get("context", {})
            
            # Format text and color based on type
            if tx_type == "GAIN":
                text = f"+{amount} runes (gain)"
                color = QColor(100, 255, 100)  # Green
            
            elif tx_type == "SPENDING":
                text = f"-{amount} runes (marchand)"
                color = QColor(255, 100, 100)  # Red
            
            elif tx_type == "LEVEL_UP":
                old = context.get("old_level", "?")
                new = context.get("new_level", "?")
                text = f"Level {old}→{new} (-{amount})"
                color = QColor(255, 215, 0)  # Gold
            
            elif tx_type == "DEATH":
                text = f"-{amount} runes (mort)"
                color = QColor(200, 50, 50)  # Dark red
            
            elif tx_type == "RECOVERY":
                text = f"+{amount} runes (récup)"
                color = QColor(100, 200, 255)  # Blue
            
            else:
                text = f"{amount:+d} runes"
                color = QColor(200, 200, 200)  # Gray
            
            painter.setPen(QPen(color))
            painter.drawText(10, y, text)
            y += 18
    
    def mousePressEvent(self, event):
        """Start dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_offset = event.pos()
    
    def mouseMoveEvent(self, event):
        """Handle dragging."""
        if self.dragging:
            new_pos = self.mapToParent(event.pos() - self.drag_offset)
            self.move(new_pos)
    
    def mouseReleaseEvent(self, event):
        """Stop dragging and save position."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            
            # Save position to config
            pos = {"x": self.x(), "y": self.y()}
            self.config.set("transaction_history_position", pos)
