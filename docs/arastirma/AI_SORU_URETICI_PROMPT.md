# GÖREV: Replay Verisinden Sistem Faydası Sağlayacak Soru Üretimi

## 1. Bağlam
BIST formasyon botunun **offline replay araştırma hattı** var (Formation-Bot). Ham fiyat
arşivi üzerinde dört domain motoru (OB, FVG, Market Structure, Hacim) + klasik formasyon
motoru (ArgentEngine) bar bar yeniden oynatılıyor ve **ölçülmüş gözlem satırları**
üretiliyor. Senin görevin: bu veri kümesinden, canlı botun işine yarayabilecek **yeni ve
cevaplanabilir sorular** üretmek. Soruların HER BİRİ bir karara bağlanmalı: kart metni,
süzgeç etiketi, uyarı cümlesi, "bunu yapma" kuralı veya backtest hipotezi.

## 2. Veri kaynağı ve ölçek
- Arşiv: 177 sembol; 1h (2025-05-07'den, ort. 3.211 bar) + 1d (2024-10-21'den, ort. 499 bar);
  2h/4h 1h'den seans-kovalı `resample_ohlcv` ile deterministik türetilir.
- Son tam koşu: **708/708 seri (177×4 TF), 0 hata**; toplam satırlar:
  - ham bar: **660.504**
  - zone (OB+FVG): **189.171**
  - zone temas epizodu: **243.256**
  - MS swing (rol-aralığı birimi): **412.045** / ayrık swing: **351.184**
  - MS olay: **202.938**
  - formasyon yaşam döngüsü (`frm`): **33.964** · formasyon olay (`frm_olay`): **229.785**
- Zaman damgası biçimi (K1): metin `YYYY-MM-DD HH:MM:SS+03:00` (Europe ISO "T" YOK).

## 3. Ölçüm kuralları (her soruda göz önünde tut)
1. **Anti-lookahead**: tüm uzanımlar **çapa barından SONRA**ki barlardan hesaplanır;
   çapa barı ölçüme girmez. MS olaylarında çapa `event_bar` (onay), `candidate_bar` DEĞİL.
2. **Birim ATR** (TL/% değil — BIST 5–500 TL arası hisseler var). rvol = göreli hacim.
3. **Sansür**: pencere veri sonuna takıldıysa satır DÜŞÜRÜLMEZ, sansür bayrağıyla taşınır;
   sansürlü gözlem "başarılı" sayılmaz.
