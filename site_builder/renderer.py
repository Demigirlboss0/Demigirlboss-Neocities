import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from .config import TEMPLATES_DIR, SITE_TITLE, logger
from .parser import ParsedContent

class SiteRenderer:
    """Handles Jinja2 template loading and rendering."""

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
        
        # Add global variables available to all templates
        self.env.globals.update({
            'site_title': SITE_TITLE,
            'now': datetime.datetime.now(),
            'current_year': datetime.datetime.now().year,
        })

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Renders a template with the given context."""
        try:
            template = self.env.get_template(template_name)
            return template.render(context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise

    def render_page(self, content: ParsedContent, template_name: str = 'base.html', updates: List[Dict[str, Any]] = None, **kwargs) -> str:
        """
        Specialized method to render a page.
        
        Args:
            content: The parsed content object for the page.
            template_name: The template to use (default: base.html).
            updates: A list of recent updates/posts for the sidebar.
            **kwargs: Additional context variables.
        """
        # Determine base_path for relative asset loading (e.g., style.css)
        # This is a simple heuristic; can be improved by counting depth.
        url_parts = [p for p in content.url.split('/') if p]
        depth = len(url_parts) - 1
        base_path = '../' * depth if depth > 0 else './'

        context = {
            'title': f"{SITE_TITLE} | {content.title}",
            'page_title': content.title,
            'content': content.content,
            'metadata': content.metadata,
            'updates': updates or [],
            'base_path': base_path,
            'current_page': content.slug,
            'url': content.url,
            **kwargs
        }
        
        return self.render(template_name, context)
