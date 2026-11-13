//  시험용 가짜 포털 — 로그인(폼) + 진짜 fax-route.js
//   PORT=3997 INBOX=/tmp/inbox STORE=/tmp/store node fake-portal.js
//   계정: kim(관리자) / lee(직원) — 비밀번호 1234
'use strict';
const express = require('express'), session = require('express-session'), path = require('path');

function start(opts) {
  opts = opts || {};
  const app = express();
  app.use(session({ secret: 'check', resave: false, saveUninitialized: false }));
  const USERS = { kim: { username: 'kim', name: '김부장', role: 'admin' }, lee: { username: 'lee', name: '이사원' } };
  app.get('/', (req, res) => {
    if (req.session.user) return res.send('<h1>포털 첫 화면</h1>');
    res.send(`<!doctype html><meta charset=utf-8><body><h1>한일 포털 로그인</h1>
<form method="post" action="/login">${req.query.next ? '<input type=hidden name=next value="' + req.query.next + '">' : ''}<input name=username id=u><input name=password id=p type=password><button id=go>로그인</button></form></body>`);
  });
  app.post('/login', express.urlencoded({ extended: false }), (req, res) => {
    const u = USERS[req.body.username];
    if (!u || req.body.password !== '1234') return res.redirect('/?err=1');
    req.session.user = u;
    res.redirect(req.body.next || '/');
  });
  const notified = [];
  const fax = require(path.join(__dirname, '..', 'portal', 'fax-route'))(app, Object.assign({
    inbox: opts.inbox || process.env.INBOX,
    dir: opts.store || process.env.STORE,
    pollSec: 3,
    notify: async (f, x) => { notified.push({ id: f.id, url: x.url }); },
  }, opts.ctx || {}));
  return new Promise((ok) => {
    const srv = app.listen(opts.port !== undefined ? opts.port : (Number(process.env.PORT) || 3997), () => ok({ srv, fax, notified, port: srv.address().port }));
  });
}
module.exports = start;
if (require.main === module) start().then(({ port }) => console.log('가짜 포털 http://localhost:' + port + '/fax  (kim / 1234)'));
