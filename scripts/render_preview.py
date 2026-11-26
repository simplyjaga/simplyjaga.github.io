#!/usr/bin/env python3
"""Minimal Jekyll emulator for previewing simplyjaga.github.io locally."""
import html
import os
import re
import shutil
import sys

import markdown
import yaml

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = "/tmp/blog_preview_site"

cfg = yaml.safe_load(open(os.path.join(SITE, "_config.yml")))
SITE_TITLE = cfg["title"]
SITE_DESC = cfg["description"]

MD_EXTS = ["fenced_code", "tables", "attr_list", "sane_lists"]


def esc(s):
    return html.escape(str(s), quote=True)


def fmt_date(d):
    return d.strftime("%b %-d, %Y")


def read_post(path):
    text = open(path).read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    fm = yaml.safe_load(m.group(1))
    fm["content_html"] = markdown.markdown(m.group(2), extensions=MD_EXTS)
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", os.path.basename(path))[:-3]
    fm["slug"] = slug
    d = fm["date"]
    fm["url"] = f"/blog/{d.year}/{d.month:02d}/{d.day:02d}/{slug}/"
    return fm


def render_default(title, description, content):
    page_title = f"{esc(title)} · {esc(SITE_TITLE)}" if title else esc(SITE_TITLE)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{esc(description or SITE_DESC)}">
    <title>{page_title}</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="stylesheet" href="/assets/style.css">
  </head>
  <body>
    <div class="site-shell">
      <header class="site-header">
        <a class="site-name" href="/">{esc(SITE_TITLE)}</a>
      </header>
      <main>
        {content}
      </main>
    </div>
  </body>
</html>"""


def render_post(page):
    toc_items = ""
    for item in page.get("toc") or []:
        children = ""
        if item.get("children"):
            lis = "".join(
                f'<li><a href="{esc(c["url"])}">{esc(c["title"])}</a></li>'
                for c in item["children"]
            )
            children = f'<ul class="toc-subsections">{lis}</ul>'
        toc_items += (
            f'<li class="toc-section"><a class="toc-section-link" '
            f'href="{esc(item["url"])}">{esc(item["title"])}</a>{children}</li>'
        )

    cats = page.get("categories") or []
    eyebrow = " · ".join(esc(c) for c in cats)
    if eyebrow:
        eyebrow += " · "
    eyebrow += fmt_date(page["date"])

    desc = (
        f'<p class="article-description">{esc(page["description"])}</p>'
        if page.get("description") else ""
    )

    content = f"""<div class="article-layout">
  <aside class="article-toc" id="article-toc">
    <button class="toc-toggle" type="button" aria-expanded="false" aria-controls="toc-navigation">
      <span class="toc-menu-icon" aria-hidden="true">&#9776;</span>
      <span>In this section</span>
    </button>
    <nav class="toc-navigation" id="toc-navigation" aria-label="Table of contents">
      <p class="toc-heading">IN THIS SECTION</p>
      <ul>{toc_items}</ul>
    </nav>
  </aside>
  <article class="article">
    <header class="article-header">
      <p class="eyebrow">{eyebrow}</p>
      <h1 id="article-start">{esc(page["title"])}</h1>
      {desc}
    </header>
    <div class="prose">
      {page["content_html"]}
    </div>
  </article>
</div>
<script>
  (() => {{
    const sidebar = document.getElementById("article-toc");
    const toggle = sidebar?.querySelector(".toc-toggle");
    const navigation = sidebar?.querySelector(".toc-navigation");
    if (!sidebar || !toggle || !navigation) return;
    toggle.addEventListener("click", () => {{
      const isOpen = sidebar.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    }});
    navigation.addEventListener("click", (event) => {{
      if (event.target.closest("a")) {{
        sidebar.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      }}
    }});
    document.addEventListener("keydown", (event) => {{
      if (event.key === "Escape") {{
        sidebar.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      }}
    }});
  }})();
</script>"""
    return render_default(page["title"], page.get("description"), content)


def render_index(posts):
    items = ""
    for p in posts:
        cats = p.get("categories") or []
        meta = fmt_date(p["date"])
        if cats:
            meta += " · " + ", ".join(esc(c) for c in cats)
        desc = (
            f'<p class="post-description">{esc(p["description"])}</p>'
            if p.get("description") else ""
        )
        items += f"""<article class="post-item">
          <h2><a href="{p["url"]}">{esc(p["title"])}</a></h2>
          <p class="post-meta">{meta}</p>
          {desc}
        </article>"""
    body = f"""<section class="home">
  <p class="intro">Explanations, learning notes, and ideas from things I'm exploring.</p>
  <div class="post-list">{items}</div>
</section>"""
    return render_default(SITE_TITLE, SITE_DESC, body)


def write(dest, content):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        f.write(content)


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    posts = []
    for name in sorted(os.listdir(os.path.join(SITE, "_posts")), reverse=True):
        if name.endswith(".md"):
            posts.append(read_post(os.path.join(SITE, "_posts", name)))

    for p in posts:
        write(os.path.join(OUT, p["url"].lstrip("/"), "index.html"), render_post(p))
    write(os.path.join(OUT, "index.html"), render_index(posts))

    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    shutil.copy(os.path.join(SITE, "assets", "style.css"),
                os.path.join(OUT, "assets", "style.css"))
    shutil.copy(os.path.join(SITE, "favicon.svg"),
                os.path.join(OUT, "favicon.svg"))
    print(f"Built {len(posts)} post(s) -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
