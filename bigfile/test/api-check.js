//  📦 대용량 파일 점검 — 가짜 포털(express + 세션)을 띄워 올리기·이어 올리기·받기·공유를 API 로 시험
//   cd bigfile/test && npm i && node api-check.js
'use strict';
const path = require('path'), os = require('os'), fs = require('fs'), crypto = require('crypto');
const express = require('express'), session = require('express-session');
const route = require('../portal/bigfile-route.js'), { crc32 } = route;
const STORE = fs.mkdtempSync(path.join(os.tmpdir(), 'bigfile-check-'));
const app = express();
app.use(express.json());
app.use(session({ secret: 'check', resave: false, saveUninitialized: false }));
app.get('/login', (q, r) => { q.session.user = { id: Number(q.query.id), name: q.query.name }; r.redirect('/bigfile'); });
route(app, { dir: STORE, chunkMB: 1 });
const srv = app.listen(0);
const B = 'http://127.0.0.1:' + srv.address().port;
let ck='';
async function f(m,u,o={}){const r=await fetch(B+u,{method:m,redirect:'manual',headers:{cookie:ck,...(o.h||{})},body:o.body});const sc=r.headers.get('set-cookie');if(sc)ck=sc.split(';')[0];return r;}
let good=0,bad=0;
const ok=(c,m)=>{console.log((c?'✅ ':'❌ ')+m); if(c) good++; else { bad++; process.exitCode=1; }};
(async()=>{
 ok((await f('GET','/bigfile/api/info')).status===401,'로그인 없으면 401');
 await f('GET','/login?id=7&name=김철수');
 const data=crypto.randomBytes(5*1048576+12345);
 let r=await (await f('POST','/bigfile/api/init?name='+encodeURIComponent('도면 묶음.zip')+'&size='+data.length+'&lm=1')).json();
 ok(r.n===6&&!r.resumed,'init n=6');
 const put=(i,b,c)=>f('PUT',`/bigfile/api/chunk/${r.id}/${i}`,{body:b,h:{'x-crc32':(c??crc32(b)).toString(16),'content-type':'application/octet-stream'}});
 const ch=i=>data.subarray(i*1048576,Math.min(data.length,(i+1)*1048576));
 ok((await put(3,ch(3),123)).status===422,'CRC 틀리면 422');
 ok((await put(2,ch(2).subarray(0,100))).status===400,'짧은 조각 400');
 ok((await put(1,Buffer.concat([ch(1),Buffer.alloc(10)]))).status===413,'긴 조각 413');
 for(const i of [5,3,0]) ok((await put(i,ch(i))).status===200,'조각 '+i);
 ok((await f('POST','/bigfile/api/done/'+r.id)).status===409,'빠진 조각 있으면 409');
 const r2=await (await f('POST','/bigfile/api/init?name='+encodeURIComponent('도면 묶음.zip')+'&size='+data.length+'&lm=1')).json();
 const have=Buffer.from(r2.have,'base64')[0];
 ok(r2.resumed&&r2.id===r.id&&have===0b101001,'이어 올리기: 받은 조각 0,3,5');
 await Promise.all([1,2,4].map(i=>put(i,ch(i))));
 ok((await put(1,ch(1))).status===200,'같은 조각 다시 보내도 괜찮음');
 const d=await (await f('POST','/bigfile/api/done/'+r.id)).json();
 ok(d.file&&d.file.state==='done','완료');
 let g=await f('GET',`/bigfile/api/file/${r.id}/dl`); const body=Buffer.from(await g.arrayBuffer());
 ok(g.status===200&&body.equals(data),'받기 전체 일치 '+body.length);
 ok(/filename\*=UTF-8''%EB%8F%84%EB%A9%B4/.test(g.headers.get('content-disposition')),'한글 파일 이름 '+g.headers.get('content-disposition'));
 g=await f('GET',`/bigfile/api/file/${r.id}/dl`,{h:{range:'bytes=1000000-'}}); const tail=Buffer.from(await g.arrayBuffer());
 ok(g.status===206&&tail.equals(data.subarray(1000000)),'이어 받기 206 '+g.headers.get('content-range'));
 g=await f('GET',`/bigfile/api/file/${r.id}/dl`,{h:{range:'bytes=-10'}}); ok(Buffer.from(await g.arrayBuffer()).equals(data.subarray(-10)),'끝 10바이트');
 g=await f('GET',`/bigfile/api/file/${r.id}/dl`,{h:{range:'bytes=99999999-'}}); ok(g.status===416,'범위 밖 416');
 // 다른 사람
 const mine=ck; ck=''; await f('GET','/login?id=8&name=이영희');
 ok((await f('GET',`/bigfile/api/file/${r.id}/dl`)).status===404,'남의 비공개 파일은 못 받음');
 ok((await f('DELETE',`/bigfile/api/file/${r.id}`)).status===404,'남의 파일 못 지움');
 const other=ck; ck=mine;
 await f('POST',`/bigfile/api/pub/${r.id}?on=1`);
 ck=other; ok((await f('GET',`/bigfile/api/file/${r.id}/dl`)).status===200,'사내 공개 후 받음');
 let l=await (await f('GET','/bigfile/api/list')).json(); ok(l.files.length===1&&!l.files[0].mine&&l.files[0].shares.length===0,'목록: 남의 공개 파일, 링크 안 보임');
 ck=mine;
 const s=await (await f('POST',`/bigfile/api/share/${r.id}?days=3&max=2`)).json();
 ck='';
 let p=await f('GET','/bigfile/s/'+s.tok); ok(p.status===200&&(await p.text()).includes('도면 묶음.zip'),'링크 화면(로그인 없이)');
 for(let k=0;k<2;k++){g=await f('GET',`/bigfile/s/${s.tok}/dl`); ok(g.status===200&&Buffer.from(await g.arrayBuffer()).equals(data),'링크로 받기 '+(k+1));}
 ok((await f('GET',`/bigfile/s/${s.tok}/dl`)).status===410,'횟수 다 쓰면 410');
 ok((await f('GET','/bigfile/s/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA')).status===404,'없는 링크 404');
 ok((await f('GET','/bigfile/view')).status===302,'화면: 로그인 없으면 로그인으로');
 ok((await f('GET','/bigfile/api/file/../../server.js/dl')).status!==200,'경로 넘기 안 됨');
 ck=mine;
 const z=await (await f('POST','/bigfile/api/init?name=empty.txt&size=0')).json();
 ok((await f('POST','/bigfile/api/done/'+z.id)).status===200,'빈 파일');
 g=await f('GET',`/bigfile/api/file/${z.id}/dl`); ok(g.status===200&&(await g.arrayBuffer()).byteLength===0,'빈 파일 받기');
 ok((await f('POST','/bigfile/api/init?name=x&size=99999999999999')).status===413,'너무 큰 파일 413');
 // 🔍 검사
 let v=await (await f('POST',`/bigfile/api/verify/${r.id}`)).json();
 for(let k=0;k<100&&v.state==='work';k++){await new Promise(z=>setTimeout(z,50)); v=await (await f('GET',`/bigfile/api/verify/${r.id}`)).json();}
 const sha=crypto.createHash('sha256').update(data).digest('hex');
 ok(v.state==='done'&&v.result.ok&&v.result.badCount===0&&v.result.compared===6,'서버 검사 합격(조각 6개 비교)');
 ok(v.result.sha256===sha,'서버 SHA-256 = 원본');
 ok(v.result.crc===crc32(data).toString(16).padStart(8,'0'),'서버 전체 CRC32 = 원본');
 const cr=await (await f('GET',`/bigfile/api/crcs/${r.id}`)).json();
 const cb=Buffer.from(cr.crcs,'base64'); let same=true; for(let i=0;i<6;i++) if(cb.readUInt32LE(i*4)!==crc32(ch(i))) same=false;
 ok(cr.n===6&&same,'조각 CRC 목록 = 원본 조각');
 // 디스크에서 파일이 바뀌면 검사가 잡아낸다
 const bin=path.join(STORE,'data',r.id+'.bin'); const fd=fs.openSync(bin,'r+'); fs.writeSync(fd,Buffer.from([0x55^data[3*1048576+7]]),0,1,3*1048576+7); fs.closeSync(fd);
 v=await (await f('POST',`/bigfile/api/verify/${r.id}?again=1`)).json();
 for(let k=0;k<100&&v.state==='work';k++){await new Promise(z=>setTimeout(z,50)); v=await (await f('GET',`/bigfile/api/verify/${r.id}`)).json();}
 ok(v.result&&!v.result.ok&&v.result.badCount===1&&v.result.bad[0]===3,'디스크에서 깨진 조각 3 을 찾아냄');
 l=await (await f('GET','/bigfile/api/list')).json(); ok(l.files.find(x=>x.id===r.id).v.ok===false,'목록에 검사 결과');
 ok((await f('DELETE',`/bigfile/api/file/${r.id}`)).status===200,'지우기');
})().catch((e)=>{console.error(e);process.exitCode=1;}).finally(()=>{console.log(`\n✅ ${good} · ❌ ${bad}`);srv.close();fs.rmSync(STORE,{recursive:true,force:true});process.exit();});
