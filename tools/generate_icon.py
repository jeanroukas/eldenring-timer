import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

def create_elden_ring_icon(path):
    size = (64, 64)
    # Background: Darker Black for contrast
    img = Image.new('RGBA', size, (5, 5, 5, 255))
    draw = ImageDraw.Draw(img)

    # Saturated Gold Color Palette
    gold_dark = (218, 165, 32, 255)   # Goldenrod
    gold_light = (255, 223, 0, 255)   # Saturated Yellow Gold
    
    # Draw simple "Elden Ring" style arcs
    # Main ring - Thicker lines
    bbox = (6, 6, 58, 58)
    draw.ellipse(bbox, outline=gold_dark, width=6)
    
    # Intersecting arcs to simulate the rune - Thicker lines
    draw.arc((6, -12, 58, 42), 180, 360, fill=gold_light, width=4)
    draw.line((32, 6, 32, 58), fill=gold_light, width=4)
    
    # Glow effect (simulated by drawing smaller lighter lines on top or blurring a copy)
    # For a simple icon script, we'll keep it crisp.
    
    # Save
    img.save(path)
    print(f"Icon saved to {path}")

output_path = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\src\assets\icon.png"
create_elden_ring_icon(output_path)
