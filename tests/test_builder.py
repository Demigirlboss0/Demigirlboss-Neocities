import unittest
import datetime
from pathlib import Path
from site_builder.parser import ContentParser
from site_builder.renderer import SiteRenderer, ParsedContent

class TestContentParser(unittest.TestCase):
    def setUp(self):
        self.parser = ContentParser()

    def test_resolve_internal_links(self):
        """Test that .md links are correctly converted to .html with fragments and slugification."""
        html = '<a href="Test Page.md">Link</a> and <a href="sub/Page Two.md#section?q=1">Link 2</a>'
        expected = '<a href="test-page.html">Link</a> and <a href="sub/page-two.html#section?q=1">Link 2</a>'
        self.assertEqual(self.parser._resolve_internal_links(html), expected)

    def test_parse_date(self):
        """Test various date formats and fallback."""
        test_path = Path("test.md")
        self.assertEqual(self.parser._parse_date("2025-01-01", test_path), datetime.date(2025, 1, 1))
        self.assertEqual(self.parser._parse_date("January 01, 2025", test_path), datetime.date(2025, 1, 1))
        
    def test_generate_url(self):
        """Test URL generation logic with slugification."""
        # Custom override
        self.assertEqual(self.parser._generate_url(Path("content/test.md"), "test", {"url": "/custom.html"}), "/custom.html")
        # Standard slugification
        self.assertEqual(self.parser._generate_url(Path("content/My Post.md"), "My Post", {}), "/my-post.html")

class TestSiteRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = SiteRenderer()

    def test_base_path_calculation(self):
        """Test that base_path is correctly calculated for different depths."""
        mock_content = ParsedContent(
            title="Test", description="SEO", date=datetime.date.today(), date_display="",
            iso_date="2026-02-19T12:00:00Z",
            published_date="2026-02-19T12:00:00Z",
            slug="post", content="", raw_content="", metadata={},
            category="Test", topic=None, url="/blog/post.html"
        )
        
        url_parts = [p for p in mock_content.url.split('/') if p]
        depth = len(url_parts) - 1
        base_path = '../' * depth if depth > 0 else './'
        self.assertEqual(base_path, "../")

        root_content = ParsedContent(
            title="Test", description="SEO", date=datetime.date.today(), date_display="",
            iso_date="2026-02-19T12:00:00Z",
            published_date="2026-02-19T12:00:00Z",
            slug="index", content="", raw_content="", metadata={},
            category="Test", topic=None, url="/index.html"
        )
        url_parts = [p for p in root_content.url.split('/') if p]
        depth = len(url_parts) - 1
        base_path = '../' * depth if depth > 0 else './'
        self.assertEqual(base_path, "./")

if __name__ == '__main__':
    unittest.main()
