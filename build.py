import shutil
from pathlib import Path
from typing import List, Dict, Any

from site_builder import (
    CONTENT_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATES_DIR,
    ContentParser, SiteRenderer, ParsedContent, logger
)

class SiteBuilder:
    def __init__(self):
        self.parser = ContentParser()
        self.renderer = SiteRenderer()
        self.all_content: List[ParsedContent] = []

    def clean_output(self):
        """Prepares the output directory."""
        if OUTPUT_DIR.exists():
            logger.info(f"Cleaning output directory: {OUTPUT_DIR}")
            shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def copy_static(self):
        """Copies static assets and the global stylesheet."""
        logger.info("Copying static assets...")
        
        # Copy global style.css from root if it exists
        style_css = Path("style.css")
        if style_css.exists():
            shutil.copy(style_css, OUTPUT_DIR / "style.css")
        
        # Copy the static folder
        if STATIC_DIR.exists():
            shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static", dirs_exist_ok=True)

    def crawl_content(self):
        """Finds and parses all markdown files in the content directory."""
        logger.info(f"Crawling content in: {CONTENT_DIR}")
        for md_file in CONTENT_DIR.rglob("*.md"):
            if md_file.name.endswith(".bak"):  # Ignore backup files
                continue
            try:
                parsed = self.parser.parse_file(md_file)
                self.all_content.append(parsed)
            except Exception as e:
                logger.error(f"Skipping {md_file} due to error: {e}")

    def get_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns a list of recent content for the sidebar."""
        sorted_content = sorted(
            self.all_content, 
            key=lambda x: x.date, 
            reverse=True
        )
        return [
            {
                'title': c.title,
                'url': c.url,
                'date_display': c.date_display,
                'category': c.category
            } for c in sorted_content[:limit]
        ]

    def build(self):
        """Orchestrates the full site build."""
        self.clean_output()
        self.copy_static()
        self.crawl_content()

        updates = self.get_updates()

        # Build individual pages
        for content in self.all_content:
            # Determine template based on content type
            template = 'base.html'
            if 'portfolio' in str(content.url):
                template = 'portfolio-item.html'
            
            # Map the URL to an actual file path in output/
            # Remove leading slash and handle index files
            rel_url = content.url.lstrip('/')
            output_file = OUTPUT_DIR / rel_url
            output_file.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Building: {content.url} -> {output_file}")
            
            html = self.renderer.render_page(
                content=content,
                template_name=template,
                updates=updates
            )
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)

        # Build Special Index Pages
        self.build_portfolio_index(updates)
        # (Optional: Add blog index or others here)

        logger.info("Build Complete! ✨")

    def build_portfolio_index(self, updates):
        """Generates the main portfolio listing page."""
        portfolio_items = [
            c for c in self.all_content if 'portfolio' in str(c.url) and c.slug != 'index'
        ]
        portfolio_items.sort(key=lambda x: x.date, reverse=True)

        # Create a dummy ParsedContent for the index itself if one doesn't exist
        # Or look for content/portfolio/index.md
        portfolio_index_md = CONTENT_DIR / "portfolio" / "index.md"
        if portfolio_index_md.exists():
            content_obj = self.parser.parse_file(portfolio_index_md)
        else:
            # Fallback if no index.md exists
            from datetime import date
            content_obj = ParsedContent(
                title="Portfolio",
                date=date.today(),
                date_display="",
                slug="index",
                content="",
                raw_content="",
                metadata={},
                category="Portfolio",
                url="/portfolio/index.html"
            )

        html = self.renderer.render_page(
            content=content_obj,
            template_name='portfolio.html',
            updates=updates,
            portfolio_items=portfolio_items
        )
        
        output_path = OUTPUT_DIR / "portfolio" / "index.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

if __name__ == "__main__":
    builder = SiteBuilder()
    builder.build()
