# Builds the static homepage (site/*.html, site/en/, site/ja/) from the content below.
# Run: python3 site/_build/build.py
import os, html, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIL = "hanil@hanil-steel.com"

L = {
"ko": dict(
  lang="ko", fonts="family=Archivo:wdth,wght@100..125,400..500&family=Noto+Sans+KR:wght@400;500",
  title="한일특장: 버스·트럭·트랙터 외장 판금 부품 제조",
  desc="버스·트럭과 트랙터의 외장 판금 부품을 1,500톤 프레스 성형부터 용접·사상·검사까지 전북 완주 한 공장에서 만듭니다.",
  name="한일특장", skip="본문으로 건너뛰기", navlabel="주 메뉴",
  nav=[("business","사업"),("plant","설비"),("process","공정"),("customers","납품처")],
  cta="도면 보내기", subject="도면 검토 요청",
  h1="버스·트럭·트랙터의 외장 판금 부품을 만듭니다",
  lead="1,500톤 유압 프레스로 성형하고, 로봇과 숙련 용접사가 용접하고, 사상과 검사까지 전북 완주 한 공장에서 마칩니다.",
  chart_t="매출 추이", chart_u="단위: 억 원", vals=["21.3","40.2","60.4","100"], years=["2023","2024","2025","2026 목표"],
  chart_aria="연도별 매출: 2023년 21.3억 원, 2024년 40.2억 원, 2025년 60.4억 원, 2026년 목표 100억 원",
  plate=[("최대 프레스","1,500","톤"),("CO₂ 용접 로봇","11","대"),("생산 공정","8","단계"),("설립","2021","년")],
  biz_h="두 사업부, 하나의 판금 기술", biz_p="눈에 보이는 바깥 판금 패널이 중심입니다. 프레스 성형, 용접, 사상까지 마친 상태로 납품합니다.",
  segs=[
   dict(h="자동차 부품", f="버스 · 트럭 · 특수 차량", t="버스와 트럭의 외판, 냉동탑차 차체 프레스 부품을 만듭니다. 신차는 설계 단계부터 고객사와 함께 개발합니다.",
        rows=[("주요 품목","버스·트럭 외판, 냉동탑차 프레스 부품"),("납품","현대모비스, KGM커머셜"),("수주 잔고","OEM 약 3년치")]),
   dict(h="농기계 부품", f="트랙터 외장 · 작업기 부품", t="트랙터 외장이 주력입니다. 후드와 펜더처럼 크고 깊게 휜 패널을 냉연강판으로 성형해 공장 안에서 용접·사상합니다.",
        rows=[("주요 품목","프런트 로더 붐, 미드 마운트 모어, 트랙터 후드·펜더, 작업기 부품"),("납품","LS엠트론, 두산밥캣"),("수출","2025년 대만, 소형 펜더 커버 세트")]),
  ],
  plant_h="성형부터 검사까지 한 공장에서", plant_p="전단, 성형, 용접, 사상, 검사가 같은 부지에서 차례로 이어집니다.",
  eq=[
   dict(h="프레스 라인", big="1,500", unit="톤", rows=[("유압 딥드로잉","대형 패널 한 번에 성형"),("소형 프레스","150톤, 작은 부품"),("성형 단계","부품에 따라 1~4단")]),
   dict(h="용접 라인", big="11", unit="대", rows=[("CO₂ 용접 로봇","처리량과 균일한 품질"),("수동 용접","로봇이 닿지 않는 이음부"),("사상","용접 비드와 결함 제거")]),
  ],
  plant_note="공정 중간에 부품이 밖으로 나가지 않아 납기를 지킵니다. 보유 인증은 10건입니다.",
  proc_h="원자재에서 출하까지 8단계", proc_p="냉연강판이 들어와 완제품으로 나가기까지의 순서입니다.",
  steps=[("원자재 입고","강종과 두께를 확인하고 등록합니다."),("전단","작업 크기로 자르고 자투리를 줄여 배치합니다."),("성형","부품에 따라 최대 네 단계로 나눠 프레스합니다."),("용접","로봇이 대부분을, 숙련 용접사가 나머지를 맡습니다."),("사상","용접 비드와 결함을 갈아내 도장 품질을 정합니다."),("검사","치수와 외관을 확인해 합격품만 넘깁니다."),("도장","협력 도장업체가 고객 사양대로 칠합니다."),("출하","수량대로 포장해 거래명세서와 함께 보냅니다.")],
  legend=("한일특장 공장","협력업체"),
  cust_h="납품처", cust_p="각 브랜드의 1차 협력사를 통해 납품합니다.",
  cust=[("LS엠트론","트랙터 외장 부품"),("두산밥캣","농기계·작업기 부품"),("현대모비스","버스·트럭 외판"),("KGM커머셜","버스 외판")],
  cust_note="2025년에는 소형 펜더 커버 세트를 대만으로 처음 수출했습니다.",
  close_h="도면을 보내 주시면 검토해 드립니다", close_p="신규 부품 견적, 기존 부품 이관, 개발 초기 검토 모두 받습니다. 도면을 첨부해 이메일로 보내 주세요.",
  addr="전북특별자치도 완주군 봉동읍 첨단산업3로 24", tel="063-714-3663", legal="© 2026 한일특장",
),
"en": dict(
  lang="en", fonts="family=Archivo:wdth,wght@100..125,400..500",
  title="Hanil Special Equipment: exterior sheet-metal parts for buses, trucks and tractors",
  desc="Exterior sheet-metal parts for buses, trucks and tractors, press-formed on presses up to 1,500 tons, welded, finished and inspected in one plant in Wanju, Korea.",
  name="Hanil Special Equipment", skip="Skip to content", navlabel="Main",
  nav=[("business","Business"),("plant","Plant"),("process","Process"),("customers","Customers")],
  cta="Send a drawing", subject="Drawing review request",
  h1="Exterior sheet-metal parts for buses, trucks and tractors",
  lead="Formed on a 1,500-ton hydraulic press, welded by robots and skilled welders, finished and inspected in one plant in Wanju, Korea.",
  chart_t="Revenue", chart_u="KRW 100 million", vals=["21.3","40.2","60.4","100"], years=["2023","2024","2025","2026 target"],
  chart_aria="Revenue by year: 2023 KRW 2.13 billion, 2024 4.02 billion, 2025 6.04 billion, 2026 target 10 billion",
  plate=[("Largest press","1,500","t"),("CO₂ welding robots","11",""),("Process steps","8",""),("Founded","2021","")],
  biz_h="Two divisions, one sheet-metal craft", biz_p="Visible outer panels are the core. Parts ship press-formed, welded and finished.",
  segs=[
   dict(h="Automotive parts", f="Buses · trucks · special vehicles", t="Outer panels for buses and trucks, and press parts for refrigerated truck bodies. New models are developed with the customer from the design stage.",
        rows=[("Main parts","Bus and truck outer panels, refrigerated body press parts"),("Supplied to","Hyundai Mobis, KGM Commercial"),("Order backlog","About three years of OEM orders")]),
   dict(h="Agricultural machinery parts", f="Tractor exteriors · implement parts", t="Tractor exteriors are the main line. Large, deeply curved hoods and fenders are formed from cold-rolled steel, then welded and finished in-house.",
        rows=[("Main parts","Front loader booms, mid-mount mowers, tractor hoods and fenders, implement parts"),("Supplied to","LS Mtron, Doosan Bobcat"),("Export","Taiwan since 2025, small fender cover sets")]),
  ],
  plant_h="From forming to inspection in one plant", plant_p="Shearing, forming, welding, finishing and inspection run in sequence on one site.",
  eq=[
   dict(h="Press line", big="1,500", unit="t", rows=[("Hydraulic deep drawing","Large panels in a single stroke"),("Compact presses","150 t, for small parts"),("Forming stages","1 to 4, by part")]),
   dict(h="Welding line", big="11", unit="robots", rows=[("CO₂ welding robots","Throughput and even quality"),("Manual welding","Joints robots cannot reach"),("Finishing","Weld beads and defects ground away")]),
  ],
  plant_note="Nothing leaves the site mid-process, which keeps delivery dates. 10 certifications held.",
  proc_h="Eight steps from steel to shipment", proc_p="How cold-rolled steel becomes a finished part.",
  steps=[("Incoming steel","Grade and thickness checked and logged."),("Shearing","Cut to size, nested to keep offcuts low."),("Forming","Pressed in up to four stages, by part."),("Welding","Robots do the bulk; skilled welders finish the rest."),("Finishing","Beads and defects ground away for paint quality."),("Inspection","Dimensions and finish checked; only passes move on."),("Painting","Partner paint shops, to customer specification."),("Shipping","Packed to quantity with a delivery statement.")],
  legend=("Hanil plant","Partner"),
  cust_h="Customers", cust_p="Parts reach these brands through their tier-1 suppliers.",
  cust=[("LS Mtron","Tractor exterior parts"),("Doosan Bobcat","Agricultural and implement parts"),("Hyundai Mobis","Bus and truck outer panels"),("KGM Commercial","Bus outer panels")],
  cust_note="In 2025 the first export shipment of small fender cover sets went to Taiwan.",
  close_h="Send us a drawing and we will review it", close_p="New part quotations, transfers of existing parts and early development reviews are all welcome. E-mail your drawing to us.",
  addr="24, Cheomdansaneop 3-ro, Bongdong-eup, Wanju-gun, Jeonbuk State, Republic of Korea", tel="+82-63-714-3663", legal="© 2026 Hanil Special Equipment",
),
"ja": dict(
  lang="ja", fonts="family=Archivo:wdth,wght@100..125,400..500&family=Noto+Sans+JP:wght@400;500",
  title="ハンイル特装: バス・トラック・トラクターの外装板金部品メーカー",
  desc="バス・トラックとトラクターの外装板金部品を、1,500トンプレスによる成形から溶接・仕上げ・検査まで、韓国・完州の一つの工場で製造しています。",
  name="ハンイル特装", skip="本文へスキップ", navlabel="メインメニュー",
  nav=[("business","事業"),("plant","設備"),("process","工程"),("customers","納入先")],
  cta="図面を送る", subject="図面検討のご依頼",
  h1="バス・トラック・トラクターの外装板金部品をつくります",
  lead="1,500トン油圧プレスで成形し、ロボットと熟練溶接工が溶接し、仕上げと検査まで韓国・完州の一つの工場で行います。",
  chart_t="売上推移", chart_u="単位: 億ウォン", vals=["21.3","40.2","60.4","100"], years=["2023","2024","2025","2026 目標"],
  chart_aria="年度別売上: 2023年21.3億ウォン、2024年40.2億ウォン、2025年60.4億ウォン、2026年目標100億ウォン",
  plate=[("最大プレス","1,500","トン"),("CO₂溶接ロボット","11","台"),("生産工程","8","段階"),("設立","2021","年")],
  biz_h="二つの事業部、一つの板金技術", biz_p="目に見える外装の板金パネルが中心です。プレス成形、溶接、仕上げまで終えた状態で納品します。",
  segs=[
   dict(h="自動車部品", f="バス · トラック · 特装車", t="バスとトラックの外板、冷凍車ボディのプレス部品をつくります。新型車は設計段階からお客様と共同で開発します。",
        rows=[("主要品目","バス・トラック外板、冷凍車プレス部品"),("納入先","現代モービス、KGMコマーシャル"),("受注残","OEM 約3年分")]),
   dict(h="農業機械部品", f="トラクター外装 · 作業機部品", t="トラクター外装が主力です。フードやフェンダーのように大きく深く曲がったパネルを冷延鋼板で成形し、工場内で溶接・仕上げします。",
        rows=[("主要品目","フロントローダーブーム、ミッドマウントモア、トラクターのフード・フェンダー、作業機部品"),("納入先","LSエムトロン、斗山ボブキャット"),("輸出","2025年 台湾、小型フェンダーカバーセット")]),
  ],
  plant_h="成形から検査まで一つの工場で", plant_p="せん断、成形、溶接、仕上げ、検査が同じ敷地内で順に続きます。",
  eq=[
   dict(h="プレスライン", big="1,500", unit="トン", rows=[("油圧深絞り","大型パネルを一工程で成形"),("小型プレス","150トン、小物部品"),("成形段階","部品に応じて1～4段")]),
   dict(h="溶接ライン", big="11", unit="台", rows=[("CO₂溶接ロボット","処理量と均一な品質"),("手溶接","ロボットが届かない継ぎ目"),("仕上げ","溶接ビードと欠陥を除去")]),
  ],
  plant_note="工程の途中で部品が外に出ないため、納期を守れます。保有認証は10件です。",
  proc_h="材料入荷から出荷まで8段階", proc_p="冷延鋼板が入荷し、完成品として出荷されるまでの流れです。",
  steps=[("材料入荷","鋼種と板厚を確認し登録します。"),("せん断","作業サイズに切断し、端材を減らして配置します。"),("成形","部品に応じて最大4段階に分けてプレスします。"),("溶接","大部分をロボットが、残りを熟練溶接工が担います。"),("仕上げ","溶接ビードと欠陥を削り、塗装品質を整えます。"),("検査","寸法と外観を確認し、合格品のみ次へ送ります。"),("塗装","協力塗装会社がお客様の仕様どおりに塗装します。"),("出荷","数量どおりに梱包し、納品書とともに発送します。")],
  legend=("ハンイル特装 工場","協力会社"),
  cust_h="納入先", cust_p="各ブランドの一次協力会社を通じて納品しています。",
  cust=[("LSエムトロン","トラクター外装部品"),("斗山ボブキャット","農業機械・作業機部品"),("現代モービス","バス・トラック外板"),("KGMコマーシャル","バス外板")],
  cust_note="2025年には小型フェンダーカバーセットを台湾へ初めて輸出しました。",
  close_h="図面をお送りいただければ検討いたします", close_p="新規部品のお見積り、既存部品の移管、開発初期のご相談まで承ります。図面を添付してメールでお送りください。",
  addr="大韓民国 全北特別自治道 完州郡 鳳東邑 チョムダンサノプ3路 24", tel="+82-63-714-3663", legal="© 2026 ハンイル特装",
),
}

