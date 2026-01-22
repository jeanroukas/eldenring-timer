# Plan d'Évolution du Projet Elden Ring Timer

Ce document détaille la feuille de route pour l'implémentation des 5 évolutions majeures sélectionnées.

## Stratégie Globale

L'approche recommandée est de procéder par étapes séquentielles pour garantir la stabilité du projet. Nous commencerons par assainir l'architecture avant de construire les nouvelles fonctionnalités graphiques et analytiques par-dessus.

---

## 📅 Phase 1 : Refactoring & Architecture (Semaines 1-2)

**Objectif :** Rendre le code modulaire, testable et prêt pour l'extension (Point 6).

### 1.1 Injection de Dépendances (DI)

Actuellement, `App` est un "God Object". Nous allons découpler les services.

- **Action** : Créer un conteneur de services (ex: implémentation simple ou via `dependency_injector`).
- **Nouveaux Services** :
  - `IConfigService` : Gestion de la configuration (JSON).
  - `IVisionService` : Abstraction de la capture et de l'OCR.
  - `IOverlayService` : Abstraction de l'affichage (permettra de changer de Tkinter à Qt plus tard).
  - `IStateService` : Gestion de la machine à états (Day 1 -> Day 2 -> Boss).

### 1.2 Nettoyage de `main.py`

- **Action** : Réduire `main.py` à un simple point d'entrée qui initialise le conteneur DI et lance l'application.

---

## 🎨 Phase 2 : Modernisation UI & UX (Semaines 3-4)

**Objectif :** Remplacer l'interface Tkinter vieillissante et offrir une configuration accessible (Points 1 & 3).

### 2.1 Choix Technologique : PyQt6 / PySide6

PyQt offre le meilleur équilibre entre performance native, capacités de transparence/overlay et look moderne.

### 2.2 Nouvel Overlay (Point 3)

- **Création du `ModernOverlay`** :
  - Fenêtre sans bordure, fond transparent, toujours au-dessus (`WindowStaysOnTopHint`).
  - Utilisation de **QML** ou de Widgets stylisés avec CSS (QSS) pour les dégradés et animations.
  - Ajout d'animations (fadeIn/fadeOut) lors des changements d'état.

### 2.3 Interface de Paramètres (Point 1)

- **Création du `SettingsWindow`** :
  - Fenêtre séparée accessible via un raccourci ou tray icon.
  - **Onglets** :
    - *Général* : Raccourcis clavier.
    - *Capture* : Sélection de l'écran, prévisualisation de la zone en temps réel.
    - *OCR* : Réglage des seuils avec feedback visuel immédiat.
  - **Sauvegarde** : Écriture directe dans `config.json` via `ConfigService`.

---

## 🧠 Phase 3 : Intelligence & Données (Semaines 5-6)

**Objectif :** Fiabiliser la détection et donner du sens aux parties jouées (Points 4 & 8).

### 3.1 OCR Spécialisé (Point 4)

- **Collecte de Données** : Utiliser l'outil existant pour générer ~500-1000 images étiquetées (Day 1, 2, 3, Victory).
- **Entraînement** :
  - *Option A (Léger)* : Entraînement fin (Fine-tuning) de Tesseract sur la police "Mantinia" (ou proche) utilisée dans le jeu.
  - *Option B (Moderne)* : Entraînement d'un petit modèle classification d'images (CNN simple ou ResNet18 réduit) avec PyTorch/ONNX.
    - **Avantage** : Plus besoin de "cleaner" l'image parfaitement. Le modèle apprend à reconnaître "JOUR 1" même avec du bruit ou en HDR.
- **Intégration** : Remplacer l'appel Tesseract par l'inférence du nouveau modèle dans `VisionEngine`.

### 3.2 Analytique & Persistance (Point 8)

- **Base de Données** : Introduction de **SQLite** (`stats.db`).
- **Schéma** :
  - Table `sessions` (id, start_time, end_time, result).
  - Table `events` (session_id, type [BOSS_1, DEATH, VICTORY], timestamp).
- **Visualisation** :
  - Ajouter un onglet "Stats" dans la nouvelle fenêtre de paramètres.
  - Graphiques simples (ex: `matplotlib` ou `PyQtCharts`) : "Temps de survie moyen", "Taux de réussite par boss".

---

## 📋 Résumé des Tâches Techniques

### Architecture

- [ ] Créer `src/services/` et définir les interfaces.
- [ ] Refactorer `VisionEngine` pour implémenter `IVisionService`.
- [ ] Refactorer `Overlay` pour implémenter `IOverlayService`.

### Interface (PyQt6)

- [ ] Installer `PyQt6`.
- [ ] Prototyper `ModernOverlay.py`.
- [ ] Créer `SettingsWindow.py` avec formulaires liés à la config.

### Data

- [ ] Créer `src/database.py` (Wrapper SQLite).
- [ ] Ajouter les hooks d'enregistrement dans `StateService`.

### OCR ML

- [ ] Script d'extraction de dataset (automatisé).
- [ ] Script d'entraînement (Google Colab ou local).
- [ ] Convertisseur de modèle vers ONNX Runtime (pour inférence rapide en C++ sans dépendance lourde PyTorch).
