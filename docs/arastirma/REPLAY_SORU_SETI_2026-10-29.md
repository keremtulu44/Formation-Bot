# REPLAY VERİSİNDEN SİSTEM FAYDASI SAĞLAYACAK SORU SETİ — v1.1

Kaynak: Formation-Bot offline replay · 708/708 seri, 0 hata
engine_version = arastirma-olcum-v1 · 32 soru (S01–S32)
Durum: koddan birebir eşleştirildi; düzeltmeler §8'de (v1.1).

## §0 ORTAK ÖLÇÜM SÖZLEŞMESİ

Her soruda geçerli, tekrar edilmez.

- **C1 ANTI-LOOKAHEAD**: Tüm uzanımlar çapa barından SONRA başlar.
  Epizod çapası = dokunus_baslangic_bar_time; ölçüm dokunus_bitis_bar_time sonrası.
  MS olay çapası = event_bar (candidate_bar DEĞİL).
  MS swing çapası = confirm_bar / capa_bar (rol ataması).
- **C2 BİRİM**: Tüm mesafeler ATR birimi. Hacim = rvol / z_score / percent_rank.
  TL ve % cinsinden uzanım yok.
- **C3 PAYDA TEMİZLİĞİ**: Payda yalnız ölçülebilir satırlar:
  yon_tepki_sinifi != OLCULEMEDI, repoh12_window_status = COMPLETE
  (uzun pencere ölçümünde yon_uzun_sansur = False ayrıca raporlanır).
- **C3b SANSÜR RAPORU**: Her tabloda n_ölçülebilir VE sansür_% birlikte verilir.
  sansür_% > 20 olan hücre karar dayanağı olamaz (yalnız gözlem notu).
  Sansürlü satır DÜŞÜRÜLMEZ, "başarılı" da SAYILMAZ.
- **C4 GÜVEN**: n>=30 YETERLI · 15<=n<30 KISMI · n<15 ZAYIF (karar yok).
  TF kırılımında hücre n<30 ise TF'ler birleştirilir (1h+2h veya 2h+4h+1d),
  birleşik n ile etiket verilir. Tek sembol / tek TF'e sıkışan soru yoktur.
- **C5 EŞİKLER (ön-tanımlı, sonradan seçilemez)**:
  HORIZON 10/12 · uzun pencere 40 · **tepki sınıfı (dokunus `yon_tepki_sinifi`)**:
  ≥1.0 ATR=CALISTI, ≥0.25=**AZ**, <0.25=**YOK**, <0=TERS, ölçülemeyen=OLCULEMEDI ·
  **devamlılık sınıfı (event `devamlilik_sinifi`)**: ≥1.0=CALISTI, ≥0.25=**AZ_DEVAM**,
  <0.25=**DEVAM_YOK**, <0=TERS, ölçülemeyen=OLCULEMEDI ·
  yükseklik kovası 0-0.5 / 0.5-1 / 1-2 / ≥2 / BILINMEYEN ·
  ATR aşım ızgarası 0.25/0.5/1.0/1.5/2.0 · hedef 0.5/1.0/1.5 ·
  tepe payı 1/3/5 bar · MS deneme 0.15/0.25/0.50 (ana 0.25).
  Yeni ölçüm eşikleri icat edilmez; yalnız bunların kesişimleri kullanılır.
  **Gruplama kovaları** (yaş, süre, gecikme, rejim oranı, çeyrek…) her sorunun
  kendi metninde önde tanımlıdır; C5 bunları değil, ölçüm eşiklerini bağlar.
- **C6 SCOPE**: MS **EXTERNAL** (pivot 5, 0.45 ATR) ve **INTERNAL** (pivot 2, 0.20 ATR)
  hiçbir soruda birleştirilmez; her sonuç iki ayrı blok/satır. (Verideki gerçek
  değerler büyük harflidir: `EXTERNAL` / `INTERNAL`.)
- **C7 ZAMAN**: bar_time = "YYYY-MM-DD HH:MM:SS+03:00" (K1, "T" yok).
  Saat kırılımlarında metin doğrudan Europe/Istanbul saati okunur.
- **C8 KIYAS**: Bütün karşılaştırmalar aynı config_hash içinde. Farklı hash →
  soru "cevaplanmadı" sayılır.

**KARAR EŞİĞİ ÖLÇEĞİ (bütün sorularda aynı, ön-kayıtlı):**

- Fark ≥12 puan + iki hücrede de n≥30 + sansür_%≤20 → canlı bileşene YAZILIR.
- Fark 5–12 puan → yalnız KART METNİ değişir (rozet yok, filtre yok).
- Fark <5 puan → hipotez REDDEDİLDİ; karta sessizce eklenmez.
- Koşu sonrası eşik kaydırılırsa sonuç geçersizdir.

---

## §1 ZONE / TEMAS EPİZODU (S01–S15)

### [S01] Taze zone
- **SORU**: Doğumundan İLK temasa kadar ≤10 bar geçen zone'larda CALISTI oranı, ≥40 bar geçenlere göre kaç puan yüksek?
- **ALANLAR**: zone.dogum_index/dogum_bar_time × dokunus(dokunus_no=1).dokunus_baslangic_index (§8-E1) → yas_bar = dokunus_baslangic_index − dogum_index × yukseklik_kovası × yon_tepki_sinifi
- **KIRILIM**: TF × family × yaş kovası (0–10 / 10–20 / 20–40 / ≥40 bar)
- **FAYDA**: süzgeç etiketi — "TAZE ZONE (≤10 bar)" rozeti + kuyruk önceliği. Yaş etkisi yoksa rozet kaldırılır (yanlış pozitif temizliği).
- **N**: dokunus⋈zone, dokunus_no=1 → ~120–150k; en küçük hücre (1d FVG ≥40 bar) ~1.2–2k.
- **CEVAP**: "%A (≤10 bar, n=…, sansür %…)" vs "%B (≥40 bar, n=…)" = +N puan; 8 hücrenin kaçında aynı yön?
- **EŞİK**: ≥12 → rozet + öncelik; 5–12 → yalnız metin; <5 → rozet yok.

