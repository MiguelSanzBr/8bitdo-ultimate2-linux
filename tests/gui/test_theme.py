"""theme (fonts, skins) plus sanity checks of the constant tables in catalog and geometry."""
import pytest

from ultimate2.gui import catalog, geometry, theme


@pytest.mark.parametrize("families,expected", [([], "Sans"), (["Foo", "Noto Sans", "Cantarell"], "Cantarell"),
                                               (["DejaVu Sans", "Inter"], "Inter")])
def test_pick_family(monkeypatch, families, expected):
    monkeypatch.setattr(theme.tkfont, "families", lambda root=None: families)
    assert theme.pick_family(None) == expected


def test_font(monkeypatch):
    monkeypatch.setattr(theme, "FAMILY", "Foo")
    assert theme.font(10) == ("Foo", 10, "normal")
    assert theme.font(9, "bold") == ("Foo", 9, "bold")


def test_skins_are_complete():
    roles = set(geometry.ROLES.values()) | {"btn"}
    for name in theme.EDITION_SKINS.values():
        assert name in theme.SKINS
    for sk in theme.SKINS.values():
        assert roles <= set(sk) and len(sk["body"]) == 3
    assert theme.SKINS["dark"]["emblem"] is None and theme.SKINS["lilac"]["emblem"]
    assert set(theme.THEME_NAMES) == {2, 3, 4, 5}


def test_catalog():
    assert [k for _, k in catalog.SECTIONS][0] == "buttons" and "None" in catalog.KEY_NAMES
    assert "P3" in catalog.KEY_NAMES and catalog.DISPLAY == {"P1": "PR", "P2": "PL", "P3": "L4", "P4": "R4"}
    assert set(catalog.GYRO_KEYS) == {"LT", "RT", "LB", "RB", "L3", "R3"}
    assert {t for _, _, t in catalog.LED_TARGETS} == {2, 3, 4}


def test_geometry_parts_fit_the_box():
    assert set(geometry.BEHIND) <= set(geometry.PARTS) and set(geometry.ROLES) <= set(geometry.PARTS)
    for pts in (geometry.BODY, geometry.LB_PTS, geometry.LT_PTS):
        assert all(0 <= x <= geometry.WIDTH and 0 <= y <= geometry.HEIGHT for x, y in pts)
    assert all(target in geometry.PARTS or target == "sticks" for *_, target in geometry.CALLOUTS)
    assert all(12 <= y <= geometry.HEIGHT - 12 for _t, _s, y, *_ in geometry.CALLOUTS)   # 22-unit cards + outline fit
