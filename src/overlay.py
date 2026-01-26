# NOTE: Always analyze and implement project tracking.md
import tkinter as tk
import time
import sys
import winsound

class Overlay:
    def __init__(self, root):
        self.root = root
        self.root.title("Elden Ring Overlay")
        # Increase size as requested: "zone soit un poil plus grande"
        # Position: Top-Right. 20px from top. 
        # Using negative offset for right alignment: -50 means 50px from right edge.
        self.root.geometry("600x120-50+20") 
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Style: White text, Black outline, Slightly reduced opacity
        # Using chroma key for transparency
        self.root.attributes("-transparentcolor", "#000001")
        self.root.configure(bg="#000001")
        self.root.attributes("-alpha", 0.50)

        # Canvas for custom text drawing (outlines)
        self.canvas = tk.Canvas(self.root, bg="#000001", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.current_text = "Waiting..."
        
        # Timer state
        self.phases = [
            {"name": "Day 1 - Storm", "duration": 270},       # 4:30
            {"name": "Day 1 - Shrinking", "duration": 180},   # 3:00
            {"name": "Day 1 - Storm 2", "duration": 210},     # 3:30
            {"name": "Day 1 - Shrinking 2", "duration": 180}, # 3:00
            {"name": "Boss 1", "duration": 0},                # Manual
            {"name": "Day 2 - Storm", "duration": 270},
            {"name": "Day 2 - Shrinking", "duration": 180},
            {"name": "Day 2 - Storm 2", "duration": 210},
            {"name": "Day 2 - Shrinking 2", "duration": 180},
            {"name": "Boss 2", "duration": 0},
            {"name": "Day 3 - Preparation", "duration": 0},
            {"name": "Day 3 - Final Boss", "duration": 0}
        ]
        self.current_phase_index = -1
        self.start_time = None
        self.running = False
        self.boss3_start_time = None  # Track when Day 3 Final Boss started
        self.day1_detection_time = None  # Track when Day 1 was first detected
        
        # Add drag functionality
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        
        # Quit Shortcut
        self.root.bind("<Control-q>", self.quit_app)
        self.root.bind("<q>", self.quit_app) # Simple q for quick exit
        
        self.x = 0
        self.y = 0

        self.is_recording = False # New state for recording indicator
        self.last_beep_second = -1 # Track last beep to avoid duplicate beeps in same second
        self.frozen = False # Victory/stopped state
        self.current_score = 0 # Latest OCR score

        self.setup_menu()
        
        # Start the update loop
        self.update_timer()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
    
    def reset_timer(self):
         self.running = False
         self.current_phase_index = -1
         self.current_text = "Waiting..."
         self.update_view()

    def trigger_day_1(self, start_timestamp=None):

        # Check if we are already in Day 1 sequence
        is_in_day_1 = (0 <= self.current_phase_index <= 3)
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        # Debounce: If we are already in Day 1, ONLY reset if it's been running for > 15 seconds.
        # This prevents the timer from resetting constantly while the "Day 1" banner is on screen (which stays for ~5-10s).
        # But allows a restart (which would happen much later).
        if not is_in_day_1 or elapsed > 15:
            # Stocker le timestamp de détection du jour 1 pour le calcul du temps total
            detection_time = start_timestamp if start_timestamp else time.time()
            if self.day1_detection_time is None:
                self.day1_detection_time = detection_time
            self.set_phase(0, start_timestamp)

    def trigger_day_2(self, start_timestamp=None):
        is_in_day_2 = (5 <= self.current_phase_index <= 8)
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        if not is_in_day_2 or elapsed > 15:
            self.set_phase(5, start_timestamp)

    def trigger_day_3(self, start_timestamp=None):
        # Day 3 - Preparation is index 10
        is_in_day_3 = (self.current_phase_index == 10 or self.current_phase_index == 11)
        
        if not is_in_day_3:
            self.set_phase(10, start_timestamp)

    def trigger_final_boss(self, start_timestamp=None):
        # Day 3 - Final Boss is index 11
        if self.current_phase_index != 11:
            self.set_phase(11, start_timestamp)
            # Track when boss 3 started
            self.boss3_start_time = start_timestamp if start_timestamp else time.time()

    def stop_timer(self):
        """Stops the timer but keeps the window open (Violence/Victory State)."""
        print("Overlay: stop_timer() called - freezing timer")
        self.frozen = True
        self.running = False  # Also stop running flag
        
        # Calculate times
        now = time.time()
        total_time = 0
        boss3_time = 0
        
        # Le temps total est entre la détection du jour 1 et la détection de "recompense"
        if self.day1_detection_time:
            total_time = now - self.day1_detection_time
        elif self.start_time:
            # Fallback si day1_detection_time n'est pas défini
            total_time = now - self.start_time
        
        if self.boss3_start_time:
            boss3_time = now - self.boss3_start_time
        
        # Format times
        def format_time(seconds):
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins:02}:{secs:02}"
        
        # Store final times for display
        self.final_total_time = format_time(total_time)
        self.final_boss3_time = format_time(boss3_time)
        
        if hasattr(self, 'timer_label'):
             self.timer_label.config(fg='#00FF00') # Green for victory

    def reset_timer(self):
        self.frozen = False
        self.current_phase_index = -1
        self.start_time = 0
        self.boss3_start_time = None
        self.day1_detection_time = None  # Réinitialiser le timestamp du jour 1
        if hasattr(self, 'label'): self.label.config(text="Waiting...", fg='white')
        if hasattr(self, 'timer_label'): self.timer_label.config(text="00:00", fg='white')

    def set_phase(self, index, start_timestamp=None):
        self.frozen = False # Always unfreeze on phase change
        if 0 <= index < len(self.phases):
            self.current_phase_index = index
            self.start_time = start_timestamp if start_timestamp else time.time()
            self.running = True
            
    def next_phase(self):
        self.set_phase(self.current_phase_index + 1)

    def update_view(self):
        self.canvas.delete("all")
        text = self.current_text
        
        # Right Aligned
        # Width is 600. Padding 10px from right -> x=590
        x, y = 590, 60 
        font_spec = ("Helvetica", 24, "bold")
        
        # Draw Outline (simulated with offsets)
        offsets = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
            (-2, 0), (2, 0), (0, -2), (0, 2)
        ]
        for ox, oy in offsets:
            self.canvas.create_text(x+ox, y+oy, text=text, font=font_spec, fill="black", anchor="e")
            
        # Draw Main Text
        self.canvas.create_text(x, y, text=text, font=font_spec, fill="white", anchor="e")

        # Draw Score (Small text below)
        if self.current_score > 0:
            score_text = f"Accuracy: {int(self.current_score)}%"
            score_font = ("Helvetica", 10, "bold")
            # Draw score outline
            for ox, oy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                self.canvas.create_text(x+ox, y+40+oy, text=score_text, font=score_font, fill="black", anchor="e")
            # Draw score text
            self.canvas.create_text(x, y+40, text=score_text, font=score_font, fill="#AAAAAA", anchor="e")

    def show_recording(self, show: bool):
        self.is_recording = show

    def set_ocr_score(self, score: float):
        self.current_score = score

    def update_timer(self):
        # Check if timer is frozen (victory/failure state)
        if hasattr(self, 'frozen') and self.frozen:
            # Timer is stopped, show final times
            if hasattr(self, 'final_total_time') and hasattr(self, 'final_boss3_time'):
                self.current_text = f"Total: {self.final_total_time} | Boss 3: {self.final_boss3_time}"
            else:
                self.current_text = "Arrêté"
            self.update_view()
            self.root.after(100, self.update_timer)
            return
        
        if self.running and self.start_time and self.current_phase_index >= 0:
            phase = self.phases[self.current_phase_index]
            elapsed = time.time() - self.start_time
            
            if phase["duration"] > 0:
                remaining = max(0, phase["duration"] - elapsed)
                remaining_int = int(remaining)
                
                if remaining == 0:
                    self.next_phase()
                    self.root.after(100, self.update_timer) # Schedule next immediately
                    return 

                mins = int(remaining // 60)
                secs = int(remaining % 60)
                timer_str = f"{mins:02}:{secs:02}"
                
                # Audio Beeps (Shrinking warning and Final Countdown)
                # REMOVED PER USER REQUEST: "enlever les bip la ou il y a deja du text to speach"
                # if remaining_int in [30, 10, 3, 2, 1] and remaining_int != self.last_beep_second:
                #      # Different tone for final 3s?
                #      freq = 1500 if remaining_int <= 3 else 1000
                #      try:
                #          winsound.Beep(freq, 200)
                #      except: pass
                #      self.last_beep_second = remaining_int
                
                # if remaining_int not in [30, 10, 3, 2, 1]:
                #     self.last_beep_second = -1

            else:
                # Stopwatch (Boss mode)
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                timer_str = f"{mins:02}:{secs:02}"
                
            # Check for upcoming phase warning (30s before)
            prefix = ""
            if self.is_recording:
                prefix += "🔴 "

            # Only checking if we are in a timed phase, theoretically.
            if phase["duration"] > 0:
                remaining = max(0, phase["duration"] - elapsed)
                next_idx = self.current_phase_index + 1
                if next_idx < len(self.phases) and "Shrinking" in self.phases[next_idx]["name"]:
                    if remaining <= 30:
                        # Blink every 500ms
                        if int(time.time() * 2) % 2 == 0:
                            prefix += "⚠️ "
            
            self.current_text = f"{prefix}{phase['name']} - {timer_str}"
        else:
            self.current_text = "Waiting for Day 1..."
            if self.is_recording:
                self.current_text = "🔴 " + self.current_text
            
        self.update_view()
        self.root.after(100, self.update_timer)

    def setup_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Next Phase", command=self.next_phase)
        self.menu.add_separator()
        self.menu.add_command(label="Exit (Q)", command=self.quit_app)
        self.root.bind("<Button-3>", self.show_menu)

    def show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def quit_app(self, event=None):
        self.root.destroy()
        sys.exit()

    def show(self):
        self.root.deiconify()

    def hide(self):
        self.root.withdraw()
