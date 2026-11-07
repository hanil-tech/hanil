//  📕 한일 PDF 리더 — 크롬 확장 뒤에서 도는 부분
//   ① 웹에서 PDF 를 열면(주소가 .pdf 이거나, 서버가 「application/pdf」로 보내면) 크롬 기본 뷰어 대신 이 리더로
//   ② 내 PC 의 PDF(file://) — 「파일 URL 에 대한 액세스 허용」을 켠 경우에만
//   ③ 도구 막대 단추 → 빈 리더 · 링크 오른쪽 단추 → 「한일 PDF 리더로 열기」
//   ⚠ 크롬 기본 뷰어로 보고 싶으면 주소 끝에 ?hanilraw=1 (또는 &hanilraw=1)
const VIEWER = chrome.runtime.getURL('viewer.html');
const viewerFor = (url) => VIEWER + '?src=' + encodeURIComponent(url);

async function setRules() {
  const old = (await chrome.declarativeNetRequest.getDynamicRules()).map((r) => r.id);
  const base = [
    { id: 1, priority: 3, action: { type: 'allow' }, condition: { urlFilter: 'hanilraw=1', resourceTypes: ['main_frame'] } },
    { id: 2, priority: 1, action: { type: 'redirect', redirect: { regexSubstitution: VIEWER + '?src=\\0' } },
      condition: { regexFilter: '^https?://[^#]*\\.[pP][dD][fF]([?][^#]*)?$', resourceTypes: ['main_frame'] } },
  ];
  await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: old, addRules: base });
  //  주소에 .pdf 가 없어도 서버가 PDF 라고 알려 주면(크롬 128 부터 되는 규칙 — 옛 크롬이면 건너뜀)
  try {
    await chrome.declarativeNetRequest.updateDynamicRules({ addRules: [{
      id: 3, priority: 1, action: { type: 'redirect', redirect: { regexSubstitution: VIEWER + '?src=\\0' } },
      condition: { regexFilter: '^https?://.*$', resourceTypes: ['main_frame'], responseHeaders: [{ header: 'content-type', values: ['application/pdf', 'application/pdf;*'] }] },
    }] });
  } catch (e) { console.log('Content-Type 규칙은 이 크롬에서 안 됨:', e.message); }
}
chrome.runtime.onInstalled.addListener(() => {
  setRules();
  chrome.contextMenus.create({ id: 'open-link', title: '한일 PDF 리더로 열기', contexts: ['link'] });
  chrome.contextMenus.create({ id: 'open-page', title: '이 PDF 를 한일 PDF 리더로', contexts: ['page'], documentUrlPatterns: ['*://*/*.pdf', '*://*/*.PDF', 'file:///*'] });
});
chrome.runtime.onStartup.addListener(setRules);
chrome.contextMenus.onClicked.addListener((info, tab) => {
  const url = info.menuItemId === 'open-link' ? info.linkUrl : info.pageUrl;
  if (url) chrome.tabs.create({ url: viewerFor(url), index: tab ? tab.index + 1 : undefined });
});
chrome.action.onClicked.addListener(() => chrome.tabs.create({ url: VIEWER }));
//  내 PC 의 PDF(file://) — 크롬 기본 뷰어가 열기 전에 바꾼다
chrome.tabs.onUpdated.addListener((tabId, info) => {
  const u = info.url;
  if (!u || !/^file:\/\/.*\.pdf$/i.test(u.split(/[?#]/)[0])) return;
  chrome.extension.isAllowedFileSchemeAccess((ok) => { if (ok) chrome.tabs.update(tabId, { url: viewerFor(u) }); });
});
