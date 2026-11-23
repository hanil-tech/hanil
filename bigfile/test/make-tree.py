#  폴더째 시험용 폴더 — 파일 1513개(0바이트~1GB, 조각 경계 8MB±1, 한글·띄어쓰기·#&%'·이모지·숨김·아주 긴 이름·「:」·맥의 낱자 한글) · 빈 폴더 4개
import os, sys, random, unicodedata
root = os.path.join(sys.argv[1], '현장 자료 2')
random.seed(7)
def w(rel, n):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f:
        while n > 0:
            k = min(n, 8 << 20); f.write(os.urandom(k)); n -= k
for d in range(50):
    sub = f"공정{d:02d}/하위 {d % 7}" if d % 3 else f"공정{d:02d}"
    for k in range(30):
        w(f"{sub}/도면_{d:02d}_{k:03d}.dwg", random.choice([0, 1, 17, 1000, 4096, 65535, random.randint(0, 200000)]))
for s in ['견적서 (최종) #3 & 50%.pdf', "+plus 파일.txt", "a'b c.txt", '.숨김파일', '시각 10:30.txt', '이모지 📐 도면.stp', '점.많은.이름.tar.gz', '이름이 ' + '아주 ' * 18 + '긴 파일.txt']:
    w('특수 이름/' + s, random.randint(1, 5000))
w('특수 이름/' + unicodedata.normalize('NFD', '맥에서 만든 한글 이름.txt'), 100)   # 맥은 한글을 낱자(NFD)로 저장한다
w('큰 파일/조립품 1GB.stp', 1 << 30)
w('큰 파일/딱 8MB.bin', 8388608); w('큰 파일/8MB 더하기 1.bin', 8388609); w('큰 파일/8MB 빼기 1.bin', 8388607)
for e in ['빈 폴더', '빈/더 빈', '공정05/비었음', '특수 이름/빈 (괄호)']:
    os.makedirs(os.path.join(root, e), exist_ok=True)
print('시험 폴더를 만들었습니다:', root)
