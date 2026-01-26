import mss
import json

# Get all monitors
with mss.mss() as sct:
    monitors = sct.monitors
    print("=== Configuration des écrans ===\n")
    for i, m in enumerate(monitors):
        print(f"Écran {i}: {m}")
    
    # Load config
    with open("data/config.json", "r") as f:
        config = json.load(f)
    
    monitor_region = config.get("monitor_region", {})
    menu_region = config.get("menu_region", {})
    runes_region = config.get("runes_region", {})
    
    print("\n=== Régions configurées ===\n")
    print(f"Monitor (zone de jeu): {monitor_region}")
    print(f"Menu: {menu_region}")
    print(f"Runes: {runes_region}")
    
    # Check which monitor contains each region
    print("\n=== Analyse ===\n")
    
    def find_monitor(x, y):
        for i, m in enumerate(monitors[1:], 1):  # Skip monitor 0 (virtual)
            if (m['left'] <= x < m['left'] + m['width'] and 
                m['top'] <= y < m['top'] + m['height']):
                return i, m
        return None, None
    
    # Check monitor region
    mon_idx, mon = find_monitor(monitor_region['left'], monitor_region['top'])
    print(f"Monitor region est sur l'écran {mon_idx}: {mon}")
    
    # Check menu region
    menu_idx, menu_mon = find_monitor(menu_region['left'], menu_region['top'])
    print(f"Menu region est sur l'écran {menu_idx}: {menu_mon}")
    
    # Check runes region
    runes_idx, runes_mon = find_monitor(runes_region['left'], runes_region['top'])
    print(f"Runes region est sur l'écran {runes_idx}: {runes_mon}")
    
    if mon_idx != menu_idx:
        print(f"\n⚠️ PROBLÈME: Le menu est sur l'écran {menu_idx}, mais la zone de jeu est sur l'écran {mon_idx}!")
    else:
        print(f"\n✓ OK: Tout est sur le même écran {mon_idx}")
