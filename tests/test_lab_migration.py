from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REDIRECTS = {
    "useful.html": "https://lab.ugatta-llc.com/",
    "dx-diagnosis.html": "https://lab.ugatta-llc.com/dx-diagnosis.html",
    "inbound-analysis.html": "https://lab.ugatta-llc.com/inbound-analysis.html",
    "report.html": "https://lab.ugatta-llc.com/report.html",
}
SHELL_PAGES = (
    "index.html",
    "services.html",
    "about.html",
    "ugatta_case_studies.html",
    "contact.html",
    "404.html",
)
REMOVED_FILES = (
    ".github/workflows/update-inbound-data.yml",
    "scripts/update_inbound_data.py",
    "scripts/generate_inbound_insights.py",
    "data/inbound/latest.json",
    "data/inbound/metadata.json",
    "data/inbound/insights.json",
    "js/inbound-analysis.js",
    "css/inbound-analysis.css",
    "tests/test_inbound_data.py",
    "requirements.txt",
)


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, object]] = []
        self._current: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._current = {"attrs": dict(attrs), "text": []}
            self.links.append(self._current)

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            text = self._current["text"]
            assert isinstance(text, list)
            text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._current = None


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def anchors(content: str) -> list[dict[str, object]]:
    parser = AnchorParser()
    parser.feed(content)
    return parser.links


def link_text(link: dict[str, object]) -> str:
    text = link["text"]
    assert isinstance(text, list)
    return "".join(str(part) for part in text).strip()


class LabMigrationTests(unittest.TestCase):
    def test_redirect_stubs(self) -> None:
        for filename, target in REDIRECTS.items():
            with self.subTest(filename=filename):
                content = read(filename)
                canonical = re.search(r'<link rel="canonical" href="([^"]+)">', content)
                refresh = re.search(r'<meta http-equiv="refresh" content="0; url=([^"]+)">', content)
                replace = re.search(r'location\.replace\("([^"]+)"\)', content)
                self.assertEqual(canonical.group(1) if canonical else None, target)
                self.assertEqual(refresh.group(1) if refresh else None, target)
                self.assertEqual(replace.group(1) if replace else None, target)
                self.assertNotIn("noindex", content.lower())
                self.assertNotIn("googletagmanager", content.lower())

    def test_nav_and_footer_point_to_lab(self) -> None:
        for filename in SHELL_PAGES:
            with self.subTest(filename=filename):
                content = read(filename)
                self.assertNotIn('href="useful.html"', content)
                self.assertNotIn("観光DX無料ツール", content)
                lab_links = [
                    link
                    for link in anchors(content)
                    if link["attrs"].get("href") == "https://lab.ugatta-llc.com/"
                    and link_text(link) == "宿泊DXラボ"
                ]
                self.assertGreaterEqual(len(lab_links), 2)

    def test_lab_links_are_tracked(self) -> None:
        for path in ROOT.rglob("*.html"):
            if path.name in REDIRECTS and path.parent == ROOT:
                continue
            for link in anchors(path.read_text(encoding="utf-8")):
                attrs = link["attrs"]
                if attrs.get("href") == "https://lab.ugatta-llc.com/":
                    with self.subTest(path=path.relative_to(ROOT), text=link_text(link)):
                        self.assertEqual(attrs.get("data-analytics-event"), "lab_click")
                        self.assertNotIn("target", attrs)
                        self.assertNotIn("utm_", str(attrs.get("href")))

    def test_index_tool_section(self) -> None:
        content = read("index.html")
        match = re.search(
            r'<section class="section tool-section">(.*?)</section>',
            content,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        section = match.group(1)
        self.assertIn("宿泊DXラボ", section)
        self.assertIn("宿泊・観光事業者向けにの", section)
        self.assertIn("お役立ちツールは宿泊DXラボで", section)
        self.assertIn("実験的に公開しています。", section)
        button = [
            link
            for link in anchors(section)
            if link["attrs"].get("href") == "https://lab.ugatta-llc.com/"
        ]
        self.assertEqual(len(button), 1)
        self.assertEqual(button[0]["attrs"].get("data-analytics-event"), "lab_click")
        self.assertIn("宿泊DXラボを見る", link_text(button[0]))

    def test_sitemap(self) -> None:
        content = read("sitemap.xml")
        for old_path in ("useful.html", "dx-diagnosis.html", "inbound-analysis.html"):
            self.assertNotIn(old_path, content)
        root = ET.fromstring(content)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall("sm:url/sm:loc", namespace):
            url_path = urlparse(loc.text or "").path
            relative = "index.html" if url_path in ("", "/") else url_path.lstrip("/")
            with self.subTest(url=loc.text):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_llms_txt(self) -> None:
        content = read("llms.txt")
        self.assertNotIn("useful.html", content)
        self.assertNotIn("dx-diagnosis.html", content)
        self.assertNotIn("inbound-analysis.html", content)
        self.assertIn("https://lab.ugatta-llc.com/", content)

    def test_removed_files(self) -> None:
        for relative in REMOVED_FILES:
            with self.subTest(relative=relative):
                self.assertFalse((ROOT / relative).exists())


if __name__ == "__main__":
    unittest.main()
