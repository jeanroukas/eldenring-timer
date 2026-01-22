import tkinter as tk
from tkinter import messagebox
import ctypes
from ctypes import wintypes

class RegionSelector:
    def __init__(self, callback):
        self.callback = callback
        self.monitors = self.get_monitors()
        self.windows = []
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.active_canvas = None
        
        # We need a root for the mainloop, but we might hide it
        self.root = tk.Tk()
        self.root.withdraw()

        for i, monitor in enumerate(self.monitors):
            win = tk.Toplevel(self.root)
            win.title(f"Monitor {i}")
            # Geometry: widthxheight+x+y
            win.geometry(f"{monitor['width']}x{monitor['height']}+{monitor['left']}+{monitor['top']}")
            win.overrideredirect(True) # No borders
            win.attributes("-alpha", 0.3)
            win.attributes("-topmost", True)
            win.configure(bg="grey")
            
            canvas = tk.Canvas(win, cursor="cross", bg="grey", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            
            # Label with instructions
            tk.Label(canvas, text=f"Monitor {i} - Click and drag to select region. Press ESC to cancel.", 
                     font=("Arial", 14), fg="white", bg="black").place(relx=0.5, rely=0.1, anchor="center")

            canvas.bind("<ButtonPress-1>", lambda e, c=canvas, m=monitor: self.on_press(e, c, m))
            canvas.bind("<B1-Motion>", lambda e, c=canvas, m=monitor: self.on_drag(e, c, m))
            canvas.bind("<ButtonRelease-1>", lambda e, c=canvas, m=monitor: self.on_release(e, c, m))
            win.bind("<Escape>", self.cancel)
            
            self.windows.append({"window": win, "canvas": canvas, "monitor": monitor})

        self.root.mainloop()

    def get_monitors(self):
        # Set DPI Awareness for accuracy
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
        # Clear other canvases
        for win_data in self.windows:
            win_data["canvas"].delete("all")
        
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.active_canvas = canvas
        self.current_rect = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=3)

    def on_drag(self, event, canvas, monitor):
        if self.active_canvas != canvas: return
        # event.x/y are relative to the window
        # We need to update the rectangle
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

        # Region in GLOBAL coordinates
        region = {"top": y1, "left": x1, "width": width, "height": height}
        
        if messagebox.askyesno("Confirm", f"Region selected on monitor:\n{region}\n\nSave this region?"):
            self.root.destroy()
            self.callback(region)
        else:
             canvas.delete("all")

    def cancel(self, event):
        self.root.destroy()
        print("Selection cancelled.")

if __name__ == "__main__":
    def print_region(r):
        print(f"Selected: {r}")
    RegionSelector(print_region)
