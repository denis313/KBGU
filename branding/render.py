"""Render the SVGs in this folder to PNG: python branding/render.py"""
import pathlib, sys
from playwright.sync_api import sync_playwright

here = pathlib.Path(__file__).resolve().parent
chrome = sys.argv[1] if len(sys.argv) > 1 else None
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome) if chrome else p.chromium.launch()
    for name, (w, h) in {"bot-avatar": (1024, 1024), "bot-description": (640, 360)}.items():  # BotFather: exactly 640x360
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.set_content(f'<html><body style="margin:0">{(here / f"{name}.svg").read_text()}</body></html>')
        pg.screenshot(path=str(here / f"{name}.png"), clip={"x": 0, "y": 0, "width": w, "height": h})
        print("wrote", name + ".png")
    b.close()