ARROW = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 8h11M9 3.5 13.5 8 9 12.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
LOGO = '<svg viewBox="0 0 28 28" aria-hidden="true"><rect x="1" y="1" width="26" height="26" rx="3" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M7 20V8l7 7 7-7v12" fill="none" stroke="#ff5a1f" stroke-width="2.2" stroke-linejoin="round"/></svg>'
PATHS = {"ko": "", "en": "en/", "ja": "ja/"}
LABEL = {"ko": "KO", "en": "EN", "ja": "JA"}
NAMES = {"ko": "한국어", "en": "English", "ja": "日本語"}

def e(s): return html.escape(s, quote=True)

X = {
 "ko": dict(boom="로더 붐", mower="미드 모어", hood="후드", fender="펜더", side="측면 외판", front="전면 외판", made="한일특장이 만드는 부품",
   tractor_alt="프런트 로더와 미드 모어를 단 트랙터 측면 도면. 한일특장이 만드는 로더 붐, 미드 모어, 후드, 펜더가 주황색으로 표시되어 있습니다.",
   bus_alt="버스 측면 도면. 한일특장이 만드는 측면·전면 외판이 주황색으로 표시되어 있습니다.",
   ticker=["프런트 로더 붐","미드 마운트 모어","트랙터 후드","트랙터 펜더","버스 측면 외판","트럭 외판","냉동탑차 프레스 부품","작업기 부품","펜더 커버 세트"],
   ticker_label="생산 품목", credits="사진 출처", alt_hero="꽃이 핀 과수원에서 프런트 로더를 단 트랙터가 밭을 가는 모습", alt_loader="프런트 로더를 단 트랙터", alt_mower="미드 마운트 모어를 단 소형 트랙터", alt_bus="도로를 달리는 시내버스", alt_weld="용접 로봇이 늘어선 생산 라인", growth_h="납품처와 성장", pause="움직임 멈추기", play="움직임 재생"),
 "en": dict(boom="Loader boom", mower="Mid-mount mower", hood="Hood", fender="Fender", side="Side panels", front="Front panel", made="Parts made by Hanil",
   tractor_alt="Side drawing of a tractor with a front loader and a mid-mount mower; the loader boom, mower, hood and fender Hanil makes are marked in orange.",
   bus_alt="Side drawing of a bus with the side and front outer panels Hanil makes marked in orange.",
   ticker=["Front loader booms","Mid-mount mowers","Tractor hoods","Tractor fenders","Bus side panels","Truck outer panels","Refrigerated body press parts","Implement parts","Fender cover sets"],
   ticker_label="Products", credits="Photo credits", alt_hero="A tractor with a front loader working a field beside a blossoming orchard", alt_loader="A tractor with a front loader", alt_mower="A compact tractor with a mid-mount mower", alt_bus="A city bus on the road", alt_weld="A production line of welding robots", growth_h="Customers and growth", pause="Pause motion", play="Play motion"),
 "ja": dict(boom="ローダーブーム", mower="ミッドモア", hood="フード", fender="フェンダー", side="側面外板", front="前面外板", made="ハンイル特装が製造する部品",
   tractor_alt="フロントローダーとミッドモアを装着したトラクターの側面図。ハンイル特装が製造するローダーブーム、ミッドモア、フード、フェンダーをオレンジで示しています。",
   bus_alt="バスの側面図。ハンイル特装が製造する側面・前面外板をオレンジで示しています。",
   ticker=["フロントローダーブーム","ミッドマウントモア","トラクターのフード","トラクターのフェンダー","バス側面外板","トラック外板","冷凍車プレス部品","作業機部品","フェンダーカバーセット"],
   ticker_label="製品", credits="写真クレジット", alt_hero="花の咲く果樹園の横でフロントローダー付きトラクターが畑を耕す様子", alt_loader="フロントローダー付きトラクター", alt_mower="ミッドマウントモアを装着した小型トラクター", alt_bus="道路を走る路線バス", alt_weld="溶接ロボットが並ぶ生産ライン", growth_h="納入先と成長", pause="動きを止める", play="動きを再生"),
}