### [S02] Rejim kayması
- **SORU**: Zone rejim kaydırdıysa (atr_at_touch / atr_at_birth ≥1.5) tepki bozuluyor mu — CALISTI oranı 0.8–1.2 grubuna göre kaç puan düşük?
- **ALANLAR**: dokunus.atr_at_touch ÷ zone.atr_at_birth = rejim_orani × yon_tepki_sinifi × yukseklik_kovası × zone.family
- **KIRILIM**: family × rejim kovası (<0.8 / 0.8–1.2 / 1.2–1.5 / ≥1.5) — OB'de daha keskin
- **FAYDA**: yapma-kuralı — "rejim_orani ≥1.5 ise yükseklik_kovası'na dayalı kart cümlesi kullanılmaz" (yükseklik_atr doğumda ölçüldü, temas anında yanıltıcı).
- **N**: dokunus⋈zone; atr_at_birth tüm zone satırlarında dolu → ~230k; kova×family ≥5k.
- **CEVAP**: "%A (≥1.5)" vs "%B (0.8–1.2)" = −N puan; ayrıca rejim_orani medyan ve p90 (kart cümlesinde eşik olarak kullanılacak).
- **EŞİK**: ≥12 → kural; aksi halde gözlem notu.

### [S03] Kenar ölçülemezliği
- **SORU**: Yükseklik 0–0.5 ATR zone'larda dokunuşların yüzde kaçı TUM_ZONE/ZONE_ICI (kenar ölçülemez) düşüyor, ≥2 ATR zone'larda kaç?
- **ALANLAR**: dokunulan_kenar ∈ {TUM_ZONE, ZONE_ICI} payı × **kenar_tepki_sinifi = OLCULEMEDI** (§8-E10; kenar_olcum_yonu bu satırlarda None olur) × yukseklik_kovası × family (kenar_* vs yon_* ayrışması)
- **KIRILIM**: yukseklik_kovası × TF × family
- **FAYDA**: yapma-kuralı — "yükseklik <0.5 ATR zone'da kenar-çapalı (kenar_*) ölçüm kart cümlesine girmez; yalnız yon_* kullanılır".
- **N**: tüm epizodlar (kenar etiketi her satırda; GECERSIZ kovası ayrıca raporlanır); kova başına ≥15–20k.
- **CEVAP**: 5 satırlık kova tablosu, her satırda n + sansür %.
- **EŞİK**: OLCULEMEDI payı ≥%40 → kural; %20–40 → uyarı cümlesi; <%20 → kural reddedilir.

