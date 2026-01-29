#!/usr/bin/env python3
"""
Questionnaire d'Implémentation - Adaptations Code Requises
===========================================================
Basé sur l'analyse des réponses utilisateur et du code actuel.
"""

import json
from typing import Dict, List

class ImplementationQuestionnaire:
    def __init__(self):
        self.answers = {}
        self.questions = self._build_questions()
    
    def _build_questions(self) -> List[Dict]:
        """Construit les questions d'implémentation basées sur l'analyse."""
        return [
            {
                "id": "ghost_cancellation_impl",
                "category": "👻 Ghost Cancellation - MANQUANT",
                "finding": "❌ AUCUNE logique de ghost cancellation trouvée dans le code",
                "user_answer": "100% exact requis (pas 98%)",
                "question": "Où et comment implémenter la ghost cancellation?",
                "context": "Le code utilise `recent_spending_history` mais ne vérifie JAMAIS si les runes reviennent à leur valeur précédente. Il faut implémenter une logique qui:\n1. Détecte quand runes reviennent à 100% de la valeur pré-dépense\n2. Annule la dépense de `recent_spending_history`\n3. Répare l'historique du graphique",
                "options": [
                    "Ajouter dans on_runes_detected() - vérifier si new_runes == old_runes_before_spending",
                    "Ajouter dans update_timer_task() - vérifier périodiquement (chaque seconde)",
                    "Créer une méthode dédiée _check_ghost_cancellation() appelée des deux endroits",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/services/state_service.py::on_runes_detected()",
                "priority": "🔴 HAUTE - Fonctionnalité documentée mais non implémentée"
            },
            {
                "id": "level_sync_duration",
                "category": "📊 Level Up Sync - DURÉE INCORRECTE",
                "finding": "❌ Variable `_level_up_pending_sync` NON TROUVÉE dans le code",
                "user_answer": "5 secondes suffisent (actuellement beaucoup plus rapide)",
                "question": "Comment implémenter le level-up sync guard de 5 secondes?",
                "context": "Actuellement, le code n'a PAS de variable `_level_up_pending_sync`. Il faut:\n1. Créer cette variable (timestamp)\n2. La définir quand level augmente\n3. Masquer le level cost du graphique pendant 5s\n4. Permettre la détection de ghost spending pendant cette période",
                "options": [
                    "Ajouter self._level_up_sync_until = time.time() + 5.0 dans on_level_detected()",
                    "Utiliser un flag booléen + timer séparé",
                    "Intégrer dans le système de 'pending events' existant",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/services/state_service.py::on_level_detected() ligne ~1400",
                "priority": "🟡 MOYENNE - Amélioration de robustesse"
            },
            {
                "id": "digit_shift_consensus",
                "category": "🔢 Digit Shift - AMÉLIORATION CONSENSUS",
                "finding": "✅ Fonction `_is_digit_shift_drop()` existe mais durée incertitude = 15s",
                "user_answer": "Réduire drastiquement - utiliser consensus OCR au lieu du temps",
                "question": "Comment remplacer le timeout 15s par un système de consensus?",
                "context": "Actuellement: digit shift → uncertain pendant 15s fixes.\nUtilisateur veut: 'dès qu'une valeur est confirmée plusieurs fois de suite, ne plus se poser la question du digit shift'",
                "options": [
                    "Remplacer timeout par compteur: 3 lectures identiques consécutives = certain",
                    "Utiliser le système de burst existant (5 scans, majorité 3/5)",
                    "Combiner: max 3s OU 3 lectures identiques (premier atteint)",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/services/state_service.py::_is_digit_shift_drop() + on_runes_detected()",
                "priority": "🟡 MOYENNE - Amélioration UX"
            },
            {
                "id": "spending_ticket_system",
                "category": "💰 Spending Validation - REFONTE ARCHITECTURE",
                "finding": "⚠️ Utilise `recent_spending_history` avec timeout 5s, pas de 'pending_spending_event'",
                "user_answer": "Système de tickets bancaires - ne pas se baser sur le temps mais sur la logique",
                "question": "Comment implémenter le système de tickets pour les transactions?",
                "context": "Utilisateur demande: 'système de ticket (comme les banques) pour valider chaque opération en attente. Mettre en attente quand on ne trouve pas de solution. Exemple: baisse rune → baisse rune → level+1 → gain rune. Un code récupère tous ces tickets et les digère.'\n\nC'est une REFONTE MAJEURE de l'architecture actuelle.",
                "options": [
                    "Créer classe TransactionQueue avec méthodes add_event() et process_queue()",
                    "Utiliser pattern Event Sourcing - tous les events dans une liste, processing différé",
                    "Garder système actuel mais améliorer la logique de matching",
                    "Reporter cette refonte (trop complexe pour l'instant)"
                ],
                "code_location": "src/services/state_service.py - Architecture globale",
                "priority": "🔴 HAUTE - Demande explicite utilisateur 'TRÈS IMPORTANT'"
            },
            {
                "id": "shrink_marker_boss_time",
                "category": "📍 SHRINK Markers - CALCUL TEMPS BOSS",
                "finding": "✅ SHRINK events créés à la fin des phases Shrinking",
                "user_answer": "7:30 et 14:00 fixes, mais 21:30 et 28:00 doivent soustraire le temps boss 1",
                "question": "Comment calculer les temps SHRINK 21:30 et 28:00 avec soustraction boss?",
                "context": "Code actuel (ligne 2066):\n```python\n't': time.time() - self.session.start_time\n```\nUtilisateur dit: '21:30 et 28:00 sont fixe aussi mais sur le graphique on doit les placer en soustraction du temps passé au boss 1'\n\nIl faut soustraire la durée du Boss 1 pour Day 2 markers.",
                "options": [
                    "Calculer: t_marker = t_real - boss1_duration (stocker boss1_duration à la fin du boss)",
                    "Utiliser 'active_gameplay_time' au lieu de 'time.time() - start_time'",
                    "Créer variable 'boss_time_offset' qui s'accumule",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/services/state_service.py::trigger_shrink_event() ligne ~2066",
                "priority": "🟡 MOYENNE - Affichage graphique correct"
            },
            {
                "id": "rune_flicker_logging",
                "category": "✨ Rune Flicker - LOGGING",
                "finding": "⚠️ Filtre ±1 rune non trouvé explicitement dans le code",
                "user_answer": "Logger ce filtre car pas sûr de son utilité (gains toujours ≥100)",
                "question": "Où ajouter le logging pour le filtre ±1 rune?",
                "context": "Utilisateur dit: 'quand on gagne des runes (en tuant des ennemis) on ne gagne jamais <100 runes'\nDonc le filtre ±1 pourrait être inutile pour les gains, utile seulement pour les drops.",
                "options": [
                    "Ajouter logger.debug() dans on_runes_detected() quand delta == ±1",
                    "Créer compteur de flickers ignorés, logger toutes les 10 occurrences",
                    "Désactiver complètement le filtre pour les gains (delta > 0)",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/services/state_service.py::on_runes_detected()",
                "priority": "🟢 BASSE - Debug/Monitoring"
            },
            {
                "id": "level_consensus_increase",
                "category": "🎯 Level Consensus - AUGMENTER SEUIL",
                "finding": "✅ Consensus actuel = 2 lectures identiques",
                "user_answer": "Passer à 3 lectures consécutives identiques",
                "question": "Modifier le seuil de consensus de 2 à 3?",
                "context": "Code actuel (recherche 'level_consensus_count'):\n```python\nif self.level_consensus_count >= 2:  # 2 lectures\n```\nUtilisateur veut 3 pour plus de robustesse.",
                "options": [
                    "Changer simplement: if self.level_consensus_count >= 3",
                    "Rendre configurable dans config.json",
                    "Garder 2 (assez robuste déjà)",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/services/state_service.py::on_level_detected()",
                "priority": "🟢 BASSE - Amélioration mineure"
            },
            {
                "id": "death_black_screen_requirement",
                "category": "💀 Death Detection - BLACK SCREEN REQUIS",
                "finding": "⚠️ Code actuel: black screen optionnel (stat-based suffit)",
                "user_answer": "Rendre black screen REQUIS (Level -1 + Runes <50 + Black screen)",
                "question": "Rendre le black screen obligatoire pour valider une mort?",
                "context": "Code actuel (GameRules.is_death_confirmed):\n- Vérifie seulement level -1 + runes <50\n- Black screen utilisé pour confiance mais pas bloquant\n\nUtilisateur veut: TOUS les 3 critères requis.",
                "options": [
                    "Modifier GameRules.is_death_confirmed() pour exiger black_screen",
                    "Ajouter paramètre last_black_screen_end et vérifier (now - last_black < 5s)",
                    "Garder optionnel (évite faux négatifs si black screen raté)",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/core/game_rules.py::is_death_confirmed()",
                "priority": "🟡 MOYENNE - Précision détection mort"
            },
            {
                "id": "recovery_ui_display",
                "category": "🔄 Recovery - AFFICHAGE UI",
                "finding": "❓ Utilisateur dit: 'la récupération ne s'affiche plus dans l'UI actuellement'",
                "user_answer": "Vérifier si l'UI affiche bien les récupérations de bloodstain",
                "question": "L'UI affiche-t-elle les récupérations de runes?",
                "context": "Utilisateur mentionne que la récupération ne s'affiche plus.\nIl faut vérifier si `lost_runes_pending` est bien affiché dans l'overlay.",
                "options": [
                    "Vérifier qt_overlay.py pour affichage de lost_runes_pending",
                    "Ajouter indicateur visuel '+X runes récupérées' temporaire",
                    "Logger les récupérations pour debug",
                    "Confirmer que c'est déjà affiché correctement"
                ],
                "code_location": "src/ui/qt_overlay.py + src/services/state_service.py",
                "priority": "🟡 MOYENNE - UX feedback"
            },
            {
                "id": "spending_multiple_100_exception",
                "category": "💰 Spending - EXCEPTION LEVEL UP",
                "finding": "✅ Level costs connus et intégrés (RuneData._LEVEL_COSTS)",
                "user_answer": "Les level-ups ne sont PAS des multiples de 100",
                "question": "Le filtre 'multiple de 100' exclut-il déjà les level-ups?",
                "context": "Utilisateur dit: 'les lvl up ne sont pas des multiples de 100 et les nombres sont déjà connus'\n\nIl faut vérifier que le code distingue bien:\n- Merchant spending (multiples de 100)\n- Level-up cost (valeurs exactes de RuneData)",
                "options": [
                    "Vérifier que level-up spending est traité séparément",
                    "Ajouter exception: if amount in RuneData._LEVEL_COSTS.values() → accept",
                    "C'est déjà correct (level-ups détectés avant spending validation)",
                    "Autre approche (préciser)"
                ],
                "code_location": "src/services/state_service.py::on_level_detected() + on_runes_detected()",
                "priority": "🟢 BASSE - Vérification"
            },
            {
                "id": "graph_repair_duration",
                "category": "📈 Graph Repair - DURÉE LOOKBACK",
                "finding": "✅ Code répare 300 secondes (5 minutes) d'historique",
                "user_answer": "Pas sûr si 60s ou autre durée",
                "question": "Quelle durée de lookback pour graph repair?",
                "context": "Code actuel (ligne 1485):\n```python\nfor i in range(max(0, history_len - 300), history_len):\n```\n= 300 secondes (5 minutes)\n\nDocumentation disait 60s, utilisateur pas sûr.",
                "options": [
                    "Garder 300s (5 min) - couvre tous les cas",
                    "Réduire à 60s comme documenté",
                    "Rendre configurable",
                    "Autre durée (préciser)"
                ],
                "code_location": "src/services/state_service.py::on_level_detected() ligne ~1485",
                "priority": "🟢 BASSE - Optimisation"
            },
            {
                "id": "ratchet_reset_behavior",
                "category": "🔒 Ratchet - RESET F4 vs F5",
                "finding": "❓ Comportement reset doux (F5) vs complet (F4) à clarifier",
                "user_answer": "Les 2 affectent la courbe. Reset supprime la courbe et repart à zéro",
                "question": "Différence entre F4 (reset complet) et F5 (reset doux)?",
                "context": "Utilisateur dit: 'les 2 affecte la courbe. le reset supprime la courbe et on repart a zero'\n\nIl faut clarifier:\n- F4 = reset complet (efface tout)\n- F5 = reset doux (quoi exactement?)",
                "options": [
                    "F4 = efface tout, F5 = garde historique mais reset stats",
                    "F4 = reset session, F5 = force Day 1 start",
                    "Les deux font la même chose actuellement",
                    "Chercher dans le code les handlers F4/F5"
                ],
                "code_location": "src/services/state_service.py - hotkey handlers",
                "priority": "🟢 BASSE - Documentation"
            },
            {
                "id": "boss_detection_methods",
                "category": "⏱️ Boss - MÉTHODES DÉTECTION FIN",
                "finding": "✅ Utilisateur a clarifié les 3 méthodes",
                "user_answer": "Boss 1: OCR 'JOUR II', Boss 2: écran noir, Boss 3: OCR 'resultat'",
                "question": "Les 3 méthodes de détection sont-elles implémentées?",
                "context": "Vérifier que le code implémente bien:\n1. Boss 1 → Day 2: OCR 'JOUR II' / 'DAY II'\n2. Boss 2 → Day 3: Black screen (fade 0.3-3.0s)\n3. Boss 3 → Victory: OCR 'resultat' / 'result'",
                "options": [
                    "Vérifier implémentation de chaque transition",
                    "Tout est déjà implémenté correctement",
                    "Manque une ou plusieurs détections",
                    "Autre (préciser)"
                ],
                "code_location": "src/services/state_service.py - trigger_day_2/3, check_victory",
                "priority": "🟢 BASSE - Vérification"
            },
            {
                "id": "uncertain_graph_behavior",
                "category": "❓ Uncertain State - COMPORTEMENT GRAPHIQUE",
                "finding": "✅ Utilisateur confirme: graphique gelé pendant uncertain",
                "user_answer": "Gelé (utilise dernière valeur certaine)",
                "question": "Le graphique est-il bien gelé pendant l'état uncertain?",
                "context": "Vérifier que pendant runes_uncertain = True:\n- Le graphique n'est PAS mis à jour\n- La dernière valeur certaine est maintenue\n- L'UI indique l'état uncertain (LED orange?)",
                "options": [
                    "Vérifier le code update_timer_task() - skip graph update si uncertain",
                    "Ajouter indicateur visuel pour uncertain state",
                    "C'est déjà correct",
                    "Autre (préciser)"
                ],
                "code_location": "src/services/state_service.py::update_timer_task()",
                "priority": "🟢 BASSE - Vérification"
            },
            {
                "id": "audio_timing_confirmation",
                "category": "🔊 Audio - TEMPS RESTANT",
                "finding": "✅ Utilisateur confirme: annonces = temps RESTANT",
                "user_answer": "'2min' = il reste 2 minutes, '5s' joué à 4:25 (il reste 5s)",
                "question": "Les annonces audio utilisent-elles bien le temps restant?",
                "context": "Vérifier que les annonces sont jouées quand:\n- remaining_time == 120s → '2 minutes'\n- remaining_time == 60s → '1 minute'\n- remaining_time == 30s → '30 secondes'\n- remaining_time == 5s → '5 secondes'",
                "options": [
                    "Vérifier le code audio dans update_timer_task()",
                    "C'est déjà correct",
                    "Inverser la logique (actuellement temps écoulé)",
                    "Autre (préciser)"
                ],
                "code_location": "src/services/state_service.py::update_timer_task() - audio section",
                "priority": "🟢 BASSE - Vérification"
            }
        ]
    
    def run(self):
        """Exécute le questionnaire interactif."""
        print("=" * 80)
        print("QUESTIONNAIRE D'IMPLÉMENTATION - ADAPTATIONS CODE REQUISES")
        print("=" * 80)
        print()
        print("Basé sur l'analyse de vos réponses et du code actuel.")
        print("Chaque question identifie un écart entre documentation et implémentation.")
        print()
        print("💡 Vous pouvez répondre par:")
        print("   - Un numéro (1, 2, 3...) pour choisir une option")
        print("   - Du texte libre pour une approche personnalisée")
        print("   - 'skip' pour passer la question")
        print()
        
        for i, q in enumerate(self.questions, 1):
            print(f"\n{'═' * 80}")
            print(f"Question {i}/{len(self.questions)} - {q['category']}")
            print(f"{'═' * 80}")
            print(f"\n🔍 Finding: {q['finding']}")
            print(f"👤 Votre réponse: {q['user_answer']}")
            print(f"\n❓ {q['question']}")
            print(f"\n💭 Contexte:\n{q['context']}")
            print(f"\n📍 Code: {q['code_location']}")
            print(f"⚠️  Priorité: {q['priority']}")
            print(f"\nOptions:")
            
            for idx, option in enumerate(q['options'], 1):
                print(f"  {idx}. {option}")
            
            # Collecte de la réponse
            while True:
                answer = input(f"\nVotre décision (1-{len(q['options'])}, texte libre, ou 'skip'): ").strip()
                
                if answer.lower() == 'skip':
                    self.answers[q['id']] = {
                        'question': q['question'],
                        'answer': 'SKIPPED',
                        'answer_index': -2,
                        'is_custom': False,
                        'priority': q['priority']
                    }
                    print("⏭️  Question passée")
                    break
                
                # Essayer de parser comme un nombre
                try:
                    answer_idx = int(answer) - 1
                    if 0 <= answer_idx < len(q['options']):
                        self.answers[q['id']] = {
                            'question': q['question'],
                            'finding': q['finding'],
                            'user_answer': q['user_answer'],
                            'answer': q['options'][answer_idx],
                            'answer_index': answer_idx,
                            'is_custom': False,
                            'code_location': q['code_location'],
                            'priority': q['priority']
                        }
                        break
                    else:
                        print(f"❌ Veuillez entrer un nombre entre 1 et {len(q['options'])}, texte libre, ou 'skip'")
                except ValueError:
                    # Texte libre
                    if len(answer) > 0:
                        self.answers[q['id']] = {
                            'question': q['question'],
                            'finding': q['finding'],
                            'user_answer': q['user_answer'],
                            'answer': answer,
                            'answer_index': -1,
                            'is_custom': True,
                            'code_location': q['code_location'],
                            'priority': q['priority']
                        }
                        print(f"✅ Décision personnalisée enregistrée")
                        break
                    else:
                        print("❌ Veuillez entrer un nombre, du texte, ou 'skip'")
        
        # Sauvegarde
        self.save_answers()
        self.display_summary()
    
    def save_answers(self):
        """Sauvegarde les réponses."""
        with open('implementation_decisions.json', 'w', encoding='utf-8') as f:
            json.dump(self.answers, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Décisions sauvegardées dans 'implementation_decisions.json'")
    
    def display_summary(self):
        """Affiche un résumé par priorité."""
        print("\n" + "=" * 80)
        print("RÉSUMÉ DES DÉCISIONS D'IMPLÉMENTATION")
        print("=" * 80)
        
        # Grouper par priorité
        high = [a for a in self.answers.values() if '🔴' in a.get('priority', '')]
        medium = [a for a in self.answers.values() if '🟡' in a.get('priority', '')]
        low = [a for a in self.answers.values() if '🟢' in a.get('priority', '')]
        
        for priority_name, items in [("HAUTE PRIORITÉ", high), ("MOYENNE PRIORITÉ", medium), ("BASSE PRIORITÉ", low)]:
            if items:
                print(f"\n{'─' * 80}")
                print(f"🎯 {priority_name} ({len(items)} items)")
                print(f"{'─' * 80}")
                for item in items:
                    if item['answer'] == 'SKIPPED':
                        print(f"\n⏭️  {item['question']} [SKIPPED]")
                    else:
                        print(f"\n❓ {item['question']}")
                        if item.get('is_custom'):
                            print(f"✅ [Personnalisé] {item['answer']}")
                        else:
                            print(f"✅ {item['answer']}")
        
        print("\n" + "=" * 80)
        print("Ces décisions guideront l'implémentation des adaptations.")
        print("=" * 80)

if __name__ == "__main__":
    questionnaire = ImplementationQuestionnaire()
    questionnaire.run()
