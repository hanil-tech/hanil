//  시험용 가짜 포털 — express + 세션 + bigfile. FLAKY=0.1 이면 조각 올리기·받기의 10%(처음 한 번)를 중간에 끊는다.
'use strict';
const express = require('express'), session = require('express-session'), path = require('path');
const app = express();
app.use(express.json());
app.use(session({ secret: 'check', resave: false, saveUninitialized: false }));
const RATE = +process.env.FLAKY || 0, seen = new Set(); let cuts = 0;
app.use((req, res, next) => {
  if (!RATE) return next();
  const up = req.method === 'PUT' && req.path.startsWith('/bigfile/api/chunk/'), down = req.method === 'GET' && /\/dl$/.test(req.path) && req.headers.range;
  if (!up && !down) return next();
  const k = req.method + req.path + (req.headers.range || '');
  if (seen.has(k) || Math.random() >= RATE) { seen.add(k); return next(); }
  seen.add(k); cuts++;
  if (up) { setTimeout(() => req.socket.destroy(), Math.random() * 200); return next(); }
  const w = res.write.bind(res); let n = 0; const lim = Math.random() * 4e6;
  res.write = (c, ...a) => { n += c.length; if (n > lim) { req.socket.destroy(); return false; } return w(c, ...a); };
  next();
});
app.get('/__cuts', (q, r) => r.json({ cuts }));
app.get('/login', (q, r) => { q.session.user = { id: Number(q.query.id || 1), name: q.query.name || '홍길동', role: q.query.admin ? 'admin' : 'user' }; r.redirect('/bigfile'); });
app.get('/', (q, r) => r.send('portal home'));
require(path.join(__dirname, '..', 'portal', 'bigfile-route.js'))(app, { dir: process.env.STORE });
app.listen(process.env.PORT || 3999);
