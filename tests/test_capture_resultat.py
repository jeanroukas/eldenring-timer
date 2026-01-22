"""
Script de test pour capturer une image raw et une image proc
pour tester la détection du texte "résultat" pour le boss du jour 3.
Permet de sélectionner manuellement la région à capturer.
"""
import os
import cv2
import datetime
import time
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import messagebox
from src.config import load_config
from src.vision_engine import VisionEngine

class RegionSelector:
    """Sélecteur de région simplifié pour ce script."""
    def __init__(self):
        self.monitors = self.get_monitors()
        self.windows = []
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.active_canvas = None
        self.selected_region = None
        
        self.root = tk.Tk()
        self.root.withdraw()

        for i, monitor in enumerate(self.monitors):
            win = tk.Toplevel(self.root)
            win.title(f"Monitor {i}")
            win.geometry(f"{monitor['width']}x{monitor['height']}+{monitor['left']}+{monitor['top']}")
            win.overrideredirect(True)
            win.attributes("-alpha", 0.3)
            win.attributes("-topmost", True)
            win.configure(bg="grey")
            
            canvas = tk.Canvas(win, cursor="cross", bg="grey", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            
            tk.Label(canvas, text=f"Monitor {i} - Cliquez et glissez pour sélectionner la région du texte 'résultat'. ESC pour annuler.", 
                     font=("Arial", 14), fg="white", bg="black").place(relx=0.5, rely=0.1, anchor="center")

            canvas.bind("<ButtonPress-1>", lambda e, c=canvas, m=monitor: self.on_press(e, c, m))
            canvas.bind("<B1-Motion>", lambda e, c=canvas, m=monitor: self.on_drag(e, c, m))
            canvas.bind("<ButtonRelease-1>", lambda e, c=canvas, m=monitor: self.on_release(e, c, m))
            win.bind("<Escape>", self.cancel)
            
            self.windows.append({"window": win, "canvas": canvas, "monitor": monitor})

    def get_monitors(self):
        """Récupère la liste des moniteurs avec gestion DPI."""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            ctypes.windll.user32.SetProcessDPIAware()

        screens = []
        def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            rect = lprcMonitor.contents
            screens.append({
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top
            })
            return True

        MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(enum_proc), 0)
        return screens

    def on_press(self, event, canvas, monitor):
        for win_data in self.windows:
            win_data["canvas"].delete("all")
        
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.active_canvas = canvas
        self.current_rect = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=3)

    def on_drag(self, event, canvas, monitor):
        if self.active_canvas != canvas: return
        start_rel_x = self.start_x - monitor['left']
        start_rel_y = self.start_y - monitor['top']
        canvas.coords(self.current_rect, start_rel_x, start_rel_y, event.x, event.y)

    def on_release(self, event, canvas, monitor):
        if self.active_canvas != canvas: return
        
        x1 = min(self.start_x, event.x_root)
        y1 = min(self.start_y, event.y_root)
        x2 = max(self.start_x, event.x_root)
        y2 = max(self.start_y, event.y_root)
        
        width = x2 - x1
        height = y2 - y1
        
        if width < 10 or height < 10:
            return

        region = {"top": y1, "left": x1, "width": width, "height": height}
        
        if messagebox.askyesno("Confirmer", f"Région sélectionnée:\n{region}\n\nUtiliser cette région pour la capture?"):
            self.selected_region = region
            self.root.destroy()
        else:
            canvas.delete("all")

    def cancel(self, event):
        self.root.destroy()
        print("Sélection annulée.")

    def select(self):
        """Lance la sélection et retourne la région sélectionnée."""
        self.root.mainloop()
        return self.selected_region

def capture_region(vision, region):
    """Capture une région spécifique en utilisant region_override."""
    # Sauvegarder temporairement la région configurée
    old_region = vision.config.get("monitor_region")
    
    # Utiliser la région sélectionnée
    vision.config["monitor_region"] = region
    vision.update_region(region)
    
    # Attendre un peu pour stabiliser
    time.sleep(0.5)
    
    # Capturer
    img = vision.capture_screen()
    
    # Restaurer l'ancienne région
    vision.config["monitor_region"] = old_region
    if old_region:
        vision.update_region(old_region)
    
    return img

