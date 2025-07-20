import os
from PIL import Image, ImageDraw, ImageFont

# Create assets directory if it doesn't exist
os.makedirs("../assets", exist_ok=True)

# Create a 64x64 image with green background
img = Image.new('RGBA', (64, 64), (0, 100, 0, 255))
draw = ImageDraw.Draw(img)

# Draw a white arrow (signal indicator)
draw.polygon([(15, 32), (49, 32), (49, 15), (64, 32), (49, 49), (49, 32)], 
             fill=(255, 255, 255, 255))

# Draw a circle around the arrow
draw.ellipse([(5, 5), (59, 59)], outline=(255, 255, 255, 255), width=3)

# Draw a small triangle at bottom right for notification badge
draw.polygon([(50, 50), (60, 50), (55, 60)], fill=(255, 0, 0, 255))

# Save as ICO
img.save("../assets/signal_icon.ico", format="ICO", sizes=[(64, 64)])

print("Icon generated at assets/signal_icon.ico")
