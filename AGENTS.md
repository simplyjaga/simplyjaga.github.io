# Curious Why — simplyjaga.github.io

Personal blog hosted on GitHub Pages. Notes on things the author is learning,
building, and trying to understand. Live at https://simplyjaga.github.io

## Stack

- **Jekyll** (GitHub Pages build, no plugins — `plugins: []` in `_config.yml`)
- **Markdown**: kramdown
- No Gemfile, no build scripts, no JS dependencies. GitHub Pages builds and
  deploys `main` automatically on push.

## Structure

```
_config.yml       Site config: title "Curious Why", permalink /blog/:year/:month/:day/:title/
index.md          Homepage — chronological list of all posts (Liquid loop over site.posts)
favicon.svg       Question-mark favicon
assets/style.css  The only stylesheet
_layouts/
  default.html    Base shell: <head>, site-name header, {{ content }}
  post.html       Article layout: collapsible TOC sidebar + .prose content
_posts/           Blog posts, one markdown file per post
```

## Writing a new post

Create `_posts/YYYY-MM-DD-slug.md` with front matter:

```yaml
---
layout: post
title: "Post Title"
date: YYYY-MM-DD
categories: [Systems]          # optional, shown on homepage and post eyebrow
description: "One-line summary shown on homepage and under the title."
toc:                            # optional but conventional — see below
  - title: "Section question?"
    url: "#anchor-of-heading"
    children:
      - title: "Subsection question?"
        url: "#sub-anchor"
---
```

- The `toc` is **hand-authored** front matter, not generated from headings.
  Keep it in sync with the post's `##`/`###` headings. Give every heading an
  explicit anchor, as all posts do: `## Why does X? {#why-does-x}`. The local
  preview script does not auto-generate anchors, so TOC links only work with
  explicit `{#id}`s.
- **Writing style convention**: posts are "question-led" — section headings are
  phrased as questions the reader would ask ("Why does one idle client stop
  this server?"). Match this style.
- **Ending convention**: every post ends with a horizontal rule (`---`)
  followed by short closing notes with no heading: a recap or "The
  takeaway: ..." paragraph that ties the post back to its opening question.
  Don't end with a "Summary"/"Conclusion" section in the TOC.

## Conventions

- Minimal, writing-first design. No navigation bar, no about page, no tags
  pages. The homepage IS the post list.
- Don't add plugins or a Gemfile unless asked — the site must stay
  GitHub Pages-compatible.
- Inline `<script>` in `post.html` handles the mobile TOC toggle; there is no
  other JavaScript.

## Local preview

The author's machine has no Ruby/Jekyll installed and system packages should
not be installed without asking. To preview, emulate the build with Python:

- Parse each post's YAML front matter and render the body with
  `python-markdown` (extensions: `fenced_code`, `tables`, `attr_list`,
  `sane_lists`) — installed via `pip install --user` (lands in `~/.local`).
- Wrap output in the `default.html`/`post.html` layouts (TOC sidebar is built
  from the post's `toc` front matter), write to a temp dir, and serve with
  `python3 -m http.server`.

Ready-made scripts (also in `/tmp/blog_preview.py` + `/tmp/serve_preview.sh`):

```bash
bash scripts/serve_preview.sh   # rebuilds and (re)starts preview on :4000
python3 scripts/render_preview.py  # render only, output -> /tmp/blog_preview_site
```

**Always use port 4000** (`http://127.0.0.1:4000`) — do not pick a different
port per session; `serve_preview.sh` kills any existing server on :4000 and
restarts it there.
- Note: kramdown renders `` \`code\` `` as literal backticks (this is
  intentional — inline code uses visible backticks on the site).

If Jekyll is ever available, `jekyll serve` also works.

## Git workflow

- Work on `main`; pushing to `main` triggers a GitHub Pages deploy.
