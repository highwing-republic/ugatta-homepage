"""Protect the homepage's public content, destinations and image loading contract."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Elements(HTMLParser):
    def __init__(self, filename):
        super().__init__()
        self.items = []
        self.feed((ROOT / filename).read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))

    def tagged(self, tag):
        return [attrs for name, attrs in self.items if name == tag]


class HomeRedesignTests(unittest.TestCase):
    def setUp(self):
        self.home = Elements("index.html")

    def test_all_four_service_destinations_exist(self):
        links = {a.get("href") for a in self.home.tagged("a")}
        ids = {attrs.get("id") for _, attrs in Elements("services.html").items}
        for anchor in ("dx", "training", "business", "marketing"):
            with self.subTest(anchor=anchor):
                self.assertIn(f"services.html#{anchor}", links)
                self.assertIn(anchor, ids)

    def test_only_two_published_case_destinations(self):
        links = {a.get("href") for a in self.home.tagged("a")}
        case_links = {link for link in links if link and link.startswith("ugatta_case_studies.html#")}
        self.assertEqual(case_links, {"ugatta_case_studies.html#case-dx", "ugatta_case_studies.html#case-inbound"})
        ids = {attrs.get("id") for _, attrs in Elements("ugatta_case_studies.html").items}
        for link in case_links:
            self.assertIn(urlsplit(link).fragment, ids)

    def test_images_have_dimensions_and_real_local_sources(self):
        images = self.home.tagged("img")
        self.assertGreater(len(images), 0)
        for img in images:
            with self.subTest(src=img.get("src")):
                self.assertIn("alt", img)
                self.assertGreater(int(img["width"]), 0)
                self.assertGreater(int(img["height"]), 0)
                self.assertTrue((ROOT / img["src"]).is_file())
        for source in self.home.tagged("source"):
            for candidate in source["srcset"].split(","):
                self.assertTrue((ROOT / candidate.strip().split()[0]).is_file())

    def test_hero_is_prioritized_and_below_fold_images_are_lazy(self):
        images = self.home.tagged("img")
        heroes = [img for img in images if img.get("fetchpriority") == "high"]
        self.assertEqual(len(heroes), 1)
        self.assertNotEqual(heroes[0].get("loading"), "lazy")
        for img in images:
            if img.get("src") == "images/brand/ugatta-noren-mark-256.png":
                self.assertNotEqual(img.get("loading"), "lazy")
            elif img not in heroes:
                self.assertEqual(img.get("loading"), "lazy")
        self.assertEqual(heroes[0]["src"], "images/brand/ugatta-noren-hero.png")
        self.assertTrue(heroes[0]["alt"].strip())
        self.assertTrue(any("images/brand/ugatta-noren-hero.webp 1000w" in s.get("srcset", "")
                            and s.get("type") == "image/webp"
                            for s in self.home.tagged("source")))

    def test_home_retains_three_faqs_and_one_primary_heading(self):
        self.assertEqual(len(self.home.tagged("h1")), 1)
        self.assertEqual(len(self.home.tagged("details")), 3)
        self.assertEqual(len(self.home.tagged("summary")), 3)

    def test_contact_attribution_is_preserved(self):
        ctas = [a for a in self.home.tagged("a") if a.get("data-analytics-event") == "contact_page_click"]
        self.assertEqual(len(ctas), 3)
        for cta in ctas:
            self.assertEqual(cta.get("href"), "contact.html")
            self.assertEqual(cta.get("data-contact-destination"), "contact_page")

    def test_real_semibold_font_and_home_styles_are_scoped(self):
        styles = [link.get("href", "") for link in self.home.tagged("link")]
        self.assertTrue(any("Shippori+Mincho:wght@500;600" in href for href in styles))
        self.assertTrue(any(href.startswith("css/home.css?") for href in styles))
        for filename in ("services.html", "about.html", "ugatta_case_studies.html", "contact.html", "404.html"):
            self.assertFalse(any(link.get("href", "").startswith("css/home.css") for link in Elements(filename).tagged("link")))

    def test_public_shell_uses_the_noren_header_brand(self):
        for filename in ("index.html", "services.html", "about.html", "ugatta_case_studies.html", "contact.html", "404.html"):
            with self.subTest(filename=filename):
                page = Elements(filename)
                images = page.tagged("img")
                sources = page.tagged("source")
                self.assertTrue(any(
                    image.get("src") == "images/brand/ugatta-noren-mark-256.png"
                    and image.get("width") == "256"
                    and image.get("height") == "187"
                    for image in images
                ))
                self.assertTrue(any(
                    source.get("srcset") == "images/brand/ugatta-noren-mark-256.webp"
                    and source.get("type") == "image/webp"
                    for source in sources
                ))


if __name__ == "__main__":
    unittest.main()
