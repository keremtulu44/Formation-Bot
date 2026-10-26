# Kod denetimi ve hata tespiti — 2026-10-26

**Durum:** Kayıt · **Kapsam:** tüm depo (kod + test + yapı + belge düzeni) ·
**Yöntem:** pytest tam suite, bağımsız regresyon scriptleri, ruff statik analiz,
kaynak düzeyinde AST koruma taraması, env değişkeni drift kontrolü.

Bu belge **o günkü** tespitleri ölçer. Düzeltilen maddeler kodda yorumla da
işaretlidir; açık kalanlar için bugünün durumuna koddan bakın.

## 1. Özet

| # | Bulgu | Önem | Durum |
|---|---|---|---|
| B1 | `main.scan_all_stocks` DM musluğu: kullan-önce-ata + aşırı geniş `continue` | **Kritik** (uykuda özellik) | ✅ düzeltildi |
| B2 | `scripts/ozellik_deposu.py`: `Tuple` importu eksik | Düşük | ✅ düzeltildi |
| B3 | `scripts/backfill/arastirma_kosu.py`: `pd` tip ipucunda tanımsız | Düşük | ✅ düzeltildi |
| B4 | `.env.example` env drift: 8 değişken belgelenmemiş | Orta (operasyon) | ✅ düzeltildi |
| B5 | Kullan-önce-ata sınıfını yakalayan koruma testi yoktu | Orta (regresyon riski) | ✅ eklendi |

Test durumu (denetim sonunda): **pytest 1768+ passed / 0 failed**,
`test_tarama_zamani.py` 102/102, diğer bağımsız scriptler yeşil.

## 2. Bulgular

### B1 — Kritik: DM devamlılık musluğu iki ayrı hata taşıyordu (`main.py`)

`DM_MIN_DEVLAMLILIK > 0` ile açılan devamlılık puanı musluğu (varsayılan `0`
= kapalı, o yüzden canlıda sessiz):