def photo(name, alt, cls="", up="", sizes="(max-width: 720px) 100vw, 50vw", lazy=True, w=1280, h=853):
    small = f"{up}assets/img/{name}-640.webp 640w, " if name != "hero" else f"{up}assets/img/{name}-960.webp 960w, "
    big = f"{up}assets/img/{name}.webp {1920 if name=='hero' else 1280}w"
    ld = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return f'<img class="{cls}" src="{up}assets/img/{name}.webp" srcset="{small}{big}" sizes="{sizes}" width="{w}" height="{h}" alt="{e(alt)}"{ld}>'

def tractor(x, cls=""):
    # side view, viewBox 0 0 820 470; ground at y 440. Parts Hanil makes carry class "mk".
    return f"""<svg class="draw {cls}" viewBox="-30 76 850 404" role="img" aria-label="{e(x['tractor_alt'])}">
  <g class="ln">
    <path pathLength="1" d="M20 440H800"/>
    <path pathLength="1" d="M150 318H520V346H170Z"/>
    <path pathLength="1" d="M470 300L486 118H664L652 300"/>
    <path pathLength="1" d="M486 118L478 98H672L664 118"/>
    <path pathLength="1" d="M500 136H640L632 262H508Z"/>
    <path pathLength="1" d="M528 262L560 210L600 214"/>
    <path pathLength="1" d="M582 262V236H624V262"/>
    <circle pathLength="1" cx="575" cy="338" r="102"/>
    <circle pathLength="1" cx="575" cy="338" r="64"/>
    <circle pathLength="1" cx="575" cy="338" r="22"/>
    <circle pathLength="1" cx="190" cy="380" r="60"/>
    <circle pathLength="1" cx="190" cy="380" r="36"/>
    <circle pathLength="1" cx="190" cy="380" r="12"/>
    <path pathLength="1" d="M104 236H124V304H104Z"/>
    <path pathLength="1" d="M108 250H120M108 262H120M108 274H120M108 286H120"/>
    <path pathLength="1" d="M434 330L448 238H472L468 330Z"/>
    <path pathLength="1" d="M-14 438H96L100 402L76 354L32 346Q2 350 -6 380Z"/>
    <path pathLength="1" d="M334 318L272 180M326 322L264 184"/>
    <circle pathLength="1" cx="284" cy="436" r="5"/><circle pathLength="1" cx="452" cy="436" r="5"/>
  </g>
  <circle class="lugs" cx="575" cy="338" r="94"/>
  <circle class="lugs lugs--s" cx="190" cy="380" r="54"/>
  <g class="mk">
    <path pathLength="1" d="M124 304V246Q128 214 168 208L452 196L470 300Z"/>
    <path pathLength="1" d="M455 338A120 120 0 0 1 679 278L668 284A108 108 0 0 0 467 338Z"/>
    <path pathLength="1" d="M170 324A68 68 0 0 1 250 344L242 348A58 58 0 0 0 176 330Z"/>
    <path pathLength="1" d="M472 244L432 150Q424 134 404 136L150 158Q120 162 110 186L52 354L80 362L134 198Q140 182 158 182L398 162Q408 162 412 172L448 252Z"/>
    <path pathLength="1" d="M264 430V406Q266 394 282 394H452Q468 394 470 406V422Q470 430 460 430Z"/>
  </g>
  <g class="call">
    <path d="M220 152V104H260"/><text x="266" y="110">{e(x['boom'])}</text>
    <text x="196" y="262" text-anchor="middle">{e(x['hood'])}</text>
    <path d="M366 430V466H404"/><text x="410" y="472">{e(x['mower'])}</text>
    <path d="M690 280L730 240H760"/><text x="680" y="230" text-anchor="start">{e(x['fender'])}</text>
  </g>
</svg>"""

def bus(x):
    return f"""<svg class="draw draw--bus" viewBox="0 0 820 420" role="img" aria-label="{e(x['bus_alt'])}">
  <g class="ln">
    <path pathLength="1" d="M20 392H800"/>
    <path pathLength="1" d="M60 352V110Q60 80 92 78H744Q782 80 786 120L790 352Z"/>
    <path pathLength="1" d="M92 110H246V200H92Z M262 110H416V200H262Z M432 110H586V200H432Z M602 110H700V200H602Z"/>
    <path pathLength="1" d="M714 110H770L776 200H714Z"/>
    <path pathLength="1" d="M714 214H770V352"/>
    <circle pathLength="1" cx="196" cy="352" r="42"/>
    <circle pathLength="1" cx="196" cy="352" r="22"/>
    <circle pathLength="1" cx="616" cy="352" r="42"/>
    <circle pathLength="1" cx="616" cy="352" r="22"/>
  </g>
  <g class="mk">
    <path pathLength="1" d="M64 222H704V340H662V330A46 46 0 0 0 570 330V340H242V330A46 46 0 0 0 150 330V340H64Z"/>
    <path pathLength="1" d="M776 214H788L790 340H776Z"/>
  </g>
  <g class="call">
    <path d="M300 262V60H340"/><text x="346" y="65">{e(x['side'])}</text>
    <path d="M783 214V60H760"/><text x="752" y="65" text-anchor="end">{e(x['front'])}</text>
  </g>
</svg>"""


# ---------------------------------------------------------------------------
# Multi-page site: home + about + products + plant + contact, in ko / en / ja.
# Every fact here comes from the company's current site or from the owner.
# ---------------------------------------------------------------------------
PAGES = ["index", "about", "products", "plant", "contact"]

