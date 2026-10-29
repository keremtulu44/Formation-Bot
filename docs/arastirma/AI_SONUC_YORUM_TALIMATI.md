# Replay Sonuç Yorumu — Dış AI İçin Tek Parça Paket
> Kullanım: bu dosyanın TAMAMINI (başlık/bitiş işaretleri dahil) başka bir AI'a yapıştır.
> O yapay zekâ yalnızca bu sonuçları yorumlayacak; ölçüm, kod, yeni soru üretmeyecek.

# ————————————————————————————————————————
# BAŞLANGIÇ — kopyala ve yapıştır
# ————————————————————————————————————————

# ROL
Sen bu projenin bulgu yorumcususun. Eline AŞAĞIDAKİ sabitlenmiş replay sonuçları verildi.
Görevin: **yalnızca yorumlamak** — sonuçları değerlendirmek, önceliklendirmek, risklerini yazmak.

# SIKI KURALLAR (ihlal etme)
1. SADECE YORUM. Yeni ölçüm isteme, "şunu da say", "tabloyu genişlet" deme, kod yazma, repo/araç adı anma.
2. ASLA sayı uydurma/ekiçme/yuvarlama. Verilmeyen bir hücre/tablo varsa "verilmedi" de; tahmin etme.
3. Eşik sözleşmesi AŞAĞIDA veriliyor; kendi eşiğini dayatma, verilenleri uygula.
4. Bulgu üreteceğin yerde bulgu üretme; mevcut bulguyu yorumla. "Ölçülmemiş" dediğin şeyleri listelemek istersen ayrı bir "izleme listesi" başlığı altında ve ölçüm talebi gibi değil, gelecek notu gibi yaz.
5. Tavsiyelerin somut ve bu projeye özgü olsun; genel geçer piyasa nasihati yazma. Her tavsiyenin dayanağı verilen sayı olsun.
6. Her sonucu iki açıdan oku: (a) karta/rozet/kuyruğa uygulanabilir tarafı, (b) motor/ölçüm güvenilirliği tarafı.

# VERİ KÜMESİ BAĞLAMI (yorum buna göre)
- BIST formasyon/zona replay arşivi: 177 sembol × 4 zaman dilimi (1h, 2h, 4h, 1d) = 708 seri; 0 hata.
- Dönem: 1h 2025-05 → 2026-10; 1d 2024-10 → 2026-10. Dış veri yok; geçmiş arşiv replay'i.
- Ham satırlar: zone 189.171 · dokunus (temas epizodu) 243.256 · swing/rol aralığı 416.685 · olay 202.938 · formasyon 34.455 · formasyon olayı 232.792. (Toplamlar önceki referans koşularla birebir tutuyor — yeniden üretim.)
- Birimler: "pp" = yüzde puan; "n" = ölçülebilir örneklem (OLCULEMEDI/sansür hariç); "sansür%" = ölçülemeyen pay.

# ÖLÇÜM SÖZLÜĞÜ (kısa)
- **CALISTI**: tepki hedefi tuttu demek — fiyat, zone yönünde 12 bar içinde ≥1.0 ATR hareket etti. Diğer sınıflar: AZ (<1 ATR), YOK (hiç ulaşmadı), TERS (ters yöne gitti), OLCULEMEDI (ölçülemiyor/sansür).
- **zone**: OB (order block) veya FVG (fair value gap) bölgesi; **dokunus**: fiyatın zone'a gelişi (epizod).
- **arrival_side**: FROM_ABOVE / FROM_BELOW / ON_ZONE_BOUNDARY — zone'a hangi yönden gelineceği.
- **repoh12**: 12 barlık hedef-sonrası ölçüm penceresi; hedefler 0.5 / 1.0 ATR.
- **PH/PL**: pivot high/low (rol taşıyan seviye); **rol süresi**: rolün kaç bar sürdüğü.
- **EXTERNAL / INTERNAL**: rolün atama kaynağı — dış sinyalle mi atandı, içsel yapıdan mı doğdu.
- **pressure_5**: 5 barlık yonlu hacim baskısı (zone yönüyle uyumlu/ters/notr etiketi).
- **effort_result_class**: efor–sonuç sınıflandırması; WEAK = güçlü efor/zayıf sonuç.
- **BOS / CHOCH / FALSE_BREAK / SWEEP**: market-structure olayları (kırılım, yön değişimi, sahte kırılım, süpürme).
- **SUPERSEDED**: olay ezildi (yenisince bastırıldı); yaş = kaç bar sonra ezildi.
- **DEVREDILDI / TEMIZLENDI**: rol kapanış türü (devredilerek / temizlenerek).
- **kirilim_atr**: yapı kırılımının derinliği (ATR ile); sığ = <0.25 ATR.
- **faz çırpınması**: formasyon yaşam döngüsünde faz değişimi sayısı.
- **DEVAM PAYI (pay_1/pay_3)**: tepe hareketin ilk 1./3. bardaki payı; medyan tepe bar = tepeye ulaşma süresi.
- **frm (formasyon)**: üçgen/kama/bayrak hattı; acik = sansürlü (hâlâ açık); ömür = bar sayısı.
- **MFE/MAE**: teyit sonrası maksimum elverişli/elverişsiz hareket (ATR).
- **K5 kirli bar**: hacmi 0 olan bar — bütün kirli pencere bulgusu bununla ilgili.

