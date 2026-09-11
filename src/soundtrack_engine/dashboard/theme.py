"""Per-stage accent colors, drawn from the same dark/gold palette used by the
other personal apps (checklist, lift-log) — so a stage's color stays the same
between the duration editor and a generated playlist's track list, making the
progression's stages scannable at a glance.
"""

from __future__ import annotations

STAGE_PALETTE = [
    "#D4A24C",  # gold
    "#7A8C4C",  # olive
    "#4C6A73",  # teal
    "#B5544A",  # red/rust
    "#8C6A9C",  # plum
]


def stage_colors_for(stage_ids: list[str]) -> dict[str, str]:
    """Map each stage id to a color, cycling through the palette in stage order."""
    return {stage_id: STAGE_PALETTE[i % len(STAGE_PALETTE)] for i, stage_id in enumerate(stage_ids)}
