# DERİN GEÇMİŞ REPLAY SONUÇLARI — 177 sembol, 4 zaman dilimi

> **Durum:** Ölçüm + depolama hattı · **Tarih:** 2026-10-28 · **Koşu:** `dz-20261028-full`
> **Okuma süresi:** 3 dk özet · tablo ekleri `ARASTIRMA_BULGULARI.md` (59K karakter)
> Sayılar bu belgede **o günün koşusundan**; tablo ekindeki hücrelerle birebir aynıdır.

---

## 0 · Tek ekran

| # | Bulgu | Sayı | Güven |
|---|---|---|---|
| 1 | **Replay birebir tekrar üretti**: 2026-10-21 doğrulamasının zone/dokunuş n'leri aynı çıktı | zone **189.171** (176'da 187.046) · dokunus **243.256** (176'da 240.484) | 708/708 seri, 0 hata |
| 2 | **Zone bariyer değil zamanlama**: OB'lerin %85–94'ü geçiliyor ama dokunuşta %65–66 tepki var — her TF'de | geçilme 1h %93.6 · tepki %65.0–66.5 | n 187.046 / 240.484 |
| 3 | **Tek ayırt edici: zone yüksekliği** | 1d FVG %64.3 → **%71.0** (≥2 ATR); 4h FVG %65.1 → **%72.6** | n 6.285 / 831+ |
| 4 | **FVG tek kullanımlık, OB tekrar denenir** | FVG tek deneme %71–78 · OB 3+ deneme %13 | n 55.145 / 131.901 |
| 5 | **MS en güvenilir yön teyidi** | uyum **%94.7–99.5** · BOS UP her TF'de daha iyi (1d dış: %77.2 vs %60.1) | n 200.028 event |
| 6 | **Hacim ikiyüzlü**: zone tepkisini ZAYIFLATIR, MS devamlılığını GÜÇLENDİRİR | dokunuş Q1 %70.1 → Q4 %61.0 (4h) · MS devam Q1 %63.0 → Q4 %72.7 (1d) | n 6.740–28.912 / 2.107–27.108 |
| 7 | **Çok denen PH/PL kırılır** | engelledi: 1 deneme %34–38 → 4+ deneme **%16–28** (1h iç PH: %34.7 → %16.2) | n 681–6.589 |
| 8 | **Tepki yavaş ama kalıcı** (anlık değil) | ort_pay_5 ~0.55–0.66, uzun/ana tepe oranı 2.6–3.3× | tüm kovalar |

Tek cümle: **zone "nereden döner"i değil "ne kadar oynar"ı veriyor; ayırıcı tek değişken
yükseklik, hacim ise tersi yönde çalışıyor ve MS eventleri bunu düzeltiyor.**

---

## 1 · Künye ve doğrulama

| Kalem | Değer |
|---|---|
| Sembol | **177** (176 BIST/XU havuzu + BRENT `--havuz-disi-dahil` ile ayrı koşuldu) |
| Zaman dilimi | 1h, 2h, 4h, 1d (`2h/4h` `resample_ohlcv` ile 1h'den türetilir) |
| Sembol × TF | **708/708 başarılı, 0 hata, 0 ms_hatalı seri** |
| Komut | `python scripts/backfill/arastirma_kosu.py` (6.920 sn) + `--semboller BRENT --havuz-disi-dahil` (85 sn) |
| Arşiv | 1h: 2025-05-07→ (3.211 ort. bar) · 1d: 2024-10-21→ (499 ort. bar) · `backfill_data/` 354 CSV.gz |
| Anti-lookahead | Çapa sonrası ölçüm; aday anından ölçüm yok; sansürlü satır düşürülmez |
| Güven etiketi | n≥30 YETERLI · n≥15 KISMI · altı ZAYIF (`analytics/backtest.py` eşikleri) |

**Reprodüksiyon kontrolü:** `REPLAY_OZET_2026-10-21` ile bu koşunun n'leri birebir:
zone 187.046 (havuz), dokunus 240.484, 1d FVG yükseklik hücresi %64.3→%71.0 (n 6.285),
hacim Q1 %70.1 → Q4 %61.0 (4h). Motor ve arşiv değişmeden aynı sonuç üretiliyor —
ölçüm hattı **kalibrasyon değil, kayıt** olarak çalışıyor.

---

## 2 · Soru başına özet (tam tablolar: `ARASTIRMA_BULGULARI.md`)

### S1 — Tek deneme mi, çok deneme mi?
OB her TF'de ~%60 tek deneme, ~%13 üç ve üzeri; ortalama epizot 1.37–1.53.
FVG %71–78 tek deneme, 3+ **%0.0–1.1** — FVG neredeyse hiç tekrar denenmiyor.

### S2 — Geçilme vs tepki (asıl ayrışma)
| TF | Family | temas | geçilme | dokunuşta CALISTI |
|---|---|---|---|---|
| 1h | OB | %94.6 | %93.6 | %66.1 |
| 4h | OB | %92.2 | %90.0 | %65.2 |
| 2h | FVG | %77.2 | — (violation yok) | %66.5 |
| 1d | FVG | %72.1 | full_fill %40.8 | %65.0 |

OB'ye giriş önemi yok denecek kadar az; **giriş ANI + yükseklik** önemli.

### S3 — Kenara-çapalı tepki
Üst kenar: %54–63 CALISTI · alt kenar: %54–63 · `TUM_ZONE`/`ZONE_ICI` %100
`OLCULEMEDI` (düşürülmez, ayrı kova). Eşik ızgarası h12: ≥0.5 ATR %69–72,
≥2 ATR %38–40 — klasik "yarım ATR tepki" eşiği veriyle destekleniyor.

### S4 — Yükseklik + ani/kalıcı
Yükseklik kovası monoton: her TF'de ≥2 ATR kova, 0–0.5 kovadan **+4–7 puan** daha
yüksek CALISTI. Şekil: pay_5 0.55–0.66 + uzun/ana oran ≈3 → tepki **yavaş yayılır**;
decay >1 hücreleri "tepki verip tamamen geri verme" olarak okunmalı (rapor notu).

### S5 — MS BOS/CHOCH
Uyum %94.7–99.5. Event tipi ayrımı küçük (BOS ~%67 CALISTI, SWEEP ~%63);
**yön ayrımı büyük**: 1d dış BOS UP %77.2 vs DOWN %60.1. Motor outcome çapraz
kontrolünde `OBSERVED` baskın (~%75–85), `FAILED` %5–8.

### S6 — PH/PL direnç-destek
Monoton: deneme arttıkça engelleme düşer (1h iç PH %34.7 → %23.7 → %16.2).
**"Çok denen seviye kırılır"** güvenli aralıkta (n≥30) tekrarlanan bir desen;
0 deneme satırları %100 engelli ama hiç denenmemiş = kanıt yok (kovayı okurken dikkat).

### S7 — WH/WL ziyaret/süpürme
Ziyaret %65–82, süpürme %56–71; INTERNAL > HER scope'ta daha sık (daha gürültülü —
şema uyarısıyla uyumlu). Ulaşma süresi ortanca **3 bar** (q25=1, q75=6–7).

### Hacim — koşullandırma değişkeni (ikiyüzlü)
| Soru | Q1 (düşük rvol) | Q4 (yüksek rvol) | Yön |
|---|---|---|---|
| Dokunuş tepkisi 4h | %70.1 | %61.0 | yüksek hacimde zone tepkisi **zayıflar** |
| Dokunuş tepkisi 1h | %66.6 | %61.3 | aynı |
| MS devamlılığı 1d | %63.0 | **%72.7** | yüksek hacimde event devamı **güçlenir** |
| MS devamlılığı 4h | %66.1 | %69.5 | aynı |

`KULLANILAMAZ` kovası (`vp_volume_usable=False`) ayrıca taşınır, satır düşürülmez.

---

## 3 · `dz_*` depolama hattı (bu koştan çıkan kalıcı artefakt)

**Kod:** `scripts/backfill/dz_yukleme.py` · **Test:** `test_dz_yukleme.py` (13 test, ağsız)
**Çıktı:** `dz_yukleme/` (gitignore'lu, 1.3 GB) — `--sadece-yukle` ile Supabase'e gider.

| Tablo | Satır | Kolon kapsamı | NULL kalan (FAZ 2 / türetilebilir) |
|---|---|---|---|
| `dz_bars` | **660.504** | 14/14 (bayraklar türetilmiş: nan/sıfır-hacim/split) | — |
| `dz_zones` | **189.171** | 25/43 (%58) | engine-native skor bloğu: `score/base_score/gap_*/body_*/evidence_count/...` |
| `dz_zone_touches` | **243.256** | 49/60 (%82) | doluluk bloğu: `remaining_*/fill_ratio/wick/close_fill`, `bars_in_profit`, `kenar_ters_h10`, VP `participation_stage/up/down` |
| `dz_ms_swings` | **351.184** | 37/41 (%90) | `distance_pct`, `ilk/son_deneme_bar_time` |
| `dz_ms_events` | **202.938** | 48/53 (%91) | `origin_swing_identity + origin_source_*`, `ters_yon_atr_h10` |

Doğrulamalar (hepsi `kapsam_raporu.json` + cross-check):
- zone/dokunus/event satır sayısı = `meta.jsonl` toplamlarıyla **birebir**; 0 eşleme hatası,
  0 atlanan event (onaysız olay yok), 0 ms hatalı seri.
- K1: tüm bar zamanları TEXT `YYYY-MM-DD HH:MM:SS+03:00` (test ile kilitli).
- K2: kimlik kolonları natural-key upsert ile yüklenir (`on_conflict` şemadaki unique'lerle aynı).
- K3: her satırda `engine_version=arastirma-olcum-v1` + `config_hash` + `kaynak=backfill` + `run_id`.
- Eşleme kararları (ör. `boundary_anchored`: FROM_ABOVE→UST, FROM_BELOW→ALT, diğer
  → BELIRSIZ; `status`: repoh12_window_status; event `direction` UP→+1/DOWN→−1) kod
  yorumlarında ve `test_dz_yukleme.py` içinde belgeli.

### Yükleme (senin cihazında; sandbox'tan Supabase ağı yok)

```bash
export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
python scripts/backfill/dz_yukleme.py --sadece-yukle            # 4 tablo
python scripts/backfill/dz_yukleme.py --sadece-yukle --bars     # + dz_bars (660K satır)
```
Upsert idempotent; yarıda kesilirse `dz_yukleme/durum.json` kaldığı yerden devam eder.

---

## 4 · Sınırlar

- Ölçüm **bant**: 1h penceresi Mayıs-2025'e, 1d Ekim-2024'e kadar; daha uzağı yok.
- Havuz dışı BRENT ana raporun dışında (istisna koşuldu, satırları dz'de `symbol=BRENT`).
- NULL kalan kolonlar **boş veri değil, henüz üretilmeyen ölçümdür** — kapsam raporu
  hangi kolonun neden boş olduğunu listeler; doldurma FAZ 2 işidir (engine-record köprüsü).
- Yükseklik/tepkı korelasyonu nedensellik değildir; Ö7 band testi gibi bağımsız
  doğrulamalardan geçmeden karar değişkeni yapılmamalı.

**İlgili belgeler:** `ARASTIRMA_BULGULARI.md` (tablo ekleri) ·
`FORMASYON_SONUCLARI.md` (formasyon cevap kartları) ·
`REPLAY_OZET_2026-10-21.md` (önceki doğrulama — n'ler birebir) ·
`supabase_backfill_schema.sql` (dz şeması + K1/K2/K3).
