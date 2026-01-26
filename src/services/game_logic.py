from typing import Tuple, Optional
from src.data.rune_data import RuneData

class NightreignLogic:
    """
    Centralized Game Logic & Invariants for Elden Ring Nightreign Mode.
    Serves as the Single Source of Truth for validity checks to filter OCR errors.
    """

    @staticmethod
    def calculate_minimum_total_runes(level: int, current_runes: int = 0) -> int:
        """
        Calculates the ABSOLUTE MINIMUM total runes a player must have earned to reach this state.
        Min Total = (Cumulative Cost 1->Level) + Current Runes.
        Does not include spending/death loss (which would only increase the total).
        """
        if level <= 1: return current_runes
        
        # Cumulative cost to reach current 'level' from 1
        # e.g. To be Level 5, you spent cost(1)+cost(2)+cost(3)+cost(4).
        spent_on_levels = RuneData.get_total_runes_for_level(level)
        return spent_on_levels + current_runes

    @staticmethod
    def is_valid_rune_reading(level: int, total_runes_in_graph: int, new_runes: int) -> bool:
        """
        Sanity Check: Is it possible to have 'new_runes' given our Level?
        This is a weak check, mainly for Level 1 starts or massive overflows.
        """
        # 1. Negative is impossible
        if new_runes < 0: return False
        
        # 2. Cap check (Level 15 limit ~500k total). 
        # If we see 1,000,000 runes, it's likely an OCR error.
        if new_runes > 1000000: return False
        
        return True

    @staticmethod
    def is_death_confirmed(old_level: int, new_level: int, new_runes: int, 
                          last_black_screen_time: float, current_time: float) -> bool:
        """
        Determines if a state change represents a VALID Death.
        Rule: 
        1. Level drops EXACTLY by 1.
        2. Runes drop to near zero (< 50).
        3. Black Screen occurred recently (last 12s) - STRICT REQUIREMENT reinstated.
        """
        # 1. Level Drop Strict
        if old_level - new_level != 1:
            return False
            
        # 2. Runes Near Zero
        if new_runes >= 50:
            return False
            
        # 3. Black Screen Requirement
        if current_time - last_black_screen_time > 12.0:
            return False
            
        return True

    @staticmethod
    def map_fuzzy_day_trigger(ocr_text: str, current_phase_index: int) -> Optional[int]:
        """
        Maps OCR text to a Day Target, allowing fuzzy matches IF the Phase Prerequisite is met.
        
        Indices:
        - Boss 1 Phase: 4 (Wait for Day 2)
        - Boss 2 Phase: 9 (Wait for Day 3)
        """
        text = ocr_text.upper()
        
        # Rule: Use fuzzy matching to detect "JOUR" or "DAY" even with typos (e.g. "JOOR")
        # But prevent "accepting everything" by checking similarity > threshold.
        import difflib
        
        # Clean text
        text = text.strip()
        if len(text) > 20: return None # Reject long sentences
        
        # Candidates to check against
        candidates = ["JOUR", "DAY", "JOUR I", "JOUR II", "JOUR III"]
        
        best_ratio = 0.0
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, text, cand).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                
        # Threshold: 
        # "JOOR" vs "JOUR" = 0.75. 
        # "J0UR" vs "JOUR" = 0.75.
        # "JOU" vs "JOUR" = 0.85 (substring logic handled by SequenceMatcher partly or just use substring? SequenceMatcher handles replacements better)
        
        # We accept if > 0.7
        is_match = (best_ratio > 0.7)
        
        # Also assume substrings are valid if they are literally "JOUR" or "DAY"
        if "JOUR" in text or "DAY" in text:
            is_match = True
            
        if not is_match:
             return None
             
        # Phase Mapping
        if current_phase_index == 4: # Boss 1 -> Day 2
             return 2
        if current_phase_index == 9: # Boss 2 -> Day 3
             return 3
             
        return None

    @staticmethod
    def validate_graph_monotonicity(current_total: int, last_total: int, 
                                  is_death: bool, is_spending: bool) -> int:
        """
        Enforces the 'Ratchet' rule: Total Wealth cannot drop unless Death or Spending occurred.
        Returns the VALID total (clamped if necessary).
        """
        # If we have a valid reason to drop, accept the new value
        if is_death or is_spending:
            return current_total
            
        # Otherwise, if it drops, it's a glitch. Clamp to last high value.
        if current_total < last_total:
            return last_total
            
        return current_total
