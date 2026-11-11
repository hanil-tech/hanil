package main

// 포털에 못 붙었을 때 띄우는 안내 화면 — 브라우저 기본 오류 화면 대신 쓴다.
const HELP = `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>한일 라벨 발행기</title>
<style>
 body{margin:0;background:#f4f6fa;color:#222;font:17px/1.6 "Segoe UI","Malgun Gothic",sans-serif;
      display:flex;align-items:center;justify-content:center;min-height:100vh}
 .card{background:#fff;border:1px solid #e3e8f0;border-radius:16px;padding:30px 34px;max-width:680px;width:92%}
 h1{font-size:24px;margin:0 0 6px;color:#1b2a4a}
 .sub{color:#6b7684;font-size:15px}
 ul{margin:14px 0;padding-left:20px;font-size:15px;color:#44506a}
 .row{display:flex;gap:10px;margin-top:18px;align-items:center;flex-wrap:wrap}
 button{border:1px solid #2954A5;background:#2954A5;color:#fff;border-radius:10px;padding:14px 26px;
        font:inherit;font-weight:700;cursor:pointer;font-size:19px}
 .hint{font-size:14px;color:#6b7684;margin-top:16px;border-top:1px solid #f0f2f6;padding-top:12px}
</style></head><body>
<div class="card">
  <h1>🏷 회사 포털에 연결하지 못했습니다</h1>
  <div class="sub">아래 주소로 접속해 봤습니다. 30초마다 저절로 다시 해 봅니다.</div>
  <ul>{{ROWS}}</ul>
  <div class="row">
    <button onclick="retry()">다시 시도</button>
    <span id="msg" class="sub"></span>
  </div>
  <div class="hint">
    · 랜선·와이파이가 연결되어 있는지 확인해 주세요.<br>
    · 서버가 꺼져 있을 수 있습니다. 관리자에게 알려 주세요.<br>
    · 주소를 바꾸시려면 이 프로그램 옆 <b>{{INI}}</b> 의 URL 줄을 고치면 됩니다.
    <span style="float:right">v{{VER}}</span>
  </div>
</div>
<script>
try{fetch('/__label/alive',{cache:'no-store'})}catch(e){}
var busy=false;
async function retry(){
  if(busy) return; busy=true;
  var m=document.getElementById('msg');
  m.textContent='확인 중…';
  try{
    var d=await (await fetch('/__label/retry',{cache:'no-store'})).json();
    if(d.ok){ m.textContent='연결됐습니다 — 엽니다'; location.replace(d.url); return; }
    m.textContent='아직 안 됩니다 — '+(d.tried||'');
  }catch(e){ m.textContent=e.message; }
  busy=false;
}
setInterval(retry, 30000);
</script></body></html>`
