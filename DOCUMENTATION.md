# Nightreign Timer - Documentation Complète

> **Version:** 2.0 | **Dernière mise à jour:** 29 Janvier 2026

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Installation](#installation)
3. [Utilisation](#utilisation)
4. [Mécanique du Jeu Nightreign](#mécanique-du-jeu-nightreign)
5. [Architecture Technique](#architecture-technique)
6. [Système OCR & Vision](#système-ocr--vision)
7. [Analytique & Courbe Idéale](#analytique--courbe-idéale)
8. [Guide Développeur](#guide-développeur)
9. [Dépannage](#dépannage)

---

## 🎮 Vue d'Ensemble

**Nightreign Timer** est une application overlay transparente pour le jeu **Nightreign** (standalone) qui suit automatiquement la progression du joueur en temps réel via OCR (reconnaissance de texte).

### Fonctionnalités Principales

- ✅ **Détection Automatique des Phases** : OCR des bannières "JOUR I", "JOUR II" avec logique floue
- ✅ **Timer Intelligent** : Suivi des phases Storm, Shrinking et Boss
- ✅ **Auto-Reset** : Détection du menu principal pour réinitialiser automatiquement
- ✅ **Analytique Avancée** : Graphique de richesse totale avec stabilité (Ratchet)
- ✅ **Détection de Mort** : Validation stricte (Level -1 + Runes = 0)
- ✅ **Overlay Non-Intrusif** : Interface PyQt6 toujours visible, haute lisibilité
- ✅ **Signaux Audio** : Annonces vocales pour les transitions critiques
- ✅ **Intégration System Tray** : Fonctionne en arrière-plan

---

## 💾 Installation

### Prérequis

1. **Python 3.8+** installé
2. **Tesseract OCR** installé et dans le PATH système

### Installation des Dépendances

```bash
pip install -r requirements.txt
```

### Démarrage

- **Mode Standard** : `start_background.bat` (démarre en arrière-plan)
- **Redémarrage** : `restart.bat` (force le redémarrage)
- **Mode Configuration** : `python main.py --config`

---

## 🎯 Utilisation

### Raccourcis Clavier

| Touche | Action |
|--------|--------|
| **F4** | Reset Complet (efface tout, retour en attente de "JOUR I") |
| **F5** | Démarrer Day 1 (lance le chrono comme si "JOUR I" était affiché) |
| **F6** | Forcer Day 2 |
| **F7** | Forcer Day 3 |
| **F8** | Skip Boss / Correction |
| **F9** | Ouvrir OCR Tuner (pause la logique) |
| **F10** | Quitter l'application |

### Configuration

Éditez `config.json` ou utilisez le menu "Settings" dans le system tray :

- **Monitor Region** : Zone d'écran où apparaît le texte "JOUR"
- **Level/Runes Regions** : Zones pour OCR du niveau et des runes
- **Volume** : Volume des annonces audio
- **Debug Options** : Activer/désactiver les images et logs de debug

### Nouvelles Fonctionnalités (Jan 2026)

- **OCR Tuner** : Ajustement en temps réel des paramètres OCR (F9)
- **Logic Pause** : Le tuning pause l'état du jeu pour éviter les faux triggers
- **Debug Overlay** : Indicateurs visuels LED (Rouge/Orange/Vert) pour Level, Runes, Zone
- **4 Marqueurs Graphiques** : Lignes verticales marquant la fin de chaque phase Shrinking

---

## 🎲 Mécanique du Jeu Nightreign

### Structure d'une Partie

Une partie complète de Nightreign se compose de **3 Days** :

#### Day 1 & Day 2 (Identiques)

Durée totale : **14 minutes** chacun

| Phase | Durée | Description |
|-------|-------|-------------|
| Storm | 4m 30s | Phase d'exploration |
| Shrinking | 3m 00s | Zone se réduit |
| Storm 2 | 3m 30s | Deuxième phase d'exploration |
| Shrinking 2 | 3m 00s | Deuxième réduction |
| **Boss** | Variable | Combat de boss |

#### Day 3 (Spécial)

- **Préparation** : Pas de timer, phase libre
- **Boss Final** : Combat final sans timer

### Transitions de Phase

#### Transitions Automatiques (Timer)

- Toutes les phases avec durée fixe avancent automatiquement à 00:00
- Exemple : `Day 1 - Shrinking 2` → `Boss 1` (automatique)

#### Transitions OCR

- **Day 1** : Détection de "JOUR I" / "DAY I"
  - Effet : Reset Level à 1, nouveau log de session
- **Day 2** : Détection de "JOUR II" / "DAY II"
  - Prérequis : Doit être en phase Boss 1

> **Note Multilingue** : L'application supporte "JOUR" (français) et "DAY" (anglais) avec logique floue (>70% similarité)

#### Transitions Écran Noir

- **Boss 2 → Day 3** : Détection d'écran noir (0.3s - 3.0s)
- **Day 3 Prep → Boss Final** : Détection d'écran noir

### Objectifs de Niveau

- **Niveau Maximum** : Level 15
- **Objectif Optimal** : Level 14 avant Boss 2 (~28 minutes)
- **Runes Totales Requises** : **512,936 runes** (Level 1 → 15)

### Récompenses Boss

Les montants sont **variables/approximatifs** :

- Boss 1 : ~50,000 runes
- Boss 2 : ~50,000 runes
- Boss 3 : Variable

### Marqueurs Shrink

4 marqueurs verticaux sur le graphique :

- **Shrink 1.1** : 7m30s (fin Day 1 - Shrinking)
- **Shrink 1.2** : 14m00s (fin Day 1 - Shrinking 2)
- **Shrink 2.1** : 21m30s (fin Day 2 - Shrinking)
- **Shrink 2.2** : 28m00s (fin Day 2 - Shrinking 2)

---

## 🏗️ Architecture Technique

### Architecture Orientée Services (SOA)

L'application utilise une architecture **Event-Driven** avec injection de dépendances via `ServiceContainer`.

#### Services Principaux

1. **`IConfigService`** : Gestion de `config.json`
2. **`IVisionService`** : Wrapper pour `VisionEngine` (OCR)
3. **`IOverlayService`** : Gestion de l'interface PyQt6 (`ModernOverlay`)
4. **`IStateService`** : "Cerveau" - Machine à états et consensus
5. **`IDatabaseService`** : Persistance SQLite des statistiques
6. **`IAudioService`** : Annonces vocales TTS
7. **`ITrayService`** : Icône system tray

#### Flux de Données

```
VisionEngine (Capture) 
    ↓
VisionService (Détection OCR)
    ↓
StateService (Décision/Logique)
    ↓
OverlayService (Mise à jour UI)
```

### Structure des Fichiers

```
nightreign-timer/
├── main.py                 # Point d'entrée
├── src/
│   ├── services/          # Services (State, Vision, Overlay, etc.)
│   ├── ui/                # Interfaces PyQt6
│   ├── core/              # Logique métier (GameRules, Session, Events)
│   ├── vision_engine.py   # Moteur OCR
│   └── logger.py          # Système de logging
├── data/
│   ├── logs/              # Logs de sessions (JSON)
│   └── stats.db           # Base de données SQLite
├── tools/                 # Scripts de diagnostic
└── config.json            # Configuration utilisateur
```

---

## 🔍 Système OCR & Vision

### Moteur OCR

- **Engine** : Tesseract OCR (`--psm 7` pour ligne unique)
- **Prétraitement** :
  - Auto-resize (160px hauteur)
  - Gamma correction (0.5)
  - Seuillage Otsu

### Stratégies de Détection

#### Logique Floue (Fuzzy Logic)

- **Algorithme** : `difflib.SequenceMatcher`
- **Seuil** : Similarité > 70%
- **Filtre** : Longueur texte < 20 caractères
- **Exemple** : "JOOR" → "JOUR" (accepté)

#### Consensus & Validation

- **Level Consensus** : 2 lectures identiques consécutives requises *(sera migré vers burst 4/5)*
- **Rune Burst** : 5 scans rapides, majorité 3/5 requise *(sera augmenté à 4/5)*
- **Filtre Flicker** : Transitions ±1 rune lissées/ignorées

> **Note**: Une refonte majeure du système de validation est prévue avec une architecture de "tickets" inspirée des systèmes bancaires, permettant une digestion robuste des événements OCR sans dépendance temporelle.

#### Vision Conditionnelle

- **Règle** : Menu principal scanné **uniquement si** l'icône Rune (HUD) est absente
- **Optimisation** : Évite les scans inutiles pendant le gameplay

### Détection Écran Noir

- **Mécanisme** : Monitoring global de la luminosité
- **Seuil** : Brightness < 3
- **Durée** : 0.3s - 3.0s pour valider une transition

### Multi-Écrans

- **Capture** : PIL `ImageGrab` avec `all_screens=True`
- **Support** : Configurations multi-moniteurs

---

## 📊 Analytique & Courbe Idéale

### Modèle "Snowball" Exponentiel

L'application calcule une courbe idéale de progression basée sur un modèle exponentiel.

#### Constantes (Configurables)

```python
# Dans config.json → "nightreign"
{
  "snowball_d1": 1.35,      # Facteur Day 1
  "snowball_d2": 1.15,      # Facteur Day 2
  "farming_goal": 337578,   # Objectif farming pur
  "target_level": 14,       # Niveau cible avant Boss 2
  "day_duration": 840,      # 14 minutes par day
  "total_time": 1680        # 28 minutes total (2 days)
}
```

#### Formule : Ideal(t)

1. **Temps Effectif** : `t_eff = max(0, t - 15)` (offset 15s pour chute/loading)
2. **Farming Continu** :
   - Utilise exposant 1.35 pour Day 1
   - Utilise exposant 1.15 pour Day 2
3. **Étapes Boss** (Discrètes) :
   - +50,000 à la fin de Day 1
   - +50,000 à la fin de Day 2

### Système de Grades

Basé sur le delta par rapport à la courbe idéale :

| Grade | Delta |
|-------|-------|
| **S** | +10% ou plus |
| **A** | +5% à +10% |
| **B** | 0% à +5% |
| **C** | -5% à 0% |
| **D** | -10% à -5% |
| **F** | -10% ou moins |

### Graphique Double Courbe

- **Courbe Verte (Real)** : Total corrigé, monotone (Ratchet)
- **Courbe Orange (Sensor)** : Données OCR brutes, montre les glitches

---

## 🎯 Logique de Mort & Récupération

### Détection de Mort (Stat-Based + Black Screen)

**Conditions** (toutes requises) :

1. ✅ **Level Drop** : Niveau diminue EXACTEMENT de 1 (ex: 9 → 8)
   - Drops > 1 rejetés comme glitches OCR
2. ✅ **Runes → Zéro** : Runes tombent à < 50
3. ✅ **Écran Noir** : REQUIS (détection black screen dans les 5 dernières secondes)

> **Changement Important**: L'écran noir est maintenant **obligatoire** pour valider une mort, évitant les faux positifs dus aux glitches OCR.

### Logique de Récupération "All or Nothing"

- **Récupération** : Gain de runes = montant bloodstain EXACT (au rune près)
- **Double Mort** : Runes pending → Perte permanente
- **Reset Guard** : Raccourcis manuels forcent les changements d'état
- **UI Feedback** : Indicateur recyclage (+1) lors de la récupération réussie

> **Note**: Un bug connu fait que l'indicateur recyclage reste parfois à 0 au lieu de +1 lors d'une récupération exacte.

### Distinction Loading vs Death

- **Loading** : Même level, mêmes runes après écran noir
- **Death** : Level -1, Runes = 0 après écran noir

---

## 💻 Guide Développeur

### Prérequis Développement

```bash
# Installer les dépendances
pip install -r requirements.txt

# Vérifier les bibliothèques
python tools/check_libs.py

# Tester la capture d'écran
python tools/diagnose_capture.py
```

### Outils de Diagnostic

| Script | Description |
|--------|-------------|
| `check_libs.py` | Vérifie les dépendances |
| `check_region.py` | Outil visuel pour vérifier les régions |
| `diagnose_capture.py` | Diagnostic de capture d'écran |
| `optimize_ocr.py` | Script de tuning OCR |

### Thread Safety

> ⚠️ **CRITIQUE** : `BetterCam` (DXGI) n'est PAS thread-safe !

- **Main Thread** : Utilise `BetterCam` pour capture haute performance
- **Secondary Thread** : **DOIT utiliser `MSS`** pour éviter les crashes

### Tests

```bash
# Exécuter les tests (si restaurés depuis archive/)
pytest tests/
```

### Packaging

```bash
# Créer un exécutable standalone
pyinstaller --onefile --windowed main.py
```

---

## 🐛 Bugs Connus & Corrections

### 1. Spike de Runes (Level Up)

**Problème** : Double comptage lors du level up (Merchant Spending + Level Cost)

**Solution** : Correction rétroactive dans la logique Level Up

- Vérifie `recent_spending_history` (60 dernières secondes)
- Annule les dépenses marchandes qui correspondent au coût du level
- Répare les 60 dernières secondes de l'historique graphique

### 2. Stabilité Graphique (Ratchet)

**Problème** : Bruit OCR (ex: 7774 → 7174) causant des dips

**Solution** :

- **Règle de Monotonie** : Courbe verte VERROUILLÉE, ne peut pas descendre
- **Exceptions** : Mort ou dépense marchande validée
- **Filtre Suspect** : Drops d'un seul chiffre → "Incertain" pendant 15s+

### 3. Logique Floue pour OCR

**Problème** : Typos fréquentes ("JOOR" au lieu de "JOUR")

**Solution** :

- Algorithme `difflib.SequenceMatcher`
- Seuil 70% de similarité
- Filtre longueur < 20 caractères

### 4. Vision Conditionnelle

**Problème** : Scans menu inutiles pendant gameplay

**Solution** :

- Menu scanné **uniquement si** icône Rune absente
- Burst de 5 frames pour confirmation (4/5 requis)
- UI Feedback : "🏠 Menu" au lieu de "00:00"

### 5. Offset Courbe Idéale

**Problème** : Premières 15s = chute/loading (0 runes)

**Solution** :

- Offset de 15 secondes : `Ideal(t) = Goal * ((t - 15) / (Total - 15))^Snowball`
- Ligne pointillée commence à t=15s sur le graphique

---

## 🔧 Dépannage

### L'application ne démarre pas

1. Vérifier que Python 3.8+ est installé
2. Vérifier que Tesseract OCR est dans le PATH
3. Exécuter `python tools/check_libs.py`

### OCR ne détecte rien

1. Ouvrir OCR Tuner (F9)
2. Vérifier que les régions sont correctement définies
3. Tester avec "Capture Test" dans le tuner
4. Ajuster les paramètres de prétraitement si nécessaire

### Le timer ne démarre pas

1. Vérifier que le jeu affiche bien "JOUR I" ou "DAY I"
2. Appuyer sur F5 pour forcer le démarrage de Day 1
3. Vérifier les logs dans `data/logs/`

### Faux positifs de mort

1. Vérifier que la détection Level/Runes est stable
2. Ajuster les régions OCR pour éviter les glitches
3. Les drops de > 1 level sont automatiquement rejetés

### L'overlay n'est pas visible

1. Vérifier que l'overlay est "Always on Top"
2. Essayer de redémarrer l'application
3. Vérifier les paramètres multi-écrans

---

## 📝 Changelog

### Version 2.0 (Jan 2026)

- ✅ Refonte complète de l'architecture (SOA)
- ✅ Migration vers PyQt6
- ✅ OCR Tuner avec pause logique
- ✅ Debug Overlay avec indicateurs LED
- ✅ 4 marqueurs Shrink sur le graphique
- ✅ Auto-reset via détection menu
- ✅ Détection de mort stat-based
- ✅ Graphique double courbe (Real + Sensor)
- ✅ Système de grades S-F
- ✅ Support multilingue (FR/EN)

---

## 📄 Licence

Ce projet est un outil personnel pour le jeu Nightreign. Utilisez-le à vos propres risques.

---

## 🙏 Crédits

- **Tesseract OCR** : Google
- **PyQt6** : Riverbank Computing
- **Nightreign** : FromSoftware

---

**Dernière mise à jour** : 29 Janvier 2026
