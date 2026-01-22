"""
Script rapide pour ajouter/sélectionner la région de victoire.
Permet de sélectionner la région et la sauvegarde automatiquement.
"""
import os
from src.config import load_config, save_config
from test_capture_resultat import RegionSelector

def main():
    print("=== Sélection de la région de victoire ===\n")
    print("Ce script vous permet de sélectionner la région où apparaît")
    print("le texte 'résultat' lors de la victoire du boss jour 3.\n")
    
    # Charger la config actuelle
    config = load_config()
    
    # Afficher la région actuelle si elle existe
    if config.get("victory_region"):
        print(f"Région actuelle: {config.get('victory_region')}")
        print()
        response = input("Voulez-vous la remplacer? (o/n): ")
        if response.lower() not in ['o', 'oui', 'y', 'yes']:
            print("Annulé.")
            return
    
    print("\nSélectionnez la région sur l'écran...")
    selector = RegionSelector()
    selected_region = selector.select()
    
    if not selected_region:
        print("Aucune région sélectionnée. Annulé.")
        return
    
    print(f"\nRégion sélectionnée: {selected_region}")
    
    # Sauvegarder automatiquement
    config["victory_region"] = selected_region
    save_config(config)
    
    print("\n✓ Région de victoire sauvegardée dans config.json!")
    print(f"  {selected_region}")
    print("\nLa détection de victoire est maintenant configurée.")
    print("Elle sera active automatiquement lors de la phase 'Day 3 - Final Boss'.")

if __name__ == "__main__":
    main()