# EŞİK SÖZLEŞMESİ (bağlayıcı; sonuçlar buna göre sınıflandırıldı)
- **YAZILIR (canlıya):** |fark| ≥ 12 pp VE her iki n ≥ 30 VE sansür ≤ %20.
- **KART METNİ:** 5–12 pp (yalnız kart cümlesi/dipnot; rozet, filtre yok).
- **RED:** |fark| < 5 pp ya da hipotez yönü ters → yeni kural açılmaz (mevcut ne varsa korunur).
- **KARAR YOK:** n < 30 ya da sansür > %20 → o hücrede sayı söylenmez.
- 5–12 ile ≥12 arası: güven notu/dipnot.

# SONUÇLAR (S01–S32 · sistemden aynen çıkarıldı)

S01 · Taze zone (yaş kovası)
- VERİ: dokunus_no=1: 167.505 epizod; ölçülebilir 167.062; sansür %0.3
- ANA: TF×family hücrelerinde <=10 bar > >=40 bar yönü: 0/7 hücre
- KARAR: FVG: RED (fark −3.9pp); OB: RED (fark −2.7pp)

S02 · Rejim kayması (atr_at_touch / atr_at_birth)
- VERİ: rejim oranı dolu 241.575; ölçülebilir 241.345
- ANA: rejim medyan=1.00, p90=1.30 (kart eşik adayı)
- KARAR: FVG: YAZILIR (fark −13.9pp, azalış, n=278/40.349, sansür≤%20); OB: RED (fark −3.8pp)

S03 · Kenar ölçülemezliği (yükseklik kovası)
- VERİ: tüm epizodlar 243.256; kenar_tepki=OLCULEMEDI: 59.254 (%24.4)
- ANA/KARAR: 0–0.5 ATR'de OLCULEMEDI %49.6 → kural; ≥2 ATR'de %5.1 (karşılaştırma)

S04 · Temas süresi (dokun-kaç vs sürtünme)
- VERİ: ölçülebilir epizod 242.668/243.256 (sansür %0.2)
- ANA/KARAR: FVG: YAZILIR (+21.0pp, n=30.995/844); OB: YAZILIR (+15.3pp, n=107.978/7.511)

S05 · Yol acısı (|dip|/tepe, CALISTI temaslarda)
- VERİ: CALISTI + oran ölçülebilir 160.066
- ANA/KARAR: Genel ağır-yol payı %26.1 (eşiği aşıyor) → STOP KURALI (havuz) — hücreler tabloda (raporda)

S06 · Horizon 10 vs 12 bar
- VERİ: her iki horizon tam dolu 241.255
- ANA/KARAR: Δ medyan (havuz) = 0.000 ATR; en büyük |Δpp| = 3.4 → TAVSİYE: 10 bar (eşik: Δmedyan≥0.15 ATR ve Δpp≥3)

