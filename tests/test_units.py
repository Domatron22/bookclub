# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Small pure functions, and the things the pipeline should catch early."""
import pytest

from app.google_oauth import is_safe_next, safe_next
from app.rate_limit import check, reset
from app.recaps import personal_recap
from app.templating import assign_cover_colors, cover_colors, cover_src, numword, star_row
from app.version import __version__


# ---------------------------------------------------------------------------
# Redirect safety
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("target", [
    "//evil.example", "///evil.example", "https://evil.example",
    "http://evil.example/x", "javascript:alert(1)", "", None,
    "\\\\evil.example",
])
def test_hostile_redirect_targets_are_rejected(target):
    assert safe_next(target, "/fallback") == "/fallback"


@pytest.mark.parametrize("target", ["/", "/clubs/ABC123", "/books/1?x=2", "/a/b/c"])
def test_local_paths_are_accepted(target):
    assert safe_next(target, "/fallback") == target
    assert is_safe_next(target) is True


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_the_limiter_allows_then_blocks():
    reset()
    assert [check("k", 3, 60)[0] for _ in range(5)] == [True, True, True, False, False]


def test_a_rejected_attempt_is_not_recorded():
    """Otherwise someone hammering the endpoint extends their own lockout."""
    reset()
    for _ in range(3):
        check("k", 3, 60)
    _, first = check("k", 3, 60)
    _, second = check("k", 3, 60)
    assert second <= first


def test_keys_are_independent():
    reset()
    for _ in range(3):
        check("a", 3, 60)
    assert check("a", 3, 60)[0] is False
    assert check("b", 3, 60)[0] is True


# ---------------------------------------------------------------------------
# Covers
# ---------------------------------------------------------------------------

def test_cover_src_picks_a_variant_by_rendered_size():
    url = "https://covers.openlibrary.org/b/id/12345-M.jpg"
    assert "-L.jpg" in cover_src(url, 150)
    assert "-M.jpg" in cover_src(url, 50)
    assert "-S.jpg" in cover_src(url, 18)
    # default=false 404s a missing cover instead of serving a blank, so the
    # template can fall back to the placeholder.
    assert "default=false" in cover_src(url, 150)


def test_cover_src_leaves_foreign_urls_alone():
    assert cover_src("https://example.com/cover.png", 150) == "https://example.com/cover.png"
    assert cover_src(None) == ""
    assert cover_src("") == ""


def test_placeholder_colours_are_stable_and_persistable():
    class FakeBook:
        title, author, cover_bg, cover_fg = "Dune", "Herbert", None, None

    book = FakeBook()
    rendered = cover_colors(book)
    assign_cover_colors(book)
    assert rendered == {"bg": book.cover_bg, "fg": book.cover_fg}

    # Search results arrive as plain dicts, not Book rows.
    assert cover_colors({"title": "Dune", "author": "Herbert"}) == rendered


def test_assign_cover_colours_does_not_overwrite():
    class FakeBook:
        title, author = "Dune", "Herbert"
        cover_bg, cover_fg = "#111111", "#eeeeee"

    book = FakeBook()
    assign_cover_colors(book)
    assert (book.cover_bg, book.cover_fg) == ("#111111", "#eeeeee")


# ---------------------------------------------------------------------------
# Small template helpers
# ---------------------------------------------------------------------------

def test_star_row_survives_junk():
    assert sum(s["filled"] for s in star_row(4)) == 4
    assert sum(s["filled"] for s in star_row(None)) == 0
    assert sum(s["filled"] for s in star_row("nonsense")) == 0
    assert len(star_row(3)) == 5


def test_numword_spells_small_counts():
    assert numword(0) == "no"
    assert numword(3) == "three"
    assert numword(11) == "11"
    assert numword("x") == "x"


# ---------------------------------------------------------------------------
# Release plumbing — cheap guards that catch a botched version bump in CI
# ---------------------------------------------------------------------------

def test_the_version_is_a_release_number():
    parts = __version__.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), __version__


def test_package_json_agrees_with_version_py():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    package = json.loads((root / "package.json").read_text())
    lock = json.loads((root / "package-lock.json").read_text())

    assert package["version"] == __version__
    assert lock["version"] == __version__
    assert lock["packages"][""]["version"] == __version__


def test_the_changelog_documents_this_version():
    from pathlib import Path

    changelog = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text()
    assert f"## [{__version__}]" in changelog


def test_the_licence_is_stated_consistently():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    assert json.loads((root / "package.json").read_text())["license"] == "GPL-3.0-or-later"
    assert (root / "LICENSE").exists()

    # Every first-party source file should carry its SPDX header. The compiled
    # stylesheet is generated by Tailwind and is not checked in.
    sources = [
        p
        for pattern in ("app/**/*.py", "tests/*.py", "scripts/*.py", "scripts/*.js",
                        "migrations/**/*.py", "app/static/js/*.js", "app/static/css/*.css")
        for p in root.glob(pattern)
        if "__pycache__" not in str(p) and p.name != "tailwind.css"
    ]
    assert len(sources) > 30, f"glob found suspiciously few files: {len(sources)}"
    missing = [
        str(p.relative_to(root))
        for p in sources
        if "SPDX-License-Identifier" not in p.read_text()
    ]
    assert not missing, f"missing SPDX header: {missing}"


# ---------------------------------------------------------------------------
# Recaps
# ---------------------------------------------------------------------------

def test_a_recap_with_no_memberships_does_not_explode(db, make_user):
    recap = personal_recap(make_user("lonely"), db)
    assert recap["books_read"] == 0
    assert recap["top_books"] == []
