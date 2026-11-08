"""Tiny dependency-free SVG plotting for the analysis scripts (numpy only, no matplotlib needed).

Each function returns an SVG string. Plots are deliberately plain: axes, ticks, points, lines and a title, in the
dashboard's palette, so a figure can go straight into a poster or a report.
"""
from __future__ import annotations

import math
from typing import Iterable, List, Optional, Sequence, Tuple

W, H = 640, 460
ML, MR, MT, MB = 70, 24, 44, 56
INK, MUTED, GRID = "#1f2a37", "#5b6b7b", "#e4e9ef"
BLUE, AMBER, RED, GREEN, VIOLET = "#1f5f8b", "#8a5a00", "#b3261e", "#2e7d32", "#5e35b1"
FONT = "font-family='Lato, Segoe UI, Helvetica, Arial, sans-serif'"


def _nice_ticks(lo: float, hi: float, n: int = 6) -> List[float]:
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / max(1, n - 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    start = math.floor(lo / step) * step
    ticks = []
    v = start
    while v <= hi + step * 0.5:
        if v >= lo - step * 0.5:
            ticks.append(round(v, 10))
        v += step
    return ticks


def _fmt(v: float) -> str:
    return f"{v:.0f}" if abs(v) >= 10 or v == 0 else f"{v:.2g}"


class Axes:
    def __init__(self, xlim: Tuple[float, float], ylim: Tuple[float, float], title: str, xlabel: str, ylabel: str,
                 subtitle: Optional[str] = None):
        self.x0, self.x1 = xlim
        self.y0, self.y1 = ylim
        if self.x1 <= self.x0:
            self.x1 = self.x0 + 1
        if self.y1 <= self.y0:
            self.y1 = self.y0 + 1
        self.parts: List[str] = []
        self.title, self.subtitle, self.xlabel, self.ylabel = title, subtitle, xlabel, ylabel
        self._legend_n = 0

    def px(self, x: float) -> float:
        return ML + (x - self.x0) / (self.x1 - self.x0) * (W - ML - MR)

    def py(self, y: float) -> float:
        return H - MB - (y - self.y0) / (self.y1 - self.y0) * (H - MT - MB)

    def points(self, xs: Iterable[float], ys: Iterable[float], color: str = BLUE, r: float = 3.2, opacity: float = 0.75,
               label: Optional[str] = None):
        for x, y in zip(xs, ys):
            if x is None or y is None or not (math.isfinite(x) and math.isfinite(y)):
                continue
            self.parts.append(f"<circle cx='{self.px(x):.1f}' cy='{self.py(y):.1f}' r='{r}' fill='{color}' fill-opacity='{opacity}'/>")
        if label:
            self._legend(label, color)

    def line(self, xs: Sequence[float], ys: Sequence[float], color: str = INK, width: float = 1.6, dash: Optional[str] = None,
             label: Optional[str] = None):
        pts = " ".join(f"{self.px(x):.1f},{self.py(y):.1f}" for x, y in zip(xs, ys) if math.isfinite(x) and math.isfinite(y))
        d = f" stroke-dasharray='{dash}'" if dash else ""
        self.parts.append(f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='{width}'{d}/>")
        if label:
            self._legend(label, color, dash)

    def hline(self, y: float, color: str = MUTED, dash: Optional[str] = "4 4", label: Optional[str] = None):
        self.line([self.x0, self.x1], [y, y], color, 1.2, dash, label)

    def vline(self, x: float, color: str = MUTED, dash: Optional[str] = "4 4", label: Optional[str] = None):
        self.line([x, x], [self.y0, self.y1], color, 1.2, dash, label)

    def band(self, x0: float, x1: float, color: str = AMBER, opacity: float = 0.08):
        self.parts.append(f"<rect x='{self.px(x0):.1f}' y='{MT}' width='{self.px(x1) - self.px(x0):.1f}' "
                          f"height='{H - MT - MB}' fill='{color}' fill-opacity='{opacity}'/>")

    def text(self, x: float, y: float, s: str, color: str = INK, size: int = 12, anchor: str = "start"):
        self.parts.append(f"<text x='{self.px(x):.1f}' y='{self.py(y):.1f}' fill='{color}' font-size='{size}' "
                          f"text-anchor='{anchor}' {FONT}>{_esc(s)}</text>")

    def _legend(self, label: str, color: str, dash: Optional[str] = None):
        y = MT + 14 + 16 * self._legend_n
        self._legend_n += 1
        x = W - MR - 190
        d = f" stroke-dasharray='{dash}'" if dash else ""
        self.parts.append(f"<line x1='{x}' y1='{y - 4}' x2='{x + 22}' y2='{y - 4}' stroke='{color}' stroke-width='2.4'{d}/>")
        self.parts.append(f"<text x='{x + 28}' y='{y}' fill='{INK}' font-size='11.5' {FONT}>{_esc(label)}</text>")

    def render(self) -> str:
        g = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
             f"<rect width='{W}' height='{H}' fill='white'/>"]
        for t in _nice_ticks(self.x0, self.x1):
            x = self.px(t)
            g.append(f"<line x1='{x:.1f}' y1='{MT}' x2='{x:.1f}' y2='{H - MB}' stroke='{GRID}'/>")
            g.append(f"<text x='{x:.1f}' y='{H - MB + 18}' fill='{MUTED}' font-size='11' text-anchor='middle' {FONT}>{_fmt(t)}</text>")
        for t in _nice_ticks(self.y0, self.y1):
            y = self.py(t)
            g.append(f"<line x1='{ML}' y1='{y:.1f}' x2='{W - MR}' y2='{y:.1f}' stroke='{GRID}'/>")
            g.append(f"<text x='{ML - 8}' y='{y + 4:.1f}' fill='{MUTED}' font-size='11' text-anchor='end' {FONT}>{_fmt(t)}</text>")
        g.append(f"<rect x='{ML}' y='{MT}' width='{W - ML - MR}' height='{H - MT - MB}' fill='none' stroke='{MUTED}' stroke-width='1'/>")
        g.append("<g>")
        if self._legend_n:
            g.append(f"<rect x='{W - MR - 198}' y='{MT + 2}' width='{198 - 2}' height='{16 * self._legend_n + 8}' "
                     f"fill='white' fill-opacity='0.88' stroke='{GRID}'/>")
        g.extend(self.parts)
        g.append("</g>")
        g.append(f"<text x='{ML}' y='22' fill='{INK}' font-size='15' font-weight='700' {FONT}>{_esc(self.title)}</text>")
        if self.subtitle:
            g.append(f"<text x='{ML}' y='37' fill='{MUTED}' font-size='11.5' {FONT}>{_esc(self.subtitle)}</text>")
        g.append(f"<text x='{(ML + W - MR) / 2:.1f}' y='{H - 14}' fill='{INK}' font-size='12.5' text-anchor='middle' {FONT}>{_esc(self.xlabel)}</text>")
        g.append(f"<text transform='translate(16,{(MT + H - MB) / 2:.1f}) rotate(-90)' fill='{INK}' font-size='12.5' "
                 f"text-anchor='middle' {FONT}>{_esc(self.ylabel)}</text>")
        g.append("</svg>")
        return "\n".join(g)


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def save(path: str, svg: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
