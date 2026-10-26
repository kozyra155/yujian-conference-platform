"""Reuse the portal shell when assembling the standalone conference list."""
import re
from pathlib import Path

portal = Path(__file__).resolve().parent / 'portal'
home = (portal / 'index.html').read_text(encoding='utf-8')
prefix = home.split('  <main id="main">', 1)[0]
prefix = prefix.replace('<title>遇见科技会议服务平台</title>', '<title>会议活动 · 遇见科技会议服务平台</title>')
prefix = re.sub(r'<meta name="description"[^>]+>', '<meta name="description" content="遇见科技会议活动：浏览平台已发布的学术会议，搜索会议名称和地点，查看会议安排。">', prefix)
prefix = prefix.replace('  <script src="/portal-assets/app.js" defer></script>', '  <link rel="stylesheet" href="/portal-assets/events.css">\n  <script src="/portal-assets/events.js" defer></script>')
prefix = prefix.replace('  <script src="/portal-assets/public-conferences.js" defer></script>\n', '')
prefix = prefix.replace('class="active" href="/" aria-current="page"', 'href="/"')
prefix = prefix.replace('<a href="/events/">会议查询</a>', '<a class="active" href="/events/" aria-current="page">会议查询</a>')
footer = home[home.index('  <footer class="site-footer">'):]
for anchor in ('features', 'news', 'contact', 'guide'):
    prefix = prefix.replace(f'href="#{anchor}"', f'href="/#{anchor}"')
    footer = footer.replace(f'href="#{anchor}"', f'href="/#{anchor}"')
footer = footer.replace('href="#conferences"', 'href="/events/"')
content = (portal / 'events-content.html').read_text(encoding='utf-8')
assert prefix.count('navigation.js') == 1
assert 'app.js' not in prefix
assert 'event-card-template' in content
(portal / 'events.html').write_text(prefix + content + '\n' + footer, encoding='utf-8')
print('Assembled portal/events.html from the shared portal shell.')