1. **Kullan-önce-ata:** musluk `mtf_uyum` ve `bant_mesafe_atr` adlarını,
   aynı `for tf_name, df_tf` döngüsünde **~140 satır sonra** atandıkları
   halde okuyordu. Python bu adları fonksiyon local'i saydığı için ilk
   uyarlanan adayda `UnboundLocalError`, sonraki adaylarda **önceki TF'nin
   eskimiş değeriyle** yanlış devamlılık puanı çıkıyordu (sessiz yanlış sonuç,
   hangi adayın DM'e gideceğini yanlış seçebilirdi).
2. **Musluk fazla geniş kesiyordu:** eşik altındakilerde `continue` ile tüm
   tur sonu kesiliyordu — `formasyon_kaydı` (yani `/formasyonlar`, Top-12,
   canlı durum kaydı) ve public kuyruk da. Oysa tasarım ilkesi (aynı fonksiyon
   içindeki `dm_gecersiz_engel` notu, 2026-10-22): **"DM engeli grubu
   etkilemez"**; `PUBLIC_MIN_DEVLAMLILIK` grubun kendi kapısıdır.

**Düzeltme:** MTF/mesafe girdileri her aktif formasyonda en başta bir kez
hesaplanır; musluk `dm_gecersiz_engel` ile aynı yola bağlandı (yalnız DM push
durur; kayıt + bağlam + public kuyruk akar). Yeni koruma testi
`test_tanimsiz_ad_korumasi.py::test_fonksiyonda_atamadan_once_kullanim_yok`
bu sınıfı kaynak düzeyinde kilitler (denetimde önce bu testle **kırmızı**
yakalandı, düzeltmeyle yeşile döndü).

### B2/B3 — Düşük: tip ipuçlarında tanımsız adlar (script'ler)

* `scripts/ozellik_deposu.py`: `List[Tuple[...]]` ipucunda `Tuple` importu yoktu.
* `scripts/backfill/arastirma_kosu.py`: `"pd.DataFrame"` ipuçlarında `pd`
  modül düzeyinde import edilmemişti (fonksiyon içi importlar vardı).

İkisi de `from __future__ import annotations` sayesinde çalışma anında
patlamaz; tip denetleyici/lint hatalarıydı. `Tuple` eklendi; `pd` için
`TYPE_CHECKING` bloğu açıldı. Bu sınıfın gerçek `NameError` hâli
`test_tanimsiz_ad_korumasi.py` modül geneli korumasının zaten kapsadığı not edilsin.

### B4 — Orta: `.env.example` env drift'i

`config.py` + kod tabanı 32 env okurken 8'i örnekte yoktu. Operasyon tarafı
(Render/yerel kurulum) bu anahtarları keşfedemiyordu. Eklendi:

| Değişken | Varsayılan | Ne yapar |
|---|---|---|
| `DEVLAMLILIK_AKTIF` | 1 | 0 = 25 Eyl kart metni birebir (rollback yolu) |
| `DM_MIN_DEVLAMLILIK` | 0 | DM devamlılık musluğu (bkz. B1) |
| `PUBLIC_MIN_DEVLAMLILIK` | 0 | Public kuyruk devamlılık musluğu |
| `MAKRO_ALARM` | 0 | Makro semboller (BRENT vb.) alarm üretsin mi |
| `TELEGRAM_KART_SUZGEC` | 1 | Kart süzgeci (0 = 25 Eyl tam kartı) |
| `TELEGRAM_KART_TAHMIN` | 0 | Beklenti hükmü satırı |
| `GRAFIK_YAZI` | (boş) | Kare içi yazı ölçeği |
| `LOCAL_LOG_DIR` | (boş) | LOG_DIR yazılamazsa fallback log dizini |

Ayrıca geliştirici/CI bayrakları (`BOT_HEALTH_SMOKE_ONLY`,
`FORMATION_BOT_ALLOW_LIVE_YAHOO_RESEARCH`) "Geliştirme / CI" başlığında
belgelendi. Drift kontrolü artık temiz.

### B5 — Regresyon koruması eklendi

`test_tanimsiz_ad_korumasi.py`ye fonksiyon-içi **kullan-önce-ata**
(UnboundLocalError) koruması eklendi: bir ad, ait olduğu fonksiyonda
atandığı satırdan önce okunuyorsa test kırılır. Kapsam kuralları dosya
docstring'inde (argümanlar güvenli, iç içe kapsam/comprehension dışarıda,
kaynak sırası over-approximation'ı bilinçli). Denetim anında tüm depoda
**yalnız B1'i** raporladı — yanlış alarm yok.

## 3. Denetlendi, sorun bulunmadı

* **`x == x` / `x != x` kalıpları** (ruff PLR0124, 13 adet): hepsi bilinçli
  NaN kontrolü (`devamlilik.py`, `notifier.py`, `patterns/*`). Hata değil;
  okunabilirlik için `math.isnan` düşünülebilir (düşük öncelik).
* **Döngü değişkeni yakalayan yardımcılar** (ruff B023, ~100 adet): örneklem
  incelendi (`domain_engines/fvg/*`, `analytics/backtest.py`); yardımcılar
  tanımlandıkları iterasyon İÇİNDE çağrıldığı için kapama kaçışı yok. Yine de
  bu kalıp kırılgandır: yardımcılar ertelenirse gerçek hataya döner.
* **`formasyon_kaydi['mtf_destek']`** önce `False` yazılır, `scan_all_stocks`
  sonunda ikinci geçişte üst TF teyidiyle güncellenir — kasıtlı iki aşamalı
  tasarım, sorun yok.
* **Bağımsız regresyon scriptleri:** `test_tarama_zamani.py` 102/102;
  `test_breakout/flag/pennant/triangle.py` yeşil. `test_accuracy.py` ve
  `test_forward.py` bilinçli olarak `FORMATION_BOT_EXPLORATORY_DATA_DIR`
  ister (arşiv ölçüm araçları).
* **Sözdizimi:** tüm `.py` dosyaları `compileall` temiz.

## 4. Açık öneriler (bu denetimde değiştirilmedi)

1. **CI'ya kalan bağımsız regresyon scriptlerini ekle.** `pytest.ini` 7
   script'i toplamadan çıkarıyor; CI yalnız `test_tarama_zamani.py`'yi
   koşuyor. `test_breakout/flag/pennant/triangle.py` saniyeler içinde biter
   ve kurulum istemez — CI adımına eklenmeleri bedava regresyon ağı.
   (`test_accuracy/forward.py` arşiv verisi ister; onlara "manuel" notu düşülmeli.)
2. **S110 (`try/except/pass`) incelemesi:** üretim kodunda ~10 sessiz yutma
   var (5'i `grafik.py`'de). 23 Ekim'deki "sade kart" olayı tam da yutulan
   `NameError` sınıfıydı; sessiz `pass`'lerin en azından `logger.debug`'a
   çevrilmesi tekrarını engeller.
3. **Ruff'ı CI'a sabitle (hata sınıfları).** Depoda ruff config'i yok; bu
   denetimde ~2.600 stil bulgusu var (UP006/UP045 modernizasyon, I001 import
   sırası vb. — acelesi yok). Ama F821/F811/E9 sınıfı hatalar ve yeni
   kullan-önce-ata koruması için `ruff check --select F,E9` gibi dar bir kapı
   düşük maliyetli bir erken uyarı verir (ruff sürümünü de pinleyin).
4. **`test_p2_6_mirror.py` / `test_p2_audit_lifecycle.py` içindeki 20 F811:**
   aynı `ortam` adı her testte yeniden tanımlanıyor; fixture'a çevrilirse hem
   gürültü azalır hem "yanlış fixture kullanılıyor" hataları görünür olur.
5. **Dosya boyutları:** `main.py` ve `grafik.py` ~5.000'er satır, `notifier.py`
   ~3.900. Şimdilik testler güçlü; bir sonraki büyük özellikte alarm gönderim
   zinciri ile tarama döngüsünün ayrıştırılması bakımı kolaylaştırır.
6. **Repo ağırlığı:** `backfill_data/` (11 MB, 357 dosya) + `bot_data/` seed +
   `docs/gorseller/` PNG'leri bilerek git'te (README/.gitignore gerekçeli).
   Büyüme eğilimi sürerse Git LFS veya seed verisinin release artefaktı olarak
   dağıtımı düşünülebilir — şu an için acil değil (`.git` toplam 15 MB).

## 5. Doğrulama kaydı (2026-10-26)

```
pytest -q                     → 2002 passed, 0 failed (43 skipped)
test_tarama_zamani.py         → 102/102
test_breakout/flag/pennant/triangle.py → yeşil
ruff --select F821            → All checks passed
compileall                    → temiz
env drift kontrolü            → 0 eksik
```

Not: `test_dm_gecersizlesme_kapisi_publici_durdurmaz` yapısal sözleşmesi, iki
DM kapısının (`dm_gecersiz_engel` + `dm_dev_engel`) aynı bağlam/public yolunu
paylaştığını doğrulayacak şekilde genişletildi (2002 sayısına yeni AST
koruma parametreleri dahildir).
