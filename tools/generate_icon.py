import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

def create_elden_ring_icon(path):
    size = (64, 64)
    # Background: Dark Gray/Black
    img = Image.new('RGBA', size, (20, 20, 20, 255))
    draw = ImageDraw.Draw(img)

    # Glowing Gold Color Palette
    gold_dark = (180, 140, 50, 255)
    gold_light = (255, 215, 0, 255)
    
    # Draw simple "Elden Ring" style arcs
    # Main ring
    bbox = (8, 8, 56, 56)
    draw.ellipse(bbox, outline=gold_dark, width=4)
    
    # Intersecting arcs to simulate the rune
    draw.arc((8, -10, 56, 40), 180, 360, fill=gold_light, width=3)
    draw.line((32, 8, 32, 56), fill=gold_light, width=3)
    
    # Glow effect (simulated by drawing smaller lighter lines on top or blurring a copy)
    # For a simple icon script, we'll keep it crisp.
    
    # Save
    img.save(path)
    print(f"Icon saved to {path}")

output_path = r"c:\Users\lprad\Documents\Python Scripts\Elden ring timer\src\assets\icon.png"
create_elden_ring_icon(output_path)
