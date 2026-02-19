# Technical Architecture: The Command Deck Logic

This document explains the structural layout of the site builder and the "Cyber-Catppuccin" design system.

## 1. Directory Structure

- `site_builder/`: The core logic package.
  - `config.py`: Global constants, paths, and HTML sanitization whitelists.
  - `parser.py`: The "Brain." Handles Markdown conversion, internal link resolution, and metadata validation.
  - `renderer.py`: The "Eye." Handles Jinja2 templating and relative path calculations.
- `templates/`: Jinja2 HTML templates.
  - `base.html`: The master layout containing the Neon Rain and global structure.
  - `portfolio.html`: The dynamic grid generator for your work.
- `static/`: Global UI assets (CSS, logos).
- `content/static/`: Assets specifically for your posts/artwork.
- `output/`: The final generated site (DO NOT edit directly).
- `build.py`: The orchestrator script.

## 2. The Build Pipeline

When you run `build.py`, the following sequence occurs:
1. **Clean:** The `output/` directory is wiped.
2. **Sync:** `style.css` and both static folders are copied to `output/`.
3. **Crawl:** Every `.md` file in `content/` is found.
4. **Parse:** 
   - Markdown is converted to HTML.
   - `.md` links are resolved to `.html`.
   - `~~strikethrough~~` is resolved to `<del>`.
   - `<h1>` tags are injected with `data-text` for glitch effects.
   - HTML/CSS is sanitized via `bleach` and `tinycss2`.
5. **Render:** Content is injected into Jinja2 templates. `base_path` is calculated based on directory depth to ensure portable asset links.
6. **Deploy:** (Optional) Files are POSTed to the Neocities API.

## 3. Design System: Cyber-Catppuccin

The aesthetic is a hybrid of the **Catppuccin Mocha** palette and **Y2K Industrial Cyberpunk**.

### Key Styling Components
- **Neon Rain:** Located in `base.html` as 20 `<i>` tags, animated in `style.css`.
- **Industrial Panels:** Uses `clip-path: polygon(...)` to create chamfered edges.
- **Glassmorphism:** Achieved via `backdrop-filter: blur()` and semi-transparent backgrounds.
- **Glitch Text:** Uses CSS pseudo-elements (`::before`/`::after`) and the `data-text` attribute to create chromatic aberration.

### Making Changes
- **Colors:** Edit the `:root` variables in `style.css`.
- **Layout:** Modify the `.container` grid in `style.css`.
- **HTML Structure:** Modify the files in `templates/`.
- **Security:** To allow new HTML tags (like `<embed>` or `<iframe>`), update the `ALLOWED_TAGS` list in `site_builder/config.py`.

## 4. Dependencies

The system stays lean by using a few industry-standard Python libraries:
- `jinja2`: Templating.
- `markdown`: Content conversion.
- `python-frontmatter`: Metadata extraction.
- `bleach` & `tinycss2`: Security and sanitization.
- `requests`: Deployment.
- `python-dotenv`: Credential management.
