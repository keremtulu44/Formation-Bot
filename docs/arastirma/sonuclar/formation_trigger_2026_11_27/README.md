# Formasyon alarmının tetikleme yeri — 27 Kasım 2026

[Değerlendirme ve düzeltme](../../../denetim/ALARM_TETIKLEME_YERI_2026-11-27.md).

- `summary.json`: 200 native seri; önek karşılaştırmaları, kod/veri hash'leri; sabit kırılım fiyatı ve olay-mumu çizgisinin kalite+kapanış kapısı farkı.
- `gate_disagreements.csv`: değerlendirme döneminde kaliteyi geçen 110 **mum snapshot'ı**; 110 bağımsız alarm/işlem değildir. Zaman UTC açılış etiketidir.
- `evidence.json`: koşu dosyalarının hash'leri, testler, geri alınan yanlış yön/AI çalışmasının kapsamı.
- Ham 3.314 teyit/retest snapshot'ı Git dışında `var/formation_trigger_aligned_20261127/rows.jsonl` altında. İlk tanı koşusu `var/formation_trigger_audit_20261127/` altında korunmuştur; tamamlanmamış koşularla karıştırılmaz.

## Yeniden üretim

Repo kökünden, native `backfill_data/` ve deploy/dev Python bağımlılıkları gerekir. Yeni/boş çıktı dizini kullanılmalıdır. Sağlayıcı, LLM, Telegram veya Supabase çağrısı yoktur; özel motorun `_key` değeri None kalır.

```bash
env TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= TELEGRAM_GROUP_ID= \
  TELEGRAM_CHANNEL_ID= SUPABASE_URL= SUPABASE_SERVICE_ROLE_KEY= \
  STOCK_UNIVERSE='' .venv/bin/python -m research.formation_trigger_audit \
  --output var/formation_trigger_reproduction

.venv/bin/python -m pytest -q test_formation_trigger_geometry.py test_tutarlilik.py
.venv/bin/python -m pytest -q test_stabil_resistance_delivery_e2e.py
```

Tam seri karşılaştırması 200/200 geçmiş öneğinde eşit. Dört TF'de değiştirilmiş gelecek testleri ayrıca var. Sonuçlara gelecek fiyat hareketi/başarı etiketi dahil edilmez. `distance_gt_1atr_descriptive_only`, yeni bir mesafe kapısı değil yalnız betimsel ölçümdür.

Dönem: 19 Ekim–18 Kasım 2026. 477 duruma giriş; eski kapıda ilk uygun 315, geometriyle hizalı kapıda 360 durum dönemi. 45'i eski kapıda durum boyunca hiç geçmiyordu; 18'i eski kapıda 1–2 mum bekliyordu. Dönemler formasyon × durum × duruma giriş mumu ile ayrılır; 18 ve 45 bağımsız işlem sayıları değildir.

**Sınır:** sabit başlangıçlı son480 native bar, kalite+kapanış kapısı; üretimin kayan penceresi, kimlik depoları, tarama programı, diğer alarm yolları ve gerçek teslim defteri değil. +45, günlük DM artışı veya kâr artışı iddiası değildir. Asıl düzeltme motor çizgisi ile bildirim kontrolünün aynı mumda aynı seviyeyi kullanmasıdır. Uçtan uca test farklı bir arşiv kesitinde üretim tarama/render hattını sahte taşıma ile doğrular; o testteki 2h/4h, üretim örneğindeki gibi saatlik veriden türetilir ve native sayım tablosuna eklenmez.

Eski üç-argümanlı `_alert_break_level` çağrısı tarihî referansı korur. Canlı tarama olay bar indeksini verir ve yalnız teyit/retestte sağlam çapa varsa olay çizgisini seçer; iptal bildirimi ile eksik çapa fallback'i değişmez. Canlı/replay denetimindeki `seviye` aynı ortak geometri yardımcısını kullanır.
