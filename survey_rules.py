import json
import os

QUESTIONS = [
    {
        "id": "q1_snowball",
        "category": "Math Model",
        "question": "1. Facteur Snowball : Doc=1.7 vs Code=1.7 vs Formule 'ratio ** 1.2'. Quelle est la bonne valeur ?",
        "default": "1.7"
    },
    {
        "id": "q2_farming_goal",
        "category": "Math Model",
        "question": "2. Objectif Farm (Total) : Doc=452,116 vs Code=400,000. Quel chiffre pour le Lvl 15 ?",
        "default": "452116"
    },
    {
        "id": "q3_day1_duration",
        "category": "Math Model",
        "question": "3. Durée Jour 1 : Segments précis (270s/180s) ou Courbe lisse 0-20min ?",
        "default": "Segments"
    },
    {
        "id": "q4_start_offset",
        "category": "Math Model",
        "question": "4. Offset de Départ (-15s) : Doit-on STRICTEMENT soustraire 15s à tout calcul ?",
        "default": "Oui"
    },
    {
        "id": "q5_boss1_drop",
        "category": "Math Model",
        "question": "5. Boss 1 Drop : Fixé à 11,000 ou Variable ?",
        "default": "Fixe"
    },
    {
        "id": "q6_boss2_drop",
        "category": "Math Model",
        "question": "6. Boss 2 Drop : Fixé à 50,000 ou Dynamique (OCR) ?",
        "default": "Fixe"
    },
    {
        "id": "q7_black_screen",
        "category": "Death & Recovery",
        "question": "7. Écran Noir (Mort) : Code exige <12s. Doc dit 'pas obligatoire'. Qui a raison ?",
        "default": "Pas obligatoire"
    },
    {
        "id": "q8_death_runes",
        "category": "Death & Recovery",
        "question": "8. Seuil Runes Mort : Code < 50. Faut-il monter à 100 pour la tolérance ?",
        "default": "50"
    },
    {
        "id": "q9_double_level_drop",
        "category": "Death & Recovery",
        "question": "9. Chute Niveau > 1 : Rejeter comme glitch (Code) ou Accepter comme mort (Lag) ?",
        "default": "Rejeter"
    },
    {
        "id": "q10_recovery_tol",
        "category": "Death & Recovery",
        "question": "10. Récupération : Tolérance ±5 runes suffisante ?",
        "default": "Oui"
    },
    {
        "id": "q11_double_death",
        "category": "Death & Recovery",
        "question": "11. Double Mort : Garder les runes perdues dans le 'Total Acquis' (Potentiel) ou les supprimer ?",
        "default": "Garder"
    },
    {
        "id": "q12_day2_req",
        "category": "Transitions",
        "question": "12. Passage Jour 2 : Strictement après Boss 1 ou Backdoor autorisé (Lvl 5+/10m+) ?",
        "default": "Backdoor"
    },
    {
        "id": "q13_day3_req",
        "category": "Transitions",
        "question": "13. Passage Jour 3 : Strictement après Boss 2 ou Backdoor autorisé (Lvl 10+) ?",
        "default": "Backdoor"
    },
    {
        "id": "q14_reset_guard",
        "category": "Transitions",
        "question": "14. Bloquer Reset Jour 1 si Lvl > 5 : Trop strict pour Reset Manuel ?",
        "default": "Trop strict"
    },
    {
        "id": "q15_min_duration",
        "category": "Transitions",
        "question": "15. Durée Min 12min pour Jour 2 : Pertinent pour Speedrun ?",
        "default": "Non"
    },
    {
        "id": "q16_digit_shift",
        "category": "Safety & UI",
        "question": "16. Glitch 'Digit Shift' (7774->7174) : Corriger silencieusement ou Afficher (⚠️) ?",
        "default": "Silencieux"
    },
    {
        "id": "q17_menu_scan",
        "category": "Safety & UI",
        "question": "17. Scan Menu : Seulement si icône Runes cachée. OK pour menu inventaire ?",
        "default": "Oui"
    },
    {
        "id": "q18_victory",
        "category": "Safety & UI",
        "question": "18. Victoire : Ajouter détection couleur (Bleu/Jaune) en plus du texte ?",
        "default": "Non"
    },
    {
        "id": "q19_ratchet",
        "category": "Safety & UI",
        "question": "19. Graphe Ratchet : Le graphe ne descend JAMAIS sur glitchs OCR. Comportement voulu ?",
        "default": "Oui"
    },
    {
        "id": "q20_logic_migration",
        "category": "Architecture",
        "question": "20. Migrer 100% des maths de StateService vers GameRules ?",
        "default": "Oui"
    },
    {
        "id": "q21_clean_json",
        "category": "Architecture",
        "question": "21. Nettoyer ocr_patterns.json (Supprimer patterns YOU DIED inutilisés) ?",
        "default": "Oui"
    },
    {
        "id": "q22_constants",
        "category": "Architecture",
        "question": "22. Sortir les durées (Storm 270s) de StateService vers Config/GameRules ?",
        "default": "Oui"
    }
]

def run_survey():
    print("=========================================")
    print("   NIGHTREIGN RULE CLARIFICATION SURVEY  ")
    print("=========================================")
    print("Instructions: Appuyez sur ENTREE pour accepter la valeur par défaut entre [].")
    print("Sinon, tapez votre réponse (Doc, Code, ou explications).")
    print("-----------------------------------------\n")
    
    answers = {}
    
    for idx, q in enumerate(QUESTIONS):
        print(f"\n[{q['category']}]")
        print(f"{q['question']}")
        
        user_input = input(f"Réponse [{q['default']}] > ").strip()
        
        if not user_input:
            answers[q['id']] = q['default']
            print(f"-> {q['default']}")
        else:
            answers[q['id']] = user_input
            
    # Save
    filename = "rule_clarifications.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=4, ensure_ascii=False)
        
    print(f"\n\n[SUCCESS] Réponses sauvegardées dans '{filename}'.")
    print("L'agent va maintenant analyser ce fichier.")

if __name__ == "__main__":
    run_survey()
