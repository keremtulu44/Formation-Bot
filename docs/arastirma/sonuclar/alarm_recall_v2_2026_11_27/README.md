# Nedensel alarm kapsamı — v2 kanıt paketi

Tarih: 2026-11-27. [Türkçe değerlendirme](../../../denetim/NEDENSEL_ALARM_KAPSAMASI_2026-11-27.md).
Bu, önceki `alarm_filter_audit_2026_11_27/` terminal-rekonstrüksiyon sayımının üzerine yazılmaz; farklı, nedensel aday akışıdır. Amaç adet azaltmak değil anlamlı olayları kaçırmamaktır.

## İçerik

- `summary.json`: P0/P6/P4/P7 seçilen, politika/cooldown engelli kohortları; P0 ile aynı-mum geçişleri; kronolojik duyarlılık; 200/200 önek karşılaştırması, 200 native arşiv hash'i, kod/config kaydı, sınırlamalar.
- `breakdown.json`: P0/P6 yön, TF ve kanal kombinasyonları; cooldown kategorik değişim proxy'si; aynı formasyonda gecikmeli P6 seçimi. Kaynak ve analiz kodu hash'leri dahil.
- `daily.csv`: 22 ortak İstanbul seansında her politikanın bağımsız altı bar cooldown sonrası potansiyel olay sayısı. Teslim edilmiş mesaj sayısı değil.
- `examples.csv`: P0 seçimi olup P6 seçimi olmayanlardan her ilk-bariyer sınıfının kronolojik ilk üçü; toplam 12 satır. Sonuç sınıfı örneklemede kullanılır, politika kararında kullanılmaz. Zaman UTC mum açılış etiketidir.
- `evidence_manifest.json`: büyük/küçük koşu çıktılarının SHA256 ve boyutları, ek kod/test hash'leri, test kapsamı. Kendisi hash'lenmez.

Ham `events.jsonl` (~31 MB), `decisions.jsonl` (~6 MB) ve seri bar/seans metası Git dışında `var/alarm_recall_v2_20261127/` altında. Üretilen büyük dosyalar commit kapsamına alınmaz. Ham dosyalar kaybolursa aynı girdilerle aşağıdaki komutlar üzerinden yeniden üretilebilir. Yeni koşunun süre alanı/kod hash'leri ve dolayısıyla üst JSON dosya hash'leri doğal olarak farklı olabilir; eski manifest mevcut kaydın kimliğidir, gelecekteki çıktının sabit checksum beklentisi değildir.

## Yeniden üretim

Repo kökünde, deploy/dev bağımlılıkları kurulu Python ortamı ve aynı `backfill_data/` gerekir. Çıktı dizini **yeni/boş** olmalı; yarım koşuyla tamamlanmış koşu karıştırılmaz. Çalışma kopyasındaki config dosyaları ve ortam değerleri de sonuçta kayıtlı değerlerle karşılaştırılmalıdır; üretim env'si doğrulanmış sayılmaz.

```bash
env STOCK_UNIVERSE='' TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= \
  TELEGRAM_GROUP_ID= TELEGRAM_CHANNEL_ID= SUPABASE_URL= \
  SUPABASE_SERVICE_ROLE_KEY= .venv/bin/python -m research.alarm_recall_study \
  --output var/alarm_recall_v2_reproduction

.venv/bin/python -m research.alarm_recall_breakdown \
  --input var/alarm_recall_v2_reproduction \
  --output var/alarm_recall_v2_reproduction

.venv/bin/python -m pytest -q test_causal_alarm_replay.py test_alarm_recall_breakdown.py
.venv/bin/python -m ruff check research/causal_alarm_replay.py \
  research/alarm_recall_study.py research/alarm_recall_breakdown.py \
  test_causal_alarm_replay.py test_alarm_recall_breakdown.py
```

Aynı offline koşuda 200 seri 428,54 sn, 200/200 önek eşitliği, 0 domain hatası, 35.071 tam-geçmiş / 6.907 pencere adayı. Ortak dönem 19 Ekim–18 Kasım 2026, 22 seans. Odaklı testler 25 geçti; ilgili 13 dosya regresyonu 1.547 geçti (örtüşür, toplanmaz). Yerel Python 3.11; deploy 3.12 ile bu çalışmada ayrıca koşulmadı.

## Ölçümde yanlış yorumlanmaması gerekenler

- **Canlı Stabil destek/mesafe kapısından önceki adaylar**, tam canlı tarama/teslim/MTF birleştirme simülasyonu değil.
- Sabit başlangıçlı son480 native bar; kayan pencere/parite iddiası yok.
- +1/−1 giriş ATR'si, ileri12bar, ilk bariyer sırası. Aynı mumda ikisi belirsiz. Sonuç ufku eksikleri ve yönü bilinmeyenler kalite başarısızlığına çevrilmez.
- Yönü bilinmeyen satırlar sayımda kalır. `UNKNOWN_DIRECTION` durum sayısı ile `unknown_direction` sayısı örtüşen sansür nedeniyle aynı olmayabilir.
- Engellenmiş satırlar bağımsız kaçırılmış işlemler değildir. Aynı formasyon/hareket çok kez ölçülebilir. Kategorik imza eşitliği gerçek domain olay kimliği eşitliği değildir.
- Gecikme analizindeki 794 satır →197 farklı sonraki seçim; +1 ATR önce görülmüş 300 satır →114 farklı sonraki seçim. Bu, 300 bağımsız kaçırılmış fırsat demek değildir.
- Kronolojik yarılar daha önce araştırılmış aynı arşivdir, kör holdout değildir. İşlem maliyeti/PnL veya istatistiksel/gelecekteki üstünlük iddiası yok.
