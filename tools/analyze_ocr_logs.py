import os
import re
import json
import glob
from collections import defaultdict, Counter
import datetime

def parse_timestamp(ts_str):
    # format: HH:MM:SS
    try:
        return datetime.datetime.strptime(ts_str, "%H:%M:%S")
    except:
        return None

def analyze_ocr_logs():
    print("LOG ANALYZER: Starting analysis...")
    
    app_log_path = os.path.join(os.getcwd(), "application.log")
    
    ocr_events = []
    sys_stats = []
    
    # Regex patterns
    # 2026-01-25 12:56:06,239 - ...
    log_pattern = re.compile(r"(\d{2}:\d{2}:\d{2}),\d+.*OCR: '([^']*)' \(Filter: (True|False), Score: (\d+)\) Br:([\d.]+) Dur:(\d+)ms")
    # [SESSION LOG] SYSTEM_RESOURCE_STATS: {'cpu': 28.0, 'ram': 77.3}
    sys_pattern = re.compile(r"(\d{2}:\d{2}:\d{2}),\d+.*SYSTEM_RESOURCE_STATS: \{'cpu': ([\d.]+), 'ram': ([\d.]+)\}")
    
    if os.path.exists(app_log_path):
        print(f"Reading {app_log_path}...")
        try:
            with open(app_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    # Parse OCR
                    match_ocr = log_pattern.search(line)
                    if match_ocr:
                        timestamp, text, filtered, score, brightness, duration = match_ocr.groups()
                        ocr_events.append({
                            "time": timestamp,
                            "dt": parse_timestamp(timestamp),
                            "text": text,
                            "duration": int(duration)
                        })
                        continue # Optimization
                        
                    # Parse Sys Stats
                    match_sys = sys_pattern.search(line)
                    if match_sys:
                         timestamp, cpu, ram = match_sys.groups()
                         sys_stats.append({
                             "time": timestamp,
                             "dt": parse_timestamp(timestamp),
                             "cpu": float(cpu),
                             "ram": float(ram)
                         })

        except Exception as e:
            print(f"Error reading log: {e}")

    print(f"Found {len(ocr_events)} OCR events and {len(sys_stats)} System Stat entries.")
    
    if not sys_stats:
        print("No System Stats found in log. Cannot perform correlation.")
        return

    print("\n--- ANALYSIS: CPU SPIKES (>25%) ---")
    high_cpu_events = [s for s in sys_stats if s["cpu"] > 25.0]
    
    print(f"Found {len(high_cpu_events)} High CPU events.")
    
    for stat in high_cpu_events[:10]: # Check first 10
        # Find OCR activity in the 2 seconds surrounding this spike
        target_dt = stat["dt"]
        if not target_dt: continue
        
        nearby_ocr = [
            o for o in ocr_events 
            if o["dt"] and abs((o["dt"] - target_dt).total_seconds()) < 2
        ]
        
        ocr_count = len(nearby_ocr)
        avg_dur = sum(o["duration"] for o in nearby_ocr) / ocr_count if ocr_count > 0 else 0
        
        print(f"[{stat['time']}] CPU: {stat['cpu']}% | Nearby OCR scans: {ocr_count} | Avg OCR Dur: {avg_dur:.1f}ms")
        if ocr_count > 10:
             print("   -> ⚠️ HIGH OCR TRAFFIC")
        if avg_dur > 200:
             print("   -> ⚠️ SLOW OCR SCANS")
             
    # Correlation Summary
    print("\n--- CORRELATION SUMMARY ---")
    if high_cpu_events:
        total_high = len(high_cpu_events)
        correlated = 0
        for stat in high_cpu_events:
            target_dt = stat["dt"]
            if not target_dt: continue
            # Look for > 5 scans per second (approx Fast Mode)
            nearby_ocr = [o for o in ocr_events if o["dt"] and abs((o["dt"] - target_dt).total_seconds()) < 1]
            if len(nearby_ocr) > 5:
                correlated += 1
        
        print(f"{correlated}/{total_high} ({correlated/total_high*100:.1f}%) of CPU spikes align with High OCR Activity (Fast Mode/Burst).")
        
    print("\nDone.")

if __name__ == "__main__":
    analyze_ocr_logs()
