// Exercise the real local server; credentials stay in the local account file.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('D:/playwright-demo/node_modules/playwright');

(async () => {
  const base = 'http://192.168.2.36:12880';
  const output = path.resolve(__dirname, '../output');
  const accounts = JSON.parse(fs.readFileSync(path.join(__dirname, 'demo-accounts.json'), 'utf8'));
  const model = JSON.parse(fs.readFileSync(path.join(__dirname, 'verification.json'), 'utf8').replace(/^\uFEFF/, ''));
  const browser = await chromium.launch({headless: true});
  try {
    const anonymous = await browser.newContext({viewport: {width: 1440, height: 1000}, locale: 'zh-CN'});
    const page = await anonymous.newPage();
    const checks = [];
    for (const event of model.events) {
      const response = await page.goto(event.url, {waitUntil: 'networkidle'});
      assert.equal(response.status(), 200);
      assert((await page.locator('body').innerText()).includes(event.title));
      assert((await page.locator('body').innerText()).includes('登录'), 'Chinese interface locale not applied');
      const headerColor = await page.locator('.confheader').evaluate(node => getComputedStyle(node).backgroundColor);
      const links = await page.locator('a').evaluateAll(nodes => nodes.map(a => ({text: a.textContent.trim(), url: a.href})));
      for (const title of ['会议委员会', '会议主题', '会议日程', '会议地点', '重要通知', '联系我们']) {
        assert(links.some(link => link.text === title), `Missing menu item: ${title}`);
      }
      const notice = links.find(link => link.text === '重要通知');
      const noticeResponse = await page.goto(notice.url, {waitUntil: 'networkidle'});
      assert.equal(noticeResponse.status(), 200);
      assert((await page.locator('body').innerText()).includes('欢迎访问遇见科技会议演示站'));
      await page.goto(event.url, {waitUntil: 'networkidle'});
      await page.screenshot({path: path.join(output, `indico-event-${event.event_id}.png`), fullPage: true});
      const protectedResponse = await page.goto(`${base}/event/${event.event_id}/manage/layout/menu/`);
      assert(protectedResponse.status() === 403 || page.url().includes('/login/'), 'Anonymous management was not denied');
      checks.push({event_id: event.event_id, header_color: headerColor, public_page: true,
        menu_links: true, anonymous_manage_denied: true});
    }
    assert.equal(new Set(checks.map(check => check.header_color)).size, 2, 'Conference colors did not render independently');
    await anonymous.close();

    for (const [index, username] of ['host-a', 'host-b'].entries()) {
      const context = await browser.newContext({viewport: {width: 1440, height: 1000}, locale: 'zh-CN'});
      const host = await context.newPage();
      const account = accounts.find(item => item.username === username);
      await host.goto(`${base}/login/`);
      await host.locator('input[name="identifier"]').fill(account.username);
      await host.locator('input[name="password"]').fill(account.password);
      await Promise.all([
        host.waitForURL(url => !url.pathname.startsWith('/login/')),
        host.locator('#login-form').evaluate(form => form.requestSubmit()),
      ]);
      const own = model.events[index].event_id;
      const other = model.events[1 - index].event_id;
      const ownResponse = await host.goto(`${base}/event/${own}/manage/layout/menu/`, {waitUntil: 'networkidle'});
      assert.equal(ownResponse.status(), 200);
      assert(!host.url().includes('/login/'));
      assert((await host.locator('body').innerText()).includes('会议委员会'));
      await host.screenshot({path: path.join(output, `indico-manager-${username}.png`), fullPage: true});
      if (index === 0) {
        await host.locator('.menu-entry').filter({hasText: '重要通知'}).first().locator('.edit-entry').click();
        const editor = host.frameLocator('iframe.tox-edit-area__iframe').locator('body');
        await editor.waitFor();
        const marker = '栏目编辑验证：主办方已通过后台保存本页。';
        if (!(await editor.innerText()).includes(marker)) {
          await editor.click();
          await editor.press('Control+End');
          await editor.press('Enter');
          await editor.pressSequentially(marker);
        }
        // Indico synchronizes TinyMCE to the form with a 200ms debounce.
        await host.waitForFunction(text => document.querySelector('.ui-dialog input[name="html"]')?.value.includes(text), marker);
        const saved = host.waitForResponse(response => response.request().method() === 'POST' &&
          response.url().includes('/manage/layout/menu/'));
        await host.locator('.ui-dialog input[type="submit"]').click();
        const saveResponse = await saved;
        assert.equal(saveResponse.status(), 200);
        assert((await saveResponse.json()).entry, 'The editor returned a validation error');
        const publicReader = await browser.newPage({locale: 'zh-CN'});
        await publicReader.goto(`${base}/event/${own}/`);
        await publicReader.getByRole('link', {name: '重要通知', exact: true}).click();
        assert((await publicReader.locator('body').innerText()).includes(marker), 'Saved content is not public');
        await publicReader.screenshot({path: path.join(output, 'indico-edited-notice.png'), fullPage: true});
        await publicReader.close();
        checks[index].editor_saved_and_public = true;
      }
      const otherResponse = await host.goto(`${base}/event/${other}/manage/layout/menu/`);
      assert.equal(otherResponse.status(), 403, 'Host gained access to another conference');
      checks[index].host_login = true;
      checks[index].own_menu_management = true;
      checks[index].other_host_http_403 = true;
      await context.close();
    }
    const result = {passed: true, checks};
    fs.writeFileSync(path.join(__dirname, 'browser-verification.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
