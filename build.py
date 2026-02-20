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
        """Generates an Atom XML feed for the site."""
        logger.info("Generating Atom feed...")
        
        # Sort content by date (newest first) and exclude index files
        feed_items = sorted(
            [c for c in self.all_content if c.slug != 'index'],
            key=lambda x: x.date,
            reverse=True
        )[:20]

        if not feed_items:
            return

        context = {
            'site_title': SITE_TITLE,
            'site_url': SITE_URL,
            'last_updated': feed_items[0].iso_date,
            'items': feed_items
        }

        xml_output = self.renderer.render('atom.xml', context)
        
        with open(OUTPUT_DIR / "atom.xml", "w", encoding="utf-8") as f:
            f.write(xml_output)
        logger.info(f"Feed generated at {OUTPUT_DIR}/atom.xml")

    def clean_output(self):
        """Prepares the output directory."""
        if OUTPUT_DIR.exists():
            logger.info(f"Cleaning output directory: {OUTPUT_DIR}")
            shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def copy_static(self):
        """Copies static assets from both root/static and content/static."""
        logger.info("Synchronizing static assets...")
        
        # 1. Copy global style.css
        style_css = Path("style.css")
        if style_css.exists():
            shutil.copy(style_css, OUTPUT_DIR / "style.css")
        
        # 2. Copy root/static folder (Global assets)
        if STATIC_DIR.exists():
            shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static", dirs_exist_ok=True)

        # 3. Copy content/static folder (Content-specific assets)
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
        
        # Neocities API expects files to be uploaded via POST /api/upload
        # We'll upload all files found in the output directory
        url = "https://neocities.org/api/upload"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            files_to_upload = {}
            # Open all files for uploading
            opened_files = []
            
            for root, _, files in os.walk(OUTPUT_DIR):
                for file in files:
                    local_path = Path(root) / file
                    remote_path = local_path.relative_to(OUTPUT_DIR)
                    
                    # We open the file and add it to the multipart/form-data
                    # The key is the remote filename
                    f = open(local_path, 'rb')
                    opened_files.append(f)
                    files_to_upload[str(remote_path)] = f

            if not files_to_upload:
                logger.info("No files to upload.")
                return

            logger.info(f"Syncing {len(files_to_upload)} files...")
            response = requests.post(url, headers=headers, files=files_to_upload)
            
            # Close all files
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
            template = 'base.html'
            if 'portfolio' in str(content.url):
                template = 'portfolio-item.html'
            elif 'wiki' in str(content.url):
                template = 'base.html' # Or 'wiki-item.html' if created
            
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

        self.build_portfolio_index(updates)
        self.build_wiki_index(updates)
        self.generate_feed()
        logger.info("Build Complete! ✨")

    def build_wiki_index(self, updates):
        """Generates the main Wiki listing page grouped by topic."""
        wiki_items = [
            c for c in self.all_content if 'wiki' in str(c.url) and c.slug != 'index'
        ]
        
        # Group items by topic
        topics = {}
        for item in wiki_items:
            t = item.topic or "Uncategorized"
            if t not in topics:
                topics[t] = []
            topics[t].append(item)
        
        # Sort topics alphabetically and items by date
        sorted_topics = []
        for topic_name in sorted(topics.keys()):
            sorted_items = sorted(topics[topic_name], key=lambda x: x.date, reverse=True)
            sorted_topics.append({
                'name': topic_name,
                'articles': sorted_items
            })

        # Look for content/wiki/index.md
        from site_builder import WIKI_DIR
        wiki_index_md = WIKI_DIR / "index.md"
        if wiki_index_md.exists():
            content_obj = self.parser.parse_file(wiki_index_md)
        else:
            from datetime import date
            content_obj = ParsedContent(
                title="Wiki",
                date=date.today(),
                date_display="",
                iso_date=date.today().strftime('%Y-%m-%dT12:00:00Z'),
                slug="index",
                content="",
                raw_content="",
                metadata={},
                category="Wiki",
                topic=None,
                url="/wiki/index.html"
            )

        html = self.renderer.render_page(
            content=content_obj,
            template_name='wiki.html',
            updates=updates,
            topics=sorted_topics
        )
        
        output_path = OUTPUT_DIR / "wiki" / "index.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def build_portfolio_index(self, updates):
        """Generates the main portfolio listing page."""
        portfolio_items = [
            c for c in self.all_content if 'portfolio' in str(c.url) and c.slug != 'index'
        ]
        portfolio_items.sort(key=lambda x: x.date, reverse=True)

        portfolio_index_md = CONTENT_DIR / "portfolio" / "index.md"
        if portfolio_index_md.exists():
            content_obj = self.parser.parse_file(portfolio_index_md)
        else:
            from datetime import date
            content_obj = ParsedContent(
                title="Portfolio",
                date=date.today(),
                date_display="",
                iso_date=date.today().strftime('%Y-%m-%dT12:00:00Z'),
                slug="index",
                content="",
                raw_content="",
                metadata={},
                category="Portfolio",
                topic=None,
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
    import sys
    
    builder = SiteBuilder()
    builder.build()
    
    if "--deploy" in sys.argv:
        builder.deploy()
