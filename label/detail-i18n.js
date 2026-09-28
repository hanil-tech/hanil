/*  🗣 상세 화면(포털 라벨 화면) 번역 — 라벨 발행기가 이 화면을 줄 때 끼워 넣는다.
 *   ⭐ 간편 화면에서 고른 말(localStorage 'hl_lang')을 그대로 따른다.
 *   ⚠ **글자가 정확히 같은 것만** 바꾼다 — 품명·거래처 같은 자료는 사전에 없으니 그대로 남는다.
 *   ⚠ 라벨 그림은 안쪽 틀(#pv)·미리보기 창에 따로 그려지므로 여기서 바뀌지 않는다(라벨은 늘 한국어).
 *   ⚠ 숨은 틀(간편 화면의 라벨 엔진)에서는 돌지 않는다. */
(function(){
  if (window.top !== window.self) return;
  var LG = 'ko';
  try { LG = localStorage.getItem('hl_lang') || 'ko'; } catch (e) {}
  var IX = { en: 0, vi: 1, my: 2, th: 3, ru: 4, zh: 5 }[LG];

  //  한국어 → [English, Tiếng Việt, မြန်မာ, ไทย, Русский, 中文]
  var D = {
    '🏷 라벨 뽑기': ['🏷 Print labels', '🏷 In nhãn', '🏷 တံဆိပ်ထုတ်ရန်', '🏷 พิมพ์ฉลาก', '🏷 Печать этикеток', '🏷 打印标签'],
    '① 품번을 찾아': ['① Find the part, add with', '① Tìm mã hàng, thêm bằng', '① ပစ္စည်းကိုရှာပြီး', '① ค้นหาสินค้า แล้วเพิ่มด้วย', '① Найдите деталь, добавьте', '① 查找品号，用'],
    '로 담고 ② 수량·장수를 맞춘 뒤 ③ 아래': ['② set quantity and labels ③ press', '② chỉnh số lượng, số nhãn ③ nhấn', 'ဖြင့်ထည့်ပါ ② အရေအတွက်ညှိပါ ③ အောက်က', '② ตั้งจำนวน ③ กด', '② укажите количество ③ нажмите', '添加 ② 设置数量和张数 ③ 按下方'],
    '인쇄': ['Print', 'In', 'ပရင့်', 'พิมพ์', 'Печать', '打印'],
    '를 누르세요.': ['below.', 'ở dưới.', 'ကိုနှိပ်ပါ။', 'ด้านล่าง', 'внизу.', '。'],
    '📅 생산계획에서': ['📅 From plan', '📅 Từ kế hoạch', '📅 ထုတ်လုပ်မှုအစီအစဉ်မှ', '📅 จากแผนผลิต', '📅 Из плана', '📅 从生产计划'],
    '📦 품목에서': ['📦 From items', '📦 Từ danh mục hàng', '📦 ပစ္စည်းစာရင်းမှ', '📦 จากรายการสินค้า', '📦 Из номенклатуры', '📦 从物品'],
    '🔍 찾기': ['🔍 Search', '🔍 Tìm', '🔍 ရှာရန်', '🔍 ค้นหา', '🔍 Найти', '🔍 搜索'],
    '없습니다.': ['None.', 'Không có.', 'မရှိပါ။', 'ไม่มี', 'Нет.', '没有。'],
    '찾는 중…': ['Searching…', 'Đang tìm…', 'ရှာနေသည်…', 'กำลังค้นหา…', 'Поиск…', '搜索中…'],
    '🧾 뽑을 라벨': ['🧾 Labels to print', '🧾 Nhãn sẽ in', '🧾 ထုတ်မည့်တံဆိပ်', '🧾 ฉลากที่จะพิมพ์', '🧾 К печати', '🧾 要打印的标签'],
    '📦 담은 것을': ['📦 Put all items on', '📦 Gộp tất cả vào', '📦 ထည့်ထားသမျှကို', '📦 รวมทั้งหมดเป็น', '📦 Объединить в', '📦 把已添加的合成'],
    '한 라벨': ['one label', 'một nhãn', 'တံဆိပ်တစ်ခု', 'ฉลากเดียว', 'одну этикетку', '一张标签'],
    '로 묶기 (한 파레트)': ['(one pallet)', '(một pallet)', '(ပယ်လက်တစ်ခု)', '(หนึ่งพาเลท)', '(одна паллета)', '（一个托盘）'],
    '라벨지': ['Label paper', 'Giấy nhãn', 'တံဆိပ်စက္ကူ', 'กระดาษฉลาก', 'Бумага', '标签纸'],
    '🔄 종이 방향': ['🔄 Orientation', '🔄 Hướng giấy', '🔄 စက္ကူလှည့်ပုံ', '🔄 แนวกระดาษ', '🔄 Ориентация', '🔄 纸张方向'],
    '🏷 라벨 양식': ['🏷 Format', '🏷 Mẫu nhãn', '🏷 ပုံစံ', '🏷 แบบฉลาก', '🏷 Шаблон', '🏷 样式'],
    '몇 장 (한 라벨로 묶을 때)': ['Copies (when combined)', 'Số tờ (khi gộp)', 'အရေအတွက် (ပေါင်းလျှင်)', 'จำนวนแผ่น (เมื่อรวม)', 'Копий (при объединении)', '张数（合并时）'],
    '한 줄당 수량(박스 1개에 몇 개)': ['Qty per box', 'SL mỗi thùng', 'တစ်သေတ္တာလျှင် အရေအတွက်', 'จำนวนต่อกล่อง', 'Кол-во в коробке', '每箱数量'],
    '날짜': ['Date', 'Ngày', 'ရက်စွဲ', 'วันที่', 'Дата', '日期'],
    '🆔 라벨 번호로 찾기': ['🆔 Find by label no.', '🆔 Tìm theo số nhãn', '🆔 တံဆိပ်နံပါတ်ဖြင့်ရှာ', '🆔 ค้นหาด้วยเลขฉลาก', '🆔 Найти по номеру', '🆔 按标签号查找'],
    '🔢 수량': ['🔢 Quantity', '🔢 Số lượng', '🔢 အရေအတွက်', '🔢 จำนวน', '🔢 Количество', '🔢 数量'],
    '🔖 로트': ['🔖 LOT', '🔖 LOT', '🔖 LOT', '🔖 LOT', '🔖 LOT', '🔖 LOT'],
    'LOT·차수': ['LOT', 'LOT', 'LOT', 'LOT', 'LOT', 'LOT'],
    '🏭 납품처(납품 장소)': ['🏭 Delivery place', '🏭 Nơi giao hàng', '🏭 ပို့ဆောင်မည့်နေရာ', '🏭 สถานที่ส่ง', '🏭 Место поставки', '🏭 交货地点'],
    '건너뛸 칸 수': ['Cells to skip', 'Số ô bỏ qua', 'ကျော်မည့်အကွက်', 'ช่องที่ข้าม', 'Пропустить ячеек', '跳过格数'],
    '🚚 납품 업체명': ['🚚 Supplier name', '🚚 Tên nhà cung cấp', '🚚 ပေးသွင်းသူအမည်', '🚚 ชื่อผู้ส่ง', '🚚 Поставщик', '🚚 供货商名称'],
    '📷 품목 사진': ['📷 Item photo', '📷 Ảnh hàng', '📷 ပစ္စည်းဓာတ်ပုံ', '📷 รูปสินค้า', '📷 Фото детали', '📷 物品照片'],
    '📅 날짜 인쇄': ['📅 Print date', '📅 In ngày', '📅 ရက်စွဲပရင့်', '📅 พิมพ์วันที่', '📅 Печать даты', '📅 打印日期'],
    '쓰던 라벨지': ['A used label sheet', 'Tờ nhãn đã dùng', 'သုံးပြီးတံဆိပ်စက္ကူ', 'แผ่นฉลากที่ใช้แล้ว', 'Начатый лист', '用过的标签纸'],
    '는 남은 자리부터 쓰도록': ['— to start from the free cells, enter', '— để in từ ô còn trống, nhập', '— ကျန်အကွက်မှစရန်', '— เพื่อเริ่มจากช่องว่าง ใส่', '— чтобы начать со свободных, введите', '— 要从空位开始，请填写'],
    '를 넣으세요.': ['.', '.', 'ထည့်ပါ။', '', '.', '。'],
    '🖨 미리보기·인쇄': ['🖨 Preview · print', '🖨 Xem trước · in', '🖨 ကြိုကြည့်·ပရင့်', '🖨 ดูตัวอย่าง·พิมพ์', '🖨 Просмотр · печать', '🖨 预览·打印'],
    '비우기': ['Clear', 'Xóa', 'ရှင်းရန်', 'ล้าง', 'Очистить', '清空'],
    '🧹 비우기': ['🧹 Clear', '🧹 Xóa', '🧹 ရှင်းရန်', '🧹 ล้าง', '🧹 Очистить', '🧹 清空'],
    '🖨 인쇄 화면': ['🖨 Print view', '🖨 Màn hình in', '🖨 ပရင့်မြင်ကွင်း', '🖨 หน้าพิมพ์', '🖨 Печать', '🖨 打印画面'],
    '⚠ 인쇄 창에서': ['⚠ In the print dialog set', '⚠ Trong hộp thoại in, chọn', '⚠ ပရင့်ဝင်းဒိုးတွင်', '⚠ ในหน้าต่างพิมพ์ ตั้ง', '⚠ В окне печати выберите', '⚠ 在打印窗口中设为'],
    '「배율 100%」·「여백 없음」': ['"Scale 100%" · "No margins"', '"Tỷ lệ 100%" · "Không lề"', '"စကေး 100%" · "မာဂျင်မရှိ"', '"ขนาด 100%" · "ไม่มีขอบ"', '«Масштаб 100%» · «Без полей»', '「缩放 100%」·「无边距」'],
    '담은 라벨': ['Labels', 'Nhãn đã chọn', 'ထည့်ထားသောတံဆိပ်', 'ฉลากที่เลือก', 'Этикеток', '已添加标签'],
    '용지': ['Paper', 'Giấy', 'စက္ကူ', 'กระดาษ', 'Бумага', '纸张'],
    '🖨 인쇄': ['🖨 Print', '🖨 In', '🖨 ပရင့်', '🖨 พิมพ์', '🖨 Печать', '🖨 打印'],
    '⛶ 전체화면': ['⛶ Full screen', '⛶ Toàn màn hình', '⛶ မျက်နှာပြင်အပြည့်', '⛶ เต็มจอ', '⛶ Весь экран', '⛶ 全屏'],
    '🖨 미리보기 창에서 인쇄': ['🖨 Print from preview', '🖨 In từ cửa sổ xem trước', '🖨 ကြိုကြည့်မှပရင့်', '🖨 พิมพ์จากหน้าตัวอย่าง', '🖨 Печать из просмотра', '🖨 从预览窗口打印'],
    '🖨 창 없이 바로 인쇄': ['🖨 Print directly', '🖨 In ngay', '🖨 တိုက်ရိုက်ပရင့်', '🖨 พิมพ์ทันที', '🖨 Печать сразу', '🖨 直接打印'],
    '배율 100%·여백 없음': ['Scale 100% · No margins', 'Tỷ lệ 100% · Không lề', 'စကေး 100% · မာဂျင်မရှိ', 'ขนาด 100% · ไม่มีขอบ', 'Масштаб 100% · Без полей', '缩放 100%·无边距'],
    '으로 두세요.': ['.', '.', 'ထားပါ။', '', '.', '。'],
    '사진': ['Photo', 'Ảnh', 'ဓာတ်ပုံ', 'รูป', 'Фото', '图片'],
    '거래처': ['Customer', 'Khách hàng', 'ဖောက်သည်', 'ลูกค้า', 'Заказчик', '客户'],
    '품번': ['Part no.', 'Mã hàng', 'ပစ္စည်းနံပါတ်', 'รหัสสินค้า', 'Код детали', '品号'],
    '품명': ['Part name', 'Tên hàng', 'ပစ္စည်းအမည်', 'ชื่อสินค้า', 'Название', '品名'],
    '모델': ['Model', 'Mẫu xe', 'မော်ဒယ်', 'รุ่น', 'Модель', '车型'],
    '수량': ['Qty', 'Số lượng', 'အရေအတွက်', 'จำนวน', 'Кол-во', '数量'],
    '납기': ['Due', 'Hạn giao', 'ပို့ရက်', 'กำหนดส่ง', 'Срок', '交期'],
    '담기': ['Add', 'Thêm', 'ထည့်', 'เพิ่ม', 'Добавить', '添加'],
    '장수': ['Labels', 'Số nhãn', 'တံဆိပ်', 'ฉลาก', 'Этикеток', '张数'],
    '품목 마스터에서': ['from item master', 'từ danh mục', 'ပစ္စည်းစာရင်းမှ', 'จากข้อมูลสินค้า', 'из справочника', '来自物品主数据'],
    '담은 것의 거래처를 한꺼번에 바꾸기': ['Change customer for all', 'Đổi khách hàng cho tất cả', 'ဖောက်သည်အားလုံးပြောင်း', 'เปลี่ยนลูกค้าทั้งหมด', 'Сменить заказчика у всех', '批量修改客户'],
    '모두 적용': ['Apply to all', 'Áp dụng tất cả', 'အားလုံးအသုံးပြု', 'ใช้ทั้งหมด', 'Применить ко всем', '全部应用'],
    '한 라벨에 몇 개씩': ['Qty per label', 'SL mỗi nhãn', 'တံဆိပ်တစ်ခုလျှင်', 'จำนวนต่อฉลาก', 'Кол-во на этикетку', '每张标签数量'],
    '✂ 모두 나누기': ['✂ Split all', '✂ Chia tất cả', '✂ အားလုံးခွဲ', '✂ แบ่งทั้งหมด', '✂ Разделить все', '✂ 全部拆分'],
    '✂ 나누기': ['✂ Split', '✂ Chia', '✂ ခွဲ', '✂ แบ่ง', '✂ Разделить', '✂ 拆分'],
    '위에서 ＋ 를 눌러 담으세요.': ['Press ＋ above to add.', 'Nhấn ＋ ở trên để thêm.', 'အပေါ်က ＋ ကိုနှိပ်ပြီးထည့်ပါ။', 'กด ＋ ด้านบนเพื่อเพิ่ม', 'Нажмите ＋ выше, чтобы добавить.', '点上方 ＋ 添加。'],
    'QR 만드는 중…': ['Making QR…', 'Đang tạo QR…', 'QR ပြုလုပ်နေသည်…', 'กำลังสร้าง QR…', 'Создание QR…', '正在生成二维码…'],
    '↺ 이 양식 기본으로': ['↺ Reset this format', '↺ Mặc định mẫu này', '↺ မူလပုံစံသို့', '↺ ค่าเริ่มต้นแบบนี้', '↺ Сбросить шаблон', '↺ 恢复此样式默认'],
    // 칸 안내·자리표시
    '으로 두셔야 자리가 맞습니다. 한 장 시험 인쇄해 보고 어긋나면 위': ['so positions match. Print one test sheet; if it is off, adjust with', 'để in đúng vị trí. In thử một tờ, nếu lệch thì chỉnh bằng', 'ထားမှ နေရာကိုက်မည်။ တစ်ရွက်စမ်းပြီး လွဲလျှင်', 'เพื่อให้ตำแหน่งตรง พิมพ์ทดลองหนึ่งแผ่น ถ้าเลื่อนให้ปรับด้วย', 'чтобы всё совпало. Напечатайте пробный лист и при сдвиге поправьте', '位置才对。先试打一张，偏了就用上方'],
    '밀기': ['offset', 'dịch chuyển', 'ရွှေ့ခြင်း', 'การเลื่อน', 'сдвиг', '偏移'],
    '로 맞추세요.': ['above.', 'ở trên.', 'ဖြင့်ညှိပါ။', 'ด้านบน', 'выше.', '调整。'],
    '미리보기의 세로 선을 끌면 열 폭이 바뀝니다.': ['Drag the vertical lines in the preview to change column widths.', 'Kéo đường dọc trong xem trước để đổi độ rộng cột.', 'ကြိုကြည့်ရှိ ဒေါင်လိုက်မျဉ်းကိုဆွဲပြီး ကော်လံအကျယ်ပြောင်းပါ။', 'ลากเส้นแนวตั้งในตัวอย่างเพื่อเปลี่ยนความกว้างคอลัมน์', 'Перетащите вертикальные линии в просмотре, чтобы изменить ширину столбцов.', '拖动预览中的竖线可改变列宽。'],
    '비우면 인쇄자·날짜': ['Empty = printed by · date', 'Để trống = người in · ngày', 'ဗလာ = ပရင့်သူ·ရက်စွဲ', 'ว่าง = ผู้พิมพ์·วันที่', 'Пусто = кто печатал · дата', '留空=打印人·日期'],
    '담은 품번이': ['The added parts are written on', 'Các mã đã thêm được ghi trên', 'ထည့်ထားသော ပစ္စည်းများကို', 'สินค้าที่เพิ่มจะเขียนบน', 'Добавленные детали пишутся на', '已添加的品号写在'],
    '한 장': ['one label', 'một nhãn', 'တံဆိပ်တစ်ခု', 'ฉลากเดียว', 'одной этикетке', '一张'],
    '에 「 / 」로 이어 적히고, QR 은': ['joined with " / ", and the QR holds the', 'nối bằng " / ", mã QR chứa', 'တွင် " / " ဖြင့်ဆက်ရေးပြီး QR တွင်', 'คั่นด้วย " / " และ QR เก็บ', 'через « / », а QR содержит', '上，用「 / 」连接，二维码存的是'],
    '파레트 번호': ['pallet number', 'số pallet', 'ပယ်လက်နံပါတ်', 'เลขพาเลท', 'номер паллеты', '托盘号'],
    '를 담습니다 — 기사님이 찍으면': ['— when the driver scans it,', '— khi tài xế quét,', 'ပါသည် — ယာဉ်မောင်းစကင်ဖတ်လျှင်', '— เมื่อคนขับสแกน', '— при сканировании водителем', '— 司机扫码时'],
    '담긴 품번이 모두 한 번에': ['all parts on it', 'tất cả mã hàng', 'ပါဝင်သောပစ္စည်းအားလုံး', 'สินค้าทั้งหมด', 'все детали', '所有品号'],
    '출고됩니다. 「몇 장」 칸은 같은 파레트 라벨을 몇 장 뽑을지입니다.': ['ship at once. "Copies" is how many of the same pallet label to print.', 'được xuất cùng lúc. Ô "Số tờ" là số nhãn pallet giống nhau cần in.', 'တစ်ပြိုင်နက်ထွက်မည်။ "အရေအတွက်" သည် ပယ်လက်တံဆိပ် ထုတ်မည့်အရေအတွက်ဖြစ်သည်။', 'จะออกพร้อมกัน ช่อง "จำนวนแผ่น" คือจำนวนฉลากพาเลทที่จะพิมพ์', 'отгружаются сразу. «Копий» — сколько одинаковых этикеток паллеты печатать.', '一次出库。「张数」是同一托盘标签要打印几张。'],
    '품번·품명·거래처 찾기': ['Part no. · name · customer', 'Mã · tên · khách hàng', 'နံပါတ်·အမည်·ဖောက်သည်', 'รหัส·ชื่อ·ลูกค้า', 'Код · название · заказчик', '品号·品名·客户'],
    '비우면 계획 수량 그대로': ['Empty = planned qty', 'Để trống = SL kế hoạch', 'ဗလာ = အစီအစဉ်အရေအတွက်', 'ว่าง = จำนวนตามแผน', 'Пусто = по плану', '留空=计划数量'],
    '거래처 이름': ['Customer name', 'Tên khách hàng', 'ဖောက်သည်အမည်', 'ชื่อลูกค้า', 'Заказчик', '客户名称'],
    '눌러서 크게 보기': ['Click to enlarge', 'Nhấn để phóng to', 'ချဲ့ကြည့်ရန်နှိပ်ပါ', 'คลิกเพื่อขยาย', 'Нажмите, чтобы увеличить', '点击放大'],
    '이 줄을 여러 장으로 나누기': ['Split this line into several labels', 'Chia dòng này thành nhiều nhãn', 'ဤတန်းကို ခွဲရန်', 'แบ่งแถวนี้เป็นหลายฉลาก', 'Разделить строку', '把这一行拆成多张'],
    // 고르기 칸
    '📄 세로': ['📄 Portrait', '📄 Dọc', '📄 ဒေါင်လိုက်', '📄 แนวตั้ง', '📄 Книжная', '📄 纵向'],
    '📃 가로': ['📃 Landscape', '📃 Ngang', '📃 အလျားလိုက်', '📃 แนวนอน', '📃 Альбомная', '📃 横向'],
    '라벨에 찍기': ['Print on label', 'In lên nhãn', 'တံဆိပ်ပေါ်ပရင့်', 'พิมพ์บนฉลาก', 'Печатать', '印在标签上'],
    '손으로 적기 (빈칸)': ['Write by hand (blank)', 'Viết tay (để trống)', 'လက်ရေး (ဗလာ)', 'เขียนเอง (ว่าง)', 'От руки (пусто)', '手写（空白）'],
    '직접 적기': ['Enter manually', 'Nhập tay', 'ကိုယ်တိုင်ရေး', 'ใส่เอง', 'Вручную', '手动填写'],
    '안 넣음': ['None', 'Không', 'မထည့်', 'ไม่ใส่', 'Нет', '不加'],
    '넣기 (기본)': ['Show (default)', 'Có (mặc định)', 'ထည့် (မူလ)', 'ใส่ (ค่าเริ่มต้น)', 'Да (по умолч.)', '显示（默认）'],
    '빼기': ['Hide', 'Bỏ', 'ဖယ်', 'ไม่ใส่', 'Нет', '不显示'],
    '빼기 (칸은 비워 둠)': ['Hide (leave blank)', 'Bỏ (để trống)', 'ဖယ် (ဗလာ)', 'ไม่ใส่ (เว้นว่าง)', 'Нет (пусто)', '不显示（留空）']
  };
  var PAT = [
    [/^예: (.+)$/, function (m) { return ['e.g. ', 'VD: ', 'ဥပမာ: ', 'เช่น ', 'напр.: ', '例：'][IX] + m[1]; }],
    [/^(\d+)장$/, function (m) { return m[1] + ' ' + ['labels', 'nhãn', 'ခု', 'ฉลาก', 'шт.', '张'][IX]; }],
    [/^자동 \((.+)\)$/, function (m) { return ['Auto', 'Tự động', 'အလိုအလျောက်', 'อัตโนมัติ', 'Авто', '自动'][IX] + ' (' + m[1] + ')'; }],
    [/^⚠ 품목 마스터는 「(.+)」$/, function (m) { return ['⚠ Item master: ', '⚠ Danh mục: ', '⚠ ပစ္စည်းစာရင်း: ', '⚠ ข้อมูลสินค้า: ', '⚠ Справочник: ', '⚠ 物品主数据：'][IX] + m[1]; }],
    [/^(\d+)장 준비됐습니다\.(.*)$/, function (m) {
      return m[1] + ' ' + ['labels ready.', 'nhãn đã sẵn sàng.', 'ခု အဆင်သင့်။', 'ฉลากพร้อมแล้ว', 'готово.', '张已就绪。'][IX] + m[2].replace('로트', 'LOT'); }]
  ];

  function tr(s) {
    var k = s.replace(/\s+/g, ' ').trim();
    if (!k) return null;
    var hit = D[k];
    if (hit && hit[IX] != null) return hit[IX];
    for (var i = 0; i < PAT.length; i++) { var m = k.match(PAT[i][0]); if (m) return PAT[i][1](m); }
    return null;
  }
  function walk(root) {
    if (IX == null || !root) return;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, list = [];
    while ((n = w.nextNode())) list.push(n);
    list.forEach(function (n) {
      var p = n.parentNode; if (!p || /^(SCRIPT|STYLE|TEXTAREA)$/.test(p.nodeName)) return;
      //  ⚠ 라벨지·양식 이름은 포털에 적힌 이름 그대로(사무실과 같은 이름으로 불러야 한다)
      if (p.closest && p.closest('#sheet,#form,#kPaper,#pv')) return;
      var t = tr(n.nodeValue); if (t != null) n.nodeValue = n.nodeValue.replace(/\S[\s\S]*\S|\S/, t);
    });
    var el = root.querySelectorAll ? root.querySelectorAll('[placeholder],[title]') : [];
    [].forEach.call(el, function (e) {
      var a = e.getAttribute('placeholder'); if (a) { var t1 = tr(a); if (t1 != null) e.setAttribute('placeholder', t1); }
      var b = e.getAttribute('title'); if (b) { var t2 = tr(b); if (t2 != null) e.setAttribute('title', t2); }
    });
  }
  //  🏠 간편 화면으로 돌아가는 단추
  function homeBtn() {
    if (document.getElementById('__hlHome')) return;
    var a = document.createElement('a');
    a.id = '__hlHome'; a.href = '/label';
    a.textContent = '🏠 ' + ({ ko: '처음으로', en: 'Home', vi: 'Trang đầu', my: 'ပင်မ', th: 'หน้าแรก', ru: 'Главная', zh: '首页' }[LG] || '처음으로');
    a.style.cssText = 'position:fixed;left:14px;bottom:96px;z-index:60;background:#fff;color:#1b2a4a;border:2px solid #2954A5;'
      + 'border-radius:14px;padding:12px 20px;font:700 19px "Segoe UI","Malgun Gothic",sans-serif;text-decoration:none;box-shadow:0 4px 16px rgba(0,0,0,.15)';
    document.body.appendChild(a);
  }
  //  🐞 아래 띠의 「용지」 칸이 이름 대신 번호(1·8·100)로 나오던 것 — 포털 화면이 없는 칸(name)을 읽어서다.
  //   위 「라벨지」 칸의 이름을 그대로 옮겨 적는다(같은 목록이다).
  function paperNames() {
    var a = document.getElementById('kPaper'), b = document.getElementById('sheet');
    if (!a || !b || !b.options.length) return;
    var nm = {}; [].forEach.call(b.options, function (o) { nm[o.value] = o.textContent; });
    [].forEach.call(a.options, function (o) { if (nm[o.value] && o.textContent !== nm[o.value]) o.textContent = nm[o.value]; });
  }
  function start() {
    try { fetch('/__label/alive', { cache: 'no-store' }); } catch (e) {}
    homeBtn();
    paperNames(); setInterval(paperNames, 1500);
    if (IX == null) return;
    document.documentElement.lang = LG;
    walk(document.body);
    var busy = false;
    new MutationObserver(function (ms) {
      if (busy) return; busy = true;
      try { ms.forEach(function (m) { [].forEach.call(m.addedNodes, function (x) {
        if (x.nodeType === 3) { var t = tr(x.nodeValue); if (t != null && !(x.parentNode && x.parentNode.closest && x.parentNode.closest('#sheet,#form,#kPaper,#pv'))) x.nodeValue = t; }
        else if (x.nodeType === 1) walk(x);
      }); if (m.type === 'characterData') { var t2 = tr(m.target.nodeValue); if (t2 != null) m.target.nodeValue = t2; } }); }
      finally { busy = false; }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
