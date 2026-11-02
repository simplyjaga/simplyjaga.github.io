---
layout: default
title: Curious Why
---
<section class="home">
  <p class="intro">Explanations, learning notes, and ideas from things I'm exploring.</p>

  {% assign posts = site.posts %}
  {% if posts.size > 0 %}
    <div class="post-list">
      {% for post in posts %}
        <article class="post-item">
          <h2><a href="{{ post.url | relative_url }}">{{ post.title | escape }}</a></h2>
          <p class="post-meta">{{ post.date | date: "%b %-d, %Y" }}{% if post.categories.size > 0 %} · {{ post.categories | join: ", " }}{% endif %}</p>
          {% if post.description %}<p class="post-description">{{ post.description | escape }}</p>{% endif %}
        </article>
      {% endfor %}
    </div>
  {% else %}
    <p class="empty-state">No posts yet.</p>
  {% endif %}
</section>