P = {
"ko": dict(
  nav=[("about","회사소개"),("products","제품"),("plant","설비·공정"),("contact","문의")],
  more_products="제품 전체 보기", more_plant="설비와 공정 자세히 보기", more_about="회사소개 보기",
  about=dict(title="회사소개 · 한일특장", desc="2021년 전북 완주에서 시작한 자동차·농기계 외장 판금 부품 제조사 한일특장의 개요, 연혁, 성장.",
    h1="회사소개", lead="한일특장은 2021년 전북 완주에서 시작한 외장 판금 부품 제조사입니다. 프레스 성형부터 용접, 사상, 검사까지 한 공장에서 합니다.",
    plate=[("설립","2021","년"),("보유 인증","10","건"),("OEM 수주 잔고","3","년치"),("최대 프레스","1,500","톤")],
    ov_h="회사 개요", ov_p="버스·트럭과 트랙터의 눈에 보이는 바깥 판금 부품을 만듭니다.",
    ov=[("회사명","한일특장 (Hanil Special Equipment)"),("설립","2021년"),("소재지","전북특별자치도 완주군 봉동읍 첨단산업3로 24"),("사업 분야","자동차 외장 부품, 농기계 외장 부품"),("주요 설비","1,500톤 유압 프레스부터 150톤 소형 프레스, CO₂ 용접 로봇 11대"),("보유 인증","10건"),("대표 전화","063-714-3663")],
    hist_h="연혁", hist_p="설립 이후 해마다 매출이 늘었고, 2025년에는 첫 수출을 했습니다.",
    hist=[("2021","전북 완주에 한일특장 설립"),("2023","매출 21.3억 원"),("2024","매출 40.2억 원"),("2025","매출 60.4억 원 · 대만으로 소형 펜더 커버 세트 첫 수출"),("2026","매출 목표 100억 원")],
    grow_h="성장과 납품처"),
  products=dict(title="제품 · 한일특장", desc="프런트 로더 붐, 미드 마운트 모어, 트랙터 후드·펜더, 버스·트럭 외판, 냉동탑차 프레스 부품.",
    h1="제품", lead="눈에 보이는 바깥 판금 패널을 프레스 성형, 용접, 사상까지 마친 상태로 납품합니다.",
    agri_h="농기계 부품", agri_p="트랙터 외장이 주력입니다. 프런트 로더와 미드 모어 같은 작업기 부품도 만듭니다. LS엠트론, 두산밥캣에 납품합니다.",
    agri=[("loader","프런트 로더 붐","트랙터 앞에 다는 로더의 붐(팔) 부분을 만듭니다."),
          ("mower","미드 마운트 모어","트랙터 배 아래에 다는 잔디깎이 모어 부품을 만듭니다."),
          ("hero","트랙터 후드·펜더","크고 깊게 휜 패널을 냉연강판으로 성형해 용접·사상합니다.")],
    agri_more=[("작업기·어태치먼트 부품","최근 추가한 품목입니다."),("펜더 커버 세트","2025년 대만으로 첫 수출했습니다.")],
    auto_h="자동차 부품", auto_p="버스·트럭 외판과 냉동탑차 차체 프레스 부품입니다. 신차는 설계 단계부터 고객사와 함께 개발합니다. 현대모비스, KGM커머셜에 납품합니다.",
    auto=[("bus","버스 외판","버스 측면과 전면의 바깥 패널을 만듭니다.")],
    auto_more=[("트럭 외판","트럭 차체의 바깥 패널입니다."),("냉동탑차 차체 프레스 부품","냉동탑차 차체에 들어가는 프레스 부품입니다."),("OEM 수주 잔고","약 3년치")],
    how_h="모든 부품은 같은 순서로 만듭니다", how_p="냉연강판 입고, 전단, 1~4단 성형, 로봇·수동 용접, 사상, 검사, 협력사 도장, 출하."),
  plant=dict(title="설비·공정 · 한일특장", desc="1,500톤 유압 프레스, CO₂ 용접 로봇 11대, 원자재 입고부터 출하까지 8단계 공정.",
    h1="설비·공정", lead="전단, 성형, 용접, 사상, 검사가 같은 부지에서 차례로 이어집니다. 공정 중간에 밖으로 나가는 일이 없어 납기를 지킵니다.",
    str_h="한 공장에서 하는 이유", str_p="부품에 맞춰 공정을 짰습니다.",
    strengths=[("1,500톤부터 150톤까지","큰 패널은 유압 딥드로잉 프레스로 한 번에, 작은 부품은 소형 프레스로 성형합니다."),
               ("로봇과 숙련공이 함께 용접","로봇 용접으로 처리량과 균일한 품질을 얻고, 로봇이 닿지 않는 이음부는 숙련 용접사가 맡습니다."),
               ("한 공장, 한 흐름","전단부터 검사까지 같은 부지에서 이어져 부품이 중간에 밖으로 나가지 않습니다.")],
    steps_h="원자재에서 출하까지 8단계",
    detail=["냉연강판을 받아 강종과 두께를 확인하고 등록합니다.","판재를 작업 크기로 자르고, 자투리가 적게 나오도록 배치합니다.","부품 모양으로 프레스합니다. 부품에 따라 최대 네 단계로 나눠 성형합니다.","대부분은 로봇이 용접하고, 로봇이 닿지 않는 이음부는 숙련 용접사가 마무리합니다.","용접 뒷비드와 결함을 갈아냅니다. 도장 품질이 여기서 정해집니다.","치수와 외관을 확인하고, 합격한 부품만 다음 단계로 보냅니다.","협력 도장업체가 맡습니다. 색과 도막은 고객 사양을 따릅니다.","수량대로 포장해 거래명세서와 함께 보냅니다."]),
  contact=dict(title="문의·오시는 길 · 한일특장", desc="도면을 보내 주시면 검토해 드립니다. 신규 부품 견적, 기존 부품 이관, 개발 초기 검토.",
    h1="문의·오시는 길", lead="도면을 보내 주시면 검토해 드립니다. 신규 부품 견적, 기존 부품 이관, 개발 초기 검토 모두 받습니다.",
    form_h="도면 검토 요청", form_p="아래 내용을 적고 버튼을 누르면 메일 창이 열립니다. 도면 파일은 열린 메일에 첨부해 주세요.",
    f_company="회사명", f_name="담당자", f_email="회신받을 이메일", f_phone="전화번호", f_kind="문의 종류",
    kinds=["신규 부품 견적","기존 부품 이관","개발 초기 검토","기타"], f_msg="부품과 수량", f_msg_ph="예: 트랙터 펜더, 연 2,000세트, 냉연강판 2.3t",
    f_send="메일로 보내기", f_note="버튼을 누르면 사용하시는 메일 프로그램이 열립니다.",
    visit_h="오시는 길", tel_l="전화", mail_l="이메일", addr_l="주소", map_naver="네이버 지도에서 보기", map_google="Google 지도에서 보기"),
),
"en": dict(
  nav=[("about","About"),("products","Products"),("plant","Plant"),("contact","Contact")],
  more_products="See all products", more_plant="See the plant and process", more_about="About the company",
  about=dict(title="About · Hanil Special Equipment", desc="Hanil Special Equipment, a maker of exterior sheet-metal parts for vehicles and agricultural machinery in Wanju, Korea, since 2021.",
    h1="About the company", lead="Hanil Special Equipment started in Wanju, Korea, in 2021. We make exterior sheet-metal parts, from press forming to welding, finishing and inspection, in one plant.",
    plate=[("Founded","2021",""),("Certifications","10",""),("OEM backlog","3","years"),("Largest press","1,500","t")],
    ov_h="Company overview", ov_p="We make the visible outer sheet-metal parts of buses, trucks and tractors.",
    ov=[("Name","Hanil Special Equipment (한일특장)"),("Founded","2021"),("Address","24, Cheomdansaneop 3-ro, Bongdong-eup, Wanju-gun, Jeonbuk State, Republic of Korea"),("Business","Automotive and agricultural machinery exterior parts"),("Main equipment","Hydraulic presses from 1,500 t down to 150 t; 11 CO₂ welding robots"),("Certifications","10 held"),("Phone","+82-63-714-3663")],
    hist_h="History", hist_p="Revenue has grown every year since founding, and the first export shipment left in 2025.",
    hist=[("2021","Hanil Special Equipment founded in Wanju, Jeonbuk"),("2023","Revenue KRW 2.13 billion"),("2024","Revenue KRW 4.02 billion"),("2025","Revenue KRW 6.04 billion · first export: small fender cover sets to Taiwan"),("2026","Revenue target KRW 10 billion")],
    grow_h="Growth and customers"),
  products=dict(title="Products · Hanil Special Equipment", desc="Front loader booms, mid-mount mowers, tractor hoods and fenders, bus and truck outer panels, refrigerated body press parts.",
    h1="Products", lead="Visible outer sheet-metal panels, delivered press-formed, welded and finished.",
    agri_h="Agricultural machinery parts", agri_p="Tractor exteriors are our main line, alongside implement parts such as front loaders and mid-mount mowers. Supplied to LS Mtron and Doosan Bobcat.",
    agri=[("loader","Front loader booms","The boom (arm) of the loader mounted on the front of a tractor."),
          ("mower","Mid-mount mowers","Parts for the mower mounted under a tractor's belly."),
          ("hero","Tractor hoods and fenders","Large, deeply curved panels formed from cold-rolled steel, then welded and finished.")],
    agri_more=[("Implement and attachment parts","Recently added to our range."),("Fender cover sets","First exported to Taiwan in 2025.")],
    auto_h="Automotive parts", auto_p="Bus and truck outer panels and press parts for refrigerated truck bodies. New models are developed with the customer from the design stage. Supplied to Hyundai Mobis and KGM Commercial.",
    auto=[("bus","Bus outer panels","The outer side and front panels of buses.")],
    auto_more=[("Truck outer panels","Outer panels of truck bodies."),("Refrigerated body press parts","Press parts for refrigerated truck bodies."),("OEM order backlog","About three years")],
    how_h="Every part follows the same route", how_p="Incoming cold-rolled steel, shearing, forming in 1 to 4 stages, robotic and manual welding, finishing, inspection, partner painting, shipping."),
  plant=dict(title="Plant and process · Hanil Special Equipment", desc="A 1,500-ton hydraulic press, 11 CO₂ welding robots and an eight-step process from incoming steel to shipment.",
    h1="Plant and process", lead="Shearing, forming, welding, finishing and inspection run in sequence on one site. Nothing leaves mid-process, which keeps delivery dates.",
    str_h="Why one plant", str_p="The process is built around the part.",
    strengths=[("From 1,500 tons down to 150","Hydraulic deep-drawing presses form large panels in a single stroke; compact presses take the small parts."),
               ("Robots and skilled welders together","Robotic welding gives throughput and even quality; skilled welders cover the joints robots cannot reach."),
               ("One plant, one flow","Shearing through inspection run on the same site, so no part leaves mid-process.")],
    steps_h="Eight steps from steel to shipment",
    detail=["Cold-rolled steel is received, checked for grade and thickness, and registered.","Sheets are cut to working size, nested to keep offcuts low.","Shapes are pressed; depending on the part, forming is split across up to four stages.","Robotic welding does the bulk; skilled welders finish the joints the robots cannot reach.","Weld beads and defects are ground away. Paint quality is decided here.","Dimensions and appearance are checked. Only passed parts move on.","Handled by partner painting shops. Colour and film follow customer specification.","Packed to quantity and dispatched with a delivery statement."]),
  contact=dict(title="Contact · Hanil Special Equipment", desc="Send us a drawing and we will review it: new part quotations, transfers of existing parts and early development reviews.",
    h1="Contact and directions", lead="Send us a drawing and we will review it. New part quotations, transfers of existing parts and early development reviews are all welcome.",
    form_h="Request a drawing review", form_p="Fill in the fields and press the button to open an e-mail. Please attach your drawing to that e-mail.",
    f_company="Company", f_name="Your name", f_email="Reply-to e-mail", f_phone="Phone", f_kind="Request type",
    kinds=["New part quotation","Transfer of an existing part","Early development review","Other"], f_msg="Part and quantity", f_msg_ph="e.g. tractor fender, 2,000 sets a year, 2.3 mm cold-rolled steel",
    f_send="Send by e-mail", f_note="The button opens your e-mail program.",
    visit_h="Directions", tel_l="Phone", mail_l="E-mail", addr_l="Address", map_naver="Open in Naver Map", map_google="Open in Google Maps"),
),
"ja": dict(
  nav=[("about","会社概要"),("products","製品"),("plant","設備・工程"),("contact","お問い合わせ")],
  more_products="製品一覧を見る", more_plant="設備と工程を詳しく見る", more_about="会社概要を見る",
  about=dict(title="会社概要 · ハンイル特装", desc="2021年に韓国・完州で創業した自動車・農業機械の外装板金部品メーカー、ハンイル特装の概要・沿革・成長。",
    h1="会社概要", lead="ハンイル特装は2021年に韓国・完州で創業した外装板金部品メーカーです。プレス成形から溶接、仕上げ、検査まで一つの工場で行います。",
    plate=[("設立","2021","年"),("保有認証","10","件"),("OEM受注残","3","年分"),("最大プレス","1,500","トン")],
    ov_h="会社概要", ov_p="バス・トラックとトラクターの、目に見える外装板金部品をつくります。",
    ov=[("会社名","ハンイル特装（한일특장 / Hanil Special Equipment）"),("設立","2021年"),("所在地","大韓民国 全北特別自治道 完州郡 鳳東邑 チョムダンサノプ3路 24"),("事業分野","自動車外装部品、農業機械外装部品"),("主要設備","1,500トンから150トンまでの油圧プレス、CO₂溶接ロボット11台"),("保有認証","10件"),("代表電話","+82-63-714-3663")],
    hist_h="沿革", hist_p="創業以来、売上は毎年伸びており、2025年には初の輸出を行いました。",
    hist=[("2021","全北・完州にハンイル特装を設立"),("2023","売上21.3億ウォン"),("2024","売上40.2億ウォン"),("2025","売上60.4億ウォン · 台湾へ小型フェンダーカバーセットを初輸出"),("2026","売上目標100億ウォン")],
    grow_h="成長と納入先"),
  products=dict(title="製品 · ハンイル特装", desc="フロントローダーブーム、ミッドマウントモア、トラクターのフード・フェンダー、バス・トラック外板、冷凍車プレス部品。",
    h1="製品", lead="目に見える外装の板金パネルを、プレス成形・溶接・仕上げまで終えた状態で納品します。",
    agri_h="農業機械部品", agri_p="トラクター外装が主力です。フロントローダーやミッドモアなどの作業機部品もつくります。LSエムトロン、斗山ボブキャットに納品しています。",
    agri=[("loader","フロントローダーブーム","トラクター前部に取り付けるローダーのブーム（アーム）部分をつくります。"),
          ("mower","ミッドマウントモア","トラクターの車体下に取り付ける芝刈りモアの部品をつくります。"),
          ("hero","トラクターのフード・フェンダー","大きく深く曲がったパネルを冷延鋼板で成形し、溶接・仕上げします。")],
    agri_more=[("作業機・アタッチメント部品","最近加わった品目です。"),("フェンダーカバーセット","2025年に台湾へ初輸出しました。")],
    auto_h="自動車部品", auto_p="バス・トラックの外板と冷凍車ボディのプレス部品です。新型車は設計段階からお客様と共同で開発します。現代モービス、KGMコマーシャルに納品しています。",
    auto=[("bus","バス外板","バスの側面・前面の外装パネルをつくります。")],
    auto_more=[("トラック外板","トラック車体の外装パネルです。"),("冷凍車ボディのプレス部品","冷凍車ボディに使われるプレス部品です。"),("OEM受注残","約3年分")],
    how_h="すべての部品は同じ流れでつくります", how_p="冷延鋼板の入荷、せん断、1～4段の成形、ロボット・手溶接、仕上げ、検査、協力会社による塗装、出荷。"),
  plant=dict(title="設備・工程 · ハンイル特装", desc="1,500トン油圧プレス、CO₂溶接ロボット11台、材料入荷から出荷までの8段階工程。",
    h1="設備・工程", lead="せん断、成形、溶接、仕上げ、検査が同じ敷地内で順に続きます。工程の途中で部品が外に出ないため、納期を守れます。",
    str_h="一つの工場で行う理由", str_p="部品に合わせて工程を組んでいます。",
    strengths=[("1,500トンから150トンまで","大型パネルは油圧深絞りプレスで一工程で、小物部品は小型プレスで成形します。"),
               ("ロボットと熟練工がともに溶接","ロボット溶接で処理量と均一な品質を確保し、ロボットが届かない継ぎ目は熟練溶接工が担います。"),
               ("一つの工場、一つの流れ","せん断から検査まで同じ敷地内で続くため、部品が途中で外に出ません。")],
    steps_h="材料入荷から出荷まで8段階",
    detail=["冷延鋼板を受け入れ、鋼種と板厚を確認して登録します。","板材を作業サイズに切断し、端材が少なくなるよう配置します。","部品の形にプレスします。部品に応じて最大4段階に分けて成形します。","大部分はロボットが溶接し、ロボットが届かない継ぎ目は熟練溶接工が仕上げます。","溶接ビードや欠陥を削ります。塗装品質はここで決まります。","寸法と外観を確認し、合格品のみ次の工程へ送ります。","協力塗装会社が担当します。色と塗膜はお客様の仕様に従います。","数量どおりに梱包し、納品書とともに発送します。"]),
  contact=dict(title="お問い合わせ · ハンイル特装", desc="図面をお送りいただければ検討いたします。新規部品のお見積り、既存部品の移管、開発初期のご相談。",
    h1="お問い合わせ・アクセス", lead="図面をお送りいただければ検討いたします。新規部品のお見積り、既存部品の移管、開発初期のご相談まで承ります。",
    form_h="図面検討のご依頼", form_p="下記をご記入のうえボタンを押すと、メール画面が開きます。図面ファイルはそのメールに添付してください。",
    f_company="会社名", f_name="ご担当者名", f_email="返信先メールアドレス", f_phone="電話番号", f_kind="お問い合わせの種類",
    kinds=["新規部品のお見積り","既存部品の移管","開発初期のご相談","その他"], f_msg="部品と数量", f_msg_ph="例：トラクターのフェンダー、年2,000セット、冷延鋼板2.3t",
    f_send="メールで送る", f_note="ボタンを押すと、お使いのメールソフトが開きます。",
    visit_h="アクセス", tel_l="電話", mail_l="メール", addr_l="住所", map_naver="NAVER地図で見る", map_google="Google マップで見る"),
),
}

