---
layout: default
title: Curious Why
---
<section class="home-intro">
  <p class="eyebrow">A PERSONAL TECHNICAL NOTEBOOK</p>
  <h1>Curious why.</h1>
  <p class="intro">Notes on things I'm learning, building, and trying to understand.</p>
  <p>I write about computer systems, machine learning, mathematics, and the occasional rabbit hole. These are my notes, explanations, questions, and discoveries along the way.</p>
  <a class="text-link" href="{{ '/blog/' | relative_url }}">Explore the writing <span aria-hidden="true">→</span></a>
</section>

<section class="home-latest">
  <div class="section-heading">
    <h2>Recent writing</h2>
    <a class="subtle-link" href="{{ '/blog/' | relative_url }}">All writing</a>
  </div>
  {% assign posts = site.posts | slice: 0, 3 %}
  {% if posts.size > 0 %}
    <div class="post-list">
      {% for post in posts %}
        <article class="post-item">
          <p class="post-meta">{{ post.date | date: "%b %-d, %Y" }}{% if post.categories.size > 0 %} · {{ post.categories | join: ", " }}{% endif %}</p>
          <h2><a href="{{ post.url | relative_url }}">{{ post.title | escape }}</a></h2>
          {% if post.description %}<p>{{ post.description | escape }}</p>{% else %}<p>{{ post.excerpt | strip_html | truncate: 180 }}</p>{% endif %}
        </article>
      {% endfor %}
    </div>
  {% else %}
    <p class="empty-state">The first article will find its way here.</p>
  {% endif %}
</section>
