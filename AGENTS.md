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
  Keep it in sync with the post's `##`/`###` headings. kramdown auto-generates
  heading anchors as lowercase-hyphenated text (e.g. `## Why does X?` → `#why-does-x`).
- **Writing style convention**: posts are "question-led" — section headings are
  phrased as questions the reader would ask ("Why does one idle client stop
  this server?"). Match this style.

## Conventions

- Minimal, writing-first design. No navigation bar, no about page, no tags
  pages. The homepage IS the post list.
- Don't add plugins or a Gemfile unless asked — the site must stay
  GitHub Pages-compatible.
- Inline `<script>` in `post.html` handles the mobile TOC toggle; there is no
  other JavaScript.

## Local preview (optional)

Requires a Jekyll install (`gem install jekyll bundler`), then:

```
jekyll serve
```

## Git workflow

- Work on `main`; pushing to `main` triggers a GitHub Pages deploy.
