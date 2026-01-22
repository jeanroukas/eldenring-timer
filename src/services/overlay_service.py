import tkinter as tk
import time
import sys
import winsound
from typing import Callable, Optional
from src.services.base_service import IOverlayService

class OverlayService(IOverlayService):
    def __init__(self, root: tk.Tk):
        self.root = root
        self.overlay_window: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.current_text = "Waiting..."
        self.is_recording = False
        self.x = 0
        self.y = 0

    def initialize(self) -> bool:
        # We don't create the window here immediately, maybe?
        # App.start_overlay() created it.
        # Let's verify if we should create it on start or on demand.
        # For DI, we might want it ready.
        return True

    def shutdown(self) -> None:
        if self.overlay_window:
            self.overlay_window.destroy()

    def create_overlay(self):
        if self.overlay_window: return

        self.overlay_window = tk.Toplevel(self.root)
        self.overlay_window.title("Elden Ring Overlay")
        self.overlay_window.geometry("600x120-50+20") 
        self.overlay_window.overrideredirect(True)
        self.overlay_window.attributes("-topmost", True)
        self.overlay_window.attributes("-transparentcolor", "#000001")
        self.overlay_window.configure(bg="#000001")
        self.overlay_window.attributes("-alpha", 0.50)

        self.canvas = tk.Canvas(self.overlay_window, bg="#000001", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.overlay_window.bind("<ButtonPress-1>", self.start_move)
        self.overlay_window.bind("<B1-Motion>", self.do_move)
        
        # We don't bind Q to quit here, as thatlogic belongs to App controller usually, 
        # but for now we can keep it or delegate.
        
        self.update_view()

    def show(self) -> None:
        if not self.overlay_window:
            self.create_overlay()
        self.overlay_window.deiconify()

    def hide(self) -> None:
        if self.overlay_window:
            self.overlay_window.withdraw()

    def update_timer(self, text: str) -> None:
        self.current_text = text
        self.update_view()

    def update_status(self, text: str) -> None:
        # For now, status and timer share the same text area in the view
        self.current_text = text
        self.update_view()

    def set_click_through(self, enabled: bool) -> None:
        # Tkinter doesn't easily support dynamic click-through modification on Windows 
        # without complex WinAPI calls. We'll ignore for Phase 1.
        pass

    def show_recording(self, show: bool):
        self.is_recording = show
        self.update_view()

    def update_view(self):
        if not self.canvas: return
        self.canvas.delete("all")
        text = self.current_text
        
        # Add recording indicator if needed
        # Logic was in StateService/App to toggle text, but here we can prepend
        # actually, StateService passes the full string usually.
        # But `show_recording` sets a flag.
        
        display_text = text
        if self.is_recording and not text.startswith("🔴"):
             # Simple check, though "Waiting..." logic did prepend it manually in old code.
             # We will let StateService handle the text content fully?
             # Old code: if self.is_recording: prefix += "🔴 "
             pass

        x, y = 590, 60 
        font_spec = ("Helvetica", 24, "bold")
        
        offsets = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1),
            (-2, 0), (2, 0), (0, -2), (0, 2)
        ]
        for ox, oy in offsets:
            self.canvas.create_text(x+ox, y+oy, text=display_text, font=font_spec, fill="black", anchor="e")
            
        self.canvas.create_text(x, y, text=display_text, font=font_spec, fill="white", anchor="e")

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.overlay_window.winfo_x() + deltax
        y = self.overlay_window.winfo_y() + deltay
        self.overlay_window.geometry(f"+{x}+{y}")

    def schedule(self, delay_ms: int, callback: Callable) -> None:
        """Schedule a callback on the UI thread."""
        self.root.after(delay_ms, callback)
