import shutil
import os
import requests
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from site_builder import (
    CONTENT_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATES_DIR, SITE_URL, SITE_TITLE,
    ContentParser, SiteRenderer, ParsedContent, logger,
    FEED_ENTRY_LIMIT, LATEST_UPDATES_LIMIT
)

# Load environment variables (API Key)
load_dotenv()

class SiteBuilder:
    def __init__(self):
        self.parser = ContentParser()
        self.renderer = SiteRenderer()
        self.all_content: List[ParsedContent] = []

    def generate_feed(self):
        """Generates an Atom XML feed without hardcoded limits."""
        logger.info("Generating Atom feed...")
        
        feed_items = sorted(
            [c for c in self.all_content if c.slug != 'index'],
            key=lambda x: x.date,
            reverse=True
        )[:FEED_ENTRY_LIMIT]

        if not feed_items:
            return

        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        processed_items = []
        for item in feed_items:
            processed_items.append({
                'title': item.title,
                'url': f"{SITE_URL}{item.url}",
                'id': f"{SITE_URL}{item.url}",
                'updated': item.iso_date,
                'published': item.published_date,
                'category': item.category,
                'date_display': item.date_display,
                'content': self.parser.make_links_absolute(item.content, SITE_URL)
            })

        context = {
            'site_title': SITE_TITLE,
            'site_url': SITE_URL,
            'feed_updated': now_iso,
            'items': processed_items
        }

        xml_output = self.renderer.render('atom.xml', context)
        with open(OUTPUT_DIR / "atom.xml", "w", encoding="utf-8") as f:
            f.write(xml_output)

    def clean_output(self):
        if OUTPUT_DIR.exists():
            logger.info(f"Cleaning: {OUTPUT_DIR}")
            shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def copy_static(self):
        logger.info("Syncing assets...")
        style_css = Path("style.css")
        if style_css.exists(): shutil.copy(style_css, OUTPUT_DIR / "style.css")
        if STATIC_DIR.exists(): shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static", dirs_exist_ok=True)
        content_static = CONTENT_DIR / "static"
        if content_static.exists(): shutil.copytree(content_static, OUTPUT_DIR / "static", dirs_exist_ok=True)

    def deploy(self):
        api_key = os.getenv("NEOCITIES_API_KEY")
        if not api_key:
            logger.error("NEOCITIES_API_KEY missing!")
            return

        logger.info("🚀 Deploying...")
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

            if files_to_upload:
                requests.post(url, headers=headers, files=files_to_upload)
            for f in opened_files: f.close()
            logger.info("✅ Deployed!")
        except Exception as e:
            logger.error(f"❌ Error: {e}")

    def crawl_content(self):
        logger.info(f"Crawling: {CONTENT_DIR}")
        for md_file in CONTENT_DIR.rglob("*.md"):
            if md_file.name.endswith(".bak"): continue
            try:
                self.all_content.append(self.parser.parse_file(md_file))
            except Exception as e:
                logger.error(f"Error parsing {md_file}: {e}")

    def get_updates(self, limit: int = LATEST_UPDATES_LIMIT) -> List[Dict[str, Any]]:
        items = [c for c in self.all_content if c.slug != 'index']
        sorted_content = sorted(items, key=lambda x: x.date, reverse=True)
        return [{'title': c.title, 'url': c.url, 'date_display': c.date_display, 'category': c.category} for c in sorted_content[:limit]]

    def build(self):
        self.clean_output()
        self.copy_static()
        self.crawl_content()
        updates = self.get_updates()

        for content in self.all_content:
            if content.slug == 'index': continue
            template = 'portfolio-item.html' if 'portfolio' in str(content.url) else 'base.html'
            rel_url = content.url.lstrip('/')
            output_file = OUTPUT_DIR / rel_url
            output_file.parent.mkdir(parents=True, exist_ok=True)
            html = self.renderer.render_page(content=content, template_name=template, updates=updates)
            with open(output_file, 'w', encoding='utf-8') as f: f.write(html)

        self.build_index_page('portfolio', 'portfolio.html', updates)
        self.build_index_page('wiki', 'wiki.html', updates)
        self.build_index_page('blog', 'blog.html', updates)
        
        root_index = next((c for c in self.all_content if c.slug == 'index' and c.url == '/index.html'), None)
        if root_index:
            html = self.renderer.render_page(content=root_index, updates=updates)
            with open(OUTPUT_DIR / "index.html", 'w', encoding='utf-8') as f: f.write(html)

        self.generate_feed()
        logger.info("Build Complete!")

    def build_index_page(self, folder_name: str, template: str, updates: List[Dict[str, Any]]):
        idx_url = f"/{folder_name.lower()}/index.html"
        idx_content = next((c for c in self.all_content if c.url == idx_url), None)
        if not idx_content: return

        ctx = {}
        if folder_name.lower() == 'portfolio':
            ctx['portfolio_items'] = sorted([c for c in self.all_content if 'portfolio' in str(c.url) and c.slug != 'index'], key=lambda x: x.date, reverse=True)
        elif folder_name.lower() == 'wiki':
            wiki_items = [c for c in self.all_content if 'wiki' in str(c.url) and c.slug != 'index']
            topics = {}
            for item in wiki_items:
                t = item.topic or DEFAULT_TOPIC
                if t not in topics: topics[t] = []
                topics[t].append(item)
            ctx['topics'] = [{'name': name, 'articles': sorted(items, key=lambda x: x.date, reverse=True)} for name, items in sorted(topics.items())]
        elif folder_name.lower() == 'blog':
            ctx['posts'] = sorted([c for c in self.all_content if 'blog' in str(c.url) and c.slug != 'index'], key=lambda x: x.date, reverse=True)

        html = self.renderer.render_page(content=idx_content, template_name=template, updates=updates, **ctx)
        out = OUTPUT_DIR / folder_name.lower() / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f: f.write(html)

if __name__ == "__main__":
    import sys
    builder = SiteBuilder()
    builder.build()
    if "--deploy" in sys.argv: builder.deploy()
