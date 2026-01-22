# Plan d'Évolution du Projet Elden Ring Timer

Ce document détaille la feuille de route pour l'implémentation des 5 évolutions majeures sélectionnées.

## Stratégie Globale

L'approche recommandée est de procéder par étapes séquentielles pour garantir la stabilité du projet. Nous commencerons par assainir l'architecture avant de construire les nouvelles fonctionnalités graphiques et analytiques par-dessus.

---

## ✅ Phase 1 : Refactoring & Architecture (Terminé)

**Objectif :** Rendre le code modulaire, testable et prêt pour l'extension.

- **Injection de Dépendances (DI)** : Implémenté via `ServiceContainer`.
- **Nouveaux Services** :
  - `ConfigService` : Gestion de la configuration.
  - `VisionService` : Abstraction de l'OCR.
  - `OverlayService` : Abstraction de l'affichage.
  - `StateService` : Gestion de la machine à états.
- **Nettoyage de `main.py`** : Réduit à un point d'entrée minimaliste.

---

## ✅ Phase 2 : Modernisation UI & UX (Terminé)

**Objectif :** Remplacer l'interface Tkinter par PyQt6 et offrir une configuration accessible.

- **Choix Technologique** : **PyQt6** utilisé pour l'ensemble de l'interface.
- **Nouvel Overlay** : `ModernOverlay` avec rendu haute qualité (outlines) et fenêtrage natif transparent.
- **Interface de Paramètres** : `SettingsWindow` avec onglets (Général, Capture, OCR) et sauvegarde en temps réel.

---

## 🧠 Phase 3 : Intelligence & Données (En cours)

**Objectif :** Fiabiliser la détection et donner du sens aux parties jouées (Points 4 & 8).

### 3.1 OCR Spécialisé (Point 4)

- **Collecte de Données** : Utiliser l'outil existant pour générer ~500-1000 images étiquetées (Day 1, 2, 3, Victory).
- **Entraînement** :
  - *Option A (Léger)* : Entraînement fin (Fine-tuning) de Tesseract sur la police "Mantinia" (ou proche) utilisée dans le jeu.
  - *Option B (Moderne)* : Entraînement d'un petit modèle classification d'images (CNN simple ou ResNet18 réduit) avec PyTorch/ONNX.
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

### Architecture & UI (Phase 1 & 2)

- [x] Créer `src/services/` et définir les interfaces.
- [x] Refactorer `VisionEngine` pour implémenter `IVisionService`.
- [x] Refactorer `Overlay` pour implémenter `IOverlayService`.
- [x] Installer `PyQt6`.
- [x] Créer `qt_overlay.py` et `settings_window.py`.

### Data (Phase 3)

- [ ] Créer `src/database.py` (Wrapper SQLite).
- [ ] Ajouter les hooks d'enregistrement dans `StateService`.

### OCR ML (Phase 3)

- [ ] Script d'extraction de dataset (automatisé).
- [ ] Script d'entraînement (Google Colab ou local).
- [ ] Convertisseur de modèle vers ONNX Runtime.
