#!/usr/bin/env python3
"""
Questionnaire de Consolidation de Documentation
================================================
Ce script pose des questions sur les incohérences trouvées dans la documentation
et le code pour créer une documentation unifiée et cohérente.
"""

import json
from typing import Dict, List

class DocumentationQuestionnaire:
    def __init__(self):
        self.answers = {}
        self.questions = self._build_questions()
    
    def _build_questions(self) -> List[Dict]:
        """Construit la liste des questions basées sur l'analyse du code."""
        return [
            {
                "id": "game_name",
                "category": "🎮 Nom du Jeu",
                "question": "Le jeu s'appelle-t-il 'Elden Ring Nightreign' ou juste 'Nightreign'?",
                "context": "Le titre du projet mentionne 'Elden Ring' mais le processus surveillé est 'nightreign.exe'",
                "options": [
                    "Elden Ring: Nightreign (DLC/Extension)",
                    "Nightreign (Jeu standalone)",
                    "Les deux noms sont valides"
                ]
            },
            {
                "id": "phase_count",
                "category": "⏱️ Phases de Jeu",
                "question": "Combien y a-t-il de 'Days' (Jours) dans une partie complète?",
                "context": "Le code mentionne Day 1, Day 2, Day 3, mais PROJECT_KNOWLEDGE parle de 'Night 1' et 'Night 2'",
                "options": [
                    "2 Days (Day 1 et Day 2 seulement)",
                    "3 Days (Day 1, Day 2, Day 3)",
                    "Autre (préciser)"
                ],
                "follow_up": "Si 3 Days: Day 3 a-t-il des phases Storm/Shrinking comme Day 1 et 2?"
            },
            {
                "id": "day_vs_night",
                "category": "📖 Terminologie",
                "question": "Quelle est la terminologie correcte dans le jeu?",
                "context": "PROJECT_KNOWLEDGE.md utilise 'Night 1 Boss' et 'Night 2 Boss', mais le code utilise 'Day 1', 'Day 2', 'Day 3'",
                "options": [
                    "Le jeu affiche 'JOUR I', 'JOUR II', 'JOUR III' (Days en français)",
                    "Le jeu affiche 'NIGHT 1', 'NIGHT 2' (Nights en anglais)",
                    "Les deux termes sont utilisés (Days pour phases, Nights pour cycles)"
                ]
            },
            {
                "id": "boss_count",
                "category": "👹 Boss",
                "question": "Combien de boss y a-t-il dans une partie complète?",
                "context": "Le code a 'Boss 1', 'Boss 2', et 'Boss 3 - Final Boss'. PROJECT_KNOWLEDGE mentionne 'Night 1 Boss' et 'Night 2 Boss' seulement.",
                "options": [
                    "2 Boss (Boss 1 après Day 1, Boss 2 après Day 2)",
                    "3 Boss (Boss 1, Boss 2, Boss 3 Final)",
                    "Autre configuration"
                ],
                "follow_up": "Les boss donnent-ils tous 50,000 runes?"
            },
            {
                "id": "phase_durations",
                "category": "⏱️ Durées des Phases",
                "question": "Les durées des phases sont-elles identiques pour Day 1 et Day 2?",
                "context": "Le code définit les mêmes durées (4:30, 3:00, 3:30, 3:00) pour Day 1 et Day 2",
                "options": [
                    "Oui, exactement les mêmes (14 minutes par Day)",
                    "Non, Day 2 est différent",
                    "Day 3 existe et a des durées différentes"
                ]
            },
            {
                "id": "day3_mechanics",
                "category": "🎯 Day 3",
                "question": "Comment fonctionne Day 3 (si il existe)?",
                "context": "Le code a 'Day 3 - Preparation' et 'Day 3 - Final Boss' avec duration=0",
                "options": [
                    "Day 3 n'a pas de timer, c'est juste la préparation + boss final",
                    "Day 3 a un timer mais il n'est pas encore implémenté",
                    "Day 3 n'existe pas, c'est une erreur dans le code"
                ],
                "follow_up": "Si Day 3 existe: Comment détecte-t-on la transition Boss 2 → Day 3?"
            },
            {
                "id": "black_screen_detection",
                "category": "🎬 Détection d'Écran Noir",
                "question": "Quelles transitions utilisent la détection d'écran noir?",
                "context": "PROJECT_KNOWLEDGE mentionne 'Boss 2 → Day 3 Prep' et 'Day 3 Prep → Final Boss' via black screen",
                "options": [
                    "Seulement Boss 2 → Day 3",
                    "Boss 2 → Day 3 ET Day 3 Prep → Final Boss",
                    "Toutes les transitions de boss utilisent l'écran noir",
                    "Aucune transition n'utilise l'écran noir (OCR uniquement)"
                ]
            },
            {
                "id": "ocr_triggers",
                "category": "🔍 Triggers OCR",
                "question": "Quels textes OCR déclenchent les transitions de Day?",
                "context": "Le code cherche 'JOUR I', 'JOUR II', mais pas 'JOUR III'",
                "options": [
                    "JOUR I pour Day 1, JOUR II pour Day 2, pas de JOUR III",
                    "JOUR I, JOUR II, JOUR III pour les 3 Days",
                    "Le jeu affiche autre chose (préciser)"
                ],
                "follow_up": "Le texte est-il toujours en français ou dépend-il de la langue du jeu?"
            },
            {
                "id": "level_target",
                "category": "📊 Objectifs de Niveau",
                "question": "Quel est l'objectif de niveau optimal?",
                "context": "PROJECT_KNOWLEDGE dit 'Level 14 at Boss 2 (28 min)' et 'Level 15 Max', mais aussi '+50k runes after Boss 2'",
                "options": [
                    "Level 14 avant Boss 2, Level 15 après Boss 2",
                    "Level 15 est le maximum absolu du jeu",
                    "Level 15 avant Boss 2 est l'objectif optimal"
                ],
                "follow_up": "Combien de runes faut-il pour atteindre Level 15 depuis Level 1?"
            },
            {
                "id": "rune_total",
                "category": "💰 Runes Totales",
                "question": "Quelle est la quantité totale de runes requise?",
                "context": "PROJECT_KNOWLEDGE dit '512,936 Runes (Lvl 1 → 15)' mais mentionne aussi un 'Farming Goal' de 412,936",
                "options": [
                    "512,936 runes au total (incluant les boss)",
                    "412,936 runes de farming + 100,000 de boss = 512,936 total",
                    "Les chiffres ont changé, préciser les nouveaux"
                ]
            },
            {
                "id": "boss_rewards",
                "category": "💎 Récompenses Boss",
                "question": "Combien de runes donnent les boss?",
                "context": "PROJECT_KNOWLEDGE dit 'Night 1 Boss: ~50,000' et 'Night 2 Boss: ~50,000'",
                "options": [
                    "Boss 1: 50,000, Boss 2: 50,000",
                    "Boss 1: 50,000, Boss 2: 50,000, Boss 3: 50,000",
                    "Les montants sont variables/approximatifs",
                    "Autre configuration"
                ]
            },
            {
                "id": "snowball_factors",
                "category": "📈 Facteurs de Snowball",
                "question": "Les facteurs de snowball (1.35 et 1.15) sont-ils corrects?",
                "context": "PROJECT_KNOWLEDGE mentionne 'Snowball Factor: 1.35 (Day 1) → 1.15 (Day 2)'",
                "options": [
                    "Oui, 1.35 pour Day 1, 1.15 pour Day 2",
                    "Non, les valeurs ont changé (préciser)",
                    "Il y a aussi un facteur pour Day 3"
                ],
                "follow_up": "Ces facteurs doivent-ils être configurables dans config.json?"
            },
            {
                "id": "menu_detection",
                "category": "🏠 Détection Menu",
                "question": "Comment détecte-t-on le retour au menu principal?",
                "context": "README mentionne 'Main Menu' detection, PROJECT_KNOWLEDGE parle de 'Character Screen'",
                "options": [
                    "Détection du Main Menu (écran titre)",
                    "Détection du Character Screen (sélection personnage)",
                    "Les deux sont utilisés pour différentes situations"
                ],
                "follow_up": "Cette détection sert-elle uniquement pour l'auto-reset?"
            },
            {
                "id": "victory_detection",
                "category": "🏆 Détection Victoire",
                "question": "Comment détecte-t-on la victoire?",
                "context": "PROJECT_KNOWLEDGE mentionne 'RÉSULTAT' comme trigger de victoire",
                "options": [
                    "OCR du texte 'RÉSULTAT' (français)",
                    "OCR du texte 'RESULT' (anglais)",
                    "Dépend de la langue du jeu",
                    "Autre méthode"
                ]
            },
            {
                "id": "shrink_markers",
                "category": "📍 Marqueurs Shrink",
                "question": "Combien de marqueurs 'Shrink' y a-t-il sur le graphique?",
                "context": "PROJECT_KNOWLEDGE mentionne 4 marqueurs (Shrink 1.1, 1.2, 2.1, 2.2) aux temps 7:30, 14:00, 21:30, 28:00",
                "options": [
                    "4 marqueurs (2 par Day, à la fin de chaque phase Shrinking)",
                    "2 marqueurs (1 par Day)",
                    "6 marqueurs (si Day 3 existe)",
                    "Autre configuration"
                ]
            },
            {
                "id": "rps_calculation",
                "category": "⚡ Calcul RPS",
                "question": "Le calcul RPS (Runes Per Second) est-il pausé pendant les boss?",
                "context": "PROJECT_KNOWLEDGE dit 'Boss 1 & 2: RPS calculation and graph progress are PAUSED'",
                "options": [
                    "Oui, RPS et graphique sont pausés pendant TOUS les boss",
                    "Seulement pendant Boss 1 et Boss 2, pas Boss 3",
                    "Non, le RPS continue pendant les boss"
                ],
                "follow_up": "Le timer continue-t-il pendant les boss ou est-il aussi pausé?"
            }
        ]
    
    def run(self):
        """Exécute le questionnaire interactif."""
        print("=" * 80)
        print("QUESTIONNAIRE DE CONSOLIDATION - ELDEN RING NIGHTREIGN TIMER")
        print("=" * 80)
        print()
        print("Ce questionnaire identifie les incohérences entre la documentation")
        print("et le code pour créer une documentation unifiée.")
        print()
        print("Répondez aux questions suivantes (tapez le numéro de l'option):")
        print()
        
        for i, q in enumerate(self.questions, 1):
            print(f"\n{'─' * 80}")
            print(f"Question {i}/{len(self.questions)} - {q['category']}")
            print(f"{'─' * 80}")
            print(f"\n{q['question']}")
            print(f"\n💡 Contexte: {q['context']}")
            print(f"\nOptions:")
            
            for idx, option in enumerate(q['options'], 1):
                print(f"  {idx}. {option}")
            
            # Collecte de la réponse
            while True:
                try:
                    answer = input(f"\nVotre réponse (1-{len(q['options'])}): ").strip()
                    answer_idx = int(answer) - 1
                    if 0 <= answer_idx < len(q['options']):
                        self.answers[q['id']] = {
                            'question': q['question'],
                            'answer': q['options'][answer_idx],
                            'answer_index': answer_idx
                        }
                        break
                    else:
                        print(f"❌ Veuillez entrer un nombre entre 1 et {len(q['options'])}")
                except ValueError:
                    print("❌ Veuillez entrer un nombre valide")
            
            # Question de suivi si présente
            if 'follow_up' in q:
                follow_up = input(f"\n📝 {q['follow_up']}\nRéponse: ").strip()
                self.answers[q['id']]['follow_up'] = follow_up
        
        # Sauvegarde des réponses
        self.save_answers()
        self.display_summary()
    
    def save_answers(self):
        """Sauvegarde les réponses dans un fichier JSON."""
        with open('documentation_answers.json', 'w', encoding='utf-8') as f:
            json.dump(self.answers, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Réponses sauvegardées dans 'documentation_answers.json'")
    
    def display_summary(self):
        """Affiche un résumé des réponses."""
        print("\n" + "=" * 80)
        print("RÉSUMÉ DES RÉPONSES")
        print("=" * 80)
        
        for q_id, answer_data in self.answers.items():
            print(f"\n❓ {answer_data['question']}")
            print(f"✅ {answer_data['answer']}")
            if 'follow_up' in answer_data and answer_data['follow_up']:
                print(f"   └─ {answer_data['follow_up']}")
        
        print("\n" + "=" * 80)
        print("Merci ! Ces réponses seront utilisées pour créer une documentation unifiée.")
        print("=" * 80)

if __name__ == "__main__":
    questionnaire = DocumentationQuestionnaire()
    questionnaire.run()
