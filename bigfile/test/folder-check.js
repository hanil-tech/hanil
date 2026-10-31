//  📁 폴더째 큰 시험 — 실제 크로미움으로
//    끌어다 놓기(브라우저 폴더 읽기 모양 그대로·빈 폴더 포함) · 망 끊김 10%(시험 서버가 조각을 중간에 끊음) · 창 닫았다 다시 열어 이어 올리기
//    · 서버 ZIP 을 풀어 원본과 하나하나 · 폴더째 받기(끊김 + 멈췄다 이어 받기) · 맞춰 보기
//   cd bigfile/test && npm i && LANG=C.UTF-8 node folder-check.js [작업 폴더]     (처음에 1.1GB 시험 폴더를 만든다 — 디스크 4GB 쯤 필요)
//   ⚠ LANG=C.UTF-8 — 없으면 시험 브라우저가 한글 경로의 파일을 못 연다
'use strict';
const { chromium } = require('playwright'); const fs=require('fs'), path=require('path'), crypto=require('crypto'), cp=require('child_process'), os=require('os');
const S=path.resolve(process.argv[2]||path.join(os.tmpdir(),'bigfile-folder-check')), PORT=3997, B='http://127.0.0.1:'+PORT, TOP='현장 자료 2', TREE=path.join(S,'tree2',TOP);
fs.mkdirSync(S,{recursive:true});
if (!fs.existsSync(TREE)) cp.execFileSync('python3',[path.join(__dirname,'make-tree.py'),path.join(S,'tree2')],{stdio:'inherit'});
fs.rmSync(path.join(S,'store'),{recursive:true,force:true});
const srv=cp.spawn(process.execPath,[path.join(__dirname,'test-server.js')],{env:{...process.env,PORT,FLAKY:'0.1',STORE:path.join(S,'store')},stdio:'inherit'});
process.on('exit',()=>srv.kill());
let fails=0; const ok=(c,m)=>{console.log((c?'✅ ':'❌ ')+m); if(!c) fails++;};
const T0=Date.now(); const t=()=>((Date.now()-T0)/1000).toFixed(0)+'초';
const sha=f=>{const h=crypto.createHash('sha256'); const fd=fs.openSync(f,'r'); const b=Buffer.alloc(8<<20); let n; while((n=fs.readSync(fd,b,0,b.length,null))>0) h.update(b.subarray(0,n)); fs.closeSync(fd); return h.digest('hex');};
const clean=p=>p.normalize('NFC');   //  이름은 올린 그대로, 한글만 NFC(맥의 낱자 → 보통 한글)
const rels=[], empties=[];
(function w(d,pre){ const ns=fs.readdirSync(d).sort(); if(!ns.length&&pre) empties.push(pre.slice(0,-1));
  for(const n of ns){ const q=path.join(d,n); if(fs.statSync(q).isDirectory()) w(q,pre+n+'/'); else rels.push(pre+n); } })(TREE,'');
