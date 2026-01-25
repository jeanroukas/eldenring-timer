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
        self.old_pos = None
        self.position_changed.emit(self.x(), self.y())

class UnifiedOverlay(DraggableWindow):
    def __init__(self):
        super().__init__()
        
        # Geometry: 550x420 (Ultra Compact)
        self.setGeometry(20, 20, 550, 420)
        
        # State Data
        self.timer_text = "00:00"
        self.ocr_score = 0.0
        self.is_recording = False
        
        self.stats = {
            "level": 1,
            "potential_level": 1,
            "current_runes": 0,
            "total_runes": 0,
            "next_level": 2,
            "needed_runes": 0,
            "missing_runes": 0,
            "is_max_level": False,
            "run_history": [],
            "transitions": [],
            "death_count": 0,
            "recovery_count": 0,
            "phase_name": "Waiting",
            "spent_at_merchants": 0,
            "graph_events": [], # [(t, type), ...]
            "rps": 0,
            "grade": "C",
            "time_to_level": "---"
        }
        
    def set_timer_text(self, text):
        self.timer_text = text
        self.update()

    def set_score(self, score):
        self.ocr_score = score
        self.update()

    def set_stats(self, stats: dict):
        self.stats = stats
        self.update()

    def shorten_phase(self, name: str) -> str:
        name = name.upper()
        if "WAITING" in name: return "WAITING..."
        if "SEARCHING" in name: return "SEARCHING..."
        
        name = name.replace("DAY 1", "D1").replace("DAY 2", "D2").replace("DAY 3", "D3")
        name = name.replace("STORMVEIL", "STORM").replace("STORM", "STORM") # Simplify
        name = name.replace("SHRINKING", "SHRINK")
        name = name.replace("PREPARATION", "PREP")
        name = name.replace("FINAL BOSS", "FINAL")
        
        # Remove " - " to save space
        name = name.replace(" - ", " ")
        return name

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Colors - Elden Ring Inspired
        color_gold = QColor(212, 175, 55) # Classic Gold
        color_amber = QColor(255, 195, 0) # Glowing Amber
        color_text_white = QColor(240, 240, 240)
        color_text_dim = QColor(180, 180, 180)
        color_bg = QColor(10, 10, 10, 200) # Dark glassmorphism
        color_border = QColor(212, 175, 55, 80)
        
        color_death = QColor(255, 80, 80)
        color_recov = QColor(80, 200, 255)
        color_green = QColor(100, 255, 100)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        
        # 1. Background Box
        painter.setBrush(color_bg)
        painter.setPen(QPen(color_border, 1))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 12, 12)
        
        # --- DATA EXTRACTION ---
        lvl = self.stats.get("level", 1)
        miss = self.stats.get("missing_runes", 0)
        is_max = self.stats.get("is_max_level", False)
        deaths = self.stats.get("death_count", 0)
        recoveries = self.stats.get("recovery_count", 0)
        total_run = self.stats.get("total_runes", 0)
        merch_spent = self.stats.get("spent_at_merchants", 0)
        phase_raw = self.stats.get("phase_name", "Waiting")
        phase = self.shorten_phase(phase_raw)
        
        rps = self.stats.get("rps", 0)
        time_to_lvl = self.stats.get("time_to_level", "---")
        grade = self.stats.get("grade", "C")
        
        history = self.stats.get("run_history", [])
        transitions = self.stats.get("transitions", [])
        events = self.stats.get("graph_events", [])
        
        # --- COLUMNS ---
        col1_x = 20
        col2_x = 220
        col3_x = 360
        
        y_top = 45 
        
        # === COL 1: TIMING (Main) ===
        # Timer
        font_timer = QFont("Helvetica", 32)
        font_timer.setBold(True)
        painter.setFont(font_timer)
        painter.setPen(color_text_white)
        painter.drawText(col1_x, y_top, self.timer_text)
        
        # Phase
        font_phase = QFont("Cinzel", 14)
        font_phase.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
        painter.setFont(font_phase)
        painter.setPen(color_gold)
        painter.drawText(col1_x + 2, y_top + 30, phase.upper())
        
        # Level Progress (NEW)
        pot = self.stats.get("potential_level", lvl)
        level_str = f"Level {lvl}"
        if pot > lvl:
             level_str += f" ➤ {pot}" # Arrow char
             
        font_lvl = QFont("Cinzel", 12)
        font_lvl.setBold(True)
        painter.setFont(font_lvl)
        painter.setPen(color_text_white)
        painter.drawText(col1_x, y_top + 60, level_str)
        
        # Missing
        font_label = QFont("Cinzel", 9)
        painter.setFont(font_label)
        painter.setPen(color_text_dim)
        painter.drawText(col1_x, y_top + 82, "MISSING")
        
        font_missing = QFont("Cinzel", 18)
        font_missing.setBold(True)
        painter.setFont(font_missing)
        if is_max:
             painter.setPen(color_gold)
             painter.drawText(col1_x, y_top + 105, "MAX")
        else:
             painter.setPen(color_amber if miss > 0 else color_green)
             painter.drawText(col1_x, y_top + 105, f"{miss:,}")


        # === COL 2: PERFORMANCE (Stacked) ===
        # Center alignment helper
        center_x = col2_x + 50 
        
        # 1. Efficiency Grade (Top)
        grade_y = y_top + 20
        font_grade = QFont("Cinzel", 36) # Smaller than 48
        font_grade.setBold(True)
        painter.setFont(font_grade)
        
        grade_color = color_text_dim 
        if grade == "S": grade_color = color_gold
        elif grade == "A": grade_color = color_green
        elif grade == "B": grade_color = color_text_white
        elif grade == "C": grade_color = color_amber
        elif grade == "D": grade_color = QColor(255, 100, 50)
        elif grade == "E": grade_color = color_death
        elif grade == "F": grade_color = QColor(150, 0, 0)
        
        # Center text roughly
        # Manual adjustment assuming single char width
        text_width = painter.fontMetrics().horizontalAdvance(grade)
        painter.setPen(grade_color)
        painter.drawText(center_x - text_width // 2, grade_y, grade)
        
        # 2. Delta (Below Grade)
        delta = self.stats.get("delta_runes", 0)
        delta_str = f"{delta/1000:+.1f}k"
        
        font_delta = QFont("Helvetica", 12)
        font_delta.setBold(True)
        painter.setFont(font_delta)
        
        if delta >= 0:
            painter.setPen(color_green)
            delta_str = "+" + delta_str.lstrip("+")
        else:
            painter.setPen(color_death)
            
        text_width = painter.fontMetrics().horizontalAdvance(delta_str)
        painter.drawText(center_x - text_width // 2, grade_y + 25, delta_str)

        # 3. Next Level (Bottom)
        painter.setFont(QFont("Cinzel", 9))
        painter.setPen(color_text_dim)
        painter.drawText(center_x - 30, grade_y + 50, "NEXT LVL")
        
        font_next = QFont("Helvetica", 11)
        font_next.setBold(True)
        painter.setFont(font_next)
        painter.setPen(color_gold)
        painter.drawText(center_x - 30, grade_y + 68, time_to_lvl)

        # === COL 3: STATS HISTORY ===
        y_right = 40
        row_height = 24
        font_stats = QFont("Helvetica", 11)
        font_stats.setBold(True)
        painter.setFont(font_stats)
        
        # OCR Dot
        ocr_color = color_green if self.ocr_score > 60 else (color_amber if self.ocr_score > 30 else color_death)
        painter.setBrush(ocr_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(col3_x, y_right - 10, 8, 8)
        painter.setPen(color_text_dim)
        painter.drawText(col3_x + 15, y_right, f"OCR: {int(self.ocr_score)}%")

        
        if self.is_recording:
             # Pulsing Red Dot for Recording
             rec_x = col3_x + 90
             rec_y = y_right - 10
             painter.setBrush(QColor(255, 50, 50))
             painter.drawEllipse(rec_x, rec_y, 8, 8)
             
        y_right += row_height + 5
        
        # Merch
        painter.setPen(color_text_white)
        painter.drawText(col3_x, y_right, f"Merch: {merch_spent:,}")
        y_right += row_height
        
        # Total
        painter.setPen(color_gold)
        painter.drawText(col3_x, y_right, f"Total: {total_run:,}")
        y_right += row_height
        
        # Deaths
        painter.setPen(color_death)
        painter.drawText(col3_x, y_right, f"💀 Deaths: {deaths}")
        y_right += row_height
        
        # Recov
        painter.setPen(color_recov)
        painter.drawText(col3_x, y_right, f"♻️ Recov: {recoveries}")


        # === GRAPH AREA (Dynamic Grid + Markers) ===
        graph_x = 20
        graph_y = 160
        graph_w = w - 40
        graph_h = h - 180 # Padding bottom
        
        # Dynamic Scaling
        max_val = 100000 # Min scale
        if history:
            m = max(history)
            if m > max_val: max_val = m * 1.1
            
        # Draw Graph BG
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(graph_x, graph_y, graph_w, graph_h)
        
        # Plot
        if len(history) > 1:
            max_val = max(1000, max(history), total_run) * 1.15
            step_x = graph_w / (len(history) - 1)
            
            # --- DYNAMIC GRID ---
            grid_step = 50000
            if max_val > 500000: grid_step = 100000
            
            num_steps = int(max_val / grid_step)
            
            pen_grid = QPen(QColor(255, 255, 255, 30))
            pen_grid.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen_grid)
            font_grid = QFont("Helvetica", 8)
            painter.setFont(font_grid)
            
            for i in range(1, num_steps + 1):
                val = i * grid_step
                if val > max_val: break
                gy = graph_y + graph_h - (val / max_val * graph_h)
                painter.drawLine(graph_x, int(gy), graph_x + graph_w, int(gy))
                label_text = f"{int(val/1000)}k"
                painter.drawText(graph_x + graph_w - 25, int(gy) - 2, label_text)

            # --- IDEAL CURVE (Nightreign) ---
            nr_config = self.stats.get("nr_config")
            if nr_config:
                goal = nr_config["goal"]
                duration = nr_config["duration"]
                exp = nr_config["snowball"]
                
                # We need to map Graph X -> Time T -> Ideal Y
                if len(history) > 1:
                    path_ideal = QPainterPath()
                    for i in range(len(history)):
                        t_sec = i # Relative seconds from session start
                        
                        # Calculate Ideal (With 15s Offset)
                        offset = 15.0
                        if t_sec <= offset:
                            ideal_val = 0
                        else:
                            effective_t = t_sec - offset
                            effective_duration = 2400.0 # 40m fixed base
                            
                            # 1. Base Farming
                            ratio = effective_t / effective_duration
                            if ratio > 1.0: ratio = 1.0
                            
                            # Farming Goal (Total - Bosses) = 452116
                            farming_goal = 452116 
                            farming_val = farming_goal * (ratio ** exp)
                            
                            # 2. Boss Steps
                            boss_bonus = 0
                            day1_end = 1200.0
                            day2_end = 2400.0
                            
                            if effective_t > day1_end: boss_bonus += 11000
                            if effective_t > day2_end: boss_bonus += 50000
                            
                            ideal_val = farming_val + boss_bonus
                        
                        # Map to Screen
                        px = graph_x + i * step_x
                        py = graph_y + graph_h - (ideal_val / max_val * graph_h)
                        
                        if i == 0:
                            path_ideal.moveTo(px, py)
                        else:
                            path_ideal.lineTo(px, py)
                    
                    pen_ideal = QPen(QColor(255, 255, 255, 40)) # Faint Grey
                    pen_ideal.setStyle(Qt.PenStyle.DashLine)
                    pen_ideal.setWidth(2)
                    painter.setPen(pen_ideal)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path_ideal)

            # --- PLOT ---
            path = QPainterPath()
            path.moveTo(graph_x, graph_y + graph_h)
            for i, val in enumerate(history):
                px = graph_x + i * step_x
                py = graph_y + graph_h - (val / max_val * graph_h)
                path.lineTo(px, py)
                
            painter.setPen(QPen(color_gold, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
            fill_path = QPainterPath(path)
            fill_path.lineTo(graph_x + (len(history)-1) * step_x, graph_y + graph_h)
            fill_path.lineTo(graph_x, graph_y + graph_h)
            fill_path.closeSubpath()
            grad = QColor(color_gold.red(), color_gold.green(), color_gold.blue(), 40)
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(fill_path)
            
            # --- MARKERS (💀, 💰, ⚔️) ---
            start_t = self.stats.get("graph_start_time", 0)
            if start_t > 0:
                 # history length is approx duration in seconds (1 Hz)
                 total_duration = len(history) # simplistic but robust enough
                 if total_duration > 0:
                     for evt in events:
                         t_evt = evt.get("t", 0)
                         bg_type = evt.get("type", "")
                         
                         relative_t = t_evt - start_t
                         if 0 <= relative_t <= total_duration:
                             # Map to X
                             # pct = relative_t / total_duration
                             # px = graph_x + pct * graph_w
                             
                             # More precisely:
                             px = graph_x + (relative_t / total_duration) * graph_w
                             
                             # Icon
                             icon = "❓"
                             if bg_type == "DEATH": icon = "💀"
                             elif bg_type == "RECOVERY": icon = "♻️"
                             elif bg_type == "BOSS": icon = "⚔️"
                             
                             # Draw
                             painter.setFont(QFont("Segoe UI Emoji", 12)) 
                             painter.drawText(int(px) - 6, int(graph_y + graph_h) - 10, icon)

            # --- TRANSITIONS ---
            for idx, day_name in transitions:
                if idx < len(history):
                    tx = int(graph_x + idx * step_x)
                    if "DAY 2" in day_name:
                        painter.setPen(QPen(color_amber, 1, Qt.PenStyle.DashLine))
                        painter.drawLine(tx, graph_y, tx, graph_y + graph_h)
                        painter.setPen(color_amber)
                        painter.drawText(tx + 2, graph_y + 12, "D2")
                    elif "DAY 3" in day_name:
                        painter.setPen(QPen(QColor(255, 80, 80), 1, Qt.PenStyle.DashLine))
                        painter.drawLine(tx, graph_y, tx, graph_y + graph_h)
                        painter.setPen(QColor(255, 80, 80))
                        painter.drawText(tx + 2, graph_y + 12, "D3")

        elif not is_max:
             painter.setFont(QFont("Cinzel", 10))
             painter.setPen(color_text_dim)

             painter.drawText(graph_x + 50, graph_y + graph_h // 2, "Waiting for run data...")

    def show_recording(self, show: bool):
        self.is_recording = show
        self.update()
