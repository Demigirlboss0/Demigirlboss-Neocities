import logging
from pathlib import Path

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("site_builder")

# Base Directories
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
CONTENT_DIR = PROJECT_ROOT / "content"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output"
STATIC_DIR = PROJECT_ROOT / "static"

# Site Metadata
SITE_TITLE = "Demigirlboss"
SITE_URL = "https://demigirlboss.neocities.org"
BASE_URL = "/"

# Content specific paths
PORTFOLIO_DIR = CONTENT_DIR / "portfolio"
BLOG_DIR = CONTENT_DIR / "blog"
WIKI_DIR = CONTENT_DIR / "wiki"

# HTML Sanitization Settings
ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol',
    'strong', 'ul', 'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'pre', 'div', 'span', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'del', 'ins', 'sub', 'sup', 'mark', 'details', 'summary', 'figure', 'figcaption'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id', 'style'],
    'a': ['href', 'title', 'rel', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}