const want={}; for(const r of rels) want[clean(r)]=sha(path.join(TREE,r));
console.log(`   시험 폴더: 파일 ${rels.length}개 · 빈 폴더 ${empties.length}개 (${t()})`);
//  끌어다 놓기 — 크롬이 주는 것과 같은 모양(디렉터리 항목, readEntries 는 한 번에 100개씩, 빈 답이면 끝)으로 진짜 파일을 넣어 drop 을 일으킨다
async function dropFolder(p){
  await p.evaluate(()=>{ if(!document.getElementById('tst')){ const i=document.createElement('input'); i.type='file'; i.multiple=true; i.id='tst'; i.hidden=true; document.body.appendChild(i);} });
  await p.setInputFiles('#tst', rels.map(r=>path.join(TREE,r)));
  await p.evaluate(([top,rels,empties])=>{
    const fl=[...document.getElementById('tst').files];
    const mkDir=(name)=>({ isFile:false, isDirectory:true, name, kids:[], createReader(){ let i=0; const k=this.kids; return { readEntries(ok){ setTimeout(()=>{ const part=k.slice(i,i+100); i+=part.length; ok(part); },0); } }; } });
    const root=mkDir(top), dirs={'':root};
    const dirOf=(p)=>{ if(dirs[p]) return dirs[p]; const j=p.lastIndexOf('/'); const par=dirOf(j<0?'':p.slice(0,j)); const d=mkDir(p.slice(j+1)); par.kids.push(d); return dirs[p]=d; };
    rels.forEach((r,k)=>{ const j=r.lastIndexOf('/'); const f=fl[k]; dirOf(j<0?'':r.slice(0,j)).kids.push({ isFile:true, isDirectory:false, name:r.slice(j+1), file(ok){ setTimeout(()=>ok(f),0); } }); });
    empties.forEach(e=>dirOf(e));
    const ev=new Event('drop',{bubbles:true,cancelable:true});
    Object.defineProperty(ev,'dataTransfer',{value:{ items:[{ webkitGetAsEntry:()=>root, getAsFile:()=>null }], files:[] }});
    document.dispatchEvent(ev);
  },[TOP,rels,empties]);
}
//  원본 폴더를 브라우저 저장소(OPFS)의 '보낼곳/<이름>' 에 그대로 넣는다(빈 폴더·낱자 이름까지) — 「폴더 고르기」 대신
async function toOpfs(p, dir, name){
  await p.evaluate(()=>{ if(!document.getElementById('tst')){ const i=document.createElement('input'); i.type='file'; i.multiple=true; i.id='tst'; i.hidden=true; document.body.appendChild(i);} });
  await p.setInputFiles('#tst', rels.map(r=>path.join(dir,r)));
  await p.evaluate(async([name,rels,empt])=>{ const fl=[...document.getElementById('tst').files]; const r=await navigator.storage.getDirectory();
    const top=await (await r.getDirectoryHandle('보낼곳',{create:true})).getDirectoryHandle(name,{create:true});
    const dirOf=async(p)=>{ let d=top; for(const s of p.split('/').filter(Boolean)) d=await d.getDirectoryHandle(s,{create:true}); return d; };
    for(let k=0;k<rels.length;k++){ const j=rels[k].lastIndexOf('/'); const d=await dirOf(j<0?'':rels[k].slice(0,j)); const w=await (await d.getFileHandle(rels[k].slice(j+1),{create:true})).createWritable(); await w.write(fl[k]); await w.close(); }
    for(const e of empt) await dirOf(e);
    localStorage.__pick=name; },[name,rels,empties]);
}
const topJob=p=>p.$eval('.up',e=>({dir:e.querySelector('.dir').textContent, hd:(e.querySelector('.rep summary')||{}).textContent||'', st:e.querySelector('.st').textContent, rows:[...e.querySelectorAll('.rep tr')].map(r=>[...r.children].map(x=>x.textContent).join(' | '))}));
const pct=async p=>{ if(!(await p.$('.up'))) return -1; const s=(await topJob(p)).st; const m=s.match(/^([\d.]+)%/); return m?+m[1]:-1; };
async function waitPct(p,v,ms){ const end=Date.now()+(ms||300000); while(Date.now()<end){ if(await pct(p)>=v) return; await p.waitForTimeout(300);} throw new Error('진행이 '+v+'% 에 안 감'); }
//  망 끊김 — 조각마다 처음 한 번은 10% 쯤 끊는다
//  (시험 서버가 FLAKY=0.1 로 떠 있어 조각 올리기·받기의 10% 를 중간에 끊는다)
let cutBase=0; const cutNow=async()=>(await (await fetch(B+'/__cuts')).json()).cuts;
function flaky(){ const b0=cutBase; return ()=>'(서버 기준) '+b0; }

