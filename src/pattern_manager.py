import json
import os
import threading
import time
import difflib
from fuzzywuzzy import fuzz
from collections import defaultdict

class PatternManager:
    def __init__(self, filepath="ocr_patterns.json"):
        self.filepath = filepath
        self.lock = threading.RLock()
        self.patterns = {}
        self.stats = {"day1_count": 0, "day2_count": 0} 
        
        self.defaults = {
            "JOUR III": {"target": "DAY 3", "weight": 60},
            "JOUR 3":   {"target": "DAY 3", "weight": 60},
            "JOU III":  {"target": "DAY 3", "weight": 40},
            "JOUR HI":  {"target": "DAY 3", "weight": 50},  # Variante OCR (HI au lieu de III)
            "JOURHI":   {"target": "DAY 3", "weight": 50},  # Variante sans espace
            "JOURIII":  {"target": "DAY 3", "weight": 70},  # Variante sans espace (Strict Whitelist)
            
            "JOUR 2": {"target": "DAY 2", "weight": 60},
            "JOUR II": {"target": "DAY 2", "weight": 60},
            "JOURII": {"target": "DAY 2", "weight": 60},  # Variante sans espace
            "JOURIL": {"target": "DAY 2", "weight": 50},  # Variante OCR (L au lieu de II)
            "JOU II": {"target": "DAY 2", "weight": 40},
            "JOU IL": {"target": "DAY 2", "weight": 40},
            
            "JOUR 1": {"target": "DAY 1", "weight": 60},
            "JOUR I":  {"target": "DAY 1", "weight": 60},
            "JOURI":  {"target": "DAY 1", "weight": 60},
            "JOU I":  {"target": "DAY 1", "weight": 40},
            
            # --- Day 3 Noise Patterns (Log Derived) ---
            "JQUR IIL": {"target": "DAY 3", "weight": 50},
            "JOUR ITE": {"target": "DAY 3", "weight": 50},
            "FOUR IIE": {"target": "DAY 3", "weight": 50},
            "FOUR ITE": {"target": "DAY 3", "weight": 50},
            "JOURTH":   {"target": "DAY 3", "weight": 50},
            "JOUR III": {"target": "DAY 3", "weight": 70}, # Boost exact match
            
            # --- Victory Check ---
            "RESULTAT": {"target": "VICTORY", "weight": 80},
            "RESULTIT": {"target": "VICTORY", "weight": 70},
            "RESULT":   {"target": "VICTORY", "weight": 70},
        }
        
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                # Check if file is empty
                if os.path.getsize(self.filepath) == 0:
                    print("Pattern file is empty, restoring defaults...")
                    self.patterns = self.defaults.copy()
                    self.save()
                    return
                
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        print("Pattern file is empty, restoring defaults...")
                        self.patterns = self.defaults.copy()
                        self.save()
                        return
                    
                    data = json.loads(content)
                    self.patterns = data.get("patterns", {})
                    self.stats = data.get("stats", self.stats)
                
                # Merge defaults if missing (Robustness)
                needs_save = False
                for key, val in self.defaults.items():
                    if key not in self.patterns:
                         print(f"Restoring default pattern: {key}")
                         self.patterns[key] = val
                         needs_save = True
                
                # Save if we added defaults
                if needs_save:
                    self.save()
                         
            except json.JSONDecodeError as e:
                print(f"Error loading patterns (JSON invalid): {e}")
                print("Restoring defaults and saving...")
                self.patterns = self.defaults.copy()
                self.save()
            except Exception as e:
                print(f"Error loading patterns: {e}")
                print("Restoring defaults and saving...")
                self.patterns = self.defaults.copy()
                self.save()
        else:
            self.patterns = self.defaults.copy()
            self.save()

    def save(self):
        with self.lock:
            try:
                with open(self.filepath, 'w') as f:
                    json.dump({
                        "patterns": self.patterns,
                        "stats": self.stats
                    }, f, indent=4)
            except Exception as e:
                print(f"Error saving patterns: {e}")

    def evaluate(self, input_text, text_width=0, center_offset=None, word_data=None):
        """
        Evaluates input text against known patterns.
        Incorporates Granular Geometric Validation (word positions).
        """
        if not input_text:
            return None, 0
            
        input_text = input_text.upper()
        if len(input_text.strip()) < 4:
            return None, 0
            
        best_target = None
        max_score = 0
        
        # --- Word-Lock: Must contain at least one word similar to 'JOUR' ---
        # This prevents tips/loading text from triggering.
        has_jour_anchor = False
        if word_data:
            for w in word_data:
                # Even a bit of leeway for "J0UR" or "JOURI"
                if fuzz.ratio(w["text"], "JOUR") > 75:
                    has_jour_anchor = True
                    break
        
        # Fallback: Check full text if word check failed
        # Handles "JO URI" -> "JOURI" case where word split occurs mid-word
        if not has_jour_anchor:
            normalized_nospace = input_text.replace(" ", "")
            if "JOUR" in normalized_nospace or "JOU" in normalized_nospace:
                 has_jour_anchor = True
        
        if not has_jour_anchor:
            return None, 0
            
        # --- Specific Noise Killers ---
        # OCR often reads banner textures as 'TI', 'IT', or 'T'
        input_noise_penalty = 0
        if any(x in input_text for x in ["TI", "IT", "JOURT"]):
             input_noise_penalty = 40
        
        for pattern, data in self.patterns.items():
            # Fuzzy match score (0-100)
            ratio = fuzz.ratio(input_text, pattern)
            
            # Base score combined with pattern weight
            score = (ratio / 100.0) * data["weight"]
            score -= input_noise_penalty # Kill noise
            
            # --- Exact Match Boost ---
            if input_text == pattern:
                score += 50 
            
            # --- Length Penalty ---
            len_diff = abs(len(input_text) - len(pattern))
            if len_diff >= 1:
                score -= len_diff * 5
            
            # --- Granular Geometric Validation ---
            if text_width > 0:
                # 1. Width Logic - REMOVED strict pixel thresholds due to animation shrink.
                
                # 2. Character Count Consistency Logic
                # "JOUR I" = 6 chars
                # "JOUR II" = 7 chars
                # "JOUR III" = 8 chars
                actual_len = len(input_text.replace(" ", ""))
                if data["target"] == "DAY 1" and actual_len <= 5: # JOURI (5), JOUR I (5 if space ignored)
                     score += 10
                elif data["target"] == "DAY 2" and actual_len == 6: # JOURII (6)
                     score += 10
                elif data["target"] == "DAY 3" and actual_len >= 7: # JOURIII (7)
                     score += 10

                # 3. Centeredness Logic 
                if center_offset is not None:
                    if center_offset < 40:
                        score += 30 # Perfectly centered bonus
                    elif center_offset > 80:
                        score -= 60 # Off-center penalty
                
                # 3. Numeral Spacing Logic (Word-Level)
                # For "JOUR III", the numerals are far from the 'J'.
                # For "JOUR I", they are close.
                if word_data and len(word_data) >= 2:
                    jour_box = next((w for w in word_data if "JOUR" in w["text"]), None)
                    numeral_box = next((w for w in word_data if w["text"] in ["I", "II", "III", "1", "2", "3"]), None)
                    
                    if jour_box and numeral_box:
                        dist = abs(numeral_box["left"] - jour_box["left"])
                        if data["target"] == "DAY 3" and dist > 350:
                             score += 20 # Long numeral spacing confirmed
                        elif data["target"] in ["DAY 1", "DAY 2"] and dist < 250:
                             score += 20 # Short numeral spacing confirmed
                        elif data["target"] == "DAY 3" and dist < 200:
                             score -= 50 # Day 3 can't be that short
                        elif data["target"] == "DAY 1" and dist > 400:
                             score -= 50 # Day 1 can't be that long

            if score > max_score:
                max_score = score
                best_target = data["target"]
                
        # Final Strict Noise Threshold
        if max_score < 55: # Lowered from 65 to 55 for robustness
             return None, max_score

             
        return best_target, max_score

    def learn(self, text, target):
        """
        Reinforces a pattern. If text not known, adds it.
        """
        normalized = text.upper().strip()
        if not normalized: return

        with self.lock:
            if normalized in self.patterns:
                # Reinforce
                if self.patterns[normalized]["target"] == target:
                    self.patterns[normalized]["weight"] += 1
                else:
                    # Conflict! It was mapped to something else.
                    # Reduce the old one? Or overwrite if user manually forced it?
                    # User manually forced it -> Overwrite logic or heavy penalty
                    self.patterns[normalized]["weight"] -= 5
                    if self.patterns[normalized]["weight"] < 0:
                         self.patterns[normalized] = {"target": target, "weight": 5}
            else:
                # New pattern
                self.patterns[normalized] = {"target": target, "weight": 5}
            
            # Stats
            stat_key = f"{target.lower().replace(' ', '')}_count"
            if stat_key not in self.stats:
                self.stats[stat_key] = 0
            self.stats[stat_key] += 1
            
            self.save()
            print(f"PatternManager: Learned '{normalized}' -> {target}")

    def punish(self, text):
        """
        Reduces weight of a pattern because it caused a false positive.
        """
        normalized = text.upper().strip()
        # This is tricky because 'text' might be the full sentence containing the pattern.
        # We need to find which pattern triggered it. 
        # For simplicity, if the exact text is a pattern, punish it.
        # Ideally, we should punish all patterns that matched this text.
        
        with self.lock:
            # punishing known substrings
            normalized_nospace = normalized.replace(" ", "")
            
            for pattern in list(self.patterns.keys()):
                p_nospace = pattern.replace(" ", "")
                if pattern in normalized or p_nospace in normalized_nospace:
                    self.patterns[pattern]["weight"] -= 2
                    if self.patterns[pattern]["weight"] < 0:
                        del self.patterns[pattern]
            
            self.save()
            print(f"PatternManager: Punished patterns in '{normalized}'")
