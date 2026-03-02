import shutil
import os
import requests
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from site_builder import (
    CONTENT_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATES_DIR, SITE_URL, SITE_TITLE,
    ContentParser, SiteRenderer, ParsedContent, logger
)

# Load environment variables (API Key)
load_dotenv()

class SiteBuilder:
    def __init__(self):
        self.parser = ContentParser()
        self.renderer = SiteRenderer()
        self.all_content: List[ParsedContent] = []

    def generate_feed(self):
        """Generates a strictly compliant Atom XML feed (V5)."""
        logger.info("Generating Atom feed (V5 - Chronological)...")
        
        # 1. Gather all non-index content
        feed_items = [c for c in self.all_content if c.slug != 'index']
        
        if not feed_items:
            return

        # 2. Sort by iso_date (last-modified time) descending
        # This ensures the newest updates are always at the top of the XML
        feed_items.sort(key=lambda x: x.iso_date, reverse=True)
        feed_items = feed_items[:20]

        # 3. Feed-level 'updated' is the date of the most recently updated item
        last_updated = feed_items[0].iso_date

        context = {
            'site_title': SITE_TITLE,
            'site_url': SITE_URL,
            'last_updated': last_updated,
            'items': feed_items
        }

        xml_output = self.renderer.render('atom.xml', context)
        
        with open(OUTPUT_DIR / "atom.xml", "w", encoding="utf-8") as f:
            f.write(xml_output)
        logger.info(f"Feed V5 generated at {OUTPUT_DIR}/atom.xml")

    def clean_output(self):
        """Prepares the output directory."""
        if OUTPUT_DIR.exists():
            logger.info(f"Cleaning output directory: {OUTPUT_DIR}")
            shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def copy_static(self):
        """Copies static assets from both root/static and content/static."""
        logger.info("Synchronizing static assets...")
        style_css = Path("style.css")
        if style_css.exists():
            shutil.copy(style_css, OUTPUT_DIR / "style.css")
        if STATIC_DIR.exists():
            shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static", dirs_exist_ok=True)
        content_static = CONTENT_DIR / "static"
        if content_static.exists():
            logger.info("Merging content/static into output...")
            shutil.copytree(content_static, OUTPUT_DIR / "static", dirs_exist_ok=True)

    def deploy(self):
        """Deploys the output directory directly to Neocities via the API."""
        api_key = os.getenv("NEOCITIES_API_KEY")
        if not api_key:
            logger.error("NEOCITIES_API_KEY not found in .env file!")
            return

        logger.info("🚀 Initiating deployment to Neocities...")
        url = "https://neocities.org/api/upload"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            files_to_upload = {}
            opened_files = []
            for root, _, files in os.walk(OUTPUT_DIR):
                for file in files:
                    local_path = Path(root) / file
                    remote_path = local_path.relative_to(OUTPUT_DIR)
                    f = open(local_path, 'rb')
                    opened_files.append(f)
                    files_to_upload[str(remote_path)] = f

            if not files_to_upload:
                logger.info("No files to upload.")
                return

            logger.info(f"Syncing {len(files_to_upload)} files...")
            response = requests.post(url, headers=headers, files=files_to_upload)
            for f in opened_files:
                f.close()

            if response.status_code == 200:
                result = response.json()
                if result.get("result") == "success":
                    logger.info("✅ Deployment successful!")
                else:
                    logger.error(f"❌ Deployment failed: {result.get('message')}")
            else:
                logger.error(f"❌ Deployment failed with status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"❌ Deployment error: {e}")

    def crawl_content(self):
        """Finds and parses all markdown files in the content directory."""
        logger.info(f"Crawling content in: {CONTENT_DIR}")
        for md_file in CONTENT_DIR.rglob("*.md"):
            if md_file.name.endswith(".bak"):
                continue
            try:
                parsed = self.parser.parse_file(md_file)
                self.all_content.append(parsed)
            except Exception as e:
                logger.error(f"Skipping {md_file} due to error: {e}")

    def get_updates(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns a list of recent content for the sidebar."""
        content_items = [c for c in self.all_content if c.slug != 'index']
        sorted_content = sorted(content_items, key=lambda x: x.date, reverse=True)
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

        for content in self.all_content:
            if content.slug == 'index':
                continue
            template = 'base.html'
            if 'portfolio' in str(content.url):
                template = 'portfolio-item.html'
            
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

        self.build_index_page('portfolio', 'portfolio.html', updates)
        self.build_index_page('wiki', 'wiki.html', updates)
        self.build_index_page('blog', 'blog.html', updates)
        
        root_index = next((c for c in self.all_content if c.slug == 'index' and c.url == '/index.html'), None)
        if root_index:
            html = self.renderer.render_page(content=root_index, updates=updates)
            with open(OUTPUT_DIR / "index.html", 'w', encoding='utf-8') as f:
                f.write(html)

        self.generate_feed()
        logger.info("Build Complete! ✨")

    def build_index_page(self, folder_name: str, template: str, updates: List[Dict[str, Any]]):
        """Generic builder for section index pages."""
        index_url = f"/{folder_name.lower()}/index.html"
        index_content = next((c for c in self.all_content if c.url == index_url), None)
        
        if not index_content:
            logger.warning(f"No index.md found for /{folder_name}/")
            return

        extra_context = {}
        if folder_name.lower() == 'portfolio':
            items = [c for c in self.all_content if 'portfolio' in str(c.url) and c.slug != 'index']
            extra_context['portfolio_items'] = sorted(items, key=lambda x: x.date, reverse=True)
        elif folder_name.lower() == 'wiki':
            items = [c for c in self.all_content if 'wiki' in str(c.url) and c.slug != 'index']
            topics = {}
            for item in items:
                t = item.topic or "Uncategorized"
                if t not in topics: topics[t] = []
                topics[t].append(item)
            
            extra_context['topics'] = [
                {'name': name, 'articles': sorted(items, key=lambda x: x.date, reverse=True)}
                for name in sorted(topics.keys())
            ]
        elif folder_name.lower() == 'blog':
            items = [c for c in self.all_content if 'blog' in str(c.url) and c.slug != 'index']
            extra_context['posts'] = sorted(items, key=lambda x: x.date, reverse=True)

        html = self.renderer.render_page(
            content=index_content,
            template_name=template,
            updates=updates,
            **extra_context
        )
        
        output_path = OUTPUT_DIR / folder_name.lower() / "index.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

if __name__ == "__main__":
    import sys
    builder = SiteBuilder()
    builder.build()
    if "--deploy" in sys.argv:
        builder.deploy()
