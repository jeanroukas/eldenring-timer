from typing import Tuple, Optional, List
import time
import difflib
from src.services.rune_data import RuneData
from src.logger import logger

class GameRules:
    """
    Centralized Game Logic & Invariants for Elden Ring Nightreign Mode.
    Serves as the Single Source of Truth for validity checks, transitions, and math.
    Pure Logic Layer - No UI or State dependencies.
    """

    # --- MATH & VALIDATION ---

    @staticmethod
    def calculate_minimum_total_runes(level: int, current_runes: int = 0) -> int:
        """
        Calculates the ABSOLUTE MINIMUM total runes a player must have earned to reach this state.
        Min Total = (Cumulative Cost 1->Level) + Current Runes.
        """
        if level <= 1: return current_runes
        spent_on_levels = RuneData.get_total_runes_for_level(level)
        return spent_on_levels + current_runes

    @staticmethod
    def is_valid_rune_reading(level: int, new_runes: int) -> bool:
        """
        Sanity Check: Is it possible to have 'new_runes' given our Level?
        """
        if new_runes < 0: return False
        if new_runes > 1000000: return False # Cap check
        return True

    @staticmethod
    def validate_graph_monotonicity(current_total: int, last_total: int, 
                                  is_death: bool, is_spending: bool) -> int:
        """
        Enforces the 'Ratchet' rule: Total Wealth cannot drop unless Death or Spending occurred.
        Returns the VALID total (clamped if necessary).
        """
        if is_death or is_spending:
            return current_total
        if current_total < last_total:
            return last_total
        return current_total

    # --- DEATH LOGIC ---

    @staticmethod
    def is_death_confirmed(old_level: int, new_level: int, new_runes: int, 
                          last_black_screen_time: float = 0.0) -> bool:
        """
        Determines if a state change represents a VALID Death.
        Rule (ALL 3 conditions required):
        1. Level drops EXACTLY by 1.
        2. Runes drop to near zero (< 50).
        3. Black screen detected within last 5 seconds (REQUIRED per user questionnaire).
        
        Args:
            old_level: Previous level
            new_level: New level
            new_runes: New rune count
            last_black_screen_time: Timestamp of last black screen detection
            
        Returns:
            True if all 3 death conditions are met
        """
        import time
        
        # Condition 1: Level drop exactly 1
        if old_level - new_level != 1: 
            return False
        
        # Condition 2: Runes near zero
        if new_runes >= 50: 
            return False
        
        # Condition 3: Black screen within last 5 seconds (REQUIRED)
        if last_black_screen_time == 0.0:
            return False  # No black screen detected yet
        
        time_since_black = time.time() - last_black_screen_time
        if time_since_black > 5.0:
            return False  # Black screen too old
        
        return True

    # --- OCR MAPPING ---

    @staticmethod
    def map_fuzzy_day_trigger(ocr_text: str, current_phase_index: int) -> Optional[int]:
        """
        Maps OCR text to a Day Target, allowing fuzzy matches IF the Phase Prerequisite is met.
        """
        text = ocr_text.upper().strip()
        if len(text) > 20: return None
        
        candidates = ["JOUR", "DAY", "JOUR I", "JOUR II", "JOUR III"]
        best_ratio = 0.0
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, text, cand).ratio()
            if ratio > best_ratio: best_ratio = ratio
                
        is_match = (best_ratio > 0.7) or ("JOUR" in text or "DAY" in text)
        if not is_match: return None
             
        # Contextual Boost
        if current_phase_index == 4: return 2 # Boss 1 -> Day 2
        if current_phase_index == 9: return 3 # Boss 2 -> Day 3
        return None

    # --- TRANSITION LOGIC ---

    @staticmethod
    def get_transition_penalty(target_day: str, current_phase_index: int, 
                             current_runes: int, elapsed_in_run: float, debug_mode: bool = False) -> int:
        """
        Calculates penalty score for a transition trigger based on current game state.
        Returns 0 if neutral, negative values for unlikely/impossible transitions.
        """
        # Phase mappings: Day 1 (0-4), Day 2 (5-9), Day 3 (10-11)
        
        # 1. Reverse Transitions
        if target_day == "DAY 1":
            if current_phase_index >= 5: return -35
            # Strict Rune Lockout (Reset Protection)
            if current_runes > 20:
                if debug_mode: logger.debug(f"Reset Lockout: Runes detected ({current_runes}). Large penalty.")
                return -100
            # Final Boss Lockout
            if current_phase_index >= 11: return -120

        if target_day == "DAY 2" and current_phase_index >= 10:
            return -35
            
        # 2. Skips
        if target_day == "DAY 3" and current_phase_index < 5:
            return -40
            
        # 3. Premature Forward Transitions
        # Day 1 -> Day 2: Should happen after Boss 1 (Index 4)
        if target_day == "DAY 2" and current_phase_index < 4:
            # Enforce 12 min (720s) minimum if not in Boss phase
            if elapsed_in_run < 720: return -100
            else: return -30 # Soft penalty
                
        # Day 2 -> Day 3: Should happen after Boss 2 (Index 9)
        if target_day == "DAY 3" and 4 < current_phase_index < 9:
            return -100
            
        return 0

    @staticmethod
    def is_transition_allowed(target_day: str, current_phase_index: int, 
                            current_run_level: int, current_runes: int, 
                            elapsed_in_run: float, last_black_screen_time: float, 
                            is_manual: bool = False, debug_mode: bool = False,
                            is_startup: bool = False) -> bool:
        """
        Determines if a phase transition is legally allowed by the Game Rules.
        """
        now = time.time()

        if target_day == "DAY 1":
            # Guard: OCR triggers for Day 1 must follow a black screen (within 15s)
            # EXCEPTION: Startup/Waiting for Day 1 sequence (NASA-grade trigger)
            if not is_manual and not is_startup:
                if now - last_black_screen_time > 15.0:
                    if debug_mode: logger.debug(f"BLOCKED Transition to DAY 1: No recent black screen.")
                    return False

            # Block accidental Day 1 resets if deep in run (Level > 5 or Runes > 200)
            # Exception: Manual Trigger
            if not is_manual:
                if current_run_level > 5 or current_runes > 200:
                    logger.warning(f"BLOCKED Transition to DAY 1: Level {current_run_level} > 5 or Runes {current_runes} > 200.")
                    return False
            return True
            
        elif target_day == "DAY 2":
            # STRICT: Must be in Boss 1 Phase (Index 4)
            if current_phase_index == 4: return True
            
            # FALLBACK: Manual Override
            if is_manual:
                logger.info(f"DAY 2 Transition ALLOWED (Manual Override): Phase {current_phase_index}")
                return True
            
            logger.warning(f"BLOCKED Transition to DAY 2: Phase {current_phase_index} != Boss 1. (Strict Logic)")
            return False

        elif target_day == "DAY 3":
            # STRICT: Must be in Boss 2 Phase (Index 9)
            if current_phase_index == 9: return True
            
            # FALLBACK: Manual Override
            if is_manual:
                logger.info(f"DAY 3 Transition ALLOWED (Manual Override): Phase {current_phase_index}")
                return True
                
            logger.warning(f"BLOCKED Transition to DAY 3: Phase {current_phase_index} != Boss 2. (Strict Logic)")
            return False
             
        return False
