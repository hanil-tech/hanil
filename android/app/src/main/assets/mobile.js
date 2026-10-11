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

  //  ⑤ 📱 서브 화면을 폰 너비에 맞추기 — 포털 화면은 PC 가 기본이라, 폰보다 넓은 것이 하나라도 있으면
  //     안드로이드가 화면 **전체를 작게 줄여** 보여 준다(그래서 글씨가 PC 화면처럼 깨알만 해진다).
  //   ⭐ 화면마다 따로 고치지 않고, 넓어지는 까닭 몇 가지를 모든 화면에서 한 번에 푼다:
  //     · 줄바꿈을 안 하는 머리줄·단추 줄 → 다음 줄로 넘기기
  //     · 옆으로 나란한 두 칸(목록 | 내용) → 위아래로 쌓기
  //     · PC 너비 그대로인 입력칸·그림 → 폰 너비까지만
  //     · 넓은 표 → 표만 옆으로 밀어 보기(글씨 크기는 그대로)
  //     · 그래도 남으면 줄이지 않는다(옆으로 밀어 볼 수 있게) — 글씨가 작아지는 것이 제일 나쁘다
  //   ⚠ 인쇄 미리보기(새 창·종이 화면)는 손대지 않는다 — A4 모양 그대로여야 한다.
  //   ⚠ 보이는 모양만 바꾼다. 자료·단추가 하는 일은 그대로다.
  if (!window.__hanilPopup) window.__hanilFitOn = 1;     //  포털의 「화면 전체 줄이기」는 앱에서 끈다(아래 ⑤)
  var FIT = path !== '/m' && !window.__hanilPopup && !/print|paper|preview/i.test(path);
  if (FIT) {
    //  ⚠⚠ 포털에도 「넘치면 화면 전체를 줄이는」 조각(FIT_SCRIPT)이 모든 화면에 들어 있다 — 그것이 바로
    //     폰에서 PC 화면처럼 깨알 글씨가 되는 까닭이다. 앱에서는 그 조각을 끄고(포털이 보는 깃발) 위처럼 접어 보인다.
    window.__hanilFitOn = 1;
    var fcss = 'html{-webkit-text-size-adjust:100%}'
      + 'img,video,canvas,iframe{max-width:100%!important}'
      + 'input:not([type=checkbox]):not([type=radio]),select,textarea{max-width:100%!important}'
      + 'pre,pre *{white-space:pre-wrap!important;word-break:break-word}'
      + 'button,.btn,label{word-break:keep-all}'
      + 'td,th,td *,th *{word-break:keep-all!important;overflow-wrap:normal!important}'
      + '.__hscroll{display:block;max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}'
      + '.__hscroll>table{margin:0}'
      + '.__hscroll th{white-space:nowrap}';
    try {
      var fst = document.createElement('style');
      fst.id = '__hanilFitCss';
      fst.textContent = fcss;
      (document.head || document.documentElement).appendChild(fst);
      document.documentElement.classList.add('__hfit');
    } catch (e) {}

    //  넓은 것을 찾아 고친다. ⚠ 표 안(칸 수천 개)은 들여다보지 않는다 — 표는 통째로 옆 밀기 상자에 담는다.
    var fitting = false;
    function fit() {
      if (fitting || !document.body) return;
      fitting = true;
      try {
        //  ⚠ 머리(head)를 통째로 다시 쓰는 화면이 있다 — 끼워 둔 모양이 사라졌으면 다시 붙인다
        if (!document.getElementById('__hanilFitCss')) document.head.appendChild(fst);
        if (st && !document.getElementById('__hanilAppCss')) document.head.appendChild(st);
        //  화면 맞춤 꼬리표 — 넓은 것이 남아도 화면을 줄이지 않게(옆으로 밀어 볼 수 있다)
        var mv = document.querySelector('meta[name=viewport]');
        var want = 'width=device-width,initial-scale=1,minimum-scale=1';
        if (mv && mv.content !== want) mv.content = want;
        var vw = document.documentElement.clientWidth || window.innerWidth;
        stack(vw);
        for (var pass = 0; pass < 4; pass++) {
          if (document.documentElement.scrollWidth <= vw + 1) break;
          var changed = 0;
          var tw = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, {
            acceptNode: function (n) {
              if (n.id === '__hanilMenuBox' || n.classList.contains('__hscroll')) return NodeFilter.FILTER_REJECT;
              return NodeFilter.FILTER_ACCEPT;
            }
          });
          var el, list = [];
          while ((el = tw.nextNode())) list.push(el);
          for (var i = 0; i < list.length; i++) {
            el = list[i];
            if (!el.isConnected || el.closest('.__hscroll,table table')) continue;
            var rc = el.getBoundingClientRect();
            if (!rc.width) continue;
            var over = el.scrollWidth > el.clientWidth + 1;
            if (rc.right <= vw + 1 && !over) continue;
            var cs = getComputedStyle(el);
            if (cs.position === 'fixed' || cs.display === 'none') continue;
            if (el.tagName === 'TABLE') {
              var pox = getComputedStyle(el.parentElement).overflowX;
              if ((pox === 'auto' || pox === 'scroll') && el.parentElement.getBoundingClientRect().right <= vw + 1) continue;              //  포털이 이미 밀기 상자에 담았다(.hm-scroll)
              if (rc.width > el.parentElement.clientWidth + 1 || rc.right > vw + 1) {
                var box = document.createElement('div');
                box.className = '__hscroll';
                el.parentNode.insertBefore(box, el);
                box.appendChild(el);
                changed++;
              }
              continue;
            }
            if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && rc.right <= vw + 1) continue;   //  원래 옆으로 미는 상자
            if (/flex/.test(cs.display) && cs.flexWrap === 'nowrap' && cs.flexDirection.indexOf('row') === 0 && over) {
              el.style.setProperty('flex-wrap', 'wrap', 'important');
              //  목록 | 내용 처럼 키 큰 칸은 한 줄을 다 쓰게
              [].forEach.call(el.children, function (k) {
                if (k.getBoundingClientRect().height > 360) k.style.setProperty('flex', '1 1 100%', 'important');
                k.style.setProperty('min-width', '0', 'important');
              });
              changed++;
              continue;
            }
            if (/grid/.test(cs.display) && over) {
              el.style.setProperty('grid-template-columns', 'repeat(auto-fit,minmax(min(100%,150px),1fr))', 'important');
              changed++;
              continue;
            }
            if (rc.right > vw + 1 && rc.width > vw * 0.6) {
              el.style.setProperty('max-width', '100%', 'important');
              el.style.setProperty('min-width', '0', 'important');
              el.style.setProperty('box-sizing', 'border-box', 'important');
              if (cs.whiteSpace === 'nowrap' && el.children.length === 0) el.style.setProperty('white-space', 'normal', 'important');
              changed++;
            }
          }
          if (!changed) break;
        }
      } catch (e) {}
      fitting = false;
    }
    //  나란한 칸이 폰에서 너무 좁아진 것(목록 236px | 내용 176px 같은) → 위아래로 쌓는다
    //   ⚠ 넓이가 맞아도 칸이 좁으면 글자가 세로로 한 자씩 선다 — 그래서 넘침과 따로 본다
    //   ⭐ 맨 앞의 좁은 칸(메뉴·목록)은 키를 줄여 그 안에서 밀게 한다 — 안 그러면 본문이 한참 아래로 밀린다
    function stack(vw) {
      var all = document.body.querySelectorAll('div,section,main,form,ul');
      for (var i = 0; i < all.length; i++) {
        var el = all[i];
        if (el.__hst || el.closest('#__hd,#__hanilMenuBox,.__hscroll,table')) continue;
        var rc = el.getBoundingClientRect();
        if (rc.width < 300 || rc.width > vw + 2 || rc.height < 250) continue;
        var cs = getComputedStyle(el);
        var row = /flex/.test(cs.display) && cs.flexDirection.indexOf('row') === 0 && cs.flexWrap === 'nowrap';
        var grid = /grid/.test(cs.display) && cs.gridTemplateColumns.split(' ').length > 1;
        if (!row && !grid) continue;
        var cols = [].filter.call(el.children, function (k) {
          var r = k.getBoundingClientRect();
          return r.width > 0 && r.height > 200 && getComputedStyle(k).position !== 'absolute';
        });
        if (cols.length < 2) continue;
        var narrow = cols.some(function (k) { return k.getBoundingClientRect().width < Math.min(280, rc.width * 0.62); });
        if (!narrow) continue;
        el.__hst = 1;
        if (grid) el.style.setProperty('grid-template-columns', '1fr', 'important');
        else {
          el.style.setProperty('flex-wrap', 'wrap', 'important');
          el.style.setProperty('height', 'auto', 'important');
        }
        cols.forEach(function (k, j) {
          //  포털의 PC 왼쪽 메뉴(#side) — 앱에는 아래 ☰ 전체 메뉴가 있으니 감춘다
          if (k.id === 'side' || /(^|\s)(side|sidebar|lnb)(\s|$)/.test(String(k.className))) {
            if (k.querySelector('a[href^="/"]') || !k.textContent.trim()) { k.style.setProperty('display', 'none', 'important'); return; }
          }
          k.style.setProperty('flex', '1 1 100%', 'important');
          k.style.setProperty('width', '100%', 'important');
          k.style.setProperty('max-width', '100%', 'important');
          k.style.setProperty('min-width', '0', 'important');
          k.style.setProperty('height', 'auto', 'important');
          if (j === 0 && k.getBoundingClientRect().height > 320 && cols.length > 1) {
            k.style.setProperty('max-height', '38vh', 'important');
            k.style.setProperty('overflow-y', 'auto', 'important');
            k.style.setProperty('border-bottom', '2px solid #e3e8f0', 'important');
          }
        });
      }
    }
    var fitT = 0;
    function fitSoon() { clearTimeout(fitT); fitT = setTimeout(fit, 250); }
    function fitStart() {
      fit();
      //  화면이 자료를 불러와 표·목록을 나중에 그리므로, 바뀔 때마다 다시 본다
      try { new MutationObserver(fitSoon).observe(document.body, { childList: true, subtree: true }); } catch (e) {}
      window.addEventListener('load', fitSoon);
      window.addEventListener('resize', fitSoon);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fitStart);
    else fitStart();
  }

  //  ⑥ 📄 결재 문서 — 폰용 화면(그룹웨어 앱처럼)
  //   ⭐ 위: 남색 머리줄(✕ · 결재 · ⋯) → 제목·기안자·날짜 → 결재선 → **종이를 폰 너비에 맞춰 줄인 것**
  //      → 첨부 파일 목록 → (내 차례면) 아래에 큰 「반려 · 승인」 단추. ‹ › 로 다음 문서.
  //   ⚠ 종이는 포털의 인쇄 화면(/api/appr/번호/print)을 **그대로** 줄여 보인다 — 따로 그리면 실제 종이와 달라진다.
  //   ⚠ 승인·반려는 포털 화면과 같은 길(/api/appr/번호/act)을 쓴다. 규칙은 포털이 정한다.
  if (window.top === window && !window.__hanilPopup) {
    var DV = { list: null, id: 0 };
    var dcss = '#__hd{position:fixed;inset:0;z-index:2147483600;background:#f4f6fa;display:flex;flex-direction:column;'
      + 'font-family:-apple-system,"Malgun Gothic",sans-serif;color:#1b1f27}'
      + '#__hd .hb{background:#1b2a4a;color:#fff;display:flex;align-items:center;height:56px;flex:0 0 auto}'
      + '#__hd .hb button{border:0;background:none;color:#fff;font-size:26px;width:56px;height:56px}'
      + '#__hd .hb b{flex:1;text-align:center;font-size:20px;font-weight:700}'
      + '#__hd .sc{flex:1;overflow:auto;-webkit-overflow-scrolling:touch}'
      + '#__hd .hd{background:#fff;padding:16px 16px 12px;border-bottom:1px solid #e3e8f0}'
      + '#__hd .tt{font-size:19px;font-weight:800;line-height:1.35;word-break:keep-all}'
      + '#__hd .who{color:#6b7684;font-size:15px;margin-top:6px}'
      + '#__hd .st{display:inline-block;border-radius:8px;padding:2px 9px;font-size:12.5px;font-weight:800;margin-right:6px;vertical-align:2px}'
      + '#__hd .ln{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}'
      + '#__hd .ln span{border-radius:9px;padding:3px 10px;font-size:12.5px;font-weight:700}'
      + '#__hd .pp{background:#fff;margin:10px 0;overflow:hidden;position:relative}'
      + '#__hd .pp iframe{border:0;transform-origin:0 0;display:block;background:#fff;pointer-events:none}'
      + '#__hd .pp .zm{position:absolute;right:10px;bottom:10px;background:rgba(27,42,74,.85);color:#fff;border-radius:16px;padding:5px 12px;font-size:13px}'
      + '#__hd .nv{display:flex;gap:12px;padding:4px 12px 10px}'
      + '#__hd .nv button{width:52px!important;height:52px!important;border-radius:50%!important;border:0!important;background:#2b2f36!important;color:#fff!important;font-size:26px!important;padding:0!important}'
      + '#__hd .nv button:disabled{opacity:.25}'
      + '#__hd .ft{text-align:center}#__hd .ft span{display:inline-block;background:#9cc3f0;color:#123;border-radius:10px 10px 0 0;padding:6px 22px;font-size:15px}'
      + '#__hd .fl{background:#fff;border-top:1px solid #e3e8f0}'
      + '#__hd .fl a{display:flex;align-items:center;gap:14px;padding:14px 16px;border-bottom:1px solid #eef1f5;text-decoration:none;color:#1b1f27}'
      + '#__hd .fl i{flex:0 0 40px;height:44px;border:2px solid #d93025;border-radius:6px;color:#d93025;font:800 11px/40px sans-serif;text-align:center;font-style:normal}'
      + '#__hd .fl b{display:block;font-size:16px;font-weight:600;word-break:break-all}#__hd .fl small{color:#6b7684;font-size:13px}'
      + '#__hd .cm{background:#fff;margin-top:10px;padding:12px 16px;font-size:14px;color:#3a4150}'
      + '#__hd .ab{flex:0 0 auto;display:flex;gap:10px;padding:10px 12px;background:#fff;border-top:1px solid #e3e8f0}'
      + '#__hd .ab button{flex:1;height:52px;border-radius:12px;font-size:18px;font-weight:800;border:0}'
      + '#__hd .mn{position:absolute;right:8px;top:52px;background:#fff;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);overflow:hidden;z-index:3}'
      + '#__hd .mn a{display:block;padding:14px 20px;font-size:16px;color:#1b1f27;text-decoration:none;border-bottom:1px solid #eef1f5}'
      + '#__hd .msg{padding:40px 20px;text-align:center;color:#6b7684}';
    var STATE = { ing: ['결재 중', '#e8f0fe', '#2954A5'], done: ['결재 완료', '#e6f4e6', '#1a7f37'], reject: ['반려', '#fdeeee', '#b3261e'], draft: ['임시', '#eef1f7', '#5a6478'], cancel: ['회수', '#eef1f7', '#5a6478'] };
    function human(n) { return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : (n / 1024).toFixed(1) + ' KB'; }
    async function dlist() {
      if (DV.list) return DV.list;
      try {
        var r = await (await fetch('/api/apprdoc/list', { cache: 'no-store' })).json();
        DV.list = [].concat(r.mine || [], r.waiting || [], r.done || []).map(function (x) { return x.id; });
      } catch (e) { DV.list = []; }
      return DV.list;
    }
    function closeDoc(fromPop) {
      var b = document.getElementById('__hd');
      if (!b) return;
      b.remove();
      if (!fromPop && history.state && history.state.__hd) history.back();
    }
    window.addEventListener('popstate', function () { closeDoc(true); });
    window.__hanilDoc = async function (id) {
      id = Number(id);
      if (!id) return;
      if (!document.getElementById('__hanilDocCss')) {
        var st2 = document.createElement('style');
        st2.id = '__hanilDocCss';
        st2.textContent = dcss;
        document.head.appendChild(st2);
      }
      var box = document.getElementById('__hd');
      if (!box) {
        box = document.createElement('div');
        box.id = '__hd';
        document.body.appendChild(box);
        try { history.pushState({ __hd: 1 }, ''); } catch (e) {}       //  안드로이드 뒤로 가기 → 이 화면만 닫힌다
      }
      DV.id = id;
      box.innerHTML = '<div class="hb"><button id="__hdX">✕</button><b>결재</b><button id="__hdM">⋯</button></div>'
        + '<div class="sc" id="__hdS"><div class="msg">불러오는 중…</div></div>';
      document.getElementById('__hdX').onclick = function () { closeDoc(false); };
      var d;
      try {
        var r = await fetch('/api/appr/' + id, { cache: 'no-store' });
        d = await r.json();
        if (!r.ok || d.ok === false) throw new Error(d.error || ('HTTP ' + r.status));
      } catch (e) {
        document.getElementById('__hdS').innerHTML = '<div class="msg">문서를 열지 못했습니다<br><small>' + esc(e.message) + '</small></div>';
        return;
      }
      if (DV.id !== id) return;
      var doc = d.doc || {};
      var stt = STATE[doc.state] || [doc.state || '', '#eef1f7', '#5a6478'];
      //  첨부 — 종이 안의 링크에서 뽑는다(포털의 fileListOf 와 같은 잣대)
      var files = [], seen = {};
      String(d.body || '').replace(/href\s*=\s*"(\/api\/appr\/file\/[^"?]+)[^"]*"[^>]*>([\s\S]*?)<\/a>/gi, function (m, u, t) {
        if (!seen[u]) { seen[u] = 1; files.push({ url: u, name: t.replace(/<[^>]+>/g, '').replace(/^\s*📎\s*/, '').trim() || u.split('/').pop() }); }
      });
      String(d.body || '').replace(/href\s*=\s*"\/pdfview\?src=([^"&]+)[^"]*"[^>]*>([\s\S]*?)<\/a>/gi, function (m, enc, t) {
        var u = ''; try { u = decodeURIComponent(enc); } catch (e) {}
        if (u && !seen[u]) { seen[u] = 1; files.push({ url: u, name: t.replace(/<[^>]+>/g, '').replace(/^\s*📎\s*/, '').trim() || u.split('/').pop() }); }
      });
      var line = (d.steps || []).filter(function (x) { return x.role !== '작성'; });
      var memos = (d.steps || []).filter(function (x) { return x.memo || x.comment; });
      var h = '<div class="hd"><div class="tt">🏷 ' + esc(doc.title || '(제목 없음)') + '</div>'
        + '<div class="who"><span class="st" style="background:' + stt[1] + ';color:' + stt[2] + '">' + esc(stt[0]) + '</span>'
        + '👤 ' + esc(doc.drafter_name || doc.drafter || '') + ' · ' + esc(doc.created_at || '') + '</div>'
        + '<div class="who" style="font-size:13px;margin-top:3px">' + esc(doc.kind_label || '') + (doc.doc_no ? ' · ' + esc(doc.doc_no) : '') + '</div>'
        + (line.length ? '<div class="ln">' + line.map(function (x) {
          var c = x.state === 'ok' ? ['#e6f4e6', '#1a7f37', '✓'] : (x.state === 'reject' ? ['#fdeeee', '#b3261e', '✕'] : (x.role === '참조' ? ['#f3f0fb', '#6a4fb3', '👁'] : ['#eef1f7', '#5a6478', '●']));
          return '<span style="background:' + c[0] + ';color:' + c[1] + '">' + c[2] + ' ' + esc(x.role || '') + ' ' + esc(x.name || x.username || '') + '</span>';
        }).join('') + '</div>' : '')
        + '</div>'
        + '<div class="pp" id="__hdP"><div class="msg">종이를 불러오는 중…</div></div>'
        + '<div class="nv"><button id="__hdPrev">‹</button><button id="__hdNext">›</button></div>';
      if (memos.length) {
        h += '<div class="cm"><b>💬 결재 의견</b>' + memos.map(function (x) {
          return '<div style="margin-top:6px"><b>' + esc(x.name || '') + '</b> ' + esc(x.memo || x.comment || '') + '</div>';
        }).join('') + '</div>';
      }
      if (files.length) {
        h += '<div class="ft" style="margin-top:12px"><span>' + files.length + ' files</span></div><div class="fl">'
          + files.map(function (f, i) {
            var ext = (f.name.split('.').pop() || '').toLowerCase();
            var href = ext === 'pdf' ? '/pdfview?src=' + encodeURIComponent(f.url) + '&name=' + encodeURIComponent(f.name)
              : (/^(png|jpe?g|gif|webp)$/.test(ext) ? f.url : f.url + '?dl=1');
            return '<a href="' + esc(href) + '"' + (ext === 'pdf' || /^(png|jpe?g|gif|webp)$/.test(ext) ? ' target="_blank"' : '') + '>'
              + '<i style="' + (ext === 'pdf' ? '' : 'border-color:#5a6478;color:#5a6478') + '">' + esc(ext.toUpperCase().slice(0, 4)) + '</i>'
              + '<span><b>' + esc(f.name) + '</b><small id="__hdF' + i + '"></small></span></a>';
          }).join('') + '</div>';
      }
      h += '<div style="height:20px"></div>';
      document.getElementById('__hdS').innerHTML = h;
      //  첨부 크기 — 받지 않고 머리만 묻는다
      files.forEach(function (f, i) {
        fetch(f.url, { method: 'HEAD' }).then(function (r) {
          var n = Number(r.headers.get('content-length')) || 0;
          var el = document.getElementById('__hdF' + i);
          if (el && n) el.textContent = human(n);
        }).catch(function () {});
      });
      //  ⋯ 메뉴
      document.getElementById('__hdM').onclick = function () {
        var old = box.querySelector('.mn');
        if (old) { old.remove(); return; }
        var mn = document.createElement('div');
        mn.className = 'mn';
        mn.innerHTML = '<a href="/api/appr/' + id + '/print" target="_blank">🔍 종이 크게 보기 · 인쇄</a>'
          + '<a href="/approval?doc=' + id + '&pc=1">🖥 PC 화면으로 보기</a>';
        box.appendChild(mn);
        mn.onclick = function () { mn.remove(); };
      };
      //  종이 — 인쇄 화면을 그대로 띄우고 폰 너비에 맞춰 줄인다
      var pp = document.getElementById('__hdP');
      var fr = document.createElement('iframe');
      fr.src = '/api/appr/' + id + '/print';
      fr.style.width = '820px';
      fr.style.height = '1100px';
      fr.onload = function () {
        try {
          var fd = fr.contentDocument;
          var s3 = fd.createElement('style');
          s3.textContent = '.noprint,.ppbar{display:none!important}html,body{margin:0!important;background:#fff!important}';
          fd.head.appendChild(s3);
          var w = Math.max(fd.documentElement.scrollWidth, 600);
          fr.style.width = w + 'px';
          var ht = fd.documentElement.scrollHeight;
          fr.style.height = ht + 'px';
          var k = pp.clientWidth / w;
          fr.style.transform = 'scale(' + k + ')';
          pp.style.height = Math.ceil(ht * k) + 'px';
          var m = pp.querySelector('.msg');
          if (m) m.remove();
        } catch (e) {}
      };
      pp.appendChild(fr);
      //  종이를 누르면 크게(손가락으로 늘려 볼 수 있는 창)
      var zm = document.createElement('div');
      zm.className = 'zm';
      zm.textContent = '🔍 눌러서 크게';
      pp.appendChild(zm);
      pp.onclick = function () { _open.call(window, '/api/appr/' + id + '/print', '_blank'); };
      //  ‹ › 다음 문서
      var ids = await dlist();
      var at = ids.indexOf(id);
      var pv = document.getElementById('__hdPrev'), nx = document.getElementById('__hdNext');
      if (pv && nx) {
        pv.disabled = at <= 0;
        nx.disabled = at < 0 || at >= ids.length - 1;
        pv.onclick = function () { if (at > 0) window.__hanilDoc(ids[at - 1]); };
        nx.onclick = function () { if (at >= 0 && at < ids.length - 1) window.__hanilDoc(ids[at + 1]); };
      }
      //  내 차례면 승인·반려
      if (d.my_turn) {
        var ab = document.createElement('div');
        ab.className = 'ab';
        ab.innerHTML = '<button id="__hdRej" style="background:#fdeeee;color:#b3261e">반려</button>'
          + '<button id="__hdOk" style="background:#2954A5;color:#fff">승인</button>';
        box.appendChild(ab);
        var act = async function (kind) {
          var note = '';
          if (kind === 'reject') {
            note = prompt('반려 사유를 적어 주세요');
            if (!note) return;
          } else if (!confirm('이 문서를 승인할까요?')) return;
          try {
            var r2 = await fetch('/api/appr/' + id + '/act', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ act: kind, comment: note }) });
            var j = await r2.json();
            if (!r2.ok || j.ok === false) throw new Error(j.error || '실패');
            DV.list = null;
            alert(kind === 'reject' ? '반려했습니다.' : '승인했습니다.');
            window.__hanilDoc(id);
            try { if (typeof loadDocs === 'function') loadDocs(); if (typeof load === 'function') load(); } catch (e) {}
          } catch (e) { alert(e.message); }
        };
        document.getElementById('__hdOk').onclick = function () { act('ok'); };
        document.getElementById('__hdRej').onclick = function () { act('reject'); };
      }
    };

    //  여는 길 세 가지를 이 화면으로 돌린다
    //   ① 결재함의 「문서 결재」 — window.open('/api/appr/번호/print')
    var _open = window.open;
    window.open = function (u) {
      var m = /\/api\/appr\/(\d+)\/print(?:$|[?#])/.exec(String(u || ''));
      if (m && !document.getElementById('__hd')) { window.__hanilDoc(m[1]); return null; }
      return _open.apply(window, arguments);
    };
    //   ② /approval?doc=번호 · 문서 링크
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[href]');
      if (!a || a.closest('#__hd')) return;
      var m = /\/approval\?(?:.*&)?doc=(\d+)/.exec(a.getAttribute('href') || '') || /\/api\/appr\/(\d+)\/print(?:$|[?#])/.exec(a.getAttribute('href') || '');
      if (m && !/[?&]pc=1/.test(a.getAttribute('href'))) { e.preventDefault(); e.stopPropagation(); window.__hanilDoc(m[1]); }
    }, true);
    //   ③ 전자결재 화면(/approval) 안에서 문서를 누를 때 — 그 화면의 openDoc 을 바꿔 낀다
    if (path === '/approval' && !/[?&]pc=1/.test(location.search)) {
      var hook = function () {
        if (typeof window.openDoc === 'function' && !window.openDoc.__h) {
          window.openDoc = function (id) { window.__hanilDoc(id); };
          window.openDoc.__h = 1;
        }
        var m = /[?&]doc=(\d+)/.exec(location.search);
        if (m && !document.getElementById('__hd')) {
          try { var ov = document.getElementById('ov'); if (ov) ov.classList.remove('on'); } catch (e) {}
          window.__hanilDoc(m[1]);
        }
      };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook);
      else hook();
    }
  }

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

  //  🔔 쪽지 알림을 눌러 들어오면(/chat#hanilc=방번호) 그 대화방을 연다 — 메신저 화면이 방 목록을 다 받은 뒤에
  var hc = /hanilc=(\d+)/.exec(location.hash || '');
  if (path === '/chat' && hc) {
    var cid = Number(hc[1]), tries = 0;
    var t = setInterval(function () {
      tries += 1;
      try {
        if (typeof selChan === 'function' && window.CHANS && CHANS.some(function (c) { return c.id === cid; })) {
          clearInterval(t);
          selChan(cid);
          history.replaceState(null, '', location.pathname);
        }
      } catch (e) {}
      if (tries > 40) clearInterval(t);
    }, 250);
  }

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
