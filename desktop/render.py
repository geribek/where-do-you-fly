"""Offline preview from a saved /api/v1/display response; never contacts FR24."""
import json
import sys
from PIL import Image, ImageDraw
PALETTE = {(255,255,255),(0,0,0),(255,0,0),(255,255,0)}
def render(payload, output):
    image = Image.new("RGB", (800,480), "white")
    d = ImageDraw.Draw(image)
    d.rectangle((0,0,799,70), fill="black")
    d.text((25,25), "FLIGHT DISPLAY / MOCK POC",fill="white")
    d.rectangle((25,100,775,145), fill="yellow")
    d.text((40,115), payload["status"].upper(),fill="black")
    f=payload.get("flight") or {}
    d.text((40,190), f.get("callsign") or "No flight",fill="black")
    d.text((40,230), f"{f.get('origin') or '???'} -> {f.get('destination') or '???'}",fill="black")
    d.text((40,290), payload.get("observed_at") or "No observation",fill="black")
    if payload.get("stale"): d.text((40,340),"STALE",fill="red")
    # Remove font antialiasing: output contains exactly the permitted pigment colors.
    image.putdata([min(PALETTE,key=lambda c:sum((c[i]-p[i])**2 for i in range(3))) for p in image.get_flattened_data()])
    image.save(output)
    return image
if __name__ == "__main__":
    render(json.load(open(sys.argv[1])),sys.argv[2])
