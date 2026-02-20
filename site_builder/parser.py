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

from .config import logger, ALLOWED_TAGS, ALLOWED_ATTRIBUTES, CONTENT_DIR

@dataclass(frozen=True)
class ParsedContent:
    """Structured data for parsed content with validation."""
    title: str
    date: datetime.date
    date_display: str
    iso_date: str 
    published_date: str # Original publication date
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
    """Handles parsing of Markdown files with sanitization, link resolution, and schema validation."""
    
    SCHEMA_CONFIG = {
        'Portfolio': ['thumbnail', 'description'],
        'Blog': [] 
    }

    def __init__(self, extensions: Optional[List[str]] = None):
        self.extensions = extensions or [
            'extra',
            'md_in_html',
            'nl2br',
            'sane_lists',
            'admonition',
            'attr_list'
        ]
        self.css_sanitizer = CSSSanitizer()

    def slugify(self, text: str) -> str:
        """Standard web slugifier: lowercase, no spaces, no special chars."""
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_]+', '-', text)
        return text.strip('-')

    def parse_file(self, file_path: Path) -> ParsedContent:
        if not file_path.exists():
            raise FileNotFoundError(f"Content file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
        except Exception as e:
            msg = f"MALFORMED METADATA in {file_path}: {e}"
            print(f"CRITICAL ERROR: {msg}", file=sys.stderr)
            logger.error(msg)
            raise ValueError(msg) from e

        raw_content = post.content.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
        html_content = markdown.markdown(raw_content, extensions=self.extensions)

        html_content = self._resolve_internal_links(html_content)
        html_content = self._resolve_strikethrough(html_content)

        try:
            html_content = bleach.clean(
                html_content,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                css_sanitizer=self.css_sanitizer,
                strip=True
            )
        except Exception as e:
            logger.error(f"Sanitization error in {file_path}: {e}")

        # Extract metadata
        metadata = post.metadata
        slug = file_path.stem
        
        # Handle date parsing
        date_obj = self._parse_date(metadata.get('date'), file_path)
        
        # Use frontmatter date for published, but current time for iso_date (updated)
        # to ensure feed readers always see it as a fresh change if needed.
        # Actually, standard Atom is better: 
        # published = original date
        # updated = file mtime or frontmatter date
        published_iso = date_obj.strftime('%Y-%m-%dT12:00:00Z')
        
        # We will use the actual file modification time for the strictly required 'updated' field
        mtime = datetime.datetime.fromtimestamp(file_path.stat().st_mtime, datetime.timezone.utc)
        updated_iso = mtime.strftime('%Y-%m-%dT%H:%M:%SZ')

        category_name = metadata.get('category')
        is_wiki = "wiki" in file_path.parts
        
        if not category_name:
            parent_name = file_path.parent.name
            category_name = parent_name if parent_name and parent_name != CONTENT_DIR.name else 'General'
        
        category = category_name.title()
        
        topic = None
        if is_wiki:
            if slug != "index":
                topic = metadata.get('topic')
                if not topic:
                    if file_path.parent.name != "wiki":
                        topic = file_path.parent.name
                    else:
                        topic = "Uncategorized"
                topic = topic.title()

        self._validate_metadata_schema(category, metadata, file_path)

        return ParsedContent(
            title=str(metadata.get('title', slug.replace('_', ' ').title())),
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
        required_fields = self.SCHEMA_CONFIG.get(category, [])
        missing = [field for field in required_fields if field not in metadata or not str(metadata[field]).strip()]
        if missing:
            msg = f"Missing required metadata for {category} in {file_path}: {', '.join(missing)}"
            logger.warning(msg)

    def _resolve_strikethrough(self, html: str) -> str:
        pattern = r'~~(.*?)~~'
        return re.sub(pattern, r'<del>\1</del>', html)

    def _resolve_internal_links(self, html: str) -> str:
        """
        Converts <a href="path/to/file.md"> to <a href="path/to/file.html">.
        Handles fragments (#), query parameters (?), and slugification.
        """
        # Group 1: href=" or href='
        # Group 2: The path part before .md (allowing spaces)
        # Group 3: optional #fragment or ?query
        # Group 4: closing quote
        pattern = r'(href=["\'])([^"\']+?)\.md([#?][^"\' >]*)?(["\'])'
        
        def replace_md(match):
            quote_start, path, extra, quote_end = match.groups()
            extra = extra if extra else ""
            
            # Slugify the path while preserving slashes
            if '/' in path:
                parts = path.split('/')
                new_path = "/".join([self.slugify(p) for p in parts])
            else:
                new_path = self.slugify(path)
                
            return f"{quote_start}{new_path}.html{extra}{quote_end}"
            
        return re.sub(pattern, replace_md, html, flags=re.IGNORECASE)

    def _parse_date(self, date_val: Any, file_path: Path) -> datetime.date:
        if isinstance(date_val, (datetime.date, datetime.datetime)):
            return date_val.date() if isinstance(date_val, datetime.datetime) else date_val
        if isinstance(date_val, str):
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%B %d, %Y'):
                try:
                    return datetime.datetime.strptime(date_val, fmt).date()
                except ValueError:
                    continue
        return datetime.date.fromtimestamp(file_path.stat().st_mtime)

    def _generate_url(self, file_path: Path, slug: str, metadata: Dict[str, Any], topic: Optional[str] = None) -> str:
        if 'url' in metadata:
            url = str(metadata['url'])
            return url if url.startswith('/') else f"/{url}"
            
        clean_slug = self.slugify(slug)
        if slug == "index": clean_slug = "index"

        if topic and "wiki" in file_path.parts:
            clean_topic = self.slugify(topic)
            return f"/wiki/{clean_topic}/{clean_slug}.html"

        try:
            abs_content_dir = CONTENT_DIR.absolute()
            abs_file_path = file_path.absolute()
            if abs_content_dir in abs_file_path.parents:
                rel_parts = list(abs_file_path.relative_to(abs_content_dir).parts[:-1])
                rel_parts = [self.slugify(p) for p in rel_parts]
            else:
                rel_parts = []
        except ValueError:
            rel_parts = []
        
        url_path = "/".join(rel_parts)
        if url_path:
            return f"/{url_path}/{clean_slug}.html"
        return f"/{clean_slug}.html"
