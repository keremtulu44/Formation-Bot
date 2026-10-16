# Örnek görsel galerisi

Bu klasördeki PNG'ler **sentetik (uydurma) veriyle** üretilmiş örnek alarm kartlarıdır;
gerçek piyasa verisi değildir, sembol hep `DEMO`'dur. Botun Telegram'a gönderdiği
karelerle **aynı çizim zinciri** (`grafik.anlik_goruntu` → `grafik.ciz`) kullanılır;
ayrı bir "demo çizicisi" yoktur. Bu yüzden buradaki görüntü, canlı karenin birebir
önizlemesidir.

## Nasıl yeniden üretilir

```bash
python scripts/ornek_gorsel_uret.py --liste          # katalog
python scripts/ornek_gorsel_uret.py                  # iki manşet kare
python scripts/ornek_gorsel_uret.py --senaryo hepsi  # tüm katalog
python scripts/ornek_gorsel_uret.py --senaryo bayrak_aday --mobil
```

Görsel dil değiştikçe (palet, bölge politikası, serit…) galeriyi yeniden üretip
`git add` ile yan yana karşılaştırabilirsin; regresyon testi
(`test_ornek_gorsel_uret.py`) katalogdaki her senaryonun çizilebildiğini,
determinizmini ve güvenlik kurallarını (bot_data yasağı, "demo · sentetik"
etiketi) korur.

## Katalog

| Dosya | Senaryo | Kartın gösterdiği |
|---|---|---|
| `ornek_ucgen_teyit_1g.png` | **manşet** — Simetrik Üçgen · 1g · `KIRILIM_TEYITLI` | Tam katmanlı teyit kartı: formasyon bantları + alarm çizgisi + OB/FVG bölgeleri + dış yapı (BOS/CHoCH, PH/PL) + kanıt etiketi + RVOL rozeti |
| `ornek_bayrak_aday_4s.png` | **manşet** — Boğa Bayrağı · 4s · `KIRILIM_ADAYI` | Kırılım öncesi aday kartı: direk FVG'si, kanal bantları, kritik seviye vurgusu |
| `ornek_flama_teyit_4s.png` | Boğa Flaması · 4s · `KIRILIM_TEYITLI` | Direk + flama + teyit barı işaretli |
| `ornek_kama_hazirlik_1g.png` | Yükselen Kama · 1g · `KIRILIM_HAZIRLIGI` | Apex'e yaklaşan sıkışma; kritik seviye alt bantta |
| `ornek_ucgen_gecersiz_1g.png` | Alçalan Üçgen · 1g · `KIRILIM_GECERSIZLESTI` | Yalançı kırılım: teyit sonrası bant altına düşüş, karşı delil vurgusu |
| `ornek_ucgen_retest_4s.png` | Yükselen Üçgen · 4s · `RETEST_BASARILI` | Kırılım sonrası banda dönüş; FVG desteği görünür |

## Kurallar

- `bot_data/` içine **asla** yazılmaz (canlı önbellek sentetik veriyle
  zehirlenmez; `grafik_uret.py --demo` ile aynı sözleşme).
- Veri tohumlu ve deterministiktir: iki çalıştırma aynı `girdi_ozeti`ni üretir.
- "Şimdi" son barın KAPANIŞ anından 90 sn sonradır (`data.mum_kapanis_ani`) —
  açık bar düşürmesi yaşanmaz, kapanış kuralı tek kaynaktan gelir.
- Güven şeridi kaynağı dürüstçe `demo · sentetik` yazar; motor kayıtları canlı
  motor alan sözleşmesiyle birebir verilir (uydurma alan yok).
