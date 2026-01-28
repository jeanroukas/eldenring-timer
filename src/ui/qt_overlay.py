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
        # Save position if we were dragging
        if self.old_pos:
            print(f"[DEBUG] Position changed: ({self.x()}, {self.y()})")
            self.position_changed.emit(self.x(), self.y())
        
        self.old_pos = None
        
        # Check for Graph Click (Bottom Area) - only if it was a click, not a drag
        # Graph Y is ~260 to H-20. X is 20 to W-20
        rect = self.rect()
        graph_y = 260  # Updated to match new graph position
        if event.pos().y() > graph_y and event.pos().x() > 20 and event.pos().x() < rect.width()-20:
             self.show_projection = not self.show_projection
             self.update()




class UnifiedOverlay(DraggableWindow):
    def __init__(self):
        super().__init__()
        
        # Set size only (position will be restored by overlay_service)
        self.resize(550, 420)  # Ultra Compact
        
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
            "delta_runes": 0,
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
        return RuneData.get_total_runes_for_level(level)
    
    def draw_text_with_shadow(self, painter, x, y, text, color, shadow_offset=2, shadow_alpha=100):
        """
        Draw text with a soft drop shadow for better visibility.
        """
        # Draw shadow (offset, semi-transparent black)
        shadow_color = QColor(0, 0, 0, shadow_alpha)
        painter.setPen(shadow_color)
        painter.drawText(x + shadow_offset, y + shadow_offset, text)
        
        # Draw main text
        painter.setPen(color)
        painter.drawText(x, y, text) or 0

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
        
        # 1. Background Box (TRANSPARENT as per user request)
        # painter.setBrush(color_bg)
        # painter.setPen(QPen(color_border, 1))
        # painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 12, 12)
        
        # --- DATA EXTRACTION ---
        lvl = self.stats.get("level", 1)
        # miss and is_max moved to MissingRunesOverlay
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
        
        # === CENTER AREA: PRIMARY FOCUS ===
        # Reorganized for maximum visibility in combat
        center_x = w // 2
        y_center = 60
        
        # 1. Timer (Chrono)
        font_timer = QFont("Helvetica", 48)
        font_timer.setBold(True)
        painter.setFont(font_timer)
        # Center horizontally
        fm_timer = QFontMetrics(font_timer)
        tw_timer = fm_timer.horizontalAdvance(self.timer_text)
        self.draw_text_with_shadow(painter, center_x - tw_timer // 2, y_center, self.timer_text, color_text_white, 3, 150)
        
        # 2. Grade & Delta (Below Timer)
        font_grade = QFont("Cinzel", 24)
        font_grade.setBold(True)
        painter.setFont(font_grade)
        
        grade_color = color_text_dim 
        if grade == "S": grade_color = color_gold
        elif grade == "A": grade_color = color_green
        elif grade == "B": grade_color = color_text_white
        elif grade == "C": grade_color = color_amber
        elif grade == "D": grade_color = QColor(255, 100, 50)
        
        fm_grade = QFontMetrics(font_grade)
        tw_grade = fm_grade.horizontalAdvance(grade)
        self.draw_text_with_shadow(painter, center_x - tw_grade // 2 - 40, y_center + 35, grade, grade_color, 2, 130)
        
        # Delta next to grade
        delta = self.stats.get("delta_runes", 0)
        delta_str = f"{delta/1000:+.1f}k"
        font_delta = QFont("Helvetica", 14, QFont.Weight.Bold)
        painter.setFont(font_delta)
        delta_color = color_green if delta >= 0 else color_death
        self.draw_text_with_shadow(painter, center_x - 10, y_center + 32, delta_str, delta_color, 2, 120)

        # 3. Missing Runes - REMOVED (now in separate overlay below level region)
        # See MissingRunesOverlay



        # === LEFT COLUMN: PHASE & LEVEL ===
        col_l_x = 20
        y_side = 40
        
        # Phase (Small, Top Left)
        font_side_p = QFont("Cinzel", 11, QFont.Weight.Bold)
        painter.setFont(font_side_p)
        self.draw_text_with_shadow(painter, col_l_x, y_side, phase.upper(), color_gold, 2, 110)
        
        # Level (Below Phase)
        pot = self.stats.get("potential_level", lvl)
        level_str = f"Lvl {lvl}"
        if pot > lvl: level_str += f" > {pot}"
        
        font_side_l = QFont("Cinzel", 14, QFont.Weight.Bold)
        painter.setFont(font_side_l)
        self.draw_text_with_shadow(painter, col_l_x, y_side + 25, level_str, color_text_white, 2, 120)
        
        # Next Level Time
        painter.setFont(QFont("Helvetica", 9))
        self.draw_text_with_shadow(painter, col_l_x, y_side + 45, f"IN: {time_to_lvl}", color_text_dim, 1, 100)

        # === RIGHT COLUMN: SECONDARY STATS ===
        col_r_x = w - 140
        y_right = 40
        row_h = 22
        
        # OCR Score
        ocr_color = color_green if self.ocr_score > 70 else (color_amber if self.ocr_score > 40 else color_death)
        painter.setPen(ocr_color)
        painter.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
        painter.drawText(col_r_x, y_right, f"OCR: {int(self.ocr_score)}%")
        y_right += row_h
        
        # Runes / Total
        curr_runes = self.stats.get("current_runes", 0)
        painter.setPen(color_text_white)
        painter.setFont(QFont("Helvetica", 10))
        painter.drawText(col_r_x, y_right, f"Runes: {curr_runes:,}")
        y_right += row_h
        painter.setPen(color_gold)
        painter.drawText(col_r_x, y_right, f"Total: {total_run//1000}k")
        y_right += row_h
        
        # Deaths / Recov
        painter.setPen(color_death)
        painter.drawText(col_r_x, y_right, f"💀 {deaths}")
        painter.setPen(color_recov)
        painter.drawText(col_r_x + 40, y_right, f"♻️ {recoveries}")


        # === GRAPH AREA (Dynamic Grid + Markers) ===
        graph_x = 20
        graph_y = 260  # Was 160, now 260 (+100px top margin for blue circles)
        graph_w = w - 40
        graph_h = h - 280  # Adjusted for new graph_y (was h-180, now h-280)
        
        # Draw Graph BG (TRANSPARENT as per user request)
        # painter.setBrush(QColor(0, 0, 0, 100))
        # painter.setPen(Qt.PenStyle.NoPen)
        # painter.drawRect(graph_x, graph_y, graph_w, graph_h)
        
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
            
            # Constants matching StateService
            # Constants matching StateService (Phase 4: 14m cycles)
            day1_dur = 840  # 14 mins
            day2_dur = 840  # 14 mins
            farming_goal = self.stats.get("nr_config", {}).get("goal", 337578)
            nr_total_time = self.stats.get("nr_config", {}).get("duration", 1680)
            
            boss1_drop = 50000
            
            # Calculate Day 1 End Value (Continuous Farming)
            # Formula: Goal * (ratio ** 1.35)
            # Ratio at 1200s = 1200/2400 = 0.5
            val_d1_farming = farming_goal * (0.5 ** 1.35)
            
            start_d2 = val_d1_farming + boss1_drop
            target_end = 437578 # Lvl 14 Total
            
            rem_farming = target_end - start_d2 # Growth needed in Day 2 (excluding Boss 2 drop which is at end)
            # Actually, target_end is reached BEFORE Boss 2 drop? 
            # "Level 14 au debut du boss". Yes.
            
            for t in range(x_range_max + 1):
                val = 0
                
                if t < day1_dur:
                    # Phase 1: Day 1 (0 -> 14m)
                    # Power 1.35
                    ratio = t / nr_total_time
                    val = farming_goal * (ratio ** 1.35)
                    
                else:
                    # Phase 2: Day 2 (20m -> 40m)
                    # Power 1.15
                    t_d2 = t - day1_dur
                    ratio_d2 = t_d2 / float(day2_dur)
                    if ratio_d2 > 1.0: ratio_d2 = 1.0
                    
                    val = start_d2 + rem_farming * (ratio_d2 ** 1.15)
                
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

        # --- RAW DATA PLOT REMOVED PER USER REQUEST ---
        start_px = graph_x
        start_py = graph_y + graph_h

        # history_raw = self.stats.get("run_history_raw", [])
        # if history_raw:
        #     path_raw = QPainterPath()
        #     path_raw.moveTo(start_px, start_py)
        #     
        #     valid_raw = False
        #     for i, val in enumerate(history_raw):
        #         if i > x_range_max: break
        #         px = graph_x + i * step_x
        #         py = graph_y + graph_h - (val / y_range_max * graph_h)
        #         path_raw.lineTo(px, py)
        #         valid_raw = True
        #     
        #     if valid_raw:
        #         color_raw = QColor(255, 120, 0, 153) 
        #         painter.setPen(QPen(color_raw, 3))
        #         painter.setBrush(Qt.BrushStyle.NoBrush)
        #         painter.drawPath(path_raw)

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
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DotLine))  # Increased from 80 to 150 for better visibility
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

        # --- VIEW LABEL REMOVED per user request ---
        # painter.setPen(color_text_dim)
        # painter.setFont(QFont("Helvetica", 9, QFont.Weight.Bold))
        # label = "VIEW: PROJECTION (40m)" if self.show_projection else "VIEW: REAL-TIME"
        # painter.drawText(graph_x + 10, graph_y + 20, label)
        
        # --- DAY TRANSITION VERTICAL BARS ---
        # Draw vertical lines at Day 2 and Day 3 transitions
        painter.setPen(QPen(QColor(255, 255, 255, 100), 2, Qt.PenStyle.DashLine))
        painter.setFont(QFont("Cinzel", 9, QFont.Weight.Bold))
        
        for trans in transitions:
            if isinstance(trans, dict):
                trans_name = trans.get("name", "")
                trans_t = trans.get("t", 0)
            else:
                # Fallback for legacy tuple format (timestamp, name)
                # Ensure we have at least 2 elements
                if len(trans) >= 2:
                    trans_t = trans[0]
                    trans_name = str(trans[1])
                else:
                    continue
            
            # Only show End Shrink transitions
            if "End Shrink" in trans_name:
                relative_t = trans_t - start_t if start_t > 0 else 0
                if relative_t < 0: continue
                
                # Clip if out of range in Zoomed Mode
                if not self.show_projection and relative_t > len(history): continue
                
                tx = graph_x + relative_t * step_x
                
                # Draw vertical line
                painter.drawLine(int(tx), graph_y, int(tx), graph_y + graph_h)
                
                # Draw label at top
                label = "D2" if "Day 2" in trans_name else "D3"
                painter.setPen(QColor(255, 215, 0, 200))  # Gold color
                painter.drawText(int(tx) - 10, graph_y - 5, label)
                painter.setPen(QPen(QColor(255, 255, 255, 100), 2, Qt.PenStyle.DashLine))  # Reset pen

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
                 
                 painter.drawText(int(px) - 6, int(graph_y + graph_h) - 10, icon)
                 
        # --- SHORTCUTS FOOTER (User Request) ---
        # --- SHORTCUTS REMOVED PER USER REQUEST ---
        pass
                 
    def show_recording(self, show: bool):
        self.is_recording = show
        self.update()

    def mouseReleaseEvent(self, event):
        # IMPORTANT: Call parent to handle position saving
        super().mouseReleaseEvent(event)
        
        # Left Click: Toggle Graph Mode
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is in graph area (roughly bottom half)
            rect = self.rect()
            graph_y = 260  # Updated to match new graph position
            if event.position().y() > graph_y:
                self.show_projection = not self.show_projection
                self.update()
        
        # Right Click: Prevent Crash / Do Nothing
        elif event.button() == Qt.MouseButton.RightButton:
            event.accept()  # Swallow event
            pass
