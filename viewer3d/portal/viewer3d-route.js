//  🧊 도면 보기(3D STEP·IGES · 2D DWG·DXF) 길 — 포털에 넣는 조각
//   넣는 법: 이 파일을 포털 폴더(server.js 옆)에 두고, server.js 에서 세션(express-session)이 붙은 뒤 한 줄:
//       require('./viewer3d-route')(app);
//     (로그인 안 했으면 로그인 화면으로 갔다가 돌아온다 — 도면 파일도 로그인해야 받으므로)
//   그리고 hanil-viewer3d-portal.zip 을 public/ 에 풀어 public/viewer3d/ 가 생기게 한다.
//   여는 법:  /viewer3d/view?src=<파일 주소>&name=<파일 이름>      (그냥 /viewer3d 는 파일 고르기 화면)
//       예) 메신저 첨부   /viewer3d/view?src=%2Fapi%2Fchat%2Ffile%2F123&name=bracket.stp
//           결재 첨부     /viewer3d/view?src=%2Fapi%2Fappr%2Ffile%2Fabc.dwg&name=도면.dwg
//   ⚠ 이 포털은 express.static 이 없다 — 그래서 이 길이 파일을 하나하나 내준다(정해 둔 이름만 — 다른 파일은 안 내준다).
//   ⚠ sendFile 로 내준다 — HTML 에 끼우는 포털 조각(쪽지함·단추 등)이 뷰어 화면 위에 올라오지 않게.
//   ⚠ 엔진(wasm)은 크니(3D 7MB · 2D 9MB) 브라우저가 한동안 받아 두게 한다. 판이 바뀌면 index.html 이 ?v= 로 새로 받는다.
'use strict';
const path = require('path');
const fs = require('fs');

module.exports = function mountViewer3d(app, ctx) {
  const auth = (ctx && ctx.auth) || ((q, r, n) => ((q.session && q.session.user) ? n()
    : r.redirect('/?next=' + encodeURIComponent(q.originalUrl || '/viewer3d/'))));
  const DIR = path.join(__dirname, 'public', 'viewer3d');
  const FILES = {
    'index.html': 'text/html; charset=utf-8',
    'viewer.js': 'text/javascript; charset=utf-8',
    'dwg.js': 'text/javascript; charset=utf-8',
    'occt-import-js.js': 'text/javascript; charset=utf-8',
    'occt-import-js.wasm': 'application/wasm',
    'libredwg-web.wasm': 'application/wasm',
    'license.occt.txt': 'text/plain; charset=utf-8',
    'license.occt-import-js.txt': 'text/plain; charset=utf-8',
    'license.libredwg.txt': 'text/plain; charset=utf-8',
  };
  //  ⭐ 화면 주소는 /viewer3d/view — 포털은 주소가 /view 로 끝나는 화면(미리보기)에는 공통 조각(쪽지함·단추·화면 줄이기 등)을
  //     끼우지 않는다. 다른 주소로 내주면 그 조각들이 도면 위에 올라와 돌리기·재기를 가린다(시험에서 확인).
  //  ⚠ express 는 /viewer3d 와 /viewer3d/ 를 같은 길로 본다 — 둘 다 /viewer3d/view 로 보낸다(주소 꼬리 ?src= 는 그대로)
  app.get('/viewer3d', auth, (req, res) => {
    const u = req.originalUrl || '';
    res.redirect('/viewer3d/view' + (u.indexOf('?') >= 0 ? u.slice(u.indexOf('?')) : ''));
  });
  app.get('/viewer3d/:f', auth, (req, res) => {
    if (req.params.f === 'index.html') return res.redirect('/viewer3d/view');   //  공통 조각이 안 끼는 주소로만
    const f = req.params.f === 'view' ? 'index.html' : req.params.f;
    if (!FILES[f]) return res.status(404).send('없는 파일입니다.');
    const fp = path.join(DIR, f);
    if (!fs.existsSync(fp)) return res.status(404).send('도면 보기가 아직 설치되지 않았습니다(public/viewer3d).');
    res.setHeader('Content-Type', FILES[f]);
    //  화면(index.html)은 늘 새로, 엔진·코드는 7일 받아 둔다(index.html 이 ?v=판 으로 부른다)
    res.setHeader('Cache-Control', f === 'index.html' ? 'no-cache' : 'private, max-age=604800');
    res.sendFile(fp);
  });
};