ADDR_Q = urllib.parse.quote("전북특별자치도 완주군 봉동읍 첨단산업3로 24")

def href(k, pid, from_k=None):
    """Link from a page in language from_k (default k) to page pid in language k."""
    src = from_k or k
    up = "" if src == "ko" else "../"
    return f"{up}{PATHS[k]}{pid}.html"


# ----- full-screen site menu ("전체 메뉴") -----
MENU = {
 "ko": dict(open="전체 메뉴", close="메뉴 닫기", sub={
   "about": [("overview", "회사 개요"), ("history", "연혁"), ("growth", "성장과 납품처")],
   "products": [("agri", "농기계 부품"), ("auto", "자동차 부품"), ("how", "생산 순서")],
   "plant": [("equipment", "프레스·용접 설비"), ("strengths", "한 공장에서 하는 이유"), ("steps", "8단계 공정")],
   "contact": [("request", "도면 검토 요청"), ("visit", "오시는 길")]}),
 "en": dict(open="Menu", close="Close menu", sub={
   "about": [("overview", "Company overview"), ("history", "History"), ("growth", "Growth and customers")],
   "products": [("agri", "Agricultural machinery parts"), ("auto", "Automotive parts"), ("how", "How parts are made")],
   "plant": [("equipment", "Presses and welding"), ("strengths", "Why one plant"), ("steps", "Eight-step process")],
   "contact": [("request", "Request a drawing review"), ("visit", "Directions")]}),
 "ja": dict(open="メニュー", close="メニューを閉じる", sub={
   "about": [("overview", "会社概要"), ("history", "沿革"), ("growth", "成長と納入先")],
   "products": [("agri", "農業機械部品"), ("auto", "自動車部品"), ("how", "製造の流れ")],
   "plant": [("equipment", "プレス・溶接設備"), ("strengths", "一つの工場で行う理由"), ("steps", "8段階の工程")],
   "contact": [("request", "図面検討のご依頼"), ("visit", "アクセス")]}),
}