### [S04] Temas süresi
- **SORU**: Uzun süren temas (dokunus_bar_sayisi ≥7) ile tek barlık "dokun-kaç" epizodu arasında CALISTI oranı kaç puan fark ediyor?
- **ALANLAR**: dokunus_bar_sayisi kovası (1 / 2–3 / 4–6 / ≥7) × yon_tepki_sinifi × yon_dip_atr (negatif korunur, §8-E16) × yukseklik_kovası × family
- **KIRILIM**: family × süre kovası (FVG'de uzun sürtünme = daha çok ihlal beklenir)
- **FAYDA**: uyarı cümlesi — "zone 6+ bar sürtünüyor, temas kalitesi düşük" + kuyrukta öncelik düşürme.
- **N**: tüm epizodlar; ≥7 kovası ~15–25k; 1d FVG hücresi sınırda → n<30 ise TF birleştirilir.
- **CEVAP**: "%A (1 bar)" vs "%B (≥7 bar)" = ±N puan; kova başına medyan yon_tepe_atr.
- **EŞİK**: ≥12 → uyarı + kuyruk düşürmesi; 5–12 → yalnız uyarı; <5 → uyarı yok.

### [S05] Yol acısı (stop mesafesi)
- **SORU**: CALISTI temaslarda tepeye giden yolun en kötü ters hareketi ne kadar derin — |yon_dip_atr|/yon_tepe_atr ≥0.5 olan temasların payı hangi geometride %25'i aşıyor?
- **ALANLAR**: yon_dip_atr, yon_tepe_atr, yon_pay_1/3/5, yon_tepki_sinifi, yukseklik_kovası, dokunus_bar_sayisi, family
- **KIRILIM**: family × yukseklik_kovası × TF (oran eşikleri 0.25/0.5/1.0 — mevcut ızgaradan)
- **FAYDA**: backtest hipotezi → "stop = |dip| p90" kuralı + kartta "%X olasılıkla Y ATR ters hareket" cümlesi.
- **N**: yon_dip_atr tüm ölçülebilir epizodlarda (~200k); CALISTI alt kümesi ~60–80k.
- **CEVAP**: hücre başına "yol acısı ≥0.5 payı = %A (n=…)", medyan dip = −N ATR, p90 dip = −M ATR. Karta yazılacak: medyan ve p90.
- **EŞİK**: pay ≥%25 → o hücre için stop kuralı; <%15 → "sığ yol" varsayımı korunur.

### [S06] Horizon 10 vs 12
- **SORU**: HORIZON'u 10'dan 12'ye çıkarmak ne kazandırıyor — (yon_h12 − yon_h10) medyanı hangi family/TF'de ≥0.15 ATR?
- **ALANLAR**: yon_h10, yon_h12, yon_h10_decay, yon_h12_decay, yon_tepe_bar, yon_tepki_sinifi
- **KIRILIM**: TF × family × yön (direction=bullish/bearish)
- **FAYDA**: backtest hipotezi → horizon parametresi hücre bazında sabitlenir (kazanç yoksa 10 bar: daha az sansür).
- **N**: yon_h10/h12 birlikte dolu ~200k; hücreler geniş.
- **CEVAP**: "Δ medyan = +N ATR, CALISTI sınıfına geçiş +P puan, n=…, sansür %…"; medyan yon_tepe_bar da yazılır (kaçıncı barda tepe).
- **EŞİK**: Δ medyan ≥0.15 ATR ve sınıf geçişi ≥3 puan → 12 bar; aksi halde 10 bar.

### [S07] Temas anında terminal
- **SORU**: Temas barının kendisinde zone ölüyor mu — **terminal_dokunusta=True** oranı family ve TF bazında yüzde kaç, ve bu satırlarda ölçüm tamamen kayıp mı (repoh12_window_status = NATIVE_TERMINAL_ON_TOUCH)?
- **ALANLAR**: terminal_dokunusta (§8-E4), repoh10_window_status, repoh12_window_status (§8-E3), dokunus.native_terminal_category + zone ⋈ native_terminal_state/reason, family, dokunus_no, yukseklik_kovası
- **KIRILIM**: TF × family × dokunus_no (1 / 2 / 3+) × yukseklik_kovası
- **FAYDA**: yapma-kuralı — "NATIVE_TERMINAL_ON_TOUCH satırından kart üretilmez" (ölçüm yok, sinyal de yok) + karne paydası düzeltmesi.
- **N**: tüm epizodlar sayılabilir (bayrak her satırda).
- **CEVAP**: family×TF tablosunda "%A (n=…)".
- **EŞİK**: oran ≥%10 → kural zorunlu; %5–10 → uyarı; <%5 → yalnız not.

### [S08] Hedef zone yaşarken mi vuruluyor
- **SORU**: 1.0 ATR hedefi gerçekten zone yaşarken mi vuruluyor — target bloklarında HIT_BEFORE_NATIVE_TERMINAL ile HIT_ONLY_AFTER_TERMINAL payı family bazında kaç?
- **ALANLAR**: repoh{10,12}_target_{0p5,1p0,1p1p5}_atr_{hit_full_window, hit_before_native_terminal, possible_on_terminal_bar, hit_only_after_terminal, active_zone_category} (§8-E1: bu blok dokunus satırına repoh önekli kopyalandı), dokunus.native_terminal_category, yon_tepe_atr, family
- **KIRILIM**: family × TF × hedef mesafesi (0.5 / 1.0 / 1.5) — ana horizon repoh12_
- **FAYDA**: yapma-kuralı — "HIT_ONLY_AFTER_TERMINAL hedefe sayılmaz, karnede ayrı satır"; kart dipnotu "zone öldükten sonra ulaşılan hedef sayılmıyor".
- **N**: ölçülebilir epizodlar (active_zone_category != NOT_EVALUABLE); her family×hedef ≥3k.
- **CEVAP**: family bazında 4 sütun: HIT_BEFORE / AMBIGUOUS_ON_TERMINAL_BAR / HIT_ONLY_AFTER / NOT_REACHED (yüzde + n).
- **EŞİK**: ONLY_AFTER payı ≥%15 → kural + karne ayrımı; %5–15 → kart dipnotu; <%5 → yok.

### [S09] Belirsizlik payı
- **SORU**: Ölçüm belirsizliği ne kadar büyük — AMBIGUOUS_ON_TERMINAL_BAR payı yüksek hücrelerde iki farklı sayım kuralı arasındaki fark kaç puan?
- **ALANLAR**: repoh12_target_1p0_atr_possible_on_terminal_bar, repoh12_target_1p0_atr_active_zone_category (§8-E1, §8-E3), yon_tepki_sinifi, yukseklik_kovası, dokunus_bar_sayisi
- **KIRILIM**: family × yukseklik_kovası (dar zone'da terminal bar ≈ temas barı)
- **FAYDA**: güven etiketi kuralı — "AMBIGUOUS payı >%5 hücrede YETERLI düşürülür, KISMI olur".
- **N**: hedef blokları; AMBIGUOUS alt kümesi (oran için yeterli, hücrede n<30 uyarısı C4 ile yönetilir).
- **CEVAP**: hücre başına "AMBIGUOUS payı = %A" ve "iki sayım kuralı farkı = ±N puan".
- **EŞİK**: fark ≥5 puan → güven etiketi düşürmesi zorunlu.

### [S10] Efor–sonuç uçurumu
- **SORU**: Hacim eforu var ama fiyat ilerlemiyorsa temas bozuluyor mu — efor-sonuç sınıfı **HIGH_EFFORT_WEAK_RESULT (+ VERY_HIGH_EFFORT_WEAK_RESULT)** olanlarda CALISTI, **HIGH_EFFORT_STRONG_RESULT**'a göre kaç puan düşük?
- **ALANLAR**: vp_effort_result_class (gerçek enum: NEUTRAL / RISING_EFFORT_STRONG_RESULT / HIGH_EFFORT_STRONG_RESULT / HIGH_EFFORT_WEAK_RESULT / VERY_HIGH_EFFORT_WEAK_RESULT — §8-E5), vp_volume_result_efficiency, vp_capital_result_efficiency, vp_net_progress_atr, vp_directional_efficiency × yon_tepki_sinifi × yukseklik_kovası
- **KIRILIM**: family × effort_result_class — yalnız vp_data_ready=True ve vp_volume_usable=True (diğerleri "hacim verisi yok" kovasında, düşürülmez)
- **FAYDA**: uyarı cümlesi — "yüksek hacim, düşük ilerleme: temas kalitesi zayıf" + kuyrukta ceza puanı.
- **N**: usable satır ~150–190k; en küçük sınıf ≥8k bekleniyor.
- **CEVAP**: sınıf × tepki matrisi (satır yüzdeleri); ana sayı "%A vs %B = −N puan".
- **EŞİK**: ≥12 → uyarı + ceza; 5–12 → yalnız uyarı; <5 → kaldır.

### [S11] Yönlü baskı uyumu
- **SORU**: Temas anındaki yönlü değer baskısı zone yönüyle aynı işaretli mi — aynı olanlarda CALISTI oranı ters işaretlilere göre kaç puan yüksek?
- **ALANLAR**: vp_directional_value_pressure_5 ve _10, zone.direction (bullish/bearish; beklenen_yon=UP/DOWN/BELIRSIZ destek) × yon_tepki_sinifi × arrival_side × approach_direction
- **KIRILIM**: family × arrival_side (FROM_ABOVE / FROM_BELOW) — geri çekilme ve kuvvetle dalma ayrı okunur; INSIDE_ZONE / ON_ZONE_BOUNDARY / NO_PREVIOUS_BAR ayrı kovada
- **FAYDA**: süzgeç etiketi — "baskı uyumlu temas" (pin/share); uyumsuzsa kart nötr.
- **N**: usable vp; arrival_side×family ≥2k.
- **CEVAP**: "%A (uyumlu)" vs "%B (ters)" = +N puan; pressure_5 medyanı sınıf bazında (kart cümlesinde eşik olarak kullanılacak).
- **EŞİK**: ≥12 → süzgeç; 5–12 → kart metni; <5 → kullanılmaz.

### [S12] Hacim ölçütü çelişkisi
- **SORU**: Hacim ölçütleri çeliştiğinde hangisi doğru çıkıyor — vp_volume_percent_rank yüksek ama vp_volume_z_score düşük (ve tersi) temaslarda CALISTI hangi ölçüte uyuyor?
- **ALANLAR**: vp_volume_percent_rank, vp_volume_z_score, vp_rvol, vp_volume_slope, vp_volume_result_efficiency × yon_tepki_sinifi
- **KIRILIM**: family × TF × (percent_rank çeyreği) içinde z_score çeyreği → 2×2 çelişki hücreleri
- **FAYDA**: kart metni standardı — kartta TEK hacim ölçütü kullanılacak; hangisi seçildiği yazılır (yanlış "hacimli" vurgusunun temizlenmesi).
- **N**: usable vp içinde 2×2 hücreler; en küçük hücre ~10–20k bekleniyor.
- **CEVAP**: 2×2 matris, her hücrede CALISTI % + n; "çelişkide kazanan ölçüt: … / fark yok".
- **EŞİK**: çelişki hücrelerinde fark ≥12 puan → kart standardı o ölçüte sabitlenir; ikisi aynı yöne bakıyorsa rvol yeterli (ek ölçüt eklenmez).

### [S13] Saat dilimi etkisi
- **SORU**: 1h temaslarında 10:00–11:00 ve 17:00–18:00 dilimlerinde CALISTI oranı, 12:00–15:00 dilimine göre kaç puan fark ediyor?
- **ALANLAR**: dokunus_baslangic_bar_time (Europe/Istanbul, K1; saat = metnin [11:16] dilimi) × yon_tepki_sinifi × yukseklik_kovası; destek: dokunus.vp_rvol
- **KIRILIM**: yalnız 1h × family × saat dilimi (1d'de saat anlamsız)
- **FAYDA**: süzgeç etiketi — seans dilimi rozeti / saat bazlı susturma ("kapanışa doğru zone temasları düşük öncelik").
- **N**: 1h epizodlar ~90–110k; saat dilimi × family ≥5k.
- **CEVAP**: saat tablosu (BIST seansı 10…18) × CALISTI %, her hücrede n; ana sayı "10:00 = %A, 12–15 ort. = %B, fark +N puan".
- **EŞİK**: en iyi–en kötü dilim farkı ≥12 → süzgeç; 5–12 → kart metni; <5 → yok.

### [S14] Hacim veri kapısı
- **SORU**: Hacim bloğu kart üretmeye yetecek kadar dolu mu — vp_data_ready=False veya vp_volume_usable=False oranı TF ve family bazında yüzde kaç?
- **ALANLAR**: vp_data_ready, vp_volume_usable, vp_capital_usable, family, vp_effort_result_class, run_meta.vp_data_quality
- **KIRILIM**: TF × family × (usable / not-usable)
- **FAYDA**: yapma-kuralı — "vp_volume_usable=False satırda kartta hacim cümlesi yazılmaz"; karne paydasından hacim koşullu sorular çıkarılır.
- **N**: tüm epizodlar + run_meta satırları.
- **CEVAP**: yüzde tablosu + run_meta.vp_data_quality dağılımı (kaç seri "iyi").
- **EŞİK**: oran ≥%20 olan hücrede S10–S12 geçersiz sayılır.

### [S15] Zone tekrar ziyareti
- **SORU**: "Çalışan" zone geri geliyor mu — CALISTI epizodlarda repoh12_next_same_zone_touch_in_window=True oranı, **YOK** (§8-E2) olanlara göre kaç puan yüksek?
- **ALANLAR**: repoh10_next_same_zone_touch_in_window, repoh12_next_same_zone_touch_in_window (§8-E3), sonraki_epizot_index, dokunus_baslangic_index (§8-E1), yon_tepki_sinifi, yon_tepe_atr, dokunus_no
- **KIRILIM**: family × dokunus_no (1 vs 2) × yukseklik_kovası
- **FAYDA**: kart metni — "zone tekrar test edilebilir, ikinci teması bekle" + aynı zone için tekrar kart bastırma (bildirim gürültüsü azaltma).
- **N**: bayrak dolu tüm ölçüm satırları; CALISTI alt kümesi ~60–80k → hücreler ≥2k.
- **CEVAP**: "%A (CALISTI)" vs "%B (YOK)" = +N puan + dönüş gecikmesi medyanı (sonraki_epizot_index − dokunus_baslangic_index), bar.
- **EŞİK**: fark ≥12 → cümle + bastırma; <12 → cümle yok.

---

## §2 MS SWING (S16–S21) — external ve internal HER ZAMAN ayrı blok (C6)

### [S16] Rol süresi → koruma
- **SORU**: Rol süresi koruma sağlıyor mu — rol_sure_bar ≥20 seviyelerde engelledi_025=True oranı, ≤5 bar olanlara göre kaç puan yüksek?
- **ALANLAR**: rol_sure_bar, engelledi_{015,025,050}, rol_kapanis, **rol** (PH/PL/WH/WL/SH/SL) + structural_role_final (§8-E7), broken_bar, kirilim_atr, scope
- **KIRILIM**: scope (EXTERNAL / INTERNAL AYRI, §8-E7) × side (HIGH/LOW) × rol süresi kovası (1–5 / 6–10 / 11–20 / ≥21)
- **FAYDA**: süzgeç etiketi — "köklü seviye" (≥20 bar) rozeti + kuyruk önceliği. EXTERNAL'da çıkıp INTERNAL'da çıkmıyorsa rozet yalnız EXTERNAL'a yazılır.
- **N**: rol aralıkları; engelledi alanı dolu PH/PL alt kümesi; her kova ≥30k.
- **CEVAP**: kova tablosu, iki scope bloğu; ayrıca engelledi_None (sansür) payı.
- **EŞİK**: ≥12 → rozet; 5–12 → kart metni; <5 → kullanılmaz.

### [S17] Belirginlik → koruma
- **SORU**: Belirginlik korumanın habercisi mi — prominence_atr ≥1.0 seviyelerde engelledi_025 oranı, <0.5 olanlara göre kaç puan yüksek?
- **ALANLAR**: prominence_atr, distance_atr, quality, engelledi_025, max_yaklasma_atr, red_magnitude_atr, scope
- **KIRILIM**: scope × side (HIGH/LOW) × prominence kovası (0–0.5 / 0.5–1 / 1–2 / ≥2 — yükseklik kovası ile aynı sınırlar)
- **FAYDA**: kart metni — seviye kartında "belirgin tepe" vurgusu; düşük prominence'ta "zayıf seviye" uyarısı.
- **N**: prominence tüm rol-aralığı satırlarında; scope×side×kova ≥10k.
- **CEVAP**: "EXTERNAL HIGH: %A vs %B = +N puan" (kova tablosu, iki scope bloğu).
- **EŞİK**: ≥12 → metin + uyarı; 5–12 → yalnız vurgu; <5 → kaldır.

### [S18] Geç rol ataması
- **SORU**: Rol geç atandıysa seviye daha mı zayıf — (capa_bar − confirm_bar) ≥5 bar olanlarda engelledi_025 oranı, 0–1 bar olanlara göre kaç puan düşük?
- **ALANLAR**: confirm_bar, capa_bar, rol_ilk_bar, engelledi_025, bars_to_break_from_rol, scope — **capa_bar yoksa (rol_kapanis=ROL_ATANMADI) soru kapsamı dışındadır** (§8-E7)
- **KIRILIM**: scope × atanma gecikmesi kovası (0–1 / 2–4 / ≥5 bar)
- **FAYDA**: uyarı cümlesi — kartta "rol yeni atandı (ölçüm gecikmesi N bar)"; gecikme yüksekse seviye iddiası yumuşatılır.
- **N**: capa_bar dolu satırlar; engelledi_None payı ayrıca raporlanır (C3b).
- **CEVAP**: "EXTERNAL: %A (0–1 bar) vs %B (≥5 bar) = −N puan".
- **EŞİK**: ≥12 → uyarı cümlesi; 5–12 → kart dipnotu; <5 → yok.

### [S19] Rol kapanış türü
- **SORU**: Rol el değiştirdiğinde mi kapanıyor, yoksa doğrudan mı kırılıyor — **rol_kapanis** gerçek dağılımı (DEVREDILDI = rolü başka swing aldı / TEMIZLENDI = rol kimliği 0'a düştü / VERI_SONU_SANSURLU / ROL_ATANMADI — §8-E6) ne; her kapanış türünde `broken=True` payı ve DEVREDILDI ile bitenlerin medyan rol_sure_bar'ı kaç bar? (Kırılım ayrı alan: `broken`/`broken_bar`.)
- **ALANLAR**: rol_kapanis, rol, rol_sure_bar, rol_son_bar, broken, broken_bar, structural_role_final, finalized, scope
- **KIRILIM**: scope × side (HIGH/LOW) × rol (PH/WH/SH, PL/WL/SL)
- **FAYDA**: kart metni — "seviye kırılmadı, rol değiştirdi (zayıf tepe → güçlü tepe)"; karne "kırılmadı" sayımının doğru yorumu.
- **N**: rol_kapanis her rol aralığında; en seyrek hücre (INTERNAL WL/SL) ≥5k beklenir, aksi halde C4 birleştirme.
- **CEVAP**: rol × kapanış türü çapraz tablo + her türde broken % + rol_sure_bar medyanı; "PH: DEVREDILDI %A / TEMIZLENDI %B / VERI_SONU_SANSURLU %C / ROL_ATANMADI %D".
- **EŞİK**: DEVREDILDI payı ≥%25 → kart cümlesi; <%10 → "engellendi" ifadesi korunur.

### [S20] İç yapı kırılımı sığ mı
- **SORU**: İç yapı kırılımları sığ mı kalıyor — INTERNAL'da medyan kırılım aşımı (kirilim_atr, pencere-içi 1-tabanlı konumun ATR aşımı — §8-E15) EXTERNAL'a göre kaç ATR sığ ve bars_to_break medyanı kaç bar kısa?
- **ALANLAR**: kirilim_atr, kirilim_bar (pencere-içi 1-tabanlı), broken_bar (mutlak bar), bars_to_break, bars_to_break_from_rol, bars_to_break_sansur, scope, broken
- **KIRILIM**: scope (AYRI BLOK) × side × bars_to_break kovası (1 / 2–3 / 4–6 / ≥7)
- **FAYDA**: yapma-kuralı — "internal kırılımı BOS/CHOCH sayılmaz, süzgeçte tek başına yeterli değil" (iç yapının gürültüsü sayısallaştırılır).
- **N**: broken=True alt kümesi; scope başına ≥60k.
- **CEVAP**: iki blok: INTERNAL "medyan aşım N ATR, medyan süre M bar, sığ kırılım (aşım <0.25 ATR) %A" vs EXTERNAL aynı üçlü.
- **EŞİK**: INTERNAL'da sığ kırılım payı ≥%40 → kural; %25–40 → uyarı; <%25 → kural reddedilir.

### [S21] Rol atama hacmi → koruma
- **SORU**: Rol atama anındaki hacim verimliliği korumayı öngörüyor mu — üst çeyrekte engelledi_025 oranı alt çeyreğe göre kaç puan yüksek?
- **ALANLAR**: vp_volume_result_efficiency, vp_rtv, vp_rvol, vp_directional_efficiency, engelledi_025, scope
- **KIRILIM**: scope × verimlilik çeyreği (Q1–Q4); yalnız vp_data_ready satırları, bayraksızlar "veri yok" kovasında düşürülmeden taşınır
- **FAYDA**: süzgeç etiketi — "verimli hacimli seviye" kart önceliği.
- **N**: vp taşıyan rol aralıkları; çeyrek hücreleri ≥50k.
- **CEVAP**: Q1..Q4 tablosu iki scope bloğu; "%Q4 − %Q1 = +N puan (n=…)".
- **EŞİK**: Q4−Q1 ≥12 → süzgeç; 5–12 → kart metni; <5 → yok.

---

## §3 MS OLAY (S22–S26) — çapa event_bar (onay), candidate_bar DEĞİL

### [S22] Olgunluk → devamlılık
- **SORU**: Olayın olgunluk etiketi devamlılığı öngörüyor mu — bos_maturity=INITIAL_STRUCTURE olan BOS'larda CALISTI oranı, CONTINUATION'a göre kaç puan düşük?
- **ALANLAR**: bos_maturity (NOT_APPLICABLE / INITIAL_STRUCTURE / TRANSITION_CONFIRMATION / CONTINUATION), devamlilik_sinifi, devam_h12, devam_h12_kapanis_atr (§8-E9), event_type (gerçek değer EVENT_BOS / EVENT_CHOCH — §8-E8), direction, onay_gecikmesi_bar, scope
- **KIRILIM**: scope × bos_maturity × direction (UP/DOWN) × event_type (BOS/CHOCH)
- **FAYDA**: süzgeç etiketi — "ilk yapı kırılımı = zayıf sinyal"; CHOCH kartında "geçiş henüz onaylanmadı" uyarısı.
- **N**: olaylar; INITIAL_STRUCTURE ve CONTINUATION ≥50k, TRANSITION_CONFIRMATION ~15–30k (C4 uyarısı ile raporlanır).
- **CEVAP**: maturity × devamlilik_sinifi matrisi, iki scope bloğu; "%A vs %B = −N puan (n=…, devam_sansur %…)".
- **EŞİK**: ≥12 → süzgeç + kart koşulu; 5–12 → yalnız metin; <5 → kaldır.

### [S23] Onay gecikmesi
- **SORU**: Teyit gecikmesi devamlılığı bozuyor mu — onay_gecikmesi_bar ≥4 olaylarda medyan devam_h12, 0–1 bar olanlara göre kaç ATR düşük?
- **ALANLAR**: onay_gecikmesi_bar (event_bar − candidate_bar; event_bar yoksa None → OLCULEMEDI, §8-E13b), devam_h12, devam_tepe_atr, devam_tepe_bar, devamlilik_sinifi, event_type, confirmation_status (CONFIRMED / CANDIDATE_FAILED), scope
- **KIRILIM**: scope × event_type × gecikme kovası (0–1 / 2–3 / ≥4 bar)
- **FAYDA**: uyarı cümlesi — "geç onaylı kırılım: hareketin ilk N barı kaçırıldı" + gecikmiş olaylarda kuyruk önceliği düşürme.
- **N**: onay_gecikmesi_bar dolu satırlar; ≥4 kovası ~40–60k.
- **CEVAP**: "medyan devam_h12: %A (0–1 bar) vs %B (≥4 bar) = −N ATR; CALISTI farkı −P puan".
- **EŞİK**: Δ medyan ≥0.25 ATR veya CALISTI farkı ≥12 puan → uyarı + öncelik düşürmesi; aksi halde yalnız kart dipnotu.

### [S24] Sahte kırılım / süpürme kontra sinyali
- **SORU**: Sahte kırılım/süpürme kontra sinyal olarak kullanılabilir mi — EVENT_FALSE_BREAK ve EVENT_SWEEP olaylarında olay yönünün TERSİNE 12 bar hareket (ters_h12 medyanı) BOS'a göre kaç ATR büyük ve "ters yön ≥1.0 ATR" oranı kaç puan yüksek?
- **ALANLAR**: event_type (EVENT_BOS / EVENT_FALSE_BREAK / EVENT_SWEEP / EVENT_CHOCH — §8-E8), ters_h12, uyum (UYUMLU/UYUMSUZ), devam_h12, broken_swing_identity, broken_level, direction, scope
- **KIRILIM**: scope × event_type × direction
- **FAYDA**: backtest hipotezi — "süpürme sonrası ters yön" ayrı kart tipi olabilir mi; kazanç yoksa EVENT_FALSE_BREAK yalnız uyarı olarak kalır, sinyal sayılmaz.
- **N**: FALSE_BREAK+SWEEP (scope kırılımında C4 birleştirme); BOS ≥80k.
- **CEVAP**: tip × "ters yön ≥1.0 ATR %" tablosu + medyan ters_h12; "%A (SWEEP) vs %B (BOS) = +N puan".
- **EŞİK**: ≥12 puan yüksek → kontra kart tipi açılır; 5–12 → yalnız uyarı cümlesi; <5 → kontra iddia reddedilir.

### [S25] Olay ezilmesi
- **SORU**: Olay kartları birbirini eziyor mu — relevance=SUPERSEDED payı event_type ve scope bazında yüzde kaç ve ezilme için geçen medyan süre (age_bars) kaç bar?
- **ALANLAR**: relevance (CURRENT / SUPERSEDED / HISTORICAL), age_bars, validity (VALID / FAILED), outcome (PENDING / FOLLOW_THROUGH_CONFIRMED / FAILED / OBSERVED), confirmed_by/failed_by, event_type, scope, direction
- **KIRILIM**: scope × event_type × direction
- **FAYDA**: yapma-kuralı (kuyruk filtresi) — "aynı yönde ardışık BOS'ta yalnız SONUNCU kart gönderilir; SUPERSEDED bildirimi bastırılır".
- **N**: relevance tüm olaylarda; en küçük scope×tip hücresi ≥5k bekleniyor.
- **CEVAP**: tip × relevance yüzdeleri (iki blok) + medyan age_bars; "BOS: CURRENT %A / SUPERSEDED %B, medyan ezilme M bar".
- **EŞİK**: SUPERSEDED payı ≥%20 → bastırma kuralı; %10–20 → uyarı; <%10 → kural gereksiz.

### [S26] Kırılım hızı (ani kırılım)
- **SORU**: Kırılım sonrası hareket ilk barlarda mı oluyor — BOS'ta devam_pay_1 ≥0.8 olanların payı ne ve bu olaylarda CALISTI, pay_1 <0.3 olanlara göre kaç puan yüksek?
- **ALANLAR**: devam_pay_1/3/5, devam_tepe_bar, devam_tepe_atr, devamlilik_sinifi, devam_h12_decay (§8-E9), event_type, scope
- **KIRILIM**: scope × event_type × direction
- **FAYDA**: kart metni — "ani kırılım" etiketi; tepe gecikmesi büyükse kart cümlesi "hareket yavaş açılıyor, teyit bekle" olur (izleme süresi).
- **N**: devam_pay_* dolu ölçülebilir olay; BOS ≥80k.
- **CEVAP**: pay_1 kova tablosu: "%A (≥0.8)" CALISTI %; medyan tepe bar = M; "hareketin %X'i ilk 3 barda".
- **EŞİK**: CALISTI farkı ≥12 → kart etiketi; 5–12 → yalnız metin; <5 → kaldır. Medyan devam_tepe_bar kart cümlesine sabit sayı olarak girer.

---

## §4 FORMASYON (S27–S30) — frm anti-dairesellik korunarak

### [S27] Faz çırpınması
- **SORU**: Faz çırpınması kaliteyi düşürüyor mu — frm_faz_gecis_sayisi ≥6 olanlarda terminal_state=FORMASYON_TAMAMLANDI oranı, ≤2 geçişlilere göre kaç puan düşük?
- **ALANLAR**: frm_faz_gecis_sayisi, terminal_state (FORMASYON_TAMAMLANDI / BASARISIZ_KIRILIM / FORMASYON_GECERSIZ / KIRILIM_TEYIT_ALAMADI; **acik=True satırlarda terminal_state ayrılır** — §8-E11), terminal_mi, frm_gecersiz_state, pattern_type, timeframe, omur_bar, frm_kirilim_deneme
- **KIRILIM**: pattern_type (seyrek tipler birleştirilir) × TF × geçiş kovası (≤2 / 3–5 / ≥6)
- **FAYDA**: yapma-kuralı — "6+ faz geçişli formasyon kart olarak yayınlanmaz" (kararsız yapı) + karne paydası düzeltmesi.
- **N**: frm satırları; hücreler küçük → C4 birleştirme zorunlu (tip + TF), birleşik n≥300, en küçük kova ≥50 beklenir.
- **CEVAP**: kova × TAMAMLANDI / GECERSIZ / BASARISIZ_KIRILIM / TEYIT_ALAMADI / acik yüzdeleri + n; "%A vs %B = −N puan".
- **EŞİK**: TAMAMLANDI farkı ≥12 → yayınlama kuralı; 5–12 → uyarı; <5 → kural reddedilir.

### [S28] Açık örneklem payı
- **SORU**: Formasyon örneklemi ne kadar açıkta — acik=True ve frm_olay'da yarım kalan segment oranı (son olay durumu terminal değil) pattern_type × TF bazında yüzde kaç?
- **ALANLAR**: acik, terminal_mi, terminal_state, omur_bar, frm_olay (stable_id başına olay sayısı + son state), run_meta.formasyon_sayisi
- **KIRILIM**: pattern_type × TF
- **FAYDA**: yapma-kuralı + karne — "açık formasyonlar KIRILIM_TEYIT_ALAMADI ile birlikte sayılmaz"; kartta "formasyon hâlâ açık" bilgisi; karne başarı oranı paydası.
- **N**: frm + frm_olay satırları; 32 hücrede ortalama ~1.000 satır, seyrek tiplerde C4.
- **CEVAP**: tip×TF tablosunda "%A açık (n=…)" + "son olayı terminal olmayan stable_id %B" + omur_bar medyanı (açık vs kapalı) + run_meta.formasyon_sayisi ile tutarlılık kontrolü.
- **EŞİK**: bir hücrede açık oranı ≥%30 → o hücrenin formasyon soruları KISMI güvene düşer; <%10 → payda düzeltmesi yeterli.

### [S29] Pivot ezilmesi → teyit sonrası getiri
- **SORU**: Pivot ezilmesi teyit sonrası getiriyi düşürüyor mu — ezilme olanlarda medyan frm_teyit_sonrasi_mfe_atr kaç ATR düşük ve MAE/MFE oranı kaç puan kötü?
- **ALANLAR**: frm_pivot_ezilme_var, frm_pivot_temas_max, frm_teyit_sonrasi_mfe_atr, frm_teyit_sonrasi_mae_atr, frm_teyit_sonrasi_mfe_uzun_atr, pattern_type, frm_kirilim_deneme_var
- **KIRILIM**: pattern_type × frm_kirilim_deneme_var (T/F) × ezilme (T/F)
- **FAYDA**: uyarı cümlesi — "pivot ezilmiş, kırılım güvenilirliği düşük" + kart önceliği.
- **N**: MFE/MAE blokları teyit almış formasyonlarda ~10–15k; ezilme T/F hücreleri ~5k; n<30 hücrede C4 tip birleştirme.
- **CEVAP**: 2×2 tablo: medyan MFE (ATR), medyan MAE (ATR), MAE/MFE oranı, n; "ezilme var: MFE N ATR vs yok: M ATR".
- **EŞİK**: MFE farkı ≥0.25 ATR veya MAE/MFE oranı farkı ≥15 puan → uyarı + öncelik düşürmesi; aksi halde yalnız gözlem.

### [S30] 12 bar yeterli mi
- **SORU**: frm_teyit_sonrasi_mfe_uzun_atr / frm_teyit_sonrasi_mfe_atr oranı pattern_type bazında kaç (40 bar tepesi, 12 bar tepesinin kaç katı) ve tepe 12 bar sonrasında mı oluşuyor? (Tepe-sonrası = mfe_uzun_atr > mfe_atr.)
- **ALANLAR**: frm_teyit_sonrasi_mfe_atr, frm_teyit_sonrasi_mfe_uzun_atr, frm_teyit_sonrasi_mae_atr, pattern_type, timeframe; **destek**: break_confirmation_strength (float; medyan olarak raporlanır, gruplama değişkeni DEĞİL — §8-E12)
- **KIRILIM**: pattern_type × TF
- **FAYDA**: backtest hipotezi → kart "izleme süresi" ve hedef mesafesi (0.5/1.0/1.5 ATR ızgarasından hangisi 12 bara sığıyor) hücre bazında sabitlenir.
- **N**: MFE ve MFE_uzun birlikte dolu satırlar; tip×TF hücrelerinde C4 birleştirme, en küçük hücre ≥50 hedefi.
- **CEVAP**: tip tablosu: oran (medyan, p90), 12 bar MFE medyanı, 40 bar MFE medyanı; "tepe 12 bar içinde: %A / sonra: %B".
- **EŞİK**: oran ≥1.5 → kart hedefi uzun pencereye göre yazılır; <1.2 → 12 bar yeterli.

---

## §5 KESİT / VERİ KAPISI (S31–S32)

### [S31] Semboller arası yayılım
- **SORU**: Tepki oranı semboller arasında ne kadar yayılıyor — sembol bazında CALISTI oranının p90 − p10 farkı kaç puan (her TF ve scope için), yani tek global oran mı yoksa sembol süzgeci mi gerekli?
- **ALANLAR**: yon_tepki_sinifi × symbol × timeframe; ikinci blok: devamlilik_sinifi × symbol × scope; destek run_meta.symbol/timeframe
- **KIRILIM**: TF × family (ZONE bloğu) ve scope (MS bloğu); sembol başına n≥30 sağlanmayan sembol KISMI/ZAYIF işaretlenir, dışlanmaz
- **FAYDA**: karne — global oranın yanına "sembol aralığı p10–p90" satırı; uç semboller için kart önceliği. Global oran tek başına karar dayanağı olmaktan çıkar.
- **N**: ZONE toplam epizod / sembol sayısı (yaklaşık 1.300+ per sembol; 1d OB/FVG'de bazıları sınırda, C4 uyarısı ile); MS olaylar / sembol.
- **CEVAP**: tüm sembollerin CALISTI dağılımı (p10, medyan, p90) + en iyi/en kötü 5 sembol; "p90−p10 = N puan (TF=1h OB)".
- **EŞİK**: p90−p10 ≥20 puan → karneye sembol aralığı + uç sembol öncelik süzgeci; <10 puan → global oran yeterli.

### [S32] Kirli bar penceresi
- **SORU**: Ölçüm pencerelerine kirli bar düşüyor mu — temas barını izleyen 12 barlık pencerede en az bir split_adayi=True veya sifir_hacim=True bar bulunan epizodların payı TF ve family bazında yüzde kaç?
- **ALANLAR**: ham bar K5 bayrakları (nan_ohlc, sifir_hacim, split_adayi = |open−önceki_kapanış|/önceki_kapanış > %10) — **JSONL'de yok; cevap motoru arşiv çerçevelerinden K5 formülüyle üretir (§8-E13)** ⋈ dokunus_baslangic_index/dokunus_bitis_index penceresi (dokunus_bitis_index+1 … +12) × episode_id × yon_tepki_sinifi × family
- **KIRILIM**: TF × family × bayrak türü (1d'de split etkisi yüksek beklenir)
- **FAYDA**: yapma-kuralı — "split_adayi bayraklı pencereye düşen epizod tepki sınıfı hesaplanmaz / karne dışı" (ölçüm temizliği kapısı).
- **N**: tüm epizod pencereleri; kirli epizod alt kümesi ~1–10k.
- **CEVAP**: hücre tablosu "%A kirli pencere (n=…)"; ayrıca ham bar seviyesinde split_adayi oranı, en yüksek 5 sembol.
- **EŞİK**: pay ≥%2 → kural + karne ayrımı; %0.5–2 → yalnız not; <%0.5 → kural gereksiz.

---

## §6 KARAR EŞLEMESİ — hangi soru hangi canlı bileşene yazılır

| Bileşen | Sorular |
|---|---|
| Telegram kartı / rozet | S01, S16, S21, S26 |
| Telegram kartı / metin | S04, S11, S15, S17, S19, S23, S26, S29 |
| Kuyruk filtresi/öncelik | S01, S04, S13, S21, S23, S29 |
| Yapma-kuralı (sert) | S02, S03, S07, S08, S14, S20, S25, S27, S28, S32 |
| Karne (payda/güven) | S07, S08, S09, S14, S19, S28, S31 |
| Backtest hipotezi | S05, S06, S24, S30 |

**Öncelik sırası (getiri ÷ maliyet):**

1. dalga: S08, S07, S02, S03, S25, S14 → tek join, boolean/oran; "yanlış kartı engelleme"
2. dalga: S01, S04, S16, S21
3. dalga: S05, S24, S30 (yeni kart tipi / horizon / hedef doğuracak olanlar)

---

## §7 ÜRETİLMEYEN KONULAR (bilinçli kapsam dışı)

PUANLAMA_MIMARISI §8: gölge 6 hafta çalıştırma, üçgen negatiflik ayrımı, TF ağırlık haritası,
PUBLIC_MIN_DEVLAMLILIK · walk-forward / jenerik drift izleyici / jenerik kalibrasyon katmanı ·
aday anında ölçüm (lookahead) · TL/% cinsinden uzanım · "gelecek barı tahmin et" ·
tek sembol/tek TF'e sıkışan iddialar · n<15 hücreye dayalı kararlar · sözlükte olmayan alan.

Her soru: tek pandas bloğu ile cevaplanabilir, iki farklı çapayı karıştırmaz (C1),
aynı config_hash içinde koşar (C8), çıktısında n + sansür_% + güven etiketi üçlüsü zorunlu.

---

## §8 KOD EŞLEŞTİRME NOTLARI (v1 → v1.1 düzeltmeleri)

- **E1 — yeni alanlar (kayit.py)**: `dokunus_satirlari` artık `dokunus_baslangic_index` ve
  `dokunus_bitis_index` yazar; `build_window_rows` hedef bloğu
  (`target_{0p5,1p0,1p1p5}_atr_*`, `active_target_eligible`, `favorable_excursion_on_terminal_bar_atr`,
  `observed_post_touch_bars`, `preterminal_post_touch_bars`, `native_terminal_at_or_before_touch`,
  `native_terminal_reason_in_window`) repoh{10,12}_ önekiyle dokunus satırına kopyalanır.
  Sebep: S08/S09 bu alanlar olmadan cevaplanamıyordu.
- **E2 — tepki sınıfı sözlüğü**: `yon_tepki_sinifi` = CALISTI/**AZ**/**YOK**/TERS/OLCULEMEDI;
  `devamlilik_sinifi` = CALISTI/**AZ_DEVAM**/**DEVAM_YOK**/TERS/OLCULEMEDI. S15'teki
  "DEVAM_YOK" → "YOK" düzeltildi; C5'e ikilik yazıldı.
- **E3 — repoh önekleri**: window_status ve next_same_zone_touch_in_window alanları ham
  isimle değil `repoh10_`/`repoh12_` önekiyle taşıyor (S07/S08/S09/S15 güncellendi).
- **E4 — terminal bayrağı adı**: dokunus satırındaki gerçek alan `terminal_dokunusta`
  (episode kökündeki `native_terminal_at_touch` dokunus satırına kopyalanmaz). S07 düzeltildi.
- **E5 — effort enum**: gerçek değerler NEUTRAL / RISING_EFFORT_STRONG_RESULT /
  HIGH_EFFORT_STRONG_RESULT / HIGH_EFFORT_WEAK_RESULT / VERY_HIGH_EFFORT_WEAK_RESULT.
  S10'daki YUKSEK_EFOR_* takma adları gerçek enumlarla değiştirildi.
- **E6 — rol_kapanis gerçeği**: değerler DEVREDILDI / TEMIZLENDI / VERI_SONU_SANSURLU /
  ROL_ATANMADI ("KIRILDI" diye bir değer YOK; kırılım `broken` alanında). S19 yeniden yazıldı.
- **E7 — scope/side büyük harf**: veride `EXTERNAL`/`INTERNAL`, `HIGH`/`LOW`; ayrıca
  `capa_bar` yalnız rol ataması olan satırlarda var (S18 kapsam notu). `structural_role`
  satırda yok → `rol` + `structural_role_final` (S16).
- **E8 — event_type gerçek değerleri**: `EVENT_BOS`, `EVENT_CHOCH`, `EVENT_FALSE_BREAK`,
  `EVENT_SWEEP`, `EVENT_TRANSITION_FAIL` (S22/S24'te EVENT_ öneki belirtildi).
- **E9 — devam alan adları**: "devam_kapanis" → `devam_h12_kapanis_atr`;
  "devam_decay" → `devam_h12_decay` (S22/S26).
- **E10 — kenar ölçülemezlik sinyali**: `kenar_olcum_yonu` None olur; ölçülemezlik
  `kenar_tepki_sinifi = OLCULEMEDI` ile okunur. S03 düzeltildi.
- **E11 — frm terminal sözlüğü**: `FORMASYON_GECERSIZ` tam yazımı; acik satırlarda
  terminal_state ayrı tutuldu (S27).
- **E12 — break_confirmation_strength float**: gruplama değişkeni olamaz → S30'da
  KIRILIM'den çıkarılıp destek medyanına indirildi; "tepe 12 sonra" tanımı eklendi.
- **E13 — S32 bar bayrakları JSONL'de yok**: cevap motoru K5 formülünü arşiv
  çerçevelerinden üretir (split > %10, sifir_hacim, nan_ohlc); pencere index'lerle kurulur.
- **E13b — event_bar yoksa gecikme yok**: `onay_gecikmesi_bar` None → gruplama dışı (S23).
- **E14 — C5 gruplama ayrımı**: yaş/süre/gecikme/rejim kovaları soru metinlerinde önde
  tanımlı; C5 yalnız ölçüm eşiklerini bağlar (paragraf eklendi).
- **E15 — kirilim_bar iki anlamı var**: `kirilim_bar` deneme penceresi içi 1-tabanlı
  konum; mutlak bar `broken_bar` (S20 ikisini de ayırarak yazdı).
- **E16 — dip negatif korunur**: `yon_dip_atr`/`devam_dip_atr` negatif değerleri korur
  (tek_yonlu_yol sözleşmesi); S04'e not eklendi.
