"""Per-stage accent colors, drawn from the same dark/gold palette used by the
other personal apps (checklist, lift-log) — so a stage's color stays the same
between the duration editor and a generated playlist's track list, making the
progression's stages scannable at a glance.
"""

from __future__ import annotations

from soundtrack_engine.publish import UNKNOWN_STAGE_ID

STAGE_PALETTE = [
    "#D4A24C",  # gold
    "#7A8C4C",  # olive
    "#4C6A73",  # teal
    "#B5544A",  # red/rust
    "#8C6A9C",  # plum
]

UNKNOWN_STAGE_COLOR = "#6E80A8"  # muted2 — reads as neutral, not a "real" stage


def stage_colors_for(stage_ids: list[str]) -> dict[str, str]:
    """Map each stage id to a color, cycling through the palette in stage order.
    Always includes UNKNOWN_STAGE_ID so callers can look it up unconditionally.
    """
    colors = {stage_id: STAGE_PALETTE[i % len(STAGE_PALETTE)] for i, stage_id in enumerate(stage_ids)}
    colors[UNKNOWN_STAGE_ID] = UNKNOWN_STAGE_COLOR
    return colors
