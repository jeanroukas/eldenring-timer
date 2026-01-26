import numpy as np
import matplotlib.pyplot as plt

def get_curve(t, duration, start_val, end_val, exponent):
    t_norm = np.clip(t / duration, 0, 1)
    return start_val + (end_val - start_val) * (t_norm ** exponent)

# Common params
day_duration = 840 # 14 minutes
total_duration = day_duration * 2
boss1_drop = 50000

t = np.linspace(0, total_duration, 1680)

# OLD CURVE (1.7 exp, Level 9 target)
y_old = np.zeros_like(t)
runes_day1_end_old = 160000
runes_day2_end_old = 437578 # L14

for i, ts in enumerate(t):
    if ts < day_duration:
        y_old[i] = get_curve(ts, day_duration, 0, runes_day1_end_old, 1.7)
    else:
        y_old[i] = get_curve(ts - day_duration, day_duration, runes_day1_end_old + boss1_drop, runes_day2_end_old, 1.7)

# NEW CURVE (1.2 exp, Level 9.5 target)
y_new = np.zeros_like(t)
runes_day1_end_new = 180881 # L9.5
runes_day2_end_new = 437578 # L14

for i, ts in enumerate(t):
    if ts < day_duration:
        y_new[i] = get_curve(ts, day_duration, 0, runes_day1_end_new, 1.2)
    else:
        y_new[i] = get_curve(ts - day_duration, day_duration, runes_day1_end_new + boss1_drop, runes_day2_end_new, 1.2)

# Plotting
plt.figure(figsize=(12, 6))
plt.plot(t / 60, y_old, label='Old Curve (1.7 exp, L9)', color='orange', linestyle='--', alpha=0.7)
plt.plot(t / 60, y_new, label='New Curve (1.2 exp, L9.5)', color='green', linewidth=2)

# Markers
plt.axvline(x=14, color='white', linestyle=':', alpha=0.3)
plt.text(14.5, 500000, 'Boss 1', color='white')

plt.axhline(y=runes_day1_end_new, color='green', linestyle=':', alpha=0.5)
plt.text(0, runes_day1_end_new + 5000, ' L9.5 (180k)', color='green')

plt.axhline(y=runes_day2_end_new, color='gold', linestyle=':', alpha=0.5)
plt.text(0, runes_day2_end_new + 5000, ' L14 (437k)', color='gold')

plt.title('Elden Ring Ideal Rune Curve Comparison', color='white', fontsize=14)
plt.xlabel('Time (minutes)', color='white')
plt.ylabel('Total Runes', color='white')
plt.legend()
plt.grid(True, alpha=0.1)

# Style (Nightreign theme)
plt.gca().set_facecolor('#0a0a0a')
plt.gcf().set_facecolor('#0a0a0a')
plt.tick_params(colors='white')

plt.tight_layout()
plt.savefig('curve_comparison.png', dpi=150)
print("Plot saved as curve_comparison.png")