4. **Güven etiketi**: n≥30 YETERLI, n≥15 KISMI, n<15 ZAYIF. Soru ancak tahmini n≥30
   üretebiliyorsa geçerli (tek sembol/tek TF'e sıkışmayan).
5. **Ön-tanımlı eşikler** (sonradan seçilemez): HORIZON 10/12 bar · uzun pencere 40 bar ·
   tepki sınıfları ≥1.0 ATR=CALISTI, ≥0.25=AZ_DEVAM, <0.25=DEVAM_YOK, <0=TERS ·
   yükseklik kovası 0–0.5 / 0.5–1 / 1–2 / ≥2 ATR (+BILINMEYEN) ·
   ATR aşım ızgarası 0.25/0.5/1.0/1.5/2.0 · hedef-erişim 0.5/1.0/1.5 ·
   tepe payı pencereleri 1/3/5 bar · MS deneme eşikleri 0.15/0.25/0.50 ATR (ana=0.25).
6. **Scope ayrımı zorunlu**: MS `external` (pivot 5, mesafe 0.45 ATR) vs `internal`
   (pivot 2, mesafe 0.20 ATR) AYRI raporlanır; iç yapı daha sık ve gürültülü.

## 4. Domain sözlükleri (üretilebilecek çıktılar)

### A) ZONE — OB ve FVG (satır birimi = 1 zone) · 189.171 satır
OB tüm TF'lerde; FVG yalnız 2h/4h/1d (warm-up 100/100/40 bar; profil "Dengeli").
- Kimlik: `zone_id, symbol, timeframe, family(OB|FVG), direction(bullish|bearish),
  beklenen_yon(UP|DOWN)`, `dogum_bar_time, dogum_index, kullanilabilir_bar_time`
- Geometri: `zone_lower, zone_upper, yukseklik_fiyat, atr_at_birth, yukseklik_atr,
  yukseklik_kovasi`
- Yaşam döngüsü: `native_terminal_state/reason/category, terminal_bar_time, terminal_index,
  native_price_violation, native_full_fill, native_fill_ratio, omur_bar, sansur(bool)`
- Temas özeti: `temas_bar_sayisi, temas_var`
- Parmak izi: `engine_version(arastirma-olcum-v1), config_hash`
- Not: OB'de `fill_cancel_threshold=0.70`; dolan zone'lar listeden silinir, replay silinenleri
  `native_terminal_*` ile geri kurar (tam popülasyon). FVG'de `full_fill` anlamlıdır; OB'de
  violation/gap_through baskındır.

### B) ZONE TEMAS EPİZODU — en zengin tablo (satır birimi = 1 temas epizodu) · 243.256 satır
Epizod = ardışık temas barları; çapa = epizodun İLK barı; ölçüm epizod bitişinden sonra başlar.
- Kimlik: `episode_id, zone_id, dokunus_no(zone içinde kaçıncı), dokunus_baslangic/bitis_bar_time,
  dokunus_bar_sayisi, sonraki_epizot_index, gozlenen_bar(epizod sonrası gözlem)`
- Geliş: `arrival_side(FROM_ABOVE|FROM_BELOW|INSIDE_ZONE|ON_ZONE_BOUNDARY|NO_PREVIOUS_BAR),
  approach_direction(DOWN_TOWARD_ZONE|UP_TOWARD_ZONE|AMBIGUOUS|UNKNOWN), arrival_previous_close,
  dokunulan_kenar(UST_KENAR|ALT_KENAR|TUM_ZONE|ZONE_ICI), kenar_olcum_yonu`
- Çapa: `atr_at_touch, yukseklik_atr, yukseklik_kovasi`
- **Yön-çapalı uzanım** (`yon_*` — zone yönüne göre; bullish→üst kenardan yukarı):
  `yon_h10, yon_h12` (horizonda max uygun uzanım), `yon_h10/h12_kapanis_atr,
  yon_h10/h12_decay` ((tepe−kapanış)/tepe), `yon_h10/h12_sansur, yon_tepe_atr(12 barda tepe),
  yon_tepe_bar, yon_dip_atr(aynı yoldaki en kötü ters hareket, negatif korunur),
  yon_pay_1/3/5` (tepenin k bardaki payı: ~1 → ani), `yon_asim_{025,050,100,150,200}(+_bar)`,
  `yon_uzun_tepe_atr/bar, yon_uzun_kapanis_atr, yon_uzun_decay, yon_uzun_sansur(40 bar)`,
  `yon_tepki_sinifi(CALISTI|AZ_DEVAM|DEVAM_YOK|TERS|OLCULEMEDI)`
- **Kenar-çapalı uzanım** (`kenar_*` — dokunulan kenara göre; UST→aşağı, ALT→yukarı):
  `kenar_h10/h12, kenar_kapanis, kenar_decay, kenar_tepe/dip/pay_*/asim_*/uzun_*, kenar_tepki_sinifi`
  (TUM_ZONE/ZONE_ICI'da yön belirlenemez → OLCULEMEDI kovası, ayrı raporlanır)
- **Sabit pencereli sonuç bloğu** (`repoh10_`/`repoh12_` — epizod bitişinden 10/12 bar sonra,
  `directional_excursions` semantiği; ≥0 kırpılır):
  `full_window_favorable/adverse_excursion_{price,atr}`,
  `favorable_excursion_before_native_terminal_atr, adverse_excursion_before_native_terminal_atr`,
  `window_complete, window_status(COMPLETE|RIGHT_CENSORED_DATA_END|
  ATR14_UNAVAILABLE_AT_TOUCH|NATIVE_TERMINAL_ON_TOUCH)`,
  `native_terminal_within_full_horizon, native_price_violation_within_full_horizon,
  next_same_zone_touch_in_window`,
  `target_{0p5,1p1p5}_atr_hit_full_window / _hit_before_native_terminal /
  _possible_on_terminal_bar / _hit_only_after_terminal / _active_zone_category
  (HIT_BEFORE_NATIVE_TERMINAL|AMBIGUOUS_ON_TERMINAL_BAR|HIT_ONLY_AFTER_NATIVE_TERMINAL|
  NOT_REACHED|NOT_EVALUABLE)`
- Terminal-temas kesişimi: `native_terminal_at_touch, sansur_pencere, sansur_terminal,
  native_terminal_*, native_price_violation, native_full_fill`
- **Hacim örneği (çapa anında)**: `vp_data_ready, vp_volume_usable(bool), vp_capital_usable,
  vp_rvol, vp_volume_z_score, vp_volume_percent_rank, vp_capital_z_score,
  vp_directional_value_pressure_5/10, vp_net_progress_atr, vp_directional_efficiency,
  vp_volume_slope, vp_rtv, vp_volume_result_efficiency, vp_capital_result_efficiency,
  vp_effort_result_class` — bayrak SATIRDA taşınır, satır düşürülmez.

### C) MARKET STRUCTURE SWING (satır birimi = swing × rol aralığı) · 412.045 satır
Bir swing zamanla farklı rol alabilir (PH↔nötr); her aralık ayrı ölçüm birimidir.
- `scope(external|internal), side(high|low), identity(pencere-relatif), swing_class(PH|PL|WH|WL|SH|SL…),
  structural_role(WEAK_HIGH|WEAK_LOW|STRONG_HIGH|STRONG_LOW|PROTECTED_HIGH|PROTECTED_LOW|neutral…),
  structural_role_final, state(SWING_CONFIRMED…), valid, finalized, locked`
- Çapalar: `source_bar(+time), confirm_bar(+time) = lookahead çapası, price, atr_at_source,
  prominence_atr, distance_atr, quality, rol, rol_ilk_bar(+time), rol_son_bar, rol_sure_bar,
  rol_kapanis(ROL_ATANMADI…), capa_bar(+time) = rol atama anı`
- Kırılma: `broken, broken_bar(+time), bars_to_break, bars_to_break_sansur, kirilim_bar/atr,
  bars_to_break_from_rol`
- **Deneme (PH/PL "kaç kez denendi")**: `deneme_bar_{015,025,050}` (eşik içindeki bar sayısı),
  `deneme_epizot_{015,025,050}` (yaklaşma epizot sayısı), `engelledi_{015,025,050}`
  (3-değerli: True=kırılmadı, False=kırıldı, None=sansürlü), `gecildi, max_yaklasma_atr/bar,
  red_magnitude_atr, gozlenen_bar, sansur, olculmedi`
- VP örneği capa anında (B'deki alanlarla aynı).

### D) MARKET STRUCTURE OLAY — BOS/CHOCH vb. (satır birimi = 1 olay) · 202.938 satır
- `event_uid, identity, scope, event_type(EVENT_BOS|EVENT_CHOCH|EVENT_FALSE_BREAK|
  EVENT_SWEEP|EVENT_TRANSITION_FAIL), direction(UP|DOWN), candidate_bar(+time),
  event_bar(+time)=confirmed_at (ÖLÇÜM ÇAPASI), onay_gecikmesi_bar`
- Kırılan/çıkış: `broken_swing_identity, broken_level, origin_price, quality`
- Güvenilirlik: `confirmation_status(CONFIRMED|CANDIDATE_FAILED), validity(VALID|FAILED),
  relevance(CURRENT|SUPERSEDED|HISTORICAL), outcome(FOLLOW_THROUGH_CONFIRMED|FAILED|
  OBSERVED|PENDING), bos_maturity(NOT_APPLICABLE|INITIAL_STRUCTURE|TRANSITION_CONFIRMATION|
  CONTINUATION), age_bars, confirmed_by/failed_by(event_uid)`
- **Devamlılık ölçümü** (onay barı çapası, olay yönünde): `referans_kapanis, atr_at_event,
  devam_h10/h12, devam_kapanis/decay/sansur, devam_tepe_atr/bar, devam_pay_1/3/5,
  devam_asim_*, devam_uzun_*` + `devamlilik_sinifi(CALISTI|AZ_DEVAM|DEVAM_YOK|TERS|OLCULEMEDI)`
- Ters yön: `ters_h12` + `uyum(UYUMLU|UYUMSUZ)` (olay yönü ↔ fiyat yönü)
- VP örneği onay barında (B'deki alanlarla aynı).

### E) HAM BARI (660.504 satır)
`bar_time, open, high, low, close, volume` (auto_adjust=False ham fiyat) + K5 bayrakları:
`nan_ohlc, sifir_hacim, split_adayi(|open−önceki_kapanış|/önceki_kapanış > %10)`.
Bazı sorular HAM bar'dan cevaplanır (ör. "süpürme derinliği", "fiyat seviyeye engel oldu mu") —
diğer domain satırları yerine bu tabloyu kullan.

### F) FORMASYON — klasik üçgen/kama/bayrak hattı (ArgentEngine replay) · `frm` 33.964 + `frm_olay` 229.785
`frm` kolonları (57): `symbol, timeframe, stable_id, pattern_type, family, classic_dir,
dogum_bar_time, omur_bar, terminal_state, acik, terminal_mi, kirilim_var,
frm_yakinlik_{ust,alt}_{fitil,kapanis}_atr, frm_asim_{ust,alt}_{fitil,kapanis}_atr,
frm_temas_{ust,alt}_epizot, frm_faz_{geometri,kirilim,retest}_bar, frm_faz_gecis_sayisi,
frm_kirilim_deneme, frm_teyit_deneme_no, frm_kirilim_deneme_var, upper_touches_son,
lower_touches_son, frm_pivot_temas_max, frm_pivot_ezilme_var, break_snapshot_{bar,price,direction},
break_strength, break_volume_score, break_confirmation_strength, break_gecikme_bar,
retest_var, retest_gecikme_bar, retest_derinlik_atr, frm_teyit_sonrasi_mfe_atr,
frm_teyit_sonrasi_mfe_uzun_atr, frm_teyit_sonrasi_mae_atr, frm_dogum_{ph,pl}_atr,
frm_dogum_rol_ucu, frm_kirilim_ms_uyum, frm_kirilim_zone_var, frm_kirilim_ob_var,
frm_kirilim_fvg_var, frm_gecersiz_state, frm_vp_rvol_{dogum,olgunlasma,teyit,retest},
frm_oncul_getiri_{20,5}bar_atr, frm_yakin_{ust,alt}_{esik}_bar/epizot`
- Faz sözlüğü: `ADAY_OLUSUYOR, GEOMETRI_ADAYI, FORMASYON_TANIMLANDI, OLGUNLASIYOR,
  SIKISMA_GUCLENIYOR, KIRILIM_HAZIRLIGI | KIRILIM_DENEMESI, KIRILIM_ADAYI, KIRILIM_TEYITLI |
  RETEST_BEKLENIYOR, RETEST_EDILIYOR, RETEST_BASARILI`
- Terminal: `FORMASYON_TAMAMLANDI, BASARISIZ_KIRILIM, FORMASYON_GECERSIZ, KIRILIM_TEYIT_ALAMADI`
- Teyit pencereleri: 12 bar (ana) / 40 bar (uzun). Anti-dairesellik: mesafe bloğu KIRILIM
  anına kadardır; sonuç (MFE/MAE) TEYİTTEN sonradır — aynı pencere asla iki türlü kullanılmaz.
- `frm_olay`: formasyon segment başına olay satırları (durum geçişleri).

### G) RUN META (708 satır)
`symbol, timeframe, bar_sayisi, atr_son, zone_sayisi, ob/fvg_zone_sayisi, epizot_sayisi,
swing_sayisi, event_sayisi, rol_araligi_sayisi, ms_data_quality, ms_hata, vp_data_quality,
engine_version, config_hash, fvg_durum, fvg_isinanma, formasyon_sayisi, formasyon_olay_sayisi`

## 5. Yapılabilecek join'ler
- `dokunus.zone_id → zone.zone_id` (temas ↔ zone geometrisi/terminali)
- `(symbol, timeframe, bar_time)` → ham bar (çapa/sonuç barı özellikleri, hacim, volatilite)
- `event.broken_swing_identity + scope → swing.identity` (kırılan seviye ile olay)
- Aynı satırda `yon_*` ↔ `kenar_*` ↔ `repoh*` ↔ `vp_*` (tek epizod için çapraz okuma)
- `frm.* ↔ zone` (kırılım anındaki canlı OB/FVG kesişimi hazır: `frm_kirilim_{ob,fvg,zone}_var`),
  `frm ↔ swing/event` (`frm_kirilim_ms_uyum`, `_rol_ucu`)
- Tüm domainlerde `config_hash` eşit → koşular karşılaştırılabilir.

## 6. ZATEN CEVAPLANMIŞ sorular ( bunları TEKRARLAMA; genişlet ):
- Zone: tek/çok deneme; geçilme/dolum; dokunuş tepki sınıfları; kenar-çapalı tepki + ATR
  eşik ızgarası; yükseklik kovası × tepki; ani/kalıcı şekil (pay/decay)
- MS: scope×tip×yön uyumu; outcome çapraz kontrol; PH/PL deneme-kova × engelleme;
  WH/WL ziyaret/süpürme + ulaşma süresi; EVENT_SWEEP çapraz kontrol
- Hacim: dokunuş tepkisi × rvol çeyreği; MS devamlılığı × rvol çeyreği
- Formasyon: FRM-01…20 (öncül, tip/kalite, PH/PL mesafesi, daralma, sıkışmada hacim,
  kırılım-yakınlık, deneme, yön-uyumu, teyit gecikmesi, teyit hacmi, BOS eşleşmesi,
  retest oranı/derinliği/hacmi, sonuç dağılımı, tamamlanma, başarısız geri dönüş,
  geçersizleşme fazı, kırılımda zone varlığı, MS yön uyumu)

## 7. Üretilecek soru formatı
Her soru şu alanlarla:
1. **SORU**: tek cümle, ölçülebilir ("X koşulunda Y, Z kıyasına göre kaç puan fark ediyor?")
2. **Hedef domain + alanlar**: örn. `dokunus.yukseklik_kovasi × dokunus.vp_rvol × yon_tepki_sinifi`
3. **Kırılım önerisi**: TF × family × scope (hangi boyutta ayrışıyor görünebilir)
4. **Sistem faydası**: [kart metni | süzgeç etiketi | uyarı cümlesi | yapma-kuralı | backtest hipotezi]
   — hangi canlı bileşene bağlanacağı yazılsın (Telegram kartı, kuyruk filtresi, karne, …)
5. **Tahmini n**: hangi tablo satırlarından geliyor (≥30 olmalı)
6. **Örnek beklenen cevap biçimi**: yüzde/sayı/medyan — hipotez değil, “şu hücreden şu sayı çıkar”

## 8. Kırmızı çizgiler ( bunları ÜRETME ):
- Depoda halen açık planlar tekrarlanmamalı: PUANLAMA_MIMARISI §8 konuları (gölge 6 hafta
  çalıştırma, üçgen negatiflik ayrımı, TF ağırlık haritası, PUBLIC_MIN_DEVLAMLILIK),
  genel/soyut öneriler (walk-forward, genel drift izleyici, jenerik kalibrasyon katmanı).
- Lookahead gerektiren sorular (aday anında ölçüm vb.).
- Kapsam dışı: tek gözlemli iddialar, n<15 hücrelere dayalı kararlar, TL/% cinsinden
  uzanım istekleri, “gelecek barı tahmin et” soruları.
- Veri setinde OLMAYAN alanları varsayan sorular (sözlükte yoksa yoktur).

## 9. Çıktı şablonu (örnek — 20–35 soru üret)
```
[S01] SORU: 1d FVG'de yükseklik ≥2 ATR olan zone'larda, Q1 rvol'de tepki CALISTI oranı
      Q4'e göre kaç puan fark ediyor?
      KIRILIM: 1d × FVG × (rvol çeyreği)
      FAYDA: kart metni — "hacimli temas" vurgusu ters teperse kartta uyarılacak
      N: dokunus (1d FVG ~6.285; kova×çeyrek n'leri kontrol edilecek)
      CEVAP BİÇİMİ: %A vs %B, fark N puan, güven etiketi
```
