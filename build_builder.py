"""Build the plugin's portal shell from the existing brand header and footer."""
from pathlib import Path

base = Path(__file__).resolve().parent
home = (base / 'portal/index.html').read_text(encoding='utf-8')
prefix = home.split('  <main id="main">', 1)[0]
prefix = prefix.replace('<script src="/portal-assets/app.js" defer></script>',
                        '<link rel="stylesheet" href="/portal-assets/ui-dist/workspace.css">\n  <script type="module" src="/portal-assets/ui-dist/workspace.js"></script>')
prefix = prefix.replace('<a class="active" href="/" aria-current="page">', '<a href="/">')
footer = home[home.index('  <footer class="site-footer">'):]
for anchor in ('features', 'news', 'contact', 'guide', 'conferences'):
    prefix = prefix.replace(f'href="#{anchor}"', f'href="/#{anchor}"')
    footer = footer.replace(f'href="#{anchor}"', f'href="/#{anchor}"')
templates = base / 'worker/extension/yujian_site/templates'
content = '''  <main id="main" class="workspace-root" data-no-translate>
    <div id="meet-workspace" data-mode="{{ mode }}" data-event-id="{{ event.id if event else '' }}" data-finance-admin="{{ 'true' if session.user and session.user.is_admin else 'false' }}">
      <p class="workspace-loading">正在加载会议工作台… Loading workspace…</p>
    </div>
    <noscript>请启用 JavaScript 使用会议工作台。Please enable JavaScript.</noscript>
  </main>'''
prefix = prefix.replace('<body>', '<body class="workspace-body">')
(templates / 'builder.html').write_text(prefix + content + '\n' + footer, encoding='utf-8')
print('Assembled branded builder template.')
