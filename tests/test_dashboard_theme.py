from soundtrack_engine.dashboard.theme import (
    STAGE_PALETTE,
    UNKNOWN_STAGE_COLOR,
    UNKNOWN_STAGE_ID,
    stage_colors_for,
)


def test_each_stage_gets_a_distinct_color_up_to_palette_size() -> None:
    colors = stage_colors_for(["a", "b", "c", "d", "e"])

    assert len(set(colors[k] for k in ["a", "b", "c", "d", "e"])) == 5
    assert list(colors.keys())[:5] == ["a", "b", "c", "d", "e"]


def test_colors_cycle_when_more_stages_than_palette_entries() -> None:
    stage_ids = [f"stage_{i}" for i in range(len(STAGE_PALETTE) + 2)]

    colors = stage_colors_for(stage_ids)

    assert colors[stage_ids[0]] == colors[stage_ids[len(STAGE_PALETTE)]]


def test_same_stage_id_gets_same_color_across_calls() -> None:
    first = stage_colors_for(["wake", "groove"])
    second = stage_colors_for(["wake", "groove"])

    assert first == second


def test_unknown_stage_always_present_with_neutral_color() -> None:
    colors = stage_colors_for(["wake"])

    assert colors[UNKNOWN_STAGE_ID] == UNKNOWN_STAGE_COLOR
    assert UNKNOWN_STAGE_COLOR not in STAGE_PALETTE
