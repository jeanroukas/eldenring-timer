from typing import Dict, Optional

class RuneData:
    """
    Static data for Elden Ring level up costs.
    Source: Provided user table.
    """
    
    # Level -> Runes required to reach NEXT level (e.g., Level 1 -> 2 cost is at index 1? No, usually Level X cost is to reach X+1)
    # The user provided:
    # Level 2 Cost: 3,698 (To reach level 2? Or to go from 2 to 3? 
    # Usually "Level 2 ..... 3698" means "Cost to reach Level 2".
    # Character starts at Level 1 (Wretch) or higher.
    # User said: "on commence lvl 1 donc on affichera des le debut du jeu combien de runes pour passe lvl2."
    # So if I am Level 1, I need 3698 runes? Wait, 3698 seems high for Lvl 1->2. 
    # Let me double check standard tables or assume user data is law.
    # User table:
    # Level 1 | - | -
    # Level 2 | 3,698 | 3,698
    # Level 3 | 7,922 | 11,620
    #
    # Standard Elden Ring Wiki:
    # Lvl 1->2: 673 runes.
    # The user's numbers are WAY higher.
    # Level 2 cost 3698?
    # Maybe this is "Shadow of the Erdtree" blessing levels? Or a specific mod?
    # User said: "Level 1 - -".
    # User said: "Level 2 3,698".
    # User said: "on commence lvl 1 donc on affichera des le debut du jeu combien de runes pour passe lvl2."
    # So if `current_level == 1`, target is 2. Cost is `_LEVEL_COSTS[2]`.
    # Let's map Target Level -> Cost to reach that level from previous.
    
    _LEVEL_COSTS = {
        2: 3698,
        3: 7922,
        4: 12348,
        5: 16798,
        6: 21818,
        7: 26869,
        8: 32137,
        9: 37624,
        10: 43335,
        11: 49271,
        12: 55439,
        13: 61840,
        14: 68479,
        15: 75358,
    }

    @staticmethod
    def get_runes_for_next_level(current_level: int) -> Optional[int]:
        """
        Returns the rune cost to reach (current_level + 1).
        """
        target_level = current_level + 1
        return RuneData._LEVEL_COSTS.get(target_level)

    @staticmethod
    def get_total_runes_for_level(target_level: int) -> Optional[int]:
        """
        Returns cumulative cost? (Not strictly requested but user data had column for it)
        User data row: Level 3 | 7,922 | 11,620 (3698 + 7922 = 11620).
        So logic holds.
        """
        if target_level > 15: return None
        # Minimal implementation for now
        total = 0
        for l in range(2, target_level + 1):
            cost = RuneData._LEVEL_COSTS.get(l, 0)
            total += cost
        return total

    @staticmethod
    def calculate_potential_level(current_level: int, current_runes: int) -> int:
        """
        Calculates the potential level reachable with current runes.
        """
        potential_level = current_level
        runes_left = current_runes
        
        while potential_level < 15:
            cost = RuneData.get_runes_for_next_level(potential_level)
            if cost is not None and runes_left >= cost:
                runes_left -= cost
                potential_level += 1
            else:
                break
                
        return potential_level