def menu_html(k, pid):
    d = L[k]; m = MENU[k]; p = P[k]
    tel = d["tel"]; telhref = "+82" + tel.replace("+82-", "").lstrip("0").replace("-", "") if not tel.startswith("+") else tel.replace("-", "")
    cols = ""
    for i, (page, label) in enumerate(p["nav"]):
        subs = "".join(f'<li><a href="{href(k, page)}#{a}">{e(t)}</a></li>' for a, t in m["sub"][page])
        cur = ' aria-current="page"' if page == pid else ""
        cols += (f'<div class="menu__col" style="--i:{i}"><a class="menu__page" href="{href(k, page)}"{cur}>'
                 f'<span class="num">{i+1:02d}</span>{e(label)}</a><ul>{subs}</ul></div>')
    langs = "".join(
        f'<a href="{href(o, pid, k)}" hreflang="{o}" lang="{o}"' + (' aria-current="true"' if o == k else '') + f'>{NAMES[o]}</a>'
        for o in ("ko", "en", "ja"))
    return (
        f'<div class="menu" id="site-menu" role="dialog" aria-modal="true" aria-label="{e(m["open"])}" hidden>\n'
        f'  <div class="wrap menu__bar">\n'
        f'    <a class="logo" href="{href(k, "index")}">{LOGO}<span translate="no">{e(d["name"])}</span></a>\n'
        f'    <button class="menu__close" type="button" data-menu-close><span>{e(m["close"])}</span>'
        f'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3 3 13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>\n'
        f'  </div>\n'
        f'  <nav class="wrap menu__grid" aria-label="{e(m["open"])}">{cols}</nav>\n'
        f'  <div class="wrap menu__foot">\n'
        f'    <a class="btn" href="{href(k, "contact")}#request">{e(d["cta"])}{ARROW}</a>\n'
        f'    <p class="menu__contact"><a href="tel:{telhref}">{e(tel)}</a><a href="mailto:{MAIL}">{MAIL}</a></p>\n'
        f'    <p class="menu__langs">{langs}</p>\n'
        f'  </div>\n'
        f'</div>')

MENU_BTN = ('<button class="menu-btn" type="button" aria-expanded="false" aria-controls="site-menu" data-menu-open>'
            '<span class="menu-btn__label">{label}</span><svg viewBox="0 0 20 20" aria-hidden="true">'
            '<path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>')


def shell(k, pid, title, desc, body, hero_photo=None):
    d = L[k]; x = X[k]; p = P[k]; up = "" if k == "ko" else "../"
    mail = f"mailto:{MAIL}?subject=" + urllib.parse.quote(d["subject"])
    langs = "".join(
        f'<a href="{href(o, pid, k)}" hreflang="{o}" lang="{o}" aria-label="{NAMES[o]}"{" aria-current=\"true\"" if o==k else ""}>{LABEL[o]}</a>'
        for o in ("ko","en","ja"))
    alts = "\n".join(f'<link rel="alternate" hreflang="{o}" href="{href(o, pid, k)}">' for o in ("ko","en","ja"))
    nav = "".join(f'<a href="{href(k, i)}"{" aria-current=\"page\"" if i==pid else ""}>{e(t)}</a>' for i, t in p["nav"])
    tel = d["tel"]; telhref = "+82" + tel.replace("+82-", "").lstrip("0").replace("-", "") if not tel.startswith("+") else tel.replace("-", "")
    close = "" if pid == "contact" else f'''    <h2 id="close-h">{e(d["close_h"])}</h2>
    <p class="close__lead">{e(d["close_p"])}</p>
    <a class="btn close__cta" href="{href(k, "contact")}">{e(d["cta"])}{ARROW}</a>
'''
    foot_nav = "".join(f'<a href="{href(k, i)}">{e(t)}</a>' for i, t in p["nav"])
    return f'''<!doctype html>
<html lang="{d["lang"]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta name="theme-color" content="#0b1f3a">
{alts}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?{d["fonts"]}&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}assets/hanil.css">
<script>document.documentElement.classList.add("js")</script>
<script src="{up}assets/hanil.js" defer></script>
</head>
<body class="pg-{pid}">
<a class="skip" href="#main">{e(d["skip"])}</a>
<header class="top">
  <div class="wrap top__bar">
    <a class="logo" href="{href(k, "index")}">{LOGO}<span translate="no">{e(d["name"])}</span></a>
    <nav class="top__nav" aria-label="{e(d["navlabel"])}">{nav}</nav>
    <div class="lang" role="group" aria-label="Language">{langs}</div>
    {MENU_BTN.format(label=e(MENU[k]["open"]))}
  </div>
</header>
{menu_html(k, pid)}

<main id="top">
{body}
</main>

<footer class="close{" close--short" if pid == "contact" else ""}" id="contact" aria-label="{e(d["name"])}">
  <div class="wrap">
{close}    <div class="foot">
      <a class="logo" href="{href(k, "index")}">{LOGO}<span translate="no">{e(d["name"])}</span></a>
      <address><span>{e(d["addr"])}</span><a href="tel:{telhref}">{e(tel)}</a><a href="mailto:{MAIL}">{MAIL}</a></address>
      <div class="foot__legal"><nav class="foot__nav" aria-label="{e(d["navlabel"])}">{foot_nav}</nav><p>{e(d["legal"])} · <a href="{up}credits.html">{e(x["credits"])}</a></p></div>
    </div>
  </div>
</footer>
</body>
</html>
'''

def page_head(k, pid, h1, lead, img, alt):
    up = "" if k == "ko" else "../"
    return f'''  <section class="hero hero--page" aria-labelledby="hero-h" id="main">
    <div class="hero__media">{photo(img, alt, "hero__img", up, "100vw", False, 1920 if img=="hero" else 1280, 1205 if img=="hero" else 853)}</div>
    <div class="wrap hero__body">
      <div>
        <h1 id="hero-h">{e(h1)}</h1>
        <p class="hero__lead">{e(lead)}</p>
      </div>
    </div>
  </section>'''

def plate_html(items):
    cells = "".join(f'<div class="plate__cell"><dt>{e(a)}</dt><dd class="num"><span data-count="{b}">{b}</span>{f"<small>{e(c)}</small>" if c else ""}</dd></div>' for a, b, c in items)
    return f'<div class="plate"><span class="plate__rivets" aria-hidden="true"></span><dl class="plate__grid">{cells}</dl></div>'