(async()=>{
 await new Promise(r=>setTimeout(r,1500));
 fs.rmSync(path.join(S,'prof'),{recursive:true,force:true});
 const ctx=await chromium.launchPersistentContext(path.join(S,'prof'),{acceptDownloads:true,viewport:{width:1100,height:1400}}); const b={close:()=>ctx.close()};   //  보통 프로필(시크릿 창은 브라우저 저장소가 작다)
 await ctx.addInitScript(()=>{ window.showDirectoryPicker=async(o)=>{ const r=await navigator.storage.getDirectory();
   if(o&&o.mode==='read') return (await r.getDirectoryHandle('보낼곳')).getDirectoryHandle(localStorage.__pick);      //  「폴더 고르기」 = 저장소에 넣어 둔 원본
   return r.getDirectoryHandle('받은곳',{create:true}); }; });
 const login=async()=>{ const p=await ctx.newPage(); p.on('pageerror',e=>console.log('   PAGEERR',e.message)); p.on('dialog',d=>d.accept()); await p.goto(B+'/login?id=1&name=한일관리자&admin=1'); await p.waitForSelector('#who:has-text("님")'); return p; };

 // ① 끌어다 놓아 올리기 — 망이 10% 끊기고, 40% 에서 창을 닫아 버림
 let p=await login(); let cuts=async()=>await cutNow();
 await dropFolder(p);
 await waitPct(p,40); console.log('   ① 40%: '+(await topJob(p)).st+' · 끊긴 연결 '+(await cuts())+'번 ('+t()+')');
 await p.close();                                  //  창을 닫음(브라우저 종료와 같음)
 // ② 다시 열어 같은 폴더를 다시 끌어다 놓음 → 이어 감
 p=await login();
 console.log('   ② 목록: '+(await p.textContent('#list tr')).replace(/\s+/g,' ').slice(0,100));
 await dropFolder(p);
 await p.waitForFunction(()=>document.querySelector('.up .rep, .up .st.bad'),null,{timeout:900000});
 let r=await topJob(p); console.log('   ② 끝 ('+t()+') · 끊긴 연결(지금까지) '+(await cuts())+'번');
 r.rows.forEach(x=>console.log('      '+x));
 ok(r.hd.startsWith('검사 합격'),'끌어다 놓아 올리기(망 끊김 + 창 닫았다 다시): '+r.hd);
 ok(r.rows.some(x=>x.startsWith('파일 수 | '+rels.length+'개 | '+rels.length+'개')),'파일 수 '+rels.length+' / '+rels.length);
 ok(r.rows.some(x=>x.startsWith('빈 폴더 | '+empties.length+'개 | '+empties.length+'개')),'빈 폴더 '+empties.length+' / '+empties.length);
 ok(r.rows.some(x=>/^폴더 수\(하위 폴더 모두\) \| (\d+)개 \| \1개 \| 맞음/.test(x)),'폴더 수(하위 폴더 모두) 같음: '+(r.rows.find(x=>x.startsWith('폴더 수'))||''));
 await p.screenshot({path:S+'/z1-up.png'});

 // ③ 서버에 있는 것 = 원본? — ZIP 으로 받아 풀어 하나하나
 const ck=(await ctx.cookies()).map(c=>c.name+'='+c.value).join('; ');
 const list=await (await fetch(B+'/bigfile/api/list',{headers:{cookie:ck}})).json(); const g=list.files.find(x=>x.kind==='group'&&x.name===TOP);
 const zp=path.join(S,'big2.zip'); fs.rmSync(zp,{force:true});
 cp.execSync(`curl -s -H "cookie: ${ck}" -o "${zp}" "${B}/bigfile/api/group/${g.id}/zip"`);
 const ux=path.join(S,'ux2'); fs.rmSync(ux,{recursive:true,force:true}); fs.mkdirSync(ux);
 cp.execSync(`python3 -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; z.extractall(sys.argv[2])" "${zp}" "${ux}"`,{env:{...process.env,LANG:'C.UTF-8'}});
 const got={}; (function w(d,pre){ for(const n of fs.readdirSync(d)){ const q=path.join(d,n); if(fs.statSync(q).isDirectory()) w(q,pre+n+'/'); else got[pre+n]=sha(q);} })(path.join(ux,TOP),'');
 const bad=Object.keys(want).filter(k=>got[k]!==want[k]);
 ok(Object.keys(got).length===rels.length&&!bad.length,'서버 ZIP 을 풀면 '+Object.keys(got).length+'개 모두 원본과 같음'+(bad.length?' — 다름: '+bad.slice(0,3):''));
 ok(empties.every(e=>fs.existsSync(path.join(ux,TOP,clean(e)))),'빈 폴더 '+empties.length+'개도 ZIP 안에 있음');
 ok(fs.existsSync(path.join(ux,TOP,'특수 이름','시각 10:30.txt')),'이름은 올린 그대로 (시각 10:30.txt)');
 ok(fs.existsSync(path.join(ux,TOP,'특수 이름','맥에서 만든 한글 이름.txt'.normalize('NFC'))),'맥의 낱자 한글 이름 → 보통 한글(NFC)로');
 console.log('   ③ ZIP '+(fs.statSync(zp).size/1048576).toFixed(0)+'MB ('+t()+')');
 fs.rmSync(zp,{force:true}); fs.rmSync(ux,{recursive:true,force:true});   //  자리 비움(받기 시험에 디스크가 필요)

 // ④ 폴더째 받기 — 망이 10% 끊기고, 40% 에서 멈췄다가 이어 받기
  let n0=await p.$$eval('.up',x=>x.length);
 await p.click('#list tr:has-text("'+TOP+'") button[data-a=dl]');
 await p.waitForFunction(n0=>document.querySelectorAll('.up').length>n0,n0);
 await waitPct(p,40); await p.$$eval('.up button',bs=>bs.find(x=>x.textContent==='멈춤').click()); await p.waitForTimeout(500);
 console.log('   ④ 멈춤: '+(await topJob(p)).st);
 await p.waitForTimeout(1500);
 await p.$$eval('.up button',bs=>bs.find(x=>x.textContent==='이어 받기').click());
 await p.waitForFunction(()=>document.querySelector('.up').querySelector('.rep, .st.bad'),null,{timeout:900000});
 r=await topJob(p); console.log('   ④ 끝 ('+t()+') · 끊긴 연결(지금까지) '+(await cuts())+'번'); r.rows.forEach(x=>console.log('      '+x));
 ok(r.hd.startsWith('검사 합격'),'폴더째 받기(망 끊김 + 멈췄다 이어 받기): '+(r.hd||r.st));
 const opfs=await p.evaluate(async(top)=>{ const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
   const out={}, dirs=[]; async function w(d,pre){ let n=0; for await (const [nm,h] of d.entries()){ n++; if(h.kind==='directory') await w(h,pre+nm+'/'); else { const f=await h.getFile(); out[pre+nm]=f.size>200e6?'big:'+f.size:hex(await crypto.subtle.digest('SHA-256',await f.arrayBuffer())); } } if(!n) dirs.push(pre.slice(0,-1)); }
   const r=await navigator.storage.getDirectory(); await w(await (await r.getDirectoryHandle('받은곳')).getDirectoryHandle(top),''); return {out,dirs}; },TOP);
 const bad2=Object.keys(want).filter(k=>!(opfs.out[k]===want[k]||(opfs.out[k]||'').startsWith('big:')));
 ok(Object.keys(opfs.out).length===rels.length&&!bad2.length,'받은 폴더의 '+Object.keys(opfs.out).length+'개 모두 원본과 같음'+(bad2.length?' — 다름: '+bad2.slice(0,3):''));
 ok(empties.every(e=>opfs.dirs.includes(clean(e))),'받은 폴더에 빈 폴더 '+empties.length+'개 그대로');
 await p.screenshot({path:S+'/z2-down.png'});

 // ⑤ 맞춰 보기 — 원본 폴더를 골라 서버와 하나하나
 n0=await p.$$eval('.up',x=>x.length);
 await toOpfs(p,TREE,TOP); await p.click('#list tr:has-text("'+TOP+'") button[data-a=cmp]');
 await p.waitForFunction(n0=>document.querySelectorAll('.up').length>n0 && document.querySelector('.up').querySelector('.rep'),n0,{timeout:600000});
 r=await topJob(p); r.rows.forEach(x=>console.log('      '+x));
 ok(r.hd.startsWith('검사 합격'),'맞춰 보기(원본 폴더 ↔ 서버): '+r.hd);
 ok(r.rows.some(x=>/^폴더 수\(하위 폴더 모두\) \| (\d+)개 있음 \| \1개 \| 맞음/.test(x)),'맞춰 보기: 폴더 수(빈 폴더 포함)까지 같음');
 const q=await p.evaluate(async()=>JSON.stringify(await navigator.storage.estimate())); console.log('   저장소',q);
 await b.close(); fs.rmSync(path.join(S,'prof'),{recursive:true,force:true});
 console.log(`\n끝 (${t()}) — ${fails ? '❌ '+fails+'개 틀림' : '✅ 모두 맞음'}`); process.exit(fails?1:0);
})().catch(e=>{console.error('멈춤:',e); process.exit(1);});
