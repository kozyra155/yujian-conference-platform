const slidesZh = [
  ['遇见科技会议服务平台\n助您轻松办会', '从会议网站到信息发布，将繁琐的会务工作化繁为简。\n为每一场学术相遇，搭建专属的线上交流空间。'],
  ['专属会议网站\n让学术交流更近一步', '集中展示会议介绍、会议日程与重要通知。\n让参会者及时了解会议信息，轻松找到所需内容。'],
  ['有序管理会务\n专注每一次学术相遇', '灵活组织网站栏目，随时更新会议内容。\n用更清晰的信息与安排，连接主办方和参会者。']
];
const slidesEn = [
  ['Meet Technology Conferences\nOrganize with ease', 'Bring your conference website and announcements together.\nCreate a dedicated space for every academic gathering.'],
  ['Your conference website\nConnect through research', 'Present introductions, schedules and announcements together.\nHelp participants find the information they need.'],
  ['Manage every detail\nFocus on the conversation', 'Organize website pages and keep your content up to date.\nConnect organizers and participants with clear information.']
];
let currentSlide = 0;
const dots = [...document.querySelectorAll('.hero-dots button')];
function showSlide(index) {
  const slides=window.MeetPortal.language==='en'?slidesEn:slidesZh;
  currentSlide = (index + slides.length) % slides.length;
  // Text nodes keep slide copy out of HTML parsing.
  for (const [selector, text] of [['#hero-title',slides[currentSlide][0]],['#hero-description',slides[currentSlide][1]]]) {
    const element = document.querySelector(selector);
    element.replaceChildren();
    text.split('\n').forEach((line,i) => {if(i) element.append(document.createElement('br'));element.append(document.createTextNode(line));});
  }
  dots.forEach((dot,i) => dot.setAttribute('aria-pressed',String(i === currentSlide)));
}
document.querySelector('.hero-prev').addEventListener('click',()=>showSlide(currentSlide-1));
document.querySelector('.hero-next').addEventListener('click',()=>showSlide(currentSlide+1));
dots.forEach((dot,i)=>dot.addEventListener('click',()=>showSlide(i)));
window.addEventListener('meet-language-change',()=>showSlide(currentSlide));
showSlide(currentSlide);

document.querySelector('#copyright-year').textContent = new Date().getFullYear();
