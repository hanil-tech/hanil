// 윈도우 프로그램이 리더에게 넣어 주는 것 — window.HANIL_HOST (리더의 app.js 가 쓴다)
//  파일 읽기·저장은 이 PC 안 작은 서버(/file · /save), 대화상자·기본 앱·끝내기는 프로그램 함수(host…)
window.HANIL_HOST = (function () {
  var T = '__TOKEN__', R = null;
  var q = function (p) { return p + (p.indexOf('?') >= 0 ? '&' : '?') + 't=' + T; };
  var nameOf = function (p) { return p.split(/[\\/]/).pop(); };
  var isLocal = function (p) { return /^[A-Za-z]:[\\/]|^\\\\/.test(p || ''); };
  function openPath(p) { return R && R.openUrl(q('/file?path=' + encodeURIComponent(p)), nameOf(p), p); }
  //  창 제목 = 문서 이름
  new MutationObserver(function () { window.hostTitle && window.hostTitle(document.title); }).observe(document.querySelector('title'), { childList: true });
  return {
    name: 'windows',
    ready: function (r) {
      R = r;
      window.hostPending().then(function (list) { (list || []).forEach(openPath); });
      window.hostFirstRun().then(function (first) { if (first && R.welcome) R.welcome(); });
    },
    open: function () { return window.hostOpenDialog().then(function (ps) { return (ps || []).reduce(function (p, f) { return p.then(function () { return openPath(f); }); }, Promise.resolve()); }); },
    openPath: openPath,
    save: async function (d, bytes, asNew) {
      var path = !asNew && isLocal(d.path) ? d.path : null;
      if (!path) { path = await window.hostSaveDialog(d.name, isLocal(d.path) ? d.path : ''); if (!path) return null; }
      var r = await fetch(q('/save?path=' + encodeURIComponent(path)), { method: 'POST', body: bytes });
      if (!r.ok) throw new Error(await r.text());
      return { name: nameOf(path), path: path };
    },
    pickFolder: function () { return window.hostPickFolder(); },
    listDir: function (p) { return window.hostListDir(p); },
    associate: function () { return window.hostAssociate().then(function (m) { R && R.ask && R.ask('기본 PDF 프로그램', m.replace(/\n/g, '<br>'), { cancel: null }); }); },
    preview: function () { return window.hostPreview().then(function (m) { R && R.ask && R.ask('탐색기 미리 보기', m, { cancel: null }); }); },
    exit: function () { window.hostExit(); },
    browserPdf: function (on) { return window.hostBrowserPdf(on).then(function (m) { R && R.ask && R.ask('크롬·엣지의 PDF', m.replace(/\n/g, '<br>'), { cancel: null }); }); },
    browserPdfState: function () { return window.hostBrowserPdfState(); },
    exportHtml: function () { return window.hostExportHtml().then(function (m) { if (m && R && R.ask) R.ask('브라우저용 파일', m.replace(/\n/g, '<br>'), { cancel: null }); }); },
  };
})();
