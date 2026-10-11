"""Static-site accessibility and privacy regression checks (not legal certification)."""
from __future__ import annotations

import unittest
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[dict[str, str]] = []
        self.navs: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: (value or "") for key, value in attrs}
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "a":
            self.links.append(values)
        if tag == "nav":
            self.navs.append(values)
        if tag == "img":
            self.images.append(values)


class StaticSiteReleaseBaselineTests(unittest.TestCase):
    def test_all_pages_have_skip_link_and_named_navigation(self) -> None:
        for path in (SITE / "index.html", SITE / "privacy/index.html", SITE / "terms/index.html", SITE / "support/index.html"):
            with self.subTest(page=str(path)):
                parser = PageParser()
                parser.feed(path.read_text(encoding="utf-8"))
                self.assertIn("main-content", parser.ids)
                self.assertTrue(any(link.get("href") == "#main-content" for link in parser.links))
                self.assertTrue(any(nav.get("aria-label") == "Primary" for nav in parser.navs))
                self.assertTrue(all("alt" in image for image in parser.images))
                self.assertTrue(any(link.get("href") == "/support/" for link in parser.links))

    def test_mobile_navigation_stays_available(self) -> None:
        styles = (SITE / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".nav nav { width: 100%", styles)
        self.assertNotIn("nav { display: none; }", styles)
        self.assertIn(":focus-visible", styles)
        self.assertIn("prefers-reduced-motion", styles)

    def test_privacy_requests_not_collected_in_public_issues(self) -> None:
        privacy = (SITE / "privacy/index.html").read_text(encoding="utf-8")
        self.assertIn("Do not post names, contact details", privacy)
        self.assertIn('href="mailto:richb.linardi@gmail.com"', privacy)
        self.assertIn("Richie Bertrand Linardi", privacy)
        self.assertIn("Do not send passwords, OAuth tokens", privacy)
        terms = (SITE / "terms/index.html").read_text(encoding="utf-8")
        self.assertIn('href="mailto:richb.linardi@gmail.com"', terms)


    def test_support_links_and_private_contact(self) -> None:
        """Direct all primary support navigation to a private contact page."""
        for path in (SITE / "index.html", SITE / "privacy/index.html", SITE / "terms/index.html", SITE / "support/index.html"):
            with self.subTest(page=str(path)):
                content = path.read_text(encoding="utf-8")
                self.assertIn('href="/support/"', content.split("<footer>", 1)[1])
                self.assertNotIn('href="https://github.com/Linardi1328/rbl-content-engine/issues">Support</a>', content)

        support = (SITE / "support/index.html").read_text(encoding="utf-8")
        self.assertIn("<h1>Support</h1>", support)
        self.assertIn('href="mailto:richb.linardi@gmail.com"', support)
        self.assertIn("richb.linardi@gmail.com</a>", support)
        self.assertIn('href="https://github.com/Linardi1328/rbl-content-engine/issues"', support)
        self.assertIn("GitHub Issues are public", support)
        self.assertIn("Never post personal or private information", support)
        self.assertIn('href="/privacy/"', support)
        self.assertNotIn("<form", support)
        self.assertNotIn("<script", support)
        self.assertNotIn("href=\"tel:", support)


if __name__ == "__main__":
    unittest.main()
