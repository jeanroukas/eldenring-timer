from PyQt6.QtWidgets import QMainWindow, QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QFontMetrics, QPainterPath
from src.services.rune_data import RuneData

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
        
        # Check for Graph Click (Bottom Area)
        # Graph Y is ~160 to H-20. X is 20 to W-20
        rect = self.rect()
        graph_y = 160
        if event.pos().y() > graph_y and event.pos().x() > 20 and event.pos().x() < rect.width()-20:
             self.show_projection = not self.show_projection
             self.update()
             return

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
        self.show_projection = False # Toggle for Graph View
        
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
    
    # ... (Keep existing methods: set_timer_text, set_score, etc.) ...
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

    def get_total_runes_for_level(self, level: int) -> int:
        return RuneData.get_total_runes_for_level(level) or 0

    def get_clean_history(self, history):
        """
        Simple outlier removal for the Green Curve.
        Removes single-point spikes that do not sustain.
        """
        if len(history) < 3: return history
        
        cleaned = list(history)
        # We only check internal points
        for i in range(1, len(history) - 1):
            prev = cleaned[i-1]
            curr = cleaned[i]
            nex = history[i+1] # Look ahead in original or cleaned? Original is safer for "next".
            
            # 1. Check for Spike (Up or Down)
            # If current deviates signficantly from prev AND next is closer to prev
            diff_prev = abs(curr - prev)
            diff_next = abs(curr - nex)
            
            # Threshold: 10% change or > 5000 runes absolute?
            # Let's say if jump is > 2000 and return is > 2000
            if diff_prev > 2000 and diff_next > 2000:
                # Check if we return somewhat to baseline
                # If prev and next are close (within 20% of each other spread)
                spread = abs(prev - nex)
                if spread < diff_prev * 0.5: 
                    # It was a spike, smooth it
                    cleaned[i] = (prev + nex) / 2
        
        return cleaned

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

        

        y_right += row_height + 5
        
        # Current Runes (NEW)
        curr_runes = self.stats.get("current_runes", 0)
        painter.setPen(color_text_white)
        painter.drawText(col3_x, y_right, f"Runes: {curr_runes:,}")
        y_right += row_height

        # Merch
        painter.setPen(color_text_dim) # Dimm merch
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
        
        # Draw Graph BG
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(graph_x, graph_y, graph_w, graph_h)
        
        if not history:
             painter.setFont(QFont("Cinzel", 10))
             painter.setPen(color_text_dim)
             painter.drawText(graph_x + 50, graph_y + graph_h // 2, "Waiting for run data...")
             return

        # --- GRAPH MODE LOGIC ---
        # MODE A: Real Time (Fit to current history len)
        # MODE B: Projected (Fit to 40mins / 2400s)
        
        if self.show_projection:
             # Total Projected: 28 mins (1680s) based on 14m Day Cycles
             TOTAL_PROJECTED_TIME = 1680
             x_range_max = max(len(history), TOTAL_PROJECTED_TIME)
             y_range_max = max(1000, 550000) 
             if total_run > y_range_max: y_range_max = total_run * 1.15
        else:
             x_range_max = max(60, len(history)) # Minimum 60s
             # Dynamic Y for Real-Time (Zoomed)
             y_range_max = max(1000, total_run * 1.2)
        
        step_x = graph_w / x_range_max
        
        # --- IDEAL CURVE (Piecewise) ---
        nr_config = self.stats.get("nr_config")
        if nr_config:
            path_ideal = QPainterPath()
            
            # Sim parameters (Aligned with 14m Phases)
            # Day 1: 14 mins (840s)
            day1_dur = 840 
            # Day 2: 14 mins (840s) for Farming
            day2_dur = 840
            
            # Key Rune Targets
            # Day 1 End: ~180k (Level 9.5 Goal)
            runes_day1_end = 180881
            # Boss 1 Drop: 50k
            boss1_drop = 50000
            # Day 2 Start = 230k
            runes_day2_start = runes_day1_end + boss1_drop
            # Day 2 End: Level 14 Goal (~437k)
            runes_day2_end = 437578
            
            for t in range(x_range_max + 1):
                val = 0
                
                if t < day1_dur:
                    # Phase 1: Day 1 (0 -> 14m)
                    # Expo curve to target
                    ratio = t / float(day1_dur)
                    if ratio < 0: ratio = 0
                    val = runes_day1_end * (ratio ** 1.2)
                    
                else:
                    # Phase 2: Day 2 (14m -> 28m)
                    # Starts higher (Jump), then exponential growth
                    
                    # Normalize t to 0..1 range for this phase
                    phase_t = t - day1_dur
                    ratio = phase_t / float(day2_dur)
                    if ratio > 1.0: ratio = 1.0
                    
                    # Curve from Start to End
                    val = runes_day2_start + (runes_day2_end - runes_day2_start) * (ratio ** 1.2)
                
                px = graph_x + t * step_x
                py = graph_y + graph_h - (val / y_range_max * graph_h)
                
                if t == 0: path_ideal.moveTo(px, py)
                else: path_ideal.lineTo(px, py)
                
            pen_ideal = QPen(QColor(255, 255, 255, 40)) 
            pen_ideal.setStyle(Qt.PenStyle.DashLine)
            pen_ideal.setWidth(2)
            painter.setPen(pen_ideal)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path_ideal)

        # --- RAW DATA PLOT (Background / Historical) ---
        # "Garder le graphique actuel en orange foncé"
        history_raw = self.stats.get("run_history_raw", [])
        if history_raw:
            path_raw = QPainterPath()
            start_px = graph_x
            start_py = graph_y + graph_h
            path_raw.moveTo(start_px, start_py)
            
            valid_raw = False
            for i, val in enumerate(history_raw):
                # Ensure we don't exceed bounds if raw is longer than max (shouldn't be)
                if i > x_range_max: break
                
                px = graph_x + i * step_x
                py = graph_y + graph_h - (val / y_range_max * graph_h)
                path_raw.lineTo(px, py)
                valid_raw = True
            
            if valid_raw:
                # User Request: "Orange très saturé mais alpha a 60%"
                # 60% of 255 is approx 153
                color_raw = QColor(255, 120, 0, 153) 
                painter.setPen(QPen(color_raw, 3)) # User Request: Thicker (was 2)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path_raw)

        # Apply Cleaning to Green Curve
        history_clean = self.get_clean_history(history)

        path = QPainterPath()
        path.moveTo(start_px, start_py)
        
        valid_points = False
        for i, val in enumerate(history_clean):
            px = graph_x + i * step_x
            py = graph_y + graph_h - (val / y_range_max * graph_h)
            path.lineTo(px, py)
            valid_points = True
            
        if valid_points:
            # CORRECTED GRAPH: THIN GREEN LINE (User Request)
            # "passer ce graf en vert avec une ligne tres fine"
            color_corrected = QColor(0, 255, 0, 255) # Pure Green
            painter.setPen(QPen(color_corrected, 1)) # Width 1 (Very Thin)
            
            # User Request: "sans remplissage" (No Fill)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            
            # --- CURSOR LABEL (User Request) ---
            # Show "3K" above the current point
            if history:
                curr_val = history[-1]
                last_idx = len(history) - 1
                px = graph_x + last_idx * step_x
                py = graph_y + graph_h - (curr_val / y_range_max * graph_h)
                
                label_txt = f"{curr_val/1000:.1f}K"
                painter.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
                painter.setPen(color_gold)
                
                # Center text above point
                fm = QFontMetrics(painter.font())
                tw = fm.horizontalAdvance(label_txt)
                painter.drawText(int(px - tw/2), int(py - 10), label_txt) 
                
                # Draw a little dot
                painter.setBrush(color_gold)
                painter.drawEllipse(QPoint(int(px), int(py)), 3, 3)

        # --- LEVEL GRID LINES ---
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DotLine))
        painter.setFont(QFont("Helvetica", 8))
        
        # Key Levels: Dynamic based on Y-Range
        # User request: "ne pas en afficher plus de 5"
        visible_levels = []
        # Optimization: Only check relevant range. 
        # Start from current level? Or Level 1?
        # Let's check levels 1 to 25 first (most common) then sparse.
        
        candidates = []
        for l in range(1, 150):
            req = self.get_total_runes_for_level(l)
            if req > y_range_max: break # Optimization
            if req > 0:
                candidates.append((l, req))
                
        # Filter to max 5 items, prioritizing higher levels (targets) or spread?
        # Let's try to keep them spread out.
        if len(candidates) > 5:
            # Always keep the highest fit (top target)
            # Pick 5 evenly spaced indices
            indices = set()
            count = len(candidates)
            if count > 0:
                indices.add(count - 1) # Top
                indices.add(0) # Bottom
                # Middle ones
                indices.add(count // 2) 
                indices.add(count // 4)
                indices.add(count * 3 // 4)
            
            # Sort and take unique
            final_indices = sorted(list(indices))
            visible_levels = [candidates[i] for i in final_indices if i < count]
            # Ensure max 5
            visible_levels = visible_levels[-5:]
        else:
            visible_levels = candidates

        for lvl_num, rune_cost in visible_levels:
            gy = graph_y + graph_h - (rune_cost / y_range_max * graph_h)
            
            # Draw Horizontal line (User called them "barres verticales" but meant Y-axis levels)
            painter.drawLine(graph_x, int(gy), graph_x + graph_w, int(gy))
            painter.drawText(graph_x + graph_w - 25, int(gy) - 3, f"L{lvl_num}")

        # --- VIEW LABEL ---
        painter.setPen(color_text_dim)
        painter.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
        label = "VIEW: PROJECTION (40m)" if self.show_projection else "VIEW: REAL-TIME"
        painter.drawText(graph_x + 10, graph_y + 20, label)

        # --- MARKERS ---
        start_t = self.stats.get("graph_start_time", 0)
        if start_t > 0 and len(history) > 0:
             for evt in events:
                 t_evt = evt.get("t", 0)
                 bg_type = evt.get("type", "")
                 
                 relative_t = t_evt - start_t
                 if relative_t < 0: continue
                 
                 # Clip if out of range in Zoomed Mode
                 if not self.show_projection and relative_t > len(history): continue
                 
                 px = graph_x + relative_t * step_x
                 
                 icon = "❓"
                 if bg_type == "DEATH": icon = "💀"
                 elif bg_type == "RECOVERY": icon = "♻️"
                 elif bg_type == "BOSS": icon = "⚔️"
                 
                 painter.setFont(QFont("Segoe UI Emoji", 12)) 
                 painter.drawText(int(px) - 6, int(graph_y + graph_h) - 10, icon)
                 
    def show_recording(self, show: bool):
        self.is_recording = show
        self.update()

    def mouseReleaseEvent(self, event):
        # Left Click: Toggle Graph Mode
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is in graph area (roughly bottom half)
            rect = self.rect()
            graph_y = 160
            if event.position().y() > graph_y:
                self.show_projection = not self.show_projection
                self.update()
        
        # Right Click: Prevent Crash / Do Nothing
        elif event.button() == Qt.MouseButton.RightButton:
            event.accept() # Swallow event
            pass
