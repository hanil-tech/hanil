/*  📱 한일 포털 앱 — 폰 화면 손보기 (앱이 포털 화면마다 끼워 넣는다)
 *   ⭐ 포털은 PC 화면이 기본이라 폰에서는 좁고 겹친다. 앱 안에서만 이렇게 바꾼다:
 *     ① 오른쪽 아래 둥근 단추 무더기(검색·알림·도움말·메모)를 감춘다 — 앱 아래 탭이 그 일을 한다
 *     ② 첫 화면(/m)의 큰 카드를 한 줄에 둘씩 — 스크롤을 줄인다
 *     ③ ☰ 메뉴 — 포털의 전체 메뉴를 폰용 목록(큰 줄 · 찾기)으로 보인다
 *     ④ 아래 탭의 빨간 숫자(결재·메신저·할 일)를 센다
 *   ⚠ 포털 자료는 건드리지 않는다 — 보이는 모양만 바꾼다. */
(function () {
  if (window.__hanilApp) return;
  window.__hanilApp = 1;
  var path = location.pathname;

  //  ① ② 모양
  var css = ''
    + '#__hanilDockBox,#mlBtn,#__hanilVer{display:none!important}'
    + 'html{-webkit-text-size-adjust:100%}';
  if (path === '/m') {
    //  ⚠ 포털의 폰 모양(.grid 를 한 줄로)이 나중에 붙어 같은 무게면 진다 → 더 구체적으로 적는다
    css += 'html body div.wrap > div.grid{grid-template-columns:1fr 1fr!important;gap:10px!important}'
      + 'html body div.wrap a.tile{padding:16px 8px 12px!important}html body div.wrap a.tile .ic{font-size:34px!important}'
      + 'html body div.wrap > div.more{grid-template-columns:repeat(3,1fr)!important}'
      + 'html body div.wrap > div.more a{padding:14px 4px!important;font-size:13.5px!important}'
      + 'html body div.wrap{padding-bottom:16px!important}';
  }
  try {
    var st = document.createElement('style');
    st.id = '__hanilAppCss';
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  } catch (e) {}

  //  ③ 폰용 전체 메뉴
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function readMenu(doc) {
    var nav = doc.getElementById('side');
    if (!nav) return [];
    var groups = [], cur = null;
    [].forEach.call(nav.children, function (e) {
      if (e.classList && e.classList.contains('pt-sg')) {
        cur = { name: e.textContent.replace(/[▾▸]/g, '').trim(), items: [] };
        groups.push(cur);
      } else if (e.tagName === 'A' && e.classList.contains('pt-sl')) {
        var a = e.cloneNode(true);
        [].forEach.call(a.querySelectorAll('.pt-no,.pt-star,.st,svg'), function (x) { x.remove(); });
        var t = a.textContent.replace(/[☆★]/g, '').trim();
        var href = e.getAttribute('href') || '';
        if (!t || !href || href.charAt(0) !== '/') return;
        if (!cur) { cur = { name: '', items: [] }; groups.push(cur); }
        cur.items.push({ t: t, href: href });
      }
    });
    return groups.filter(function (g) { return g.items.length; });
  }
  async function loadMenu() {
    try {
      var c = sessionStorage.getItem('__hanilMenu');
      if (c) return JSON.parse(c);
    } catch (e) {}
    var html = await (await fetch('/', { credentials: 'same-origin', cache: 'no-store' })).text();
    var g = readMenu(new DOMParser().parseFromString(html, 'text/html'));
    try { if (g.length) sessionStorage.setItem('__hanilMenu', JSON.stringify(g)); } catch (e) {}
    return g;
  }
  window.__hanilMenu = async function () {
    var old = document.getElementById('__hanilMenuBox');
    if (old) { old.remove(); return; }
    var box = document.createElement('div');
    box.id = '__hanilMenuBox';
    box.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#f4f6fa;display:flex;flex-direction:column;'
      + 'font-family:-apple-system,"Malgun Gothic",sans-serif;color:#1b1f27';
    box.innerHTML = '<div style="background:#1b2a4a;color:#fff;padding:14px 14px 12px;display:flex;align-items:center;gap:10px">'
      + '<b style="font-size:19px;flex:1">☰ 전체 메뉴</b>'
      + '<button id="__hmX" style="border:0;background:#2b3d63;color:#fff;border-radius:10px;padding:9px 14px;font-size:16px">✕ 닫기</button></div>'
      + '<div style="padding:10px 12px;background:#fff;border-bottom:1px solid #e3e8f0">'
      + '<input id="__hmQ" placeholder="🔍 메뉴 찾기 (예: 라벨, 결재, 출하)" style="width:100%;box-sizing:border-box;border:2px solid #e3e8f0;'
      + 'border-radius:12px;padding:12px 14px;font-size:17px;outline:0"></div>'
      + '<div id="__hmL" style="flex:1;overflow:auto;-webkit-overflow-scrolling:touch;padding:4px 0 24px">'
      + '<div style="padding:30px;text-align:center;color:#6b7684">불러오는 중…</div></div>';
    document.body.appendChild(box);
    document.getElementById('__hmX').onclick = function () { box.remove(); };
    var groups = [];
    try { groups = await loadMenu(); } catch (e) {}
    function draw(q) {
      q = (q || '').trim().toLowerCase();
      var h = '';
      groups.forEach(function (g) {
        var items = g.items.filter(function (it) { return !q || it.t.toLowerCase().indexOf(q) >= 0; });
        if (!items.length) return;
        h += '<div style="padding:14px 16px 6px;font-size:13px;font-weight:800;color:#2954A5">' + esc(g.name) + '</div>'
          + '<div style="background:#fff;border-top:1px solid #e3e8f0;border-bottom:1px solid #e3e8f0">';
        items.forEach(function (it, i) {
          h += '<a href="' + esc(it.href) + '" style="display:flex;align-items:center;min-height:52px;padding:0 16px;'
            + 'text-decoration:none;color:#1b1f27;font-size:17px;' + (i ? 'border-top:1px solid #f0f2f6;' : '') + '">'
            + '<span style="flex:1">' + esc(it.t) + '</span><span style="color:#c2c9d6;font-size:20px">›</span></a>';
        });
        h += '</div>';
      });
      if (!h) h = '<div style="padding:30px;text-align:center;color:#6b7684">'
        + (groups.length ? '찾은 메뉴가 없습니다' : '메뉴를 불러오지 못했습니다 — 로그인을 확인해 주세요') + '</div>';
      h += '<div style="padding:18px 16px;text-align:center"><a href="/" style="color:#6b7684;font-size:14px">🖥 PC 화면으로 보기</a></div>';
      document.getElementById('__hmL').innerHTML = h;
    }
    draw('');
    var qi = document.getElementById('__hmQ');
    qi.oninput = function () { draw(qi.value); };
  };

  //  ④ 아래 탭의 빨간 숫자 — /m 첫 화면이 세는 것과 같은 곳에서 센다(두 벌로 세면 어긋난다)
  async function badges() {
    if (!window.HanilApp || !HanilApp.badges) return;
    var appr = 0, todo = 0, chat = 0;
    try {
      var d = await (await fetch('/api/my-today', { cache: 'no-store' })).json();
      (d.items || []).forEach(function (x) {
        var n = Number(x.n) || 0;
        if (x.key === 'appr') appr = n;
        todo += n;
      });
    } catch (e) {}
    try {
      var d2 = await (await fetch('/api/chat/channels', { cache: 'no-store' })).json();
      chat = (d2.channels || d2 || []).reduce(function (a, c) { return a + (Number(c.unread) || 0); }, 0);
    } catch (e) {}
    try { HanilApp.badges(appr, chat, todo); } catch (e) {}
  }
  if (window.top === window) {
    badges();
    setInterval(badges, 60000);
  }
})();
