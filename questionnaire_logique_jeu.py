#!/usr/bin/env python3
"""
Questionnaire sur la Logique du Jeu - Clarification des Doutes
===============================================================
Ce questionnaire traite des ambiguïtés découvertes lors de la documentation du code.
"""

import json
from typing import Dict, List

class GameLogicQuestionnaire:
    def __init__(self):
        self.answers = {}
        self.questions = self._build_questions()
    
    def _build_questions(self) -> List[Dict]:
        """Construit la liste des questions basées sur les doutes lors de la documentation."""
        return [
            {
                "id": "rps_pause_timing",
                "category": "⚡ RPS (Runes Per Second)",
                "question": "Le RPS est pausé pendant les boss, mais le TIMER continue. Est-ce correct?",
                "context": "Dans update_timer_task(), le RPS est pausé pendant les boss mais le timer continue. Cela signifie que le graphique RPS montre un plateau pendant les boss?",
                "options": [
                    "Oui, RPS pausé (plateau) mais timer continue (correct)",
                    "Non, RPS ET timer doivent être pausés tous les deux",
                    "Non, RPS continue pendant les boss (pas de pause)"
                ]
            },
            {
                "id": "ghost_cancellation_threshold",
                "category": "👻 Ghost Cancellation",
                "question": "Le seuil de ghost cancellation est-il vraiment 98% ou 100%?",
                "context": "Si j'avais 10000 runes, dépense fantôme de 5000, est-ce que 9800 runes suffit pour annuler ou faut-il exactement 10000?",
                "options": [
                    "98% suffit (9800 runes dans l'exemple)",
                    "100% exact requis (10000 runes exactement)",
                    "Autre seuil (préciser)"
                ],
                "follow_up": "Si 98%, pourquoi cette tolérance? OCR imprécis?"
            },
            {
                "id": "level_up_sync_duration",
                "category": "📊 Level Up Sync",
                "question": "La durée du 'level-up sync guard' est-elle vraiment 12 secondes?",
                "context": "Pendant cette période, le coût du level est masqué du graphique pour éviter un spike.",
                "options": [
                    "Oui, exactement 12 secondes",
                    "Non, c'est 10 secondes",
                    "Non, c'est 15 secondes",
                    "Autre durée (préciser)"
                ],
                "follow_up": "Cette durée correspond-elle au délai OCR pour détecter le nouveau level?"
            },
            {
                "id": "digit_shift_detection",
                "category": "🔢 Digit Shift Detection",
                "question": "Comment fonctionne exactement la détection de 'digit shift' (7774 → 7174)?",
                "context": "Les digit shifts sont marqués comme 'uncertain' pendant 15s.",
                "options": [
                    "Vérifie si un seul chiffre a changé de position",
                    "Vérifie si la différence est un multiple de 100/1000",
                    "Vérifie si les chiffres sont les mêmes mais réarrangés",
                    "Autre méthode (voir _is_digit_shift_drop)"
                ],
                "follow_up": "Pourquoi 15 secondes d'incertitude? Temps moyen pour OCR se stabiliser?"
            },
            {
                "id": "death_black_screen_requirement",
                "category": "💀 Death Detection",
                "question": "L'écran noir est-il REQUIS pour valider une mort ou juste optionnel?",
                "context": "Le code vérifie last_black_screen_end. Est-ce juste pour la confiance ou c'est bloquant?",
                "options": [
                    "Optionnel - La mort est validée sans écran noir (stat-based uniquement)",
                    "Requis - Level -1 + Runes < 50 + Black screen tous nécessaires",
                    "Hybride - Black screen augmente la confiance mais pas bloquant"
                ]
            },
            {
                "id": "recovery_exact_match",
                "category": "🔄 Recovery Logic",
                "question": "La récupération doit-elle être EXACTEMENT le montant perdu ou y a-t-il une tolérance?",
                "context": "'All or Nothing' - mais est-ce vraiment exact au rune près?",
                "options": [
                    "Exact au rune près (10000 perdus = 10000 récupérés)",
                    "Tolérance de ±1% (OCR imprécis)",
                    "Tolérance de ±10 runes",
                    "Autre tolérance (préciser)"
                ],
                "follow_up": "Si exact, comment gérer les erreurs OCR lors de la récupération?"
            },
            {
                "id": "spending_validation_multiple",
                "category": "💰 Spending Validation",
                "question": "Pourquoi les dépenses doivent-elles être des multiples de 100?",
                "context": "Validation 'amount is multiple of 100'",
                "options": [
                    "Les prix marchands sont toujours des multiples de 100",
                    "C'est pour filtrer les erreurs OCR (nombres bizarres)",
                    "Les deux raisons ci-dessus",
                    "Autre raison (préciser)"
                ],
                "follow_up": "Y a-t-il des exceptions? Level-up coûts sont-ils aussi multiples de 100?"
            },
            {
                "id": "rune_flicker_threshold",
                "category": "✨ Rune Flicker",
                "question": "Le filtre de ±1 rune s'applique-t-il aussi aux gains ou seulement aux drops?",
                "context": "Filtre '±1 rune flickers (OCR noise)'",
                "options": [
                    "Seulement les drops (pertes) sont filtrés",
                    "Gains ET drops de ±1 sont ignorés",
                    "Dépend du contexte (préciser)"
                ],
                "follow_up": "Si les gains de +1 sont filtrés, ne perd-on pas des petits gains légitimes?"
            },
            {
                "id": "consensus_reset_conditions",
                "category": "🎯 Consensus",
                "question": "Quand le compteur de consensus (level_consensus_count) est-il réinitialisé?",
                "context": "'Requires 2 consecutive identical readings'",
                "options": [
                    "Reset à chaque lecture différente de pending_level",
                    "Reset seulement après validation du nouveau level",
                    "Reset après timeout (préciser durée)",
                    "Autre condition (préciser)"
                ]
            },
            {
                "id": "phase_transition_audio_timing",
                "category": "🔊 Audio Announcements",
                "question": "Les annonces audio (2min, 1min, 30s, 5s) sont-elles jouées AVANT la fin de phase?",
                "context": "'2min' signifie '2 minutes restantes' ou '2 minutes écoulées'?",
                "options": [
                    "Temps RESTANT (ex: '2min' = il reste 2 minutes)",
                    "Temps ÉCOULÉ (ex: '2min' = 2 minutes se sont écoulées)",
                    "Dépend de la phase (préciser)"
                ],
                "follow_up": "L'annonce '5s' est-elle jouée à 4:25 (5s restantes) ou à 0:05 (5s écoulées)?"
            },
            {
                "id": "graph_repair_lookback",
                "category": "📈 Graph Repair",
                "question": "Pourquoi la réparation du graphique regarde-t-elle 60 secondes en arrière?",
                "context": "'Repairs graph history (last 60s)' après ghost cancellation",
                "options": [
                    "C'est la durée de recent_spending_history",
                    "C'est arbitraire, pourrait être changé",
                    "C'est lié au délai maximum entre dépense et level-up",
                    "Autre raison (préciser)"
                ],
                "follow_up": "Que se passe-t-il si le level-up arrive après 60s? La dépense fantôme reste?"
            },
            {
                "id": "ratchet_exceptions",
                "category": "🔒 Ratchet (Monotonicity)",
                "question": "Quelles sont TOUTES les exceptions à la règle de monotonie?",
                "context": "'never decreases except validated death/spending'",
                "options": [
                    "Seulement mort et spending validé",
                    "Mort, spending, ET reset manuel (F4)",
                    "Mort, spending, reset, ET corrections OCR",
                    "Autres exceptions (préciser)"
                ],
                "follow_up": "Le reset doux (F5) affecte-t-il la courbe ou seulement le reset complet (F4)?"
            },
            {
                "id": "boss_phase_duration",
                "category": "⏱️ Boss Phases",
                "question": "Les phases Boss ont-elles une durée maximale ou sont-elles infinies?",
                "context": "'duration=0' pour les boss - infini ou juste 'pas de timer affiché'?",
                "options": [
                    "Infini - Le boss dure jusqu'à la mort ou victoire",
                    "Pas de timer affiché mais timeout interne existe",
                    "Durée variable selon le boss (préciser)"
                ],
                "follow_up": "Comment détecte-t-on la fin d'un boss? OCR 'JOUR II' ou autre méthode?"
            },
            {
                "id": "uncertain_state_duration",
                "category": "❓ Uncertain State",
                "question": "Combien de temps l'état 'uncertain' dure-t-il pour les runes?",
                "context": "'held for 15s' pour digit shifts",
                "options": [
                    "15 secondes pour tous les cas d'incertitude",
                    "15s pour digit shift, autre durée pour low confidence",
                    "Jusqu'à ce qu'une lecture certaine arrive",
                    "Autre logique (préciser)"
                ],
                "follow_up": "Pendant uncertain, le graphique est-il gelé ou utilise la dernière valeur certaine?"
            },
            {
                "id": "pending_spending_grace_period",
                "category": "⏳ Pending Spending",
                "question": "La grace period de 10s pour pending_spending_event commence quand?",
                "context": "'10s grace period'",
                "options": [
                    "Commence à la détection de la baisse de runes",
                    "Commence après validation que ce n'est pas un glitch OCR",
                    "Autre timing (préciser)"
                ],
                "follow_up": "Si un level-up arrive à 9.5s, la dépense est-elle annulée ou validée?"
            },
            {
                "id": "shrink_marker_trigger",
                "category": "📍 SHRINK Markers",
                "question": "Les marqueurs SHRINK sont-ils déclenchés au DÉBUT ou à la FIN de Shrinking?",
                "context": "'4 markers at phase boundaries'",
                "options": [
                    "Fin de phase Shrinking (quand timer atteint 0:00)",
                    "Début de phase Shrinking (quand phase commence)",
                    "Milieu de phase Shrinking (moment de réduction max)",
                    "Autre timing (préciser)"
                ],
                "follow_up": "Les temps 7:30, 14:00, 21:30, 28:00 sont-ils globaux ou de phase?"
            }
        ]
    
    def run(self):
        """Exécute le questionnaire interactif."""
        print("=" * 80)
        print("QUESTIONNAIRE SUR LA LOGIQUE DU JEU - CLARIFICATION DES DOUTES")
        print("=" * 80)
        print()
        print("Ces questions ont émergé lors de la documentation du code.")
        print("Vos réponses aideront à clarifier les ambiguïtés.")
        print()
        print("💡 Vous pouvez répondre par:")
        print("   - Un numéro (1, 2, 3...) pour choisir une option")
        print("   - Du texte libre pour une réponse personnalisée")
        print()
        
        for i, q in enumerate(self.questions, 1):
            print(f"\n{'─' * 80}")
            print(f"Question {i}/{len(self.questions)} - {q['category']}")
            print(f"{'─' * 80}")
            print(f"\n❓ {q['question']}")
            print(f"\n💭 Contexte: {q['context']}")
            print(f"\nOptions:")
            
            for idx, option in enumerate(q['options'], 1):
                print(f"  {idx}. {option}")
            
            # Collecte de la réponse
            while True:
                answer = input(f"\nVotre réponse (1-{len(q['options'])} ou texte libre): ").strip()
                
                # Essayer d'abord de parser comme un nombre
                try:
                    answer_idx = int(answer) - 1
                    if 0 <= answer_idx < len(q['options']):
                        self.answers[q['id']] = {
                            'question': q['question'],
                            'answer': q['options'][answer_idx],
                            'answer_index': answer_idx,
                            'is_custom': False
                        }
                        break
                    else:
                        print(f"❌ Veuillez entrer un nombre entre 1 et {len(q['options'])} ou du texte libre")
                except ValueError:
                    # Si ce n'est pas un nombre, accepter comme texte libre
                    if len(answer) > 0:
                        self.answers[q['id']] = {
                            'question': q['question'],
                            'answer': answer,
                            'answer_index': -1,  # -1 indique une réponse personnalisée
                            'is_custom': True
                        }
                        print(f"✅ Réponse personnalisée enregistrée: \"{answer}\"")
                        break
                    else:
                        print("❌ Veuillez entrer un nombre ou du texte")
            
            # Question de suivi si présente
            if 'follow_up' in q:
                follow_up = input(f"\n📝 {q['follow_up']}\nRéponse: ").strip()
                if follow_up:
                    self.answers[q['id']]['follow_up'] = follow_up
        
        # Sauvegarde des réponses
        self.save_answers()
        self.display_summary()
    
    def save_answers(self):
        """Sauvegarde les réponses dans un fichier JSON."""
        with open('logique_jeu_answers.json', 'w', encoding='utf-8') as f:
            json.dump(self.answers, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Réponses sauvegardées dans 'logique_jeu_answers.json'")
    
    def display_summary(self):
        """Affiche un résumé des réponses."""
        print("\n" + "=" * 80)
        print("RÉSUMÉ DES RÉPONSES")
        print("=" * 80)
        
        for q_id, answer_data in self.answers.items():
            print(f"\n❓ {answer_data['question']}")
            
            # Afficher différemment les réponses personnalisées
            if answer_data.get('is_custom', False):
                print(f"✅ [Réponse personnalisée] {answer_data['answer']}")
            else:
                print(f"✅ {answer_data['answer']}")
            
            if 'follow_up' in answer_data and answer_data['follow_up']:
                print(f"   └─ {answer_data['follow_up']}")
        
        print("\n" + "=" * 80)
        print("Merci ! Ces réponses clarifieront les ambiguïtés du code.")
        print("=" * 80)

if __name__ == "__main__":
    questionnaire = GameLogicQuestionnaire()
    questionnaire.run()
