# Klasik Replay — "Tepeden Ne Bıraktı?" (detaylı, H=10,990 plan)

> ⚠️ **GEÇERSİZ KAYNAK ŞERİDİ (2026-11-12, FAZ9-C denetimi):** Bu belgedeki
> tüm sayılar **sızıntılı tetikle** (G5 tepki-onayı gelecek bar okuyordu;
> FAZ9-C'de kapatıldı) ölçülmüştür. **Sayılar karar tabanı olarak
> GEÇERSİZDİR; yalnız tarihsel kayıt olarak durur.** Tek geçerli ölçümler:
> `docs/tasarim/faz9_tecrube/FAZ9_PLAN_VE_SONUCLAR.md` (audit-öncesi §8 +
> audit'li §11/§12).


**Tanım:** her planın girişinden **çıkışına kadar (H=10)** ve **çıkışından
sonra20 bardaki** en yüksek kapanış ile gerçekleşen çıkış fiyatı arasındaki
fark (ATR). Çıkış sonrası koşu = "erken satılan / arkasından koşulan" fırsat.

## 1. Toplamlar (tüm120 klasik evren)

| lens | toplam | ort/plan |
|---|---|---|
| **Çıkış sonrası20-bar tepe koşusu (bırakılan)** | **+2.215,8 ATR** | **+2,24** |
| hedef sonrası devam (n299) | +1.034 ATR | +3,46 |
| zaman sonrası (n340) | +544 ATR | +1,60 |
| stop sonrası toparlanma koşusu (n351) | +637 ATR | +1,81 |
| Kazananlarda MFE gerçekleşmesi (10-bar) | — | **%46** (MFE ort +3,79A) |

**Ana50 kesiti:** bırakılan +984,9 ATR (ort +2,39) · Diğer70:
+1.230,9 ATR (ort +2,13 — daha çok stop sonrası koşu).

## 2. Yorum (dürüst okuma)

1. **+2.215 ATR "bırakılan" ham bir üst sınırdır** — hepsi geri
   alınamaz: (a) hedef sonrası devamın çoğu planlı kârın doğal devamı
   (hedefe kilitleyip koşmak İYİ davranış); (b) stop sonrası koşuların
   bir kısmı20-bar sonraki tepe, o tepeye **tutunarak** ulaşmak stop
   derinliğini de gerektirirdi (asimetri var).
2. **Gerçek izlenebilir kaçış: zaman çıkışları** (n340, ort +1,60 ATR
   arkadan koşu) — §7 erken-satış analiziyle aynı aile: erken çıkışın
   bıraktığı (§7:1.419,9 ATR,176-evren) ölçümü bu990-planda da aynı
   yönde: zaman çıkışları toplam +73 ATR kazanmış ama çıkış sonrası
   potansiyel +544 — **fark = "geç kalmak erken olmaktan iyidir"
   prensibinin kanıtı**.
3. **Stop sonrası +637 ATR koşusu** "stop yanlış yerde mi?" sorusunu
   doğuruyor — ama Faz7 tampon testi bunu yanıtladı: stop'u genişletmek
   (0,10→1,00) her adımda NET beklentiyi düşürdü (+0,295→+0,172). Yani
   o koşulara yetişmek için ödenecek derinlik, koşunun kendisinden pahalı.
   **Stop korunur.**
4. **MFE gerçekleşmesi %46:** kazananların10-bar tepe fırsatının ~yarısı
   alınıyor (hedef/R kilidi + zaman stopu). H=20 denemesi bu oranı
   artırdı ama doğrulama minderini eritti (FAZ7 Ek B) — denge H=10'da.

## 3. Çıkarılan kararlar (bu rapor + önceki testler)

| Kaldıraç | Durum |
|---|---|
| Tepeden kovalama (trailing/erken-çıkış) | **RED** (Faz7 Ek A: hep negatif) |
| Stop genişletme (koşuya yetiş) | **RED** (Faz7 Ek C) |
| H=20 (daha çok zaman) | **RED** (K3 minderi eridi) |
| **Evren = ana50** | **ÖNCELİKLİ** (FAZ8, replay doğrulanıyor) |
| Zaman-çıkışı/erken-satış ailesi (geç bırakma) | Gelecek faz adayı — ama H=20 ile kısmen çakışıyor, dikkatli |
