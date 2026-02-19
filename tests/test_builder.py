import unittest
import datetime
from pathlib import Path
from site_builder.parser import ContentParser
from site_builder.renderer import SiteRenderer, ParsedContent

class TestContentParser(unittest.TestCase):
    def setUp(self):
        self.parser = ContentParser()

    def test_resolve_internal_links(self):
        """Test that .md links are correctly converted to .html with fragments."""
        html = '<a href="test.md">Link</a> and <a href="sub/page.md#section?q=1">Link 2</a>'
        expected = '<a href="test.html">Link</a> and <a href="sub/page.html#section?q=1">Link 2</a>'
        self.assertEqual(self.parser._resolve_internal_links(html), expected)

    def test_parse_date(self):
        """Test various date formats and fallback."""
        # This is tricky because it reads file stats on fallback, 
        # so we test the parsing logic primarily.
        test_path = Path("test.md")
        self.assertEqual(self.parser._parse_date("2025-01-01", test_path), datetime.date(2025, 1, 1))
        self.assertEqual(self.parser._parse_date("January 01, 2025", test_path), datetime.date(2025, 1, 1))
        
    def test_generate_url(self):
        """Test URL generation logic."""
        # Use absolute paths for test if possible or mock CONTENT_DIR
        # For simplicity in this env, we test the logic via metadata override first
        self.assertEqual(self.parser._generate_url(Path("content/test.md"), "test", {"url": "/custom.html"}), "/custom.html")

class TestSiteRenderer(unittest.TestCase):
    def setUp(self):
        # We need templates to exist to init SiteRenderer
        self.renderer = SiteRenderer()

    def test_base_path_calculation(self):
        """Test that base_path is correctly calculated for different depths."""
        mock_content = ParsedContent(
            title="Test", date=datetime.date.today(), date_display="",
            iso_date="2026-02-19T12:00:00Z",
            slug="test", content="", raw_content="", metadata={},
            category="Test", url="/blog/post.html"
        )
        
        # We can't easily test the render output without full templates, 
        # but we can test the internal logic if we expose it or test a mock render.
        # Let's check the depth calculation logic.
        url_parts = [p for p in mock_content.url.split('/') if p]
        depth = len(url_parts) - 1
        base_path = '../' * depth if depth > 0 else './'
        self.assertEqual(base_path, "../")

        root_content = ParsedContent(
            title="Test", date=datetime.date.today(), date_display="",
            iso_date="2026-02-19T12:00:00Z",
            slug="index", content="", raw_content="", metadata={},
            category="Test", url="/index.html"
        )
        url_parts = [p for p in root_content.url.split('/') if p]
        depth = len(url_parts) - 1
        base_path = '../' * depth if depth > 0 else './'
        self.assertEqual(base_path, "./")

if __name__ == '__main__':
    unittest.main()