S07 · Temas anında terminal (zone ilk temasta kapanıyor mu)
- VERİ: tüm epizodlar 243.256; terminal_dokunusta=True: 158.789
- ANA/KARAR: havuz terminal_dokunusta=%65.3; NATIVE_TERMINAL_ON_TOUCH(repoh12)=%64.8 → kural zorunlu

S08 · Hedef zone yaşarken mi vuruluyor (repoh12, 1.0 ATR)
- VERİ: değerlendirilebilir 241.255
- ANA/KARAR: FVG: HIT_ONLY_AFTER=%61.7 → kural+karne; OB: HIT_ONLY_AFTER=%30.9 → kural+karne
- (rapor tablosu: 0.5 ATR'de FVG HIT_BEFORE %2.3 / ONLY_AFTER %71.9; OB HIT_BEFORE %39.5 / ONLY_AFTER %37.2)

S09 · Belirsizlik payı (AMBIGUOUS_ON_TERMINAL_BAR)
- VERİ: 1p0 değerlendirebilir 241.255
- ANA/KARAR: iki sayım kuralı farkı en yüksek 19.0 pp → güven etiketi düşürmesi zorunlu (≥5 pp)

S10 · Efor–sonuç uçurumu (effort_result_class)
- VERİ: kapıdan geçen 222.494; ölçülebilir 222.268; kapalı oran %8.5
- ANA/KARAR: FVG: RED (+3.6pp); OB: YAZILIR (+34.3pp, n=6.383/15.737, sansür≤%20)

S11 · Yönlü baskı uyumu (pressure_5 vs zone yönü)
- VERİ: uyumlu/ters etiketli 222.092; ölçülebilir 221.866
- ANA/KARAR: FVG/FROM_ABOVE +15.6pp · FVG/FROM_BELOW +18.5pp · FVG/ON_ZONE_BOUNDARY +25.3pp · OB/FROM_ABOVE +18.8pp · OB/FROM_BELOW +20.0pp → hepsi YAZILIR (n'ler yeterli, sansür≤%20)

S12 · Hacim ölçütü çelişkisi (percent_rank vs z_score)
- VERİ: kapıdan geçen ölçülebilir 222.268; uç çeyrek kesişimi 97.327
- ANA: ÇELİŞKİ YOK — her iki zıt hücre de 0 satır. rank ve z aynı pencerenin monotone dönüşümü (yüksek rank ⇔ yüksek z); iki ölçüt asla ayrışmaz. "Hangi ölçüt doğru" sorusu yapısal olarak boştur.
- KARAR: RED — kart standardı: rvol tek ölçüt, ek ölçüt eklenmez.

S13 · Saat dilimi etkisi (1h, Europe/Istanbul)
- VERİ: 1h epizod (10–17) 64.634
- ANA/KARAR: OB: en iyi−en kötü +5.5pp → kart metni (5–12 bandı)

S14 · Hacim veri kapısı (vp_data_ready/usable)
- VERİ: epizod 243.256; run_meta 708
- ANA/KARAR: en kötü hücre kapanı %25.3 (n≥30 hücrelerde) → S10–S12'nin o hücrelerinde KARAR YOK

S15 · Zone tekrar ziyareti (dokunus_no)
- VERİ: repoh12 tam pencere + CALISTI/YOK: 170.362; bayraklı 45.499
- ANA: dönüş gecikmesi medyanı (bayraklı CALISTI): 5.0 bar
- KARAR: FVG/no1 RED (+1.2pp) · FVG/no2 KARAR YOK (n2=17) · OB/no1 YAZILIR (+32.7pp, n=81.647/5.919) · OB/no2 YAZILIR (+34.9pp) · OB/no3+ YAZILIR (+40.3pp, n=19.915/1.251)

S16 · Rol süresi → PH/PL koruması
- VERİ: PH/PL + engelledi dolu: 86.004 rol aralığı
- ANA/KARAR: EXTERNAL/HIGH +14.7pp (n=9.321/1.023) YAZILIR · EXTERNAL/LOW +8.1pp KART METNİ · INTERNAL/HIGH +27.5pp (n=9.178/4.084) YAZILIR · INTERNAL/LOW +19.6pp (n=9.882/3.817) YAZILIR

S17 · Belirginlik (prominence) → koruma
- VERİ: prominence + engelledi dolu: 410.229
- ANA/KARAR: INTERNAL/HIGH: ≥2 vs <0.5 fark +13.7pp YAZILIR · INTERNAL/LOW: +14.4pp YAZILIR

S18 · Geç rol ataması
- VERİ: capa+confirm+engelledi dolu: 410.229 (ROL_ATANMADI hariç; havuzda %28.4)
- ANA/KARAR: EXTERNAL: 0-1 vs ≥5 fark −37.2pp YAZILIR · INTERNAL: −36.7pp YAZILIR (erken atama çok daha iyi)

S19 · Rol kapanış türü
- VERİ: tüm rol aralıkları 416.685
- ANA/KARAR: havuz DEVREDILDI payı %42.4 (eşik: ≥25 → kart cümlesi, <10 → koru) → DEVREDILDI kart cümlesi yazılır

S20 · İç yapı kırılımı sığ mı (kirilim_atr < 0.25)
- VERİ: broken=True: 89.408
- ANA/KARAR: HIGH: INTERNAL sığ kırılım %4.7 → kural-RED | LOW: %10.2 → kural-RED (sığ kırılım eşiği kurala bağlanmaz)

S21 · Rol atama hacmi → koruma (verimlilik çeyrekleri)
- VERİ: vp_ready + engelledi dolu: 370.861
- ANA/KARAR: EXTERNAL: Q4−Q1 +10.6pp → YALNIZ KART METNİ · INTERNAL: +12.1pp → YAZILIR

S22 · Olgunluk → devamlılık (BOS/CHOCH)
- VERİ: olgunluk+devamlılık dolu olay: 81.527 (toplam 202.938)
- ANA/KARAR: EXTERNAL/EVENT_BOS +2.2pp RED · INTERNAL/EVENT_BOS +3.5pp RED

S23 · Onay gecikmesi → devamlılık
- VERİ: onay_gecikmesi dolu: 202.938
- ANA/KARAR: EXTERNAL/FALSE_BREAK: Δmedyan 0.21 ATR, ΔCALISTI +2.8pp → kart dipnotu · INTERNAL/FALSE_BREAK: Δmedyan 0.34 ATR, ΔCALISTI +2.8pp → RED: hipotez TERS (geç onaylılar daha iyi; gecikme cezası kurulmaz)

S24 · Sahte kırılım/süpürme kontra sinyali
- VERİ: ters_h12 dolu: 202.550
- ANA/KARAR: hepsi RED — EXTERNAL: SWEEP +0.8 / FALSE_BREAK −0.6 / CHOCH −0.1pp · INTERNAL: +1.4 / −1.1 / −1.1pp → kontra sinyal reddedilir

S25 · Olay ezilmesi (relevance)
- VERİ: tüm olaylar 202.938; SUPERSEDED: 171.023
- ANA/KARAR: SUPERSEDED medyan age_bars=976 → EXTERNAL BOS: %93.2, INTERNAL BOS: %96.4 → bastırma kuralı

S26 · Kırılım hızı (ani kırılım, BOS)
- VERİ: pay_1 dolu BOS: 57.647
- ANA: pay_1≥0.8 payı %21.6; medyan tepe bar 6; hareketin ort. %60'ı ilk 3 barda
- KARAR: EXTERNAL fark −61.0pp YAZILIR · INTERNAL −61.1pp YAZILIR
- DİKKAT: yön NEGATİF — tepeyi 1. barda yapan kırılımlarda devam ~61pp daha zayıf; etiket yazılır ama yönü kartta doğru anlatılmalı.

S27 · Faz çırpınması → sonuç
- VERİ: frm 34.455 (kova dışı 0)
- ANA/KARAR: ≤2 vs ≥6 faz farkı — 1d −69.1pp (n=240/711) · 1h −77.9pp (n=1.571/6.593) · 2h −77.5pp (n=822/3.349) · 4h −76.9pp (n=447/1.703) → hepsi YAZILIR (çok fazla çırpınan formasyon devam etmez)

S28 · Açık örneklem payı (sansür)
- VERİ: frm=34.455, frm_olay=232.792, stable_id son olay satırı=34.455
- ANA/KARAR: havuz açık %0.5; son olayı terminal olmayan stable_id %4.8; meta.formasyon_sayisi ↔ frm tutarlı EVET; en yüksek hücre açık %6.8 (n≥30) → payda düzeltmesi yeterli

S29 · Pivot ezilmesi → teyit sonrası getiri
- VERİ: mfe+mae dolu (teyitli) 29.039; ezilen 337
- ANA/KARAR: ezilen MFE 1.10 vs değil 1.06 (Δ 0.04 ATR); MAE/MFE %84.2 vs %92.6 (Δ −8.3pp) → yalnız gözlem (ezilen n küçük)

S30 · 12 bar yeterli mi (MFE_uzun / MFE)
- VERİ: mfe + mfe_uzun dolu, mfe>0: 27.827
- ANA/KARAR: havuz medyan oran=1.00; tepe sonrada oluşan pay %0.2 → 12 bar yeterli
- NOT: eşitliğin kaynağı — formasyon sonrası ölçüm, ömür terminalinde kesiliyor (anti-dairesellik kesiği); 40-bar pencere fiilen nadiren açılıyor. Yani "12 bar yeterli" bir GÜVEN değil, YAPISAL bir sonuç.

S31 · Semboller arası yayılım (p10–p90)
- VERİ: zone ölçülebilir sembol grupları (n≥30 semboller); MS 2 scope
- ANA/KARAR: en geniş p90−p10 = 16.1pp · en düşük 5: GSRAY %49, ASELS/SISE/SASA/XU100 %59 · en yüksek 5: ANSGR/OFSYM %72, AVPGY/AKFGY/IHEVA %73 → global oran + aralık notu (yapısal gözlem)

S32 · Kirli bar penceresi (K5, 12 bar sonrası)
- VERİ: penceresi hesaplanan epizod 243.256; bayraklı epizod 90.063 (%37.02)
- ANA/KARAR: en kötü hücre kirli pencere %94.57 → kural + karne ayrımı
- NOT (yapısal): 1h'daki kirli payın kaynağı, 1h barlarının %11.62'sinin hacim=0 olması ve HEPSİNİN saat 09'da (09:30 açılış öncesi bar) toplanması. Bu, veri bozulması değil, piyasa yapısı. Bölünmüş aday bar oranları minik (%0.018–0.072); 1d hücreleri %0.8–1.2 kirli.

# ÖNCEDEN SINIFLANDIRILMIŞ §6 KARAR KOVALARI (bunu değiştirme; üzerine yorum yaz)
- CANLIYA YAZILIR (20): S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S15, S16, S17, S18, S19, S21, S25, S26, S27, S32
- YALNIZ KART METNİ (1): S13
- RED — yeni kural açılmaz (6): S01, S12, S20, S22, S23, S24
- KARAR YOK (1): S14
- YAPISAL GÖZLEM (4): S28, S29, S30, S31
(YAZILIR = kart/rozet/kuyruk/filtre yazılabilir; RED'ler mevcut kararlardan da silinmez, yalnız yeni kural açılmaz.)

# İSTENEN ÇIKTI (şu başlıklarla, sayıları kullanarak)
1. **Genel değerlendirme** (5–8 cümle): bu bulgu seti sistemi ne yönde değiştiriyor?
2. **Öncelik sıralaması** (5–8 madde): hangi bulgu → neden önemli → somut eylem (hangi bulgu kart/rozet/kuyruk/askı olur). Her maddeye dayanak sayı yaz.
3. **Kırılgan / dikkatli okunması gerekenler** (S26 yönü, S02 n=278 hücresi, S12 yapısal 0, S30 kesiği, S14 kapalı hücre, S32 %94.57 vb.): hangisine güvenilmeli, hangisi "sadece gözlem" kalmalı — nedenleriyle.
4. **Uygulama sırası + riskler**: canlıya alım sırası önerisi (bağımlılıklar/çakışmalar dahil) ve ters gidebilecek senaryolar.
5. **İzleme listesi** (opsiyonel, ölçüm talebi değil): bu sonuçların yanında gelecekte not edilecek göstergeler.

# ————————————————————————————————————————
# BİTİŞ
# ————————————————————————————————————————