def main():
    print("=== Script de test pour capturer images raw et proc ===\n")
    print("Ce script vous permet de sélectionner manuellement la région")
    print("où se trouve le texte 'résultat' pour le boss du jour 3.\n")
    
    # Charger la configuration
    config = load_config()
    print(f"Configuration chargée:")
    print(f"  - HDR Mode: {config.get('hdr_mode', False)}")
    print()
    
    # Initialiser VisionEngine
    print("Initialisation de VisionEngine...")
    vision = VisionEngine(config)
    
    # Sélectionner la région
    print("\n=== Sélection de la région ===")
    print("Une fenêtre va s'ouvrir sur chaque moniteur.")
    print("Cliquez et glissez pour sélectionner la région contenant le texte 'résultat'.")
    print("Appuyez sur ESC pour annuler.\n")
    
    selector = RegionSelector()
    selected_region = selector.select()
    
    if not selected_region:
        print("Aucune région sélectionnée. Arrêt du script.")
        return
    
    print(f"\nRégion sélectionnée: {selected_region}")
    
    # Attendre un peu avant la capture
    print("\nAttente de 1 seconde avant la capture...")
    time.sleep(1)
    
    # Capturer l'image raw avec la région sélectionnée
    print("Capture de l'image raw...")
    raw_img = capture_region(vision, selected_region)
    
    if raw_img is None:
        print("ERREUR: Impossible de capturer l'image!")
        return
    
    print(f"Image raw capturée: {raw_img.shape[1]}x{raw_img.shape[0]}")
    
    # Traiter l'image avec toutes les passes
    print("\nTraitement de l'image...")
    
    # Créer le répertoire debug_images s'il n'existe pas
    debug_dir = os.path.join(os.path.dirname(__file__), "debug_images")
    os.makedirs(debug_dir, exist_ok=True)
    
    # Générer un timestamp
    timestamp = datetime.datetime.now().strftime("%H%M%S")
    
    # Sauvegarder l'image raw
    raw_path = os.path.join(debug_dir, f"debug_raw_{timestamp}.png")
    cv2.imwrite(raw_path, raw_img)
    print(f"  ✓ Image raw sauvegardée: {raw_path}")
    
    # Traiter et sauvegarder avec chaque passe
    passes = ["otsu", "fixed", "adaptive"]
    for pass_type in passes:
        proc_img = vision.preprocess_image(raw_img, pass_type=pass_type)
        if proc_img is not None:
            proc_path = os.path.join(debug_dir, f"debug_proc_{pass_type}_{timestamp}.png")
            cv2.imwrite(proc_path, proc_img)
            print(f"  ✓ Image proc ({pass_type}) sauvegardée: {proc_path}")
    
    # Tester aussi l'OCR pour voir si "résultat" est détecté
    print("\n=== Test OCR sur l'image traitée ===")
    import pytesseract
    
    tesseract_cmd = config.get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    for pass_type in passes:
        proc_img = vision.preprocess_image(raw_img, pass_type=pass_type)
        if proc_img is not None:
            data = pytesseract.image_to_data(proc_img, config='--psm 7', output_type=pytesseract.Output.DICT)
            valid_indices = [i for i, t in enumerate(data['text']) if t.strip()]
            raw_text = " ".join([data['text'][i] for i in valid_indices]).strip()
            text = vision.clean_text(raw_text)
            
            if text:
                print(f"  {pass_type}: '{text}' (raw: '{raw_text}')")
            else:
                print(f"  {pass_type}: (aucun texte détecté)")
    
    print("\n=== Capture terminée avec succès! ===")
    print(f"Vérifiez les images dans: {debug_dir}")
    print(f"\nRégion sélectionnée: {selected_region}")
    
    # Proposer de sauvegarder dans la config
    print("\n=== Sauvegarde de la région ===")
    print("Cette région sera utilisée pour détecter le texte 'résultat' lors de la victoire du boss jour 3.")
    print()
    response = input("Voulez-vous sauvegarder cette région comme 'victory_region' dans config.json? (o/n): ")
    if response.lower() in ['o', 'oui', 'y', 'yes']:
        from src.config import save_config
        config["victory_region"] = selected_region
        save_config(config)
        print(f"\n✓ Région de victoire sauvegardée dans config.json")
        print(f"  {selected_region}")
        print("\nVous pouvez maintenant utiliser le script principal. La détection de victoire sera active!")
    else:
        print("\n⚠ Région non sauvegardée automatiquement.")
        print("\nPour l'ajouter manuellement, ajoutez ceci dans votre config.json:")
        print("=" * 60)
        print(f'"victory_region": {selected_region},')
        print("=" * 60)
        print("\nOu relancez ce script et répondez 'o' pour sauvegarder automatiquement.")

if __name__ == "__main__":
    main()
