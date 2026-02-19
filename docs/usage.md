# User Manual: Operating the Command Deck

This guide explains how to manage content and deploy your Neocities website using the custom Python build system.

## 1. Adding New Content

All content is stored in the `content/` directory as Markdown (`.md`) files.

- **Blog Posts:** Place in `content/blog/`.
- **Portfolio Items:** Place in `content/portfolio/`.
- **Static Pages:** Place directly in `content/` (e.g., `index.md`, `about.md`).

### Images and Assets
- **Global Assets:** Put UI-related images in the root `static/` folder.
- **Content Assets:** Put post-specific images in `content/static/`. 
The build system merges these into `output/static/` automatically.

## 2. Frontmatter Schema

Every Markdown file **must** start with a YAML frontmatter block.

### Standard Fields (All Pages)
```yaml
---
title: "My New Page"
date: 2026-02-19
category: "Updates" # Optional: Defaults to folder name
---
```

### Portfolio Specific Fields
The Portfolio index requires these fields to generate the grid:
```yaml
---
title: "Project Alpha"
date: 2026-02-19
image: "/static/project-alpha.png" # Full size image (auto-scaled)
description: "A brief summary of the project."
---
```
*Note: You can also use `thumbnail: "..."` if you want a specific small image, otherwise it scales the `image` field.*

## 3. Build & Deployment

The build system is consolidated into `build.py`.

### To Build Locally
This generates the HTML files in the `output/` folder.
```bash
python3 build.py
```

### To Build and Deploy
This builds the site and pushes all changes to Neocities via the API.
```bash
python3 build.py --deploy
```

## 4. Testing

To ensure the parser and link resolver are functioning correctly, run the test suite:
```bash
PYTHONPATH=. python3 tests/test_builder.py
```

## 5. Helpful Tips
- **Strikethrough:** Use `~~text~~` for ~~strikethrough~~.
- **Internal Links:** You can link to other markdown files using `.md` (e.g., `[Link](page.md)`). The builder converts these to `.html` automatically.
- **Glitch Text:** The top-level `h1` in any page automatically receives a high-tech glitch animation.
