// Keep the upstream authentication form, CSRF fields and event handlers intact.
document.title = '遇见科技会议服务平台 · 账户';
const login = document.querySelector('#login-form');
if (login) {
  const english=window.MeetPortal.language==='en';
  document.title = '登录 · 遇见科技会议服务平台';
  const identifier = login.querySelector('input[name="identifier"]');
  const password = login.querySelector('input[name="password"]');
  if (identifier) {
    identifier.placeholder = english?'Username or email':'用户名或邮箱';
    identifier.setAttribute('aria-label',english?'Username or email':'用户名或邮箱');
    identifier.autocomplete = 'username';
  }
  if (password) {
    password.placeholder = english?'Password':'密码';
    password.setAttribute('aria-label',english?'Password':'密码');
    password.autocomplete = 'current-password';
  }
  const button = document.querySelector('.login-form-button[data-provider="Indico"]');
  if (button) button.textContent = english?'Log in':'登录';
  const registration = document.querySelector('.register');
  const link = registration?.querySelector('a');
  if (link) {
    link.textContent = english?'Create an account':'创建账号';
    registration.replaceChildren(document.createTextNode(english?'New to Meet Technology? ':'还没有遇见科技账号？'),link);
  }
  const logo = document.querySelector('.header-logo');
  if (logo) logo.alt = '遇见科技 Meet Technology';
}
