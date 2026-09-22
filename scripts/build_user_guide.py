"""Synchronize the Markdown user guide into the packaged docs page.

Run from any directory; --check exits nonzero if regeneration is needed.
markdown-it-py is installed with Bamboo's Rich dependency.
"""

from __future__ import annotations

import argparse
import re
from html import escape
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/user-guide.md"
TARGET = ROOT / "bamboo/adapters/web/static/docs.html"


def render(page: str, source: str) -> str:
    renderer = MarkdownIt("commonmark").enable("table")
    parts = re.split(r'^<a id="([a-z0-9-]+)"></a>\n\n## (.+)$', source, flags=re.M)
    if len(parts) < 4:
        raise ValueError("Guide must contain anchored level-two headings")
    navigation = ['<div class="toc-group">使用指南</div>']
    sections = []
    ids = set()
    for offset in range(1, len(parts), 3):
        anchor, title, body = parts[offset:offset + 3]
        if anchor in ids:
            raise ValueError(f"Duplicate guide anchor: {anchor}")
        ids.add(anchor)
        navigation.append(f'<a href="#{anchor}">{escape(title)}</a>')
        sections.append(
            f'<section id="{anchor}">\n<h2>{escape(title)}</h2>\n'
            f'{renderer.render(body.strip())}</section>'
        )
    for name, content in (("NAV", "\n".join(navigation)), ("CONTENT", "\n".join(sections))):
        pattern = rf"<!-- USER GUIDE {name} START -->.*?<!-- USER GUIDE {name} END -->"
        replacement = f"<!-- USER GUIDE {name} START -->\n{content}\n<!-- USER GUIDE {name} END -->"
        page, count = re.subn(pattern, lambda _: replacement, page, flags=re.S)
        if count != 1:
            raise ValueError(f"Expected exactly one {name} marker pair")
    return page


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original = TARGET.read_text(encoding="utf-8")
    rendered = render(original, SOURCE.read_text(encoding="utf-8"))
    if args.check:
        if original != rendered:
            raise SystemExit("Docs are stale: run python scripts/build_user_guide.py")
        print("User guide and packaged HTML are in sync.")
    else:
        TARGET.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Updated {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
