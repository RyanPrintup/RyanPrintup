#!/usr/bin/env python3
"""Builds the README's banner, section headings and social tiles from assets.json.

GitHub READMEs can't load fonts or CSS, so all type is converted to outlines.

Install dependencies with:
    pip install -r scripts/requirements.txt

Run with:
    python3 scripts/make_assets.py <fonts dir> <logo.svg> <social icons dir>

Inputs:
    <fonts dir>: a folder containing big-shoulders-display-latin-900-normal.woff2
        (Big Shoulders Display, Black 900, from Fontsource / Google Fonts)
    <logo.svg>: the RYAN PRINTUP logo, in its colors for navy backgrounds
    <social icons dir>: a folder of single-color SVG icons named linkedin.svg,
        instagram.svg, youtube.svg, facebook.svg and bandsintown.svg
"""
import io
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).parent.parent
CONFIG = json.loads((Path(__file__).parent / "assets.json").read_text())
COLORS = CONFIG["colors"]


class Font:
    def __init__(self, path):
        self.tt = TTFont(path)
        self.tt.flavor = None
        data = io.BytesIO()
        self.tt.save(data)
        self.hb = hb.Font(hb.Face(data.getvalue()))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upm = self.tt["head"].unitsPerEm
        self.cap = self.tt["OS/2"].sCapHeight

    def layout(self, text, size, x, baseline, tracking=0.0):
        """Returns the path data for text, with the font's kerning, and where the text ends."""
        if not text:
            return "", x
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf)
        scale = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            transform = (scale, 0, 0, -scale, x + pos.x_offset * scale, baseline - pos.y_offset * scale)
            self.glyphs[self.order[info.codepoint]].draw(TransformPen(pen, transform))
            x += pos.x_advance * scale + tracking * size
        return pen.getCommands(), x


def svg(width, height, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" width="{width:g}" '
            f'height="{height:g}" role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>{body}</svg>\n')


def banner(display, logo_src):
    config = CONFIG["banner"]
    width, height = config["width"], config["height"]
    logo = config["logo"]

    inner = re.search(r"<defs>.*</svg>", logo_src, re.S).group(0).removesuffix("</svg>")
    view_w, view_h = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', logo_src).groups())
    scale = logo["height"] / view_h
    text_x = logo["x"] + view_w * scale + logo["gap"]

    # Each headline line sits on a tier of the logo: RYAN's baseline and the bottom of the PRINTUP block.
    logo_y = (config["contentHeight"] - logo["height"]) / 2
    size = logo["baselines"][0] * scale * display.upm / display.cap
    parts = []
    for line, logo_baseline in zip(config["headline"], logo["baselines"]):
        x = text_x
        for run in line:
            path, x = display.layout(run["text"], size, x, logo_y + logo_baseline * scale, tracking=0.01)
            parts.append(f'<path d="{path}" fill="{COLORS["ember"] if run.get("ember") else COLORS["sand"]}"/>')
        assert x <= width - logo["x"], f"headline runs to {x:.0f}"

    return svg(width, height, config["title"],
               f'<clipPath id="corners"><rect width="{width}" height="{height}" rx="4"/></clipPath>'
               f'<g clip-path="url(#corners)"><rect width="{width}" height="{height}" fill="{COLORS["navy"]}"/>'
               f'<rect y="{config["contentHeight"]}" width="{width}" height="{height - config["contentHeight"]}" '
               f'fill="{COLORS["ember"]}"/></g>'
               f'<g transform="translate({logo["x"]} {logo_y:g}) scale({scale:.5f})">{inner}</g>'
               + "".join(parts))


def heading(display, plain, word, plain_color, word_color):
    size = CONFIG["headings"]["size"]
    height = round(display.cap * size / display.upm)
    first, x = display.layout(plain, size, 0, height, tracking=0.01)
    second, x = display.layout(word, size, x, height, tracking=0.01)
    return svg(round(x + 1), height, (plain + word).title(),
               f'<path d="{first}" fill="{plain_color}"/><path d="{second}" fill="{word_color}"/>')


def tile(icon_src, name):
    size, icon_size = CONFIG["tiles"]["size"], CONFIG["tiles"]["iconSize"]
    view_w, view_h = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', icon_src).groups())
    shapes = re.search(r"<svg[^>]*>(.*)</svg>", icon_src, re.S).group(1)
    scale = icon_size / max(view_w, view_h)
    x, y = (size - view_w * scale) / 2, (size - view_h * scale) / 2
    return svg(size, size, name,
               f'<rect width="{size}" height="{size}" rx="4" fill="{COLORS["harbor"]}"/>'
               f'<g transform="translate({x:g} {y:g}) scale({scale:.5f})" fill="{COLORS["ember"]}">{shapes}</g>')


def main(fonts, logo, icons):
    out = ROOT / "media"
    display = Font(Path(fonts) / CONFIG["font"])

    (out / "banner.svg").write_text(banner(display, Path(logo).read_text()))
    for name, (plain, word) in CONFIG["headings"]["items"].items():
        (out / f"headings/{name}-dark.svg").write_text(
            heading(display, plain, word, COLORS["sand"], COLORS["ember"]))
        (out / f"headings/{name}-light.svg").write_text(
            heading(display, plain, word, COLORS["navy"], COLORS["rust"]))
    for name, label in CONFIG["tiles"]["icons"].items():
        icon = (Path(icons) / f"{name}.svg").read_text()
        (out / f"social-media/{name}.svg").write_text(tile(icon, label))


if __name__ == "__main__":
    main(*sys.argv[1:])
