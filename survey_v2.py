import json
import os

QUESTIONS = [
    {
        "id": "arch_eventbus",
        "category": "Architecture",
        "question": "1. EventBus vs PyQt Signals : Pourquoi un EventBus personnalisé pour la logique métier ?",
        "default": "Isolation Logique"
    },
    {
        "id": "arch_recovery",
        "category": "Architecture",
        "question": "2. Persistence : En cas de crash, comment assurer que les données de la run ne sont pas perdues ?",
        "default": "JSONL Stream"
    },
    {
        "id": "arch_init",
        "category": "Architecture",
        "question": "3. Initialisation : Existe-t-il un ordre critique pour l'enregistrement des services ?",
        "default": "Config -> Database -> Vision -> State"
    },
    {
        "id": "arch_menu",
        "category": "Architecture",
        "question": "4. Validation Menu (3s) : Suffisant pour éviter les faux positifs lors des cinématiques ?",
        "default": "Oui (3s)"
    },
    {
        "id": "math_costs",
        "category": "Math Model",
        "question": "5. Coûts RuneData : Devrait-on permettre de charger les coûts via un fichier .csv externe ?",
        "default": "Non (Hardcoded)"
    },
    {
        "id": "math_snowball",
        "category": "Math Model",
        "question": "6. Snowball Config : Souhaites-tu déplacer les facteurs (1.35/1.15) dans config.json ?",
        "default": "Oui"
    },
    {
        "id": "math_curve_post",
        "category": "Math Model",
        "question": "7. Fin de Courbe : Que doit afficher la courbe idéale après le niveau 14 (28 min) ?",
        "default": "Ligne Plate"
    },
    {
        "id": "math_grade",
        "category": "Math Model",
        "question": "8. Calcul Grade : Doit-on inclure les morts et les dépenses dans la note S/A/B ?",
        "default": "Non (Delta Runes Uniquement)"
    },
    {
        "id": "vis_hud",
        "category": "Vision & OCR",
        "question": "9. HUD Caché : Si le joueur masque son HUD, doit-on bloquer toute l'analyse ?",
        "default": "Oui"
    },
    {
        "id": "vis_burst",
        "category": "Vision & OCR",
        "question": "10. Burst Logic : Doit-on l'étendre à la Mort ou à la Victoire ?",
        "default": "Seulement Victoire"
    },
    {
        "id": "vis_dpi",
        "category": "Vision & OCR",
        "question": "11. DPI 4K : Le mode Awareness actuel (-4) pose-t-il des problèmes de zone ?",
        "default": "Non"
    },
    {
        "id": "vis_typo",
        "category": "Vision & OCR",
        "question": "12. Seuil 'JOUR' (70%) : Trop laxiste ou suffisant ?",
        "default": "Suffisant"
    },
    {
        "id": "death_drop",
        "category": "Death & Recovery",
        "question": "13. Chute Niveau > 1 : Existe-t-il une mécanique de jeu qui permettrait cela ?",
        "default": "Non (Glitch)"
    },
    {
        "id": "death_black",
        "category": "Death & Recovery",
        "question": "14. Écran Noir : Comment distinguer Loading (Safe) vs Mort (Reset) ?",
        "default": "Runes à 0"
    },
    {
        "id": "death_double",
        "category": "Death & Recovery",
        "question": "15. Double Mort : Doit-on retirer les runes du 'Total Acquis' sur la courbe verte ?",
        "default": "Oui (Strict)"
    },
    {
        "id": "death_victory",
        "category": "Death & Recovery",
        "question": "16. Verification Victoire : Doit-on scanner le gain massif de runes après 'RESULTAT' ?",
        "default": "Non"
    },
    {
        "id": "ui_columns",
        "category": "UI/UX",
        "question": "17. Dashboard : Quelle colonne est la plus critique en plein combat ?",
        "default": "Gauche (Level/Timer)"
    },
    {
        "id": "ui_undo",
        "category": "UI/UX",
        "question": "18. Ratchet Error : Souhaites-tu un bouton 'Undo Last Gain' pour corriger une erreur OCR ?",
        "default": "Non (Ratchet Automatique)"
    },
    {
        "id": "ui_audio",
        "category": "UI/UX",
        "question": "19. Audio : Préfères-tu le TTS (voix) ou des sons d'ambiance (cloche) ?",
        "default": "TTS"
    },
    {
        "id": "ui_hotkeys",
        "category": "UI/UX",
        "question": "20. Raccourcis : Liste des raccourcis à garder (ex: J1, J2, Reset, Victory) ?",
        "default": "J1, J2, Reset, Victory"
    },
    {
        "id": "perf_logs",
        "category": "Maintenance",
        "question": "21. Logs : Un fichier application.jsonl de 100Mo est-il acceptable ?",
        "default": "Non (Rotation needed)"
    },
    {
        "id": "perf_boss_bar",
        "category": "Maintenance",
        "question": "22. Boss Detection : Implémenter une détection auto de la barre de vie boss ?",
        "default": "Basé temps (Actuel)"
    },
    {
        "id": "perf_repair",
        "category": "Maintenance",
        "question": "23. Graph Repair (60s) : Suffisant pour couvrir le trajet vers un marchand ?",
        "default": "Suffisant"
    }
]

def run_survey():
    print("=========================================")
    print("   ELDEN RING TIMER - PROJECT SURVEY V2  ")
    print("=========================================")
    print("Instructions: Appuyez sur ENTREE pour accepter la valeur par défaut entre [].")
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
    filename = "rule_clarifications_v2.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=4, ensure_ascii=False)
        
    print(f"\n\n[SUCCESS] Réponses sauvegardées dans '{filename}'.")
    print("Merci pour ces clarifications !")

if __name__ == "__main__":
    run_survey()
