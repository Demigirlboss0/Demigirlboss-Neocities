import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import minify_html
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .config import TEMPLATES_DIR, SITE_TITLE, SITE_DESCRIPTION, logger
from .parser import ParsedContent

class SiteRenderer:
    """Handles Jinja2 template loading, SEO injection, and HTML minification."""

    def __init__(self, templates_dir: Path = TEMPLATES_DIR):
        if not templates_dir.exists():
            logger.error(f"Templates directory not found: {templates_dir}")
            raise FileNotFoundError(f"Templates directory not found: {templates_dir}")

        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        self.env.globals.update({
            'site_title': SITE_TITLE,
            'default_description': SITE_DESCRIPTION,
            'now': datetime.datetime.now(),
            'current_year': datetime.datetime.now().year,
        })

    def render(self, template_name: str, context: Dict[str, Any], minify: bool = False) -> str:
        """Renders a template and optionally minifies the output."""
        try:
            template = self.env.get_template(template_name)
            html = template.render(context)
            
            if minify and template_name.endswith('.html'):
                return minify_html.minify(
                    html,
                    minify_css=True,
                    minify_js=False, # We strictly follow No-JS
                    remove_processing_instructions=True
                )
            return html
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise

    def render_page(self, content: ParsedContent, template_name: str = 'base.html', updates: List[Dict[str, Any]] = None, **kwargs) -> str:
        """Specialized method to render a page with SEO metadata."""
        url_parts = [p for p in content.url.split('/') if p]
        depth = len(url_parts) - 1
        base_path = '../' * depth if depth > 0 else './'

        context = {
            'title': f"{SITE_TITLE} | {content.title}",
            'page_title': content.title,
            'page_description': content.description or SITE_DESCRIPTION,
            'content': content.content,
            'metadata': content.metadata,
            'updates': updates or [],
            'base_path': base_path,
            'current_page': content.slug,
            'url': content.url,
            **kwargs
        }
        
        return self.render(template_name, context, minify=True)
