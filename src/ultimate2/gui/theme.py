"""Colours, fonts, timings and controller skins of the interface.

Values that other modules read at call time (``FAMILY``, ``AUTOSAVE_MS``, ``POLL_MS``, ``FRAME_MS``) are
always accessed as ``theme.NAME`` so they can be changed in one place (and patched in tests).
"""
import tkinter.font as tkfont

# palette
BG, TILE, TILE_HI, LINE, FG, MUTED, ACCENT, DANGER, WARN = (
    "#1b1b1b", "#262626", "#313131", "#3c3c3c", "#ececec", "#8c8c8c", "#4cd964", "#ff6b6b", "#ffcc66")
BODY_FILL, SEL_FILL = "#222222", "#1d3524"
CALLOUT_FILL, CALLOUT_LINE, CALLOUT_DOT = "#1d1733", "#7c5cd6", "#b9a1ec"

# timings (ms) and the ripple duration (s)
AUTOSAVE_MS, POLL_MS, FRAME_MS = 400, 2500, 33
PULSE = 0.35

FAMILY = "Sans"          # replaced at startup by pick_family()
PREFERRED_FAMILIES = ("Inter", "Cantarell", "Noto Sans", "DejaVu Sans")


def pick_family(root):
    """Nicest installed UI font (fallback: Tk's generic "Sans")."""
    return next((f for f in PREFERRED_FAMILIES if f in tkfont.families(root)), "Sans")


def font(size, weight="normal"):
    return (FAMILY, size, weight)


# LED theme names shown in the UI (protocol values: see ultimate2.protocol.THEMES)
THEME_NAMES = {2: "Dinâmico", 3: "Roda", 4: "Personalizado", 5: "Desligado"}

# controller skins: body gradient (top, middle, bottom) and (fill, outline, label) per button role
SKINS = {
    "dark": dict(name="Preto", glow="#4b2f9a", body=("#2c2c2c", "#232323", "#1a1a1a"), line="#6a6a6a", well="#161616", emblem=None,
                 led_off="#3a3a3a", btn=("#2e2e2e", "#808080", FG), face=("#2e2e2e", "#808080", FG),
                 dpad=("#2e2e2e", "#808080", FG), stick=("#1e1e1e", "#5a5a5a", FG), shoulder=("#2e2e2e", "#808080", FG),
                 trigger=("#262626", "#6a6a6a", FG), home=("#2e2e2e", "#808080", FG)),
    # colours sampled from a photo of the edition: pale mauve-pink fading to dark mauve, white shoulders and
    # ABXY with red letters, black d-pad and sticks, dark red flower emblem
    "lilac": dict(name="Rosa", glow="#6a3a5e", body=("#e2d0de", "#ab97ab", "#6f5a73"), line="#5e4a62", well="#241b26", emblem="#b3122a",
                  led_off="#4a3a4e", btn=("#e6d9e2", "#9a8597", "#4a3550"), face=("#fdf9fb", "#c4afbd", "#a3122a"),
                  dpad=("#2c2c30", "#46464c", FG), stick=("#2a2a2e", "#46464c", FG),
                  shoulder=("#f7f2f5", "#c3b1bd", "#4a3550"), trigger=("#ece3e9", "#b6a2b1", "#4a3550"),
                  home=("#f3eef1", "#6e0f1d", FG)),
}
# controller edition (the app's m_ControllerColor) -> skin; 3 is the lilac edition with red stick rings
EDITION_SKINS = {3: "lilac"}
