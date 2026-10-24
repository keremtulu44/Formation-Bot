# Puan doğrulama — ÖN KAYIT (veriye bakılmadan yazıldı)

Tarih: 2026-10-24
Kapsam: `formasyon kalitesi` puanının öngörü gücü ve yerine kurulabilecek koşul
tabanlı bir puanın doğrulanması.

Bu dosya, ölçümler çalıştırılmadan **önce** yazılmıştır. Bir bulgunun
"doğrulandı" sayılması için burada yazılı kuralların sağlanması gerekir.
Sonradan kural değiştirilirse o bulgu geçersiz sayılır ve yeniden hesaplanır.

## 1. Sabitlenmiş tanımlar

- **Gözlem birimi:** bir `BREAK_CONFIRMED` olayı. Kalite, olay anında
  dondurulmuş değerdir.
- **Etiket (ana):** lehte **2,0 ATR**, ters **1,0 ATR**, ufuk **24 bar**.
  Giriş = kırılım barı kapanışı. Barajlar bar içi yüksek/düşük ile ölçülür.
- **Etiket duyarlılığı (7 varyant, hepsi raporlanır):**
  (1;1;12) (1;1;24) (1,5;1;24) (2;1;24) (2;1,5;24) (2,1;48) (3;1;48).
  Bir sonuç, bu 7 varyantın **en az 6'sında** aynı yönde olmalıdır.
- **Endeks uyumu:** XU100 kapanışının 20 barlık getirisi (`close/close[-20]-1`).
  Kırılım yönü bu getirinin işaretiyle aynıysa "uyumlu". 1h/2h/4h için XU100_1h,
  1d için XU100_1d serisi kullanılır.
- **Likidite:** sembolün medyan günlük işlem hacmi (`close*volume`, 1h seride
  medyan). Kesme noktası: örneklem medyanı. "Üst yarı" = kesme üstü.
- **Geçit (önceden tanımlı kural):** bildirim yalnızca (a) endeks uyumu VAR ve
  (b) likidite üst yarı ise gider. Bu kural başka hiçbir değişken içermez.

## 2. Bölmeler (yalnızca bunlar karar için kullanılır)

- **S — ayrık sembol:** semboller `crc32(sembol) % 2` ile ikiye ayrılır.
- **Z — uzak dönem:** gözlemlerin %70 zaman kesmesi; kesmenin 35 gün öncesinden
  öncekiler keşif, 35 gün sonrasındakiler doğrulama, aradaki gözlemler atılır.
- **Y — yan yana blok:** yalnızca "tuzak" göstergesi olarak hesaplanır,
  **karar için kullanılmaz**.

## 3. Hipotezler, testler, kabul barları

### H0 (Aşama 0) — Formasyon katkısı
Kırılım gözlemleri, aynı sembolde aynı dönemde **rastgele girişlerle** kıyaslanır.
Rastgele giriş: her bar, yön = endeks işareti (uyumlu) veya tersi (uyumsuz).
Baraj/ufuk/ATR normalizasyonu kırılım gözlemleriyle birebir aynıdır.
- **Kabul:** ana etikette `kırılım(uyumlu) − rastgele(uyumlu) ≥ +3,0 puan`
  ve fark sembol kümesi bootstrap GA alt sınırı > 0.
- **Ret:** fark < +3 puan → "formasyon katkısı yok" hükmü verilir; Aşama 2-3 atlanır.

### H1 (Aşama 2) — Endeks uyumu geçidi, geniş evrende
177 sembolde, geçit tanımı yukarıdaki gibi sabit.
- **Kabul:** S ve Z bölmelerinde uyumlu − uyumsuz farkı ≥ +3 puan, her iki
  bölmede GA alt sınırı > 0, ve 7 etiket varyantının ≥ 6'sında aynı yönde.
- **Kısmi:** yalnız 1h/2h'de sağlanıyorsa "kısmen doğrulandı (1h-2h)" denir.
- **Ret:** S veya Z'de fark < +3 → S5 şans olarak işaretlenir, geçit önerilmez.

### H2 (Aşama 2b) — Likidite katkısı
Aynı barlar: likidite üst yarı − alt yarı ≥ +3 puan ve S/Z'de aynı yön.

### H3 (Aşama 3) — Geçit mi eşik mi
Aynı bildirim hacminde (kapsam %50) iki kural yarışır:
- (a) yumuşak eşik: 0,5·koşul + 0,5·şekil puanı,
- (b) sert geçit: geçit sağlanmayan gider, kalan şekil puanına göre sıralanır.
- **Kabul:** geçit, eşiği ≥ +3 puan geçerse geçit önerilir.

### H4 (Aşama 4) — Kalibrasyon
Hücre taban oranları **walk-forward** hesaplanır (tahmin yalnızca geçmiş veriden).
- **Kabul:** her hücrede |gözlenen − tahmin| ≤ 5 puan ve Brier skoru sabit
  tahminciden düşük.

## 4. Çokluk (multiplicity) kuralı
Birincil hipotez sayısı 4'tür (H0-H3 + H4). Keşifsel olarak bakılan diğer
değişkenler raporlanır ama **karar için kullanılmaz**. Bir keşifsel bulgu
birincil sayılmak istenirse bu dosya güncellenir ve bulgu yeni veride
(doğrulama diliminde) yeniden sınanır.

## 5. Durdurma kuralları
- H0 ret → Aşama 2 ve 3 çalıştırılmaz, doğrudan hüküm yazılır.
- H1 ret → geçit önerilmez; H3 anlamsız, çalıştırılmaz.
- Her durumda H4 (kalibrasyon) çalıştırılır, çünkü kartta "%76" iddiası var.

## 6. Dokunulmayacaklar
Üretim kodu, `config.py` eşikleri, kart metinleri, Telegram. Hiçbir otomatik
ayar yok. Tüm çalışma `scripts/` + `var/replay/` içinde; sonuç dokümanı
`docs/arastirma/` altına yazılır.

## 7. Bilinen sınırlar (baştan kabul)
- 18 ay, tek piyasa rejimi, tek ülke.
- 100/177 sembol, BIST evreni.
- Haber/gündem verisi yok; S2 türü takvim hipotezleri ölçülemez.
- "Kartta etiket faydalı mı" sorusu replay ile ölçülemez (kullanıcı davranışı).
