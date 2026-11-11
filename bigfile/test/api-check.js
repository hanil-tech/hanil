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
 // 🔧 틀린 조각 다시 받기 — 디스크가 깨진 조각 3 만 다시 연다
 ck=other; ok((await f('POST',`/bigfile/api/reopen/${r.id}?chunks=3`)).status===404,'남의 파일은 다시 열 수 없음'); ck=mine;
 ok((await f('POST',`/bigfile/api/reopen/${r.id}?chunks=9`)).status===400,'없는 조각 번호 400');
 const ro=await (await f('POST',`/bigfile/api/reopen/${r.id}?chunks=3`)).json();
 ok(ro.reopened===1&&Buffer.from(ro.have,'base64')[0]===0b110111,'조각 3 만 「안 받음」으로');
 ok((await f('GET',`/bigfile/api/file/${r.id}/dl`)).status===404,'고치는 동안은 받기 안 됨');
 ok((await put(3,ch(3))).status===200,'조각 3 다시 보냄');
 ok((await f('POST','/bigfile/api/done/'+r.id)).status===200,'다시 완료');
 v=await (await f('POST',`/bigfile/api/verify/${r.id}`)).json();
 for(let k=0;k<100&&v.state==='work';k++){await new Promise(z=>setTimeout(z,50)); v=await (await f('GET',`/bigfile/api/verify/${r.id}`)).json();}
 ok(v.result&&v.result.ok&&v.result.sha256===sha,'고친 뒤 검사 합격 · SHA-256 = 원본');
 // 디스크가 더 길어졌으면 잘라 낸다
 fs.appendFileSync(bin,Buffer.alloc(100));
 await f('POST',`/bigfile/api/reopen/${r.id}?chunks=5`); await put(5,ch(5)); await f('POST','/bigfile/api/done/'+r.id);
 ok(fs.statSync(bin).size===data.length,'디스크 꼬리 잘라 냄');
 // ── 📁 폴더 ──
 const PUTG=(body)=>f('PUT','/bigfile/api/group',{body:JSON.stringify(body),h:{'content-type':'text/plain;charset=UTF-8'}});
 ok((await PUTG({name:'x',entries:[{p:'../../etc/passwd',s:1}]})).status===400,'폴더: 「..」 경로 막음');
 const A=crypto.randomBytes(2500000), Bf=crypto.randomBytes(10), C=Buffer.alloc(0), D=crypto.randomBytes(1048576*2+3);
 const tree={'도면/부품 A.stp':A,'도면/하위/b.txt':Bf,'빈파일.txt':C,'c.bin':D};
 const man={name:'현장 자료',entries:[...Object.entries(tree).map(([p,b])=>({p,s:b.length,lm:1700000000000})),{p:'도면/빈 폴더',d:1}]};
 let G=await (await PUTG(man)).json();
 ok(G.gid&&!G.resumed&&G.entries.length===5,'폴더 목록표 받음 (5개)');
 const upF=async(p,b,skipChunk)=>{ const q=await (await f('POST',`/bigfile/api/init?g=${G.gid}&p=${encodeURIComponent(p)}&size=${b.length}&lm=1700000000000`)).json();
   for(let i=0;i<q.n;i++){ if(i===skipChunk) continue; const c=b.subarray(i*1048576,(i+1)*1048576); await f('PUT',`/bigfile/api/chunk/${q.id}/${i}`,{body:c,h:{'x-crc32':crc32(c).toString(16)}}); }
   return [q, await f('POST','/bigfile/api/done/'+q.id)]; };
 await upF('도면/부품 A.stp',A); await upF('도면/하위/b.txt',Bf); await upF('빈파일.txt',C);
 let gd=await f('POST','/bigfile/api/gdone/'+G.gid); let gj=await gd.json();
 ok(gd.status===409&&gj.missing.length===1&&gj.missing[0]==='c.bin','다 올림 전에 빠진 파일(c.bin)을 찾아냄');
 // 끊긴 척 — 다시 같은 폴더를 고르면 이어 감
 const G2=await (await PUTG(man)).json();
 ok(G2.gid===G.gid&&G2.resumed&&G2.entries.filter(e=>e.state==='done').length===3,'같은 폴더 다시 고름 → 이어 감(3개는 이미 있음)');
 await upF('c.bin',D);
 gd=await f('POST','/bigfile/api/gdone/'+G.gid); ok(gd.status===200,'폴더 다 올림');
 let gv=await (await f('POST',`/bigfile/api/gverify/${G.gid}`)).json();
 for(let k=0;k<200&&gv.state==='work';k++){await new Promise(r2=>setTimeout(r2,50)); gv=await (await f('GET',`/bigfile/api/gverify/${G.gid}`)).json();}
 ok(gv.state==='done'&&gv.ok===4&&!gv.badCount&&!gv.missingCount,'폴더 검사: 4개 모두 합격, 빠진 것 0');
 const gi=await (await f('GET',`/bigfile/api/group/${G.gid}?crcs=1`)).json();
 ok(gi.entries.filter(e=>!e.d).every(e=>e.crc===crc32(tree[e.p]).toString(16).padStart(8,'0')),'파일마다 전체 CRC32 = 원본');
 // ZIP
 let zz=await f('GET',`/bigfile/api/group/${G.gid}/zip`); const zb=Buffer.from(await zz.arrayBuffer());
 ok(zz.status===200&&+zz.headers.get('content-length')===zb.length,'ZIP 받기 '+zb.length+'바이트, 길이 미리 앎');
 const ZP=path.join(STORE,'check.zip'); fs.writeFileSync(ZP,zb);
 const py=require('child_process').spawnSync('python3',['-c',`import zipfile,sys,hashlib,json
zz=zipfile.ZipFile(sys.argv[1]); bad=zz.testzip(); print(json.dumps({'bad':bad,'names':zz.namelist(),'sha':{i.filename:hashlib.sha256(zz.read(i)).hexdigest() for i in zz.infolist() if not i.is_dir()}}))`,ZP],{encoding:'utf8'});
 const zr=JSON.parse(py.stdout||'{}');
 ok(zr.bad===null&&zr.names.includes('현장 자료/도면/빈 폴더/')&&Object.entries(tree).every(([p,b])=>zr.sha['현장 자료/'+p]===crypto.createHash('sha256').update(b).digest('hex')),'ZIP 을 파이썬이 열어 4개 파일 내용·빈 폴더 모두 맞음');
 zz=await f('GET',`/bigfile/api/group/${G.gid}/zip`,{h:{range:'bytes=1000-2000000'}}); const zr2=Buffer.from(await zz.arrayBuffer());
 ok(zz.status===206&&zr2.equals(zb.subarray(1000,2000001)),'ZIP 이어 받기(Range) = 전체의 그 부분');
 // 사내 공개·링크
 ck=other; ok((await f('GET',`/bigfile/api/group/${G.gid}/zip`)).status===404,'남의 폴더 ZIP 못 받음'); ck=mine;
 await f('POST',`/bigfile/api/pub/g/${G.gid}?on=1`);
 ck=other; ok((await f('GET',`/bigfile/api/group/${G.gid}/zip`)).status===200,'사내 공개 폴더는 받음');
 const fid=gi.entries.find(e=>e.p==='c.bin').id; ok((await f('GET',`/bigfile/api/file/${fid}/dl`)).status===200,'공개 폴더 안 파일 하나 받음'); ck=mine;
 const gs=await (await f('POST',`/bigfile/api/share/g/${G.gid}?days=1&max=1`)).json();
 ck=''; let sp=await f('GET','/bigfile/s/'+gs.tok); const spt=await sp.text();
 ok(spt.includes('현장 자료')&&spt.includes('도면/부품 A.stp'),'폴더 링크 화면에 파일 목록');
 zz=await f('GET',`/bigfile/s/${gs.tok}/dl`); ok(zz.status===200&&Buffer.from(await zz.arrayBuffer()).equals(zb),'링크로 ZIP 받음');
 ok((await f('GET',`/bigfile/s/${gs.tok}/dl`)).status===410,'횟수 다 쓰면 410'); ck=mine;
 l=await (await f('GET','/bigfile/api/list')).json();
 ok(l.files.some(x=>x.kind==='group'&&x.nfiles===4&&x.ndirs===1)&&!l.files.some(x=>x.kind==='file'&&x.id===fid),'목록: 폴더는 한 줄(안 파일은 따로 안 보임)');
 ok((await f('DELETE',`/bigfile/api/file/${fid}`)).status===409,'폴더 안 파일 하나만 지우기 막음');
 // 이름은 올린 그대로(: 도 그대로) · 맥의 낱자 한글(NFD)은 NFC 로 · 폴더 수 · 목록(CSV)
 const nfd='맥에서 온 이름.txt'.normalize('NFD');
 const GN=await (await PUTG({name:'이름 시험',entries:[{p:'시각 10:30 (최종) #1.txt',s:3},{p:'하위/'+nfd,s:3},{p:'하위/더/빈 폴더',d:1}]})).json();
 ok(GN.entries.some(e=>e.p==='시각 10:30 (최종) #1.txt'),'이름 그대로: 「시각 10:30 (최종) #1.txt」');
 ok(GN.entries.some(e=>e.p==='하위/맥에서 온 이름.txt'.normalize('NFC'))&&!GN.entries.some(e=>e.p.includes(nfd)),'맥의 낱자 한글 → 보통 한글(NFC)');
 for (const e of GN.entries.filter(e=>!e.d)) { const q=await (await f('POST',`/bigfile/api/init?g=${GN.gid}&p=${encodeURIComponent(e.p)}&size=3`)).json(); const c=Buffer.from('abc'); await f('PUT',`/bigfile/api/chunk/${q.id}/0`,{body:c,h:{'x-crc32':crc32(c).toString(16)}}); await f('POST','/bigfile/api/done/'+q.id); }
 ok((await f('POST','/bigfile/api/gdone/'+GN.gid)).status===200,'이름 시험 폴더 다 올림');
 l=await (await f('GET','/bigfile/api/list')).json(); const gl=l.files.find(x=>x.id===GN.gid);
 ok(gl.nfiles===2&&gl.nfolders===3&&gl.ndirs===1,'폴더 수: 하위·더·빈 폴더 = 3 (파일 2 · 빈 폴더 1)');
 const csvb=Buffer.from(await (await f('GET',`/bigfile/api/group/${GN.gid}/list.csv`)).arrayBuffer()); const csv=csvb.toString('utf8');
 ok(csvb[0]===0xef&&csvb[1]===0xbb&&csvb[2]===0xbf&&csv.includes('"이름 시험/시각 10:30 (최종) #1.txt",3')&&csv.includes('"빈 폴더","이름 시험/하위/더/빈 폴더/"')&&csv.includes('"폴더","이름 시험/하위/"'),'목록(CSV): 파일·폴더·빈 폴더 줄');
 const zn=await f('GET',`/bigfile/api/group/${GN.gid}/zip`); const znb=Buffer.from(await zn.arrayBuffer());
 ok(znb.includes(Buffer.from('이름 시험/시각 10:30 (최종) #1.txt'))&&znb.includes(Buffer.from('이름 시험/하위/더/빈 폴더/')),'ZIP 안 이름도 그대로');
 await f('DELETE',`/bigfile/api/group/${GN.gid}`);
 // 고치기(gid)로 다른 폴더를 골라도 서버 파일은 그대로
 const G4=await (await PUTG({gid:G.gid,name:'아무거나',entries:[{p:'c.bin',s:D.length,lm:1700000000000}]})).json();
 ok(G4.gid===G.gid&&G4.entries.filter(e=>!e.d).length===4&&G4.entries.every(e=>e.d||e.state==='done'),'고치기: 고른 폴더에 없는 파일도 서버에 남음(4개 그대로)');
 ok((await f('POST','/bigfile/api/gdone/'+G.gid)).status===200,'고치기 뒤 다시 다 올림');
 // 목록표가 바뀌면(파일 하나 빠지고 하나 바뀜) — 새로 올리는 폴더
 const G3=await (await PUTG({name:'현장 자료',entries:[{p:'a.txt',s:3}]})).json();
 ok(G3.gid!==G.gid,'다 올린 폴더와 같은 이름 → 새 폴더');
 ok((await f('DELETE',`/bigfile/api/group/${G3.gid}`)).status===200&&(await f('DELETE',`/bigfile/api/group/${G.gid}`)).status===200,'폴더 지우기');
 await new Promise(r2=>setTimeout(r2,300)); const left=fs.readdirSync(path.join(STORE,'data')); ok(gi.entries.filter(e=>e.id).every(e=>!left.includes(e.id+'.bin')),'폴더 파일들 디스크에서 지워짐');
 ok((await f('DELETE',`/bigfile/api/file/${r.id}`)).status===200,'지우기');
})().catch((e)=>{console.error(e);process.exitCode=1;}).finally(()=>{console.log(`\n✅ ${good} · ❌ ${bad}`);srv.close();fs.rmSync(STORE,{recursive:true,force:true});process.exit();});