def chart_html(d):
    bars = "".join(f'<div class="bar{" bar--target" if i == 3 else ""}" style="--v: {v}; --i: {i}"><span class="bar__v">{v}</span></div>' for i, v in enumerate(d["vals"]))
    years = "".join(f"<span>{e(y)}</span>" for y in d["years"])
    return f'''<figure class="chart" role="img" aria-label="{e(d["chart_aria"])}" data-run>
          <div class="chart__head" aria-hidden="true"><strong>{e(d["chart_t"])}</strong><span>{e(d["chart_u"])}</span></div>
          <div class="chart__plot" aria-hidden="true">{bars}</div>
          <div class="chart__years" aria-hidden="true">{years}</div>
        </figure>'''

def cust_html(d):
    return "".join(f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td></tr>' for a, b in d["cust"])

def more(k, pid, label):
    return f'<p class="more"><a href="{href(k, pid)}">{e(label)}{ARROW}</a></p>'

def eqs_html(d):
    out = ""
    for q in d["eq"]:
        rows = "".join(f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td></tr>' for a, b in q["rows"])
        out += f'<article class="eq"><span class="plate__rivets" aria-hidden="true"></span><h3>{e(q["h"])}</h3><p class="eq__big"><span data-count="{q["big"]}">{q["big"]}</span><small>{e(q["unit"])}</small></p><table>{rows}</table></article>'
    return out

def steps_html(d, detail=None):
    out = ""
    for i, (h, ptxt) in enumerate(d["steps"], 1):
        cls = "st st--partner" if i == 7 else "st"
        txt = detail[i-1] if detail else ptxt
        out += f'<li class="{cls}"><span class="st__dot" aria-hidden="true"></span><span class="st__n">{i:02d}</span><h3>{e(h)}</h3><p>{e(txt)}</p></li>'
    return out


# ----- extra photographs (shown only when the file exists in assets/img) -----
IMG_ALT = {
 "ko": dict(coil="냉연강판 코일", shear="판재를 자르는 전단기", press="프레스 기계", grind="그라인더로 용접부를 다듬는 작업", inspect="부품 치수를 재는 모습",
            paint="도장 작업", ship="지게차로 팔레트를 옮기는 모습", truck="화물 트럭", reefer="냉동탑차", field="밭을 가는 트랙터", factory="금속 가공 공장 내부",
            gallery_h="현장", gallery_p="강판이 들어와 부품으로 나가기까지의 모습입니다."),
 "en": dict(coil="Cold-rolled steel coils", shear="A shearing machine cutting sheet metal", press="A press", grind="Grinding a weld", inspect="Measuring a part",
            paint="Painting", ship="Moving pallets with a forklift", truck="A cargo truck", reefer="A refrigerated truck", field="A tractor ploughing a field", factory="Inside a metal fabrication plant",
            gallery_h="On the shop floor", gallery_p="From incoming steel to finished parts."),
 "ja": dict(coil="冷延鋼板のコイル", shear="板材を切断するシャーリング機", press="プレス機", grind="グラインダーによる溶接部の仕上げ", inspect="部品の寸法を測る様子",
            paint="塗装作業", ship="フォークリフトでパレットを運ぶ様子", truck="貨物トラック", reefer="冷凍車", field="畑を耕すトラクター", factory="金属加工工場の内部",
            gallery_h="現場", gallery_p="鋼板が入荷し、部品として出荷されるまでの様子です。"),
}
STEP_IMG = ["coil", "shear", "press", "welding", "grind", "inspect", "paint", "ship"]

def has(name):
    return os.path.exists(os.path.join(ROOT, "assets", "img", f"{name}.webp"))

def alt_of(k, name):
    x = X[k]
    return {"welding": x["alt_weld"], "loader": x["alt_loader"], "mower": x["alt_mower"], "bus": x["alt_bus"], "hero": x["alt_hero"]}.get(name) or IMG_ALT[k].get(name, "")

def proc_cards(k, detail):
    d = L[k]; up = "" if k == "ko" else "../"; out = ""
    for i, (h, ptxt) in enumerate(d["steps"], 1):
        img = STEP_IMG[i-1]
        pic = (f'<figure class="ph">{photo(img, alt_of(k, img), "ph__img", up, "(max-width: 720px) 100vw, 25vw")}</figure>' if has(img)
               else f'<div class="ph ph--num" aria-hidden="true"><span class="num">{i:02d}</span></div>')
        partner = " pcard--partner" if i == 7 else ""
        out += f'<li class="pcard{partner}" data-reveal style="--i:{(i-1)%4}">{pic}<span class="st__n">{i:02d}</span><h3>{e(h)}</h3><p>{e(detail[i-1])}</p></li>'
    return f'<ol class="pcards">{out}</ol>'

def strip(k, names, cls="strip"):
    up = "" if k == "ko" else "../"
    names = [n for n in names if has(n)]
    if len(names) < 3: return ""
    figs = "".join(f'<figure class="ph" style="--i:{i}">{photo(n, alt_of(k, n), "ph__img", up, "(max-width: 720px) 50vw, 25vw")}</figure>' for i, n in enumerate(names))
    return f'<div class="{cls}" data-reveal>{figs}</div>'

# ----- home -----
def page_home(k):
    d = L[k]; x = X[k]; p = P[k]; up = "" if k == "ko" else "../"
    ticker = "".join(f"<li>{e(t)}</li>" for t in x['ticker'])
    segs = ""
    for si, s in enumerate(d["segs"]):
        art = (f'<figure class="ph">{photo("bus", x["alt_bus"], "ph__img", up)}</figure>' if si == 0 else
               f'<div class="ph-pair"><figure class="ph">{photo("loader", x["alt_loader"], "ph__img", up, "(max-width: 720px) 50vw, 25vw")}</figure><figure class="ph">{photo("mower", x["alt_mower"], "ph__img", up, "(max-width: 720px) 50vw, 25vw")}</figure></div>')
        rows = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in s["rows"])
        segs += f'<article class="seg" data-reveal>{art}<h3>{e(s["h"])}</h3><p class="seg__for">{e(s["f"])}</p><p class="seg__text">{e(s["t"])}</p><dl>{rows}</dl></article>'
    body = f'''  <section class="hero" aria-labelledby="hero-h">
    <div class="hero__media">{photo("hero", x["alt_hero"], "hero__img", up, "100vw", False, 1920, 1205)}</div>
    <div class="wrap hero__body">
      <div>
        <h1 id="hero-h">{e(d["h1"])}</h1>
        <p class="hero__lead">{e(d["lead"])}</p>
        <a class="btn hero__cta" href="{href(k, "contact")}">{e(d["cta"])}{ARROW}</a>
      </div>
    </div>
    <div class="wrap hero__plate">{plate_html(d["plate"])}</div>
    <div class="ticker" aria-label="{e(x['ticker_label'])}">
      <ul class="ticker__track">{ticker}</ul>
      <ul class="ticker__track" aria-hidden="true">{ticker}</ul>
      <button class="ticker__pause" type="button" aria-pressed="false" data-pause="{e(x['pause'])}" data-play="{e(x['play'])}" aria-label="{e(x['pause'])}"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 2v8M9 2v8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>
    </div>
  </section>

  <section class="sec" id="main" aria-labelledby="business-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="business-h">{e(d["biz_h"])}</h2><p>{e(d["biz_p"])}</p></div>
      <div class="segments">{segs}</div>
      {more(k, "products", p["more_products"])}
    </div>
  </section>

  <section class="sec sec--paper" id="plant" aria-labelledby="plant-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="plant-h">{e(d["plant_h"])}</h2><p>{e(d["plant_p"])}</p></div>
      <figure class="band" data-reveal>{photo("welding", x["alt_weld"], "band__img", up, "(max-width: 1240px) 100vw, 1240px")}</figure>
      <div class="plates" data-reveal>{eqs_html(d)}</div>
      <p class="plates__note">{e(d["plant_note"])}</p>
    </div>
  </section>

  <section class="sec" id="process" aria-labelledby="process-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="process-h">{e(d["proc_h"])}</h2><p>{e(d["proc_p"])}</p></div>
      <ol class="line" data-run>{steps_html(d)}</ol>
      <p class="line__legend"><span><i aria-hidden="true"></i>{e(d["legend"][0])}</span><span><i class="d" aria-hidden="true"></i>{e(d["legend"][1])}</span></p>
      {strip(k, ["coil", "grind", "inspect", "ship"])}
      {more(k, "plant", p["more_plant"])}
    </div>
  </section>

  <section class="sec sec--paper" id="customers" aria-labelledby="customers-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="customers-h">{e(x["growth_h"])}</h2><p>{e(d["cust_p"])}</p></div>
      <div class="growth">
        <div>
          <table class="cust"><tbody>{cust_html(d)}</tbody></table>
          <p class="cust__note">{e(d["cust_note"])}</p>
        </div>
        {chart_html(d)}
      </div>
      {more(k, "about", p["more_about"])}
    </div>
  </section>'''
    return shell(k, "index", d["title"], d["desc"], body)

# ----- about -----
def page_about(k):
    d = L[k]; x = X[k]; a = P[k]["about"]
    ov = "".join(f'<div><dt>{e(t)}</dt><dd>{e(v)}</dd></div>' for t, v in a["ov"])
    hist = "".join(f'<li class="tl__item"><span class="tl__year num">{y}</span><p>{e(t)}</p></li>' for y, t in a["hist"])
    body = f'''{page_head(k, "about", a["h1"], a["lead"], "welding", x["alt_weld"])}
  <div class="wrap page-plate">{plate_html(a["plate"])}</div>

  <section id="overview" class="sec" aria-labelledby="ov-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="ov-h">{e(a["ov_h"])}</h2><p>{e(a["ov_p"])}</p></div>
      <dl class="info" data-reveal>{ov}</dl>
      {strip(k, ["field", "coil", "grind", "welding"], "strip strip--wide")}
    </div>
  </section>

  <section id="history" class="sec sec--paper" aria-labelledby="hist-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="hist-h">{e(a["hist_h"])}</h2><p>{e(a["hist_p"])}</p></div>
      <ol class="tl" data-run>{hist}</ol>
    </div>
  </section>

  <section id="growth" class="sec" aria-labelledby="grow-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="grow-h">{e(a["grow_h"])}</h2><p>{e(d["cust_p"])}</p></div>
      <div class="growth">
        <div>
          <table class="cust"><tbody>{cust_html(d)}</tbody></table>
          <p class="cust__note">{e(d["cust_note"])}</p>
        </div>
        {chart_html(d)}
      </div>
    </div>
  </section>'''
    return shell(k, "about", a["title"], a["desc"], body)

# ----- products -----
def page_products(k):
    x = X[k]; pr = P[k]["products"]; up = "" if k == "ko" else "../"
    def cards(items):
        return "".join(f'<article class="prod" data-reveal><figure class="ph">{photo(img, name, "ph__img", up, "(max-width: 720px) 100vw, 33vw")}</figure><h3>{e(name)}</h3><p>{e(txt)}</p></article>' for img, name, txt in items)
    def rows(items):
        return "".join(f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td></tr>' for a, b in items)
    body = f'''{page_head(k, "products", pr["h1"], pr["lead"], "loader", x["alt_loader"])}

  <section id="agri" class="sec" aria-labelledby="agri-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="agri-h">{e(pr["agri_h"])}</h2><p>{e(pr["agri_p"])}</p></div>
      <div class="prods">{cards(pr["agri"])}</div>
      <table class="cust cust--sm"><tbody>{rows(pr["agri_more"])}</tbody></table>
    </div>
  </section>

  <section id="auto" class="sec sec--paper" aria-labelledby="auto-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="auto-h">{e(pr["auto_h"])}</h2><p>{e(pr["auto_p"])}</p></div>
      <div class="prods">{cards(pr["auto"] + [(img, n, t) for img, (n, t) in zip(["truck", "reefer"], pr["auto_more"][:2]) if has(img)])}</div>
      <table class="cust cust--sm"><tbody>{rows([r for img, r in zip(["truck", "reefer", None], pr["auto_more"]) if not (img and has(img))])}</tbody></table>
    </div>
  </section>

  <section id="how" class="sec" aria-labelledby="how-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="how-h">{e(pr["how_h"])}</h2><p>{e(pr["how_p"])}</p></div>
      <ol class="line" data-run>{steps_html(L[k])}</ol>
      {more(k, "plant", P[k]["more_plant"])}
    </div>
  </section>'''
    return shell(k, "products", pr["title"], pr["desc"], body)

# ----- plant -----
def page_plant(k):
    d = L[k]; x = X[k]; pl = P[k]["plant"]; up = "" if k == "ko" else "../"
    strengths = "".join(f'<article class="strength" data-reveal><h3>{e(h)}</h3><p>{e(t)}</p></article>' for h, t in pl["strengths"])
    body = f'''{page_head(k, "plant", pl["h1"], pl["lead"], "welding", x["alt_weld"])}

  <section id="equipment" class="sec" aria-labelledby="eq-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="eq-h">{e(d["plant_h"])}</h2><p>{e(d["plant_note"])}</p></div>
      <div class="plates" data-reveal>{eqs_html(d)}</div>
    </div>
  </section>

  <section id="strengths" class="sec sec--paper" aria-labelledby="str-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="str-h">{e(pl["str_h"])}</h2><p>{e(pl["str_p"])}</p></div>
      <div class="strengths">{strengths}</div>
    </div>
  </section>

  <section id="steps" class="sec" aria-labelledby="steps-h">
    <div class="wrap">
      <div class="sec__head"><h2 id="steps-h">{e(pl["steps_h"])}</h2><p>{e(d["proc_p"])}</p></div>
      {proc_cards(k, pl["detail"])}
      <p class="line__legend"><span><i aria-hidden="true"></i>{e(d["legend"][0])}</span><span><i class="d" aria-hidden="true"></i>{e(d["legend"][1])}</span></p>
    </div>
  </section>'''
    return shell(k, "plant", pl["title"], pl["desc"], body)

# ----- contact -----
def page_contact(k):
    d = L[k]; x = X[k]; c = P[k]["contact"]
    tel = d["tel"]; telhref = "+82" + tel.replace("+82-", "").lstrip("0").replace("-", "") if not tel.startswith("+") else tel.replace("-", "")
    kinds = "".join(f"<option>{e(o)}</option>" for o in c["kinds"])
    mail = f"mailto:{MAIL}?subject=" + urllib.parse.quote(d["subject"])
    body = f'''{page_head(k, "contact", c["h1"], c["lead"], "hero", x["alt_hero"])}

  <section id="request" class="sec" aria-labelledby="form-h">
    <div class="wrap contact">
      <form class="form" action="{mail}" method="post" enctype="text/plain" data-mailto="{MAIL}" data-subject="{e(d["subject"])}">
        <h2 id="form-h">{e(c["form_h"])}</h2>
        <p class="form__intro">{e(c["form_p"])}</p>
        <div class="form__row">
          <label>{e(c["f_company"])}<input name="company" autocomplete="organization" required></label>
          <label>{e(c["f_name"])}<input name="name" autocomplete="name" required></label>
        </div>
        <div class="form__row">
          <label>{e(c["f_email"])}<input name="email" type="email" autocomplete="email" spellcheck="false" required></label>
          <label>{e(c["f_phone"])}<input name="phone" type="tel" autocomplete="tel" inputmode="tel"></label>
        </div>
        <label>{e(c["f_kind"])}<select name="kind">{kinds}</select></label>
        <label>{e(c["f_msg"])}<textarea name="message" rows="5" placeholder="{e(c["f_msg_ph"])}"></textarea></label>
        <button class="btn" type="submit">{e(c["f_send"])}{ARROW}</button>
        <p class="form__note">{e(c["f_note"])}</p>
      </form>
      <aside class="visit" id="visit" aria-labelledby="visit-h">
        <div class="eq">
          <span class="plate__rivets" aria-hidden="true"></span>
          <h2 id="visit-h">{e(c["visit_h"])}</h2>
          <dl class="visit__list">
            <div><dt>{e(c["addr_l"])}</dt><dd>{e(d["addr"])}</dd></div>
            <div><dt>{e(c["tel_l"])}</dt><dd><a href="tel:{telhref}">{e(tel)}</a></dd></div>
            <div><dt>{e(c["mail_l"])}</dt><dd><a href="mailto:{MAIL}">{MAIL}</a></dd></div>
          </dl>
          <p class="visit__maps"><a href="https://map.naver.com/p/search/{ADDR_Q}">{e(c["map_naver"])}{ARROW}</a><a href="https://www.google.com/maps/search/?api=1&amp;query={ADDR_Q}">{e(c["map_google"])}{ARROW}</a></p>
        </div>
      </aside>
    </div>
  </section>'''
    return shell(k, "contact", c["title"], c["desc"], body)

BUILD = {"index": page_home, "about": page_about, "products": page_products, "plant": page_plant, "contact": page_contact}
for k in L:
    for pid in PAGES:
        out = os.path.join(ROOT, PATHS[k], f"{pid}.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(BUILD[pid](k))
        print("wrote", out)
