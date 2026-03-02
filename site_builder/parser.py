import datetime
import logging
import sys
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

import frontmatter
import markdown
import bleach
from bleach.css_sanitizer import CSSSanitizer

from .config import (
    logger, ALLOWED_TAGS, ALLOWED_ATTRIBUTES, CONTENT_DIR, SCHEMA_CONFIG,
    DEFAULT_CATEGORY, DEFAULT_TOPIC
)

@dataclass(frozen=True)
class ParsedContent:
    """Structured data for parsed content with validation."""
    title: str
    description: str 
    date: datetime.date
    date_display: str
    iso_date: str 
    published_date: str 
    slug: str
    content: str
    raw_content: str
    metadata: Dict[str, Any]
    category: str
    topic: Optional[str]
    url: str

    def __post_init__(self):
        errors = []
        if not self.title.strip():
            errors.append("Title cannot be empty")
        if not self.slug.strip():
            errors.append("Slug cannot be empty")
        if not self.url.startswith('/'):
            errors.append(f"URL must be absolute (start with /): {self.url}")
        
        if errors:
            error_msg = f"Validation failed for '{self.slug}': {', '.join(errors)}"
            logger.error(error_msg)
            print(f"CRITICAL ERROR: {error_msg}", file=sys.stderr)
            raise ValueError(error_msg)

class ContentParser:
    """Handles parsing of Markdown files without hardcoded defaults."""
    
    def __init__(self, extensions: Optional[List[str]] = None):
        self.extensions = extensions or [
            'extra', 'md_in_html', 'nl2br', 'sane_lists', 'admonition', 'attr_list'
        ]
        self.css_sanitizer = CSSSanitizer()

    def slugify(self, text: str) -> str:
        """Standard web slugifier: lowercase, no spaces, no multiple hyphens."""
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'-+', '-', text) 
        return text.strip('-')

    def parse_file(self, file_path: Path) -> ParsedContent:
        if not file_path.exists():
            raise FileNotFoundError(f"Content file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
        except Exception as e:
            msg = f"MALFORMED METADATA in {file_path}: {e}"
            logger.error(msg)
            raise ValueError(msg) from e

        # Pre-processing
        raw_content = post.content.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
        html_content = markdown.markdown(raw_content, extensions=self.extensions)
        html_content = self._resolve_internal_links(html_content)
        html_content = self._resolve_strikethrough(html_content)

        # Sanitization
        try:
            html_content = bleach.clean(
                html_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES,
                css_sanitizer=self.css_sanitizer, strip=True
            )
        except Exception as e:
            logger.error(f"Sanitization error in {file_path}: {e}")

        # Metadata & Dates
        metadata = post.metadata
        slug = file_path.stem
        date_obj = self._parse_date(metadata.get('date'), file_path)
        
        # Build UTC-aware published time (defaults to midnight of the date)
        published_dt = datetime.datetime.combine(date_obj, datetime.time.min, tzinfo=datetime.timezone.utc)
        published_iso = published_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Updated time from file or frontmatter
        mtime_dt = datetime.datetime.fromtimestamp(file_path.stat().st_mtime, datetime.timezone.utc)
        if mtime_dt < published_dt:
            # Logic: If mtime is earlier than published day, use published day + 1s
            updated_dt = published_dt + datetime.timedelta(seconds=1)
        else:
            updated_dt = mtime_dt
        updated_iso = updated_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Taxonomies
        category_name = metadata.get('category')
        is_wiki = "wiki" in file_path.parts
        if not category_name:
            parent_name = file_path.parent.name
            category_name = parent_name if parent_name and parent_name != CONTENT_DIR.name else DEFAULT_CATEGORY
        category = category_name.title()
        
        topic = None
        if is_wiki and slug != "index":
            topic = metadata.get('topic', file_path.parent.name if file_path.parent.name != "wiki" else DEFAULT_TOPIC).title()

        self._validate_metadata_schema(category, metadata, file_path)

        return ParsedContent(
            title=str(metadata.get('title', slug.replace('_', ' ').title())),
            description=str(metadata.get('description', '')),
            date=date_obj,
            date_display=date_obj.strftime('%B %d, %Y'),
            iso_date=updated_iso,
            published_date=published_iso,
            slug=slug,
            content=html_content,
            raw_content=post.content,
            metadata=metadata,
            category=category,
            topic=topic,
            url=self._generate_url(file_path, slug, metadata, topic)
        )

    def _validate_metadata_schema(self, category: str, metadata: Dict[str, Any], file_path: Path):
        required_fields = SCHEMA_CONFIG.get(category, [])
        missing = [f for f in required_fields if f not in metadata or not str(metadata[f]).strip()]
        if missing:
            logger.warning(f"Missing metadata for {category} in {file_path}: {', '.join(missing)}")

    def _resolve_strikethrough(self, html: str) -> str:
        return re.sub(r'~~(.*?)~~', r'<del>\1</del>', html)

    def _resolve_internal_links(self, html: str) -> str:
        pattern = r'(href=["\'])([^"\']+?)\.md([#?][^"\' >]*)?(["\'])'
        def replace_md(match):
            q1, path, extra, q2 = match.groups()
            new_path = "/".join([self.slugify(p) for p in path.split('/')])
            return f"{q1}{new_path}.html{extra or ''}{q2}"
        return re.sub(pattern, replace_md, html, flags=re.IGNORECASE)

    def make_links_absolute(self, html: str, site_url: str) -> str:
        html = re.sub(r'href="/', f'href="{site_url}/', html)
        html = re.sub(r'src="/', f'src="{site_url}/', html)
        return html

    def _parse_date(self, date_val: Any, file_path: Path) -> datetime.date:
        if isinstance(date_val, (datetime.date, datetime.datetime)):
            return date_val.date() if isinstance(date_val, datetime.datetime) else date_val
        if isinstance(date_val, str):
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%B %d, %Y'):
                try: return datetime.datetime.strptime(date_val, fmt).date()
                except ValueError: continue
        return datetime.date.fromtimestamp(file_path.stat().st_mtime)

    def _generate_url(self, file_path: Path, slug: str, metadata: Dict[str, Any], topic: Optional[str] = None) -> str:
        if 'url' in metadata:
            u = str(metadata['url'])
            return u if u.startswith('/') else f"/{u}"
        clean_slug = "index" if slug == "index" else self.slugify(slug)
        if topic and "wiki" in file_path.parts:
            return f"/wiki/{self.slugify(topic)}/{clean_slug}.html"
        try:
            abs_content_dir = CONTENT_DIR.absolute()
            abs_file_path = file_path.absolute()
            if abs_content_dir in abs_file_path.parents:
                rel_parts = [self.slugify(p) for p in abs_file_path.relative_to(abs_content_dir).parts[:-1]]
                if rel_parts: return f"/{'/'.join(rel_parts)}/{clean_slug}.html"
        except ValueError: pass
        return f"/{clean_slug}.html"
