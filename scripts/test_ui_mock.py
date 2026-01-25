import sys
import os
import random
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ui.qt_overlay import UnifiedOverlay

app = QApplication(sys.argv)
overlay = UnifiedOverlay()
overlay.show()

# Mock Data
stats = {
    "level": 3,
    "missing_runes": 2450,
    "current_runes": 1500,
    "total_runes": 45120,
    "death_count": 1,
    "recovery_count": 1,
    "phase_name": "Day 2 - Storm",
    "spent_at_merchants": 12000,
    "rps": 340,
    "grade": "A",
    "delta_runes": 3200,
    "time_to_level": "4m 12s",
    "run_history": [1000 * i + random.randint(-500, 500) for i in range(50)],
    "transitions": [(20, "DAY 2")],
    "ocr_score": 98.0,
    "graph_start_time": 1000, 
    "graph_events": [{"t": 1025, "type": "DEATH"}, {"t": 1045, "type": "RECOVERY"}],
    "nr_config": {
        "snowball": 1.7,
        "goal": 452116,
        "duration": 2400
    }
}
overlay.set_score(98.0)
overlay.set_stats(stats)
overlay.set_timer_text("04:20")

# Simulate Updates
frame = 0
grades = ["S", "A", "B", "C", "D", "E", "F"]
def update():
    global frame
    frame += 1
    
    stats["current_runes"] += 100
    stats["total_runes"] += 100
    stats["run_history"].append(stats["total_runes"])
    if len(stats["run_history"]) > 100: stats["run_history"].pop(0)
    
    stats["rps"] = random.randint(300, 400)
    
    # Auto-cycle grades to test colors
    cycle_idx = (frame // 20) % len(grades)
    stats["grade"] = grades[cycle_idx]
    
    # Vary Delta
    stats["delta_runes"] = 5000 - (frame * 50) # Drift from +5k to negative
    
    # Cycle Waiting / Active
    if (frame // 50) % 2 == 0:
        stats["phase_name"] = "Day 1 - Storm"
        overlay.set_timer_text("04:20")
    else:
        stats["phase_name"] = "WAITING"
        overlay.set_timer_text("00:00")
    
    overlay.set_stats(stats)

timer = QTimer()
timer.timeout.connect(update)
timer.start(100)

print("UI Mock Running... Close window to exit.")
sys.exit(app.exec())
