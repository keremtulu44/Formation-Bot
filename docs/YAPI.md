# Depo Yapısı — Plan ve Uygulama Kaydı

> **Durum:** Yürürlükte (2026-10-20).
> **Kapsam:** Yalnız **belge ve görsel yerleşimi**. Kod, test, davranış, iş mantığı
> değişmedi. Bu belge "hangi dosya nerede olmalı, neden orada" sorusunun tek cevabıdır.
> **Giriş noktası:** [README.md](README.md) (belge haritası) · [../README.md](../README.md) (proje).

## 1. İlkeler

1. **Kök dizin çalıştırılabilir olsun, okunabilir olsun.** Kökte yalnız giriş noktaları
   (`main.py` vb.), yapılandırma ve `README.md` kalır. Anlatı belgeleri `docs/` altına gider.
2. **Kod yerinde kalır.** Python modülleri, testler ve `scripts/` taşınmaz; import yolları,
   `pytest` toplaması ve CI komutları aynı kalır. Yerleşim değişikliği davranış değişikliği
   üretmez (bkz. §6).
3. **Yürürlükteki belge ile tarihli kayıt ayrılır.** Karar/sözleşme belgeleri `tasarim/`,
   işletim belgeleri `operasyon/`, geçmişe ait plan ve raporlar `denetim/` + `arsiv/`.
4. **Tek harita.** Hangi belgenin güncel olduğu dosya adından değil,
   [README.md](README.md) tablosundan okunur (durum + tarih sütunları).
5. **Taşınan yol, kodda/testte kalan referanslarıyla birlikte taşınır.** Bir belge taşınıyorsa
   onu işaret eden kod, CI ve kullanıcıya basılan metinler aynı adımda güncellenir; kırık yol
   bırakılmaz. (Yalnız tarihsel test docstring'lerindeki belge adları bilinçli olarak
   bırakıldı: yorumdur, tıklanabilir bağlantı değildir — bkz. §4 A4.)

## 2. Hedef ağaç

```
.
├── README.md                       ← proje girişi + belge haritası bağlantısı
├── main.py · test_*.py · conftest.py  ← KOD: yerinde (main.py İNCE başlatıcı — §8)
├── bot/ grafik/ notifier/ data/    ← KOD PAKETLERİ (2026-10-26 modülerleştirme — §8)
├── requirements*.txt · pytest.ini · render.yaml · .env.example · *.sql · *.service
├── backfill_data/ · bot_data/      ← VERİ: yerinde
├── scripts/ patterns/ state/ domain_engines/ research/ reporting/ transport/ analytics/
└── docs/
    ├── README.md                   ← BELGE HARİTASI (tek giriş, durum + tarih)
    ├── YAPI.md                     ← bu belge: yerleşim planı ve kuralları
    ├── arastirma/                  ← ÖLÇÜM: arşiv araştırması (değerli çıktı)
    │   ├── README.md               ← kilit bulgular + açık bulgu + yeniden üretim
    │   ├── ARASTIRMA_SONUCLARI.md            (yorum: soruların cevapları)
    │   ├── ARASTIRMA_BULGULARI.md            (tablo eki; üretici buraya yazar)
    │   ├── ARASTIRMA_HATTI.md                (hattın yöntemi ve modülleri)
    │   ├── ARASTIRMA_RAPORU_DUZMETIN.txt     (düz metin dışa aktarım)
    │   └── arastirma_ms_hatali_seriler.txt   (MS motoru hata listesi — AÇIK BULGU)
    ├── tasarim/                    ← YÜRÜRLÜKTEKİ SÖZLEŞMELER (karar belgeleri)
    │   ├── GRAFIK_TASARIM.md
    │   ├── GRAFIK_GUVEN_ODAK_AYRINTI.md
    │   ├── TELEGRAM_KART_FORMAT.md
    │   ├── BILDIRIM_TESLIM_POLITIKASI.md
    │   ├── FORMASYON_MANTIGI.md
    │   ├── PINE_FARK_ANALIZI.md
    │   ├── FAZ3_BACKTEST_VERI_ANALIZI.md
    │   └── PHASE2_TASARIM_NOTLARI.md
    ├── kurulum/                    ← KUR → ÇALIŞTIR
    │   ├── LOCAL_SETUP.md
    │   ├── RENDER_DEPLOY.md
    │   └── TERMUX_BACKFILL.md
    ├── operasyon/                  ← CANLIYA ALMA VE İŞLETİM
    │   ├── CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md
    │   ├── KANAL_ACILIS_PAKETI.md
    │   └── PUBLIC_GRUP_HAZIRLIK.md
    ├── denetim/                    ← TARİHLİ DENETİM/İNCELEME (kayıt değeri)
    │   ├── GENEL_INCELEME_VE_YOL_HARITASI_2026-10-16.md
    │   ├── SORUN_RAPORU.md
    │   ├── ZONE_SCORING_AUDIT.md
    │   ├── TELEGRAM_SYSTEM_AUDIT.md
    │   ├── TELEGRAM_PRODUCT_AND_LIVE_READINESS_AUDIT.md
    │   ├── TELEGRAM_FORMAT_COMPARISON_EXAMPLES.md
    │   ├── GRAFIK_YEREL_DOGRULAMA_RAPORU.md
    │   └── GRAFIK_BILDIRIM_DENETIMI_2026-10-15.md
    ├── rehber/                     ← DEVİR TESLİM / AI BAĞLAMI
    │   ├── MASTER_PROMPT.md
    │   └── AI_PROJE_TANITIMI.md
    ├── gorseller/                  ← TÜM GÖRSELLER (belge kanıtları + demo galeri)
    │   ├── AKBNK_ODAK_MOBIL.png
    │   ├── ornek_*.png
    │   └── ornek_galeri/           ← üretici script'in varsayılan çıktısı
    └── arsiv/                      ← YÜRÜRLÜKTEN KALKMIŞ PLAN/NOT (silinmez, arşivlenir)
        ├── README.md
        ├── YAPILACAKLAR.md
        ├── KODLAMA_PLANI.md
        ├── ASAMA4_CANLIYA_HAZIRLIK_PLANI.md
        ├── BILDIRIM_INCELEME_NOTLARI_2026-10-16.md
        ├── MERGE_MAIN_CELISKI_RAPORU.md
        ├── DOGRULAMA_RAPORU.md
        ├── FAZ2_FINAL_AUDIT_RAPORU.md
        ├── P26_MIMARI_ONERI.md
        └── TESHIS_RAPORU.md
```

## 3. Klasör sözleşmesi

| Klasör | Neye girer | Neye girmez |
|---|---|---|
| `docs/arastirma/` | Ölçüm hattının çıktıları, yöntem, ham tablo eki, yeniden üretim komutları | Tek seferlik denetim yorumları |
| `docs/tasarim/` | Bugün de geçerli sözleşme/karar belgeleri; kodda `§` ile referans verilen metinler | Tamamlanmış iş planları |
| `docs/kurulum/` | Kurulum, dağıtım, cihazdan veri çekme adımları | Ürün/strateji notları |
| `docs/operasyon/` | Canlıya alma runbook'u, kanal/grup işletimi | Geçmiş faz planları |
| `docs/denetim/` | Tarihli inceleme/denetim raporları (karar gerekçesi olarak yaşar) | Güncel sözleşme (o `tasarim/`) |
| `docs/rehber/` | Projeyi başka birine/AI'ya devretme bağlamı | Günlük notlar |
| `docs/gorseller/` | Belge kanıtı PNG'ler + demo galeri | Üretim/runtime çıktıları (`bot_data/` dışında tutulmaz) |
| `docs/arsiv/` | Yürürlükten kalkmış plan/not; başında "arşiv" bandı taşır | Hâlâ geçerli bir kural |

**Adlandırma:** dosya adları Türkçe ve `BÜYÜK_HARF` (mevcut gelenek korunur); tarihli
belgeler adında `YYYY-MM-DD` taşır. Klasör adları küçük harf Türkçe (`gorseller`,
`arastirma` — ASCII, Türkçe karakter yok).

## 4. Uygulama kaydı (adım adım)

Her adım kendi doğrulamasıyla kapandı; hiçbir adımda kod davranışı değişmedi.

| # | Adım | Ne yapıldı | Doğrulama |
|---|---|---|---|
| A1 | Plan | Bu belge + hedef ağaç + klasör sözleşmesi | Gözden geçirme |
| A2 | Belgeleri taşı | 25 kök belge + `docs/` içi 9 belge yerine taşındı (`git mv` — geçmiş korunur) | `git status` yalnız `R` (rename) gösterir |
| A3 | Görselleri topla | Kök `AKBNK_ODAK_MOBIL.png` + `docs/*.png` + `docs/ornek_galeri/` → `docs/gorseller/` | Galeri üreticisi yeni varsayılan yolla çalışıyor |
| A4 | Referansları güncelle | Taşınan yolları işaret eden docstring/print/CI yorumu satırları (`deploy_check.py`, `research/rapor.py`, `scripts/backfill/*`, `scripts/ornek_gorsel_uret.py`, `canli_tarama.py`, `config.py`, `grafik.py`, `reporting/format.py`, `state/formation_history.py`, `analytics/backtest.py`, `keepalive.yml`) | `grep` ile eski yol kalmadı; testler yeşil. **Bilinçli istisna:** `test_*.py` içindeki tarihsel belge adı geçen docstring'ler (yorum) değiştirilmedi |
| A5 | Harita | `docs/README.md`: tek tabloda konum + durum + tarih; eski→yeni yol karşılığı | Tüm satırların hedefi mevcut (link denetimi) |
| A6 | Arşiv bandı | `docs/arsiv/*` belgelerinin başına "ARŞİV — yürürlükte değil" bandı | 9 belgede band var, gövde değişmedi |
| A7 | Temizlik | `.coverage` silindi; `.coverage`, `.ruff_cache/`, `.pytest_cache/` `.gitignore`'a; PNG istisnası yeni klasöre taşındı | `git ls-files -ci --exclude-standard` boş |
| A8 | Doğrulama | Tam `pytest` paketi + belge bağlantı denetimi | §5 |

## 5. Doğrulama sonuçları

| Kontrol | Komut | Sonuç |
|---|---|---|
| Tam test paketi | `.venv/bin/python -m pytest -q` | **1494 passed, 43 skipped** (taşıma öncesiyle aynı) |
| Belge bağlantıları | tek seferlik Python denetimi (göreli markdown linkleri + kod/CI `.md` yolları) | **0 kırık bağlantı** (42 belge) |
| Yol referansı | `grep` eski konumlar | Kodda eski yol kalmadı |
| Git geçmişi | `git log --follow` | Taşımalar `R` (rename) olarak izlenir |
| Görsel üretici | `scripts/ornek_gorsel_uret.py` (test) | Yeni varsayılan dizin `docs/gorseller/ornek_galeri` |

## 6. Bilerek yapılmayanlar (sonraki faz)

Aşağıdakiler **planlandı ama bu turda uygulanmadı**; gerekçe: her biri import yolu / test
toplaması gibi çalışma zamanı sözleşmelerine dokunur ve ayrı bir doğrulama turu ister.

| Faz | İş | Neden ertelendi | Ön koşul |
|---|---|---|---|
| F2 | `test_*.py` (83 dosya) → `tests/` | Testler `Path(__file__).parent` ile repo köküne ve `bot_data/`'ya göreli erişiyor; 7 script tarzı test doğrudan `python test_x.py` ile koşuyor | Yol varsayımlarının tek yardımcıya (`tests/_yol.py`) çekilmesi, CI komutlarının güncellenmesi |
| F3 | Kök modüller → `formation_bot/` paketi | 40+ test dosyası ve `scripts/` düz import kullanıyor; `main.py` giriş noktası, Render start command ve service dosyası değişir | Önce F2, sonra tek dalda import + entrypoint göçü |
| F4 | `canli_tarama.py`, `gun_simulasyonu.py`, `deploy_check.py` gibi tek amaçlı araçlar → `tools/` | Testler bunları modül adıyla import ediyor; paket olmadan `tools/` import edilemez | `tools/__init__.py` + test import güncellemesi |

## 7. Yeni belge eklerken

1. Doğru klasörü seç (§3).
2. Tarihliyse adına `YYYY-MM-DD` koy, gövdesinde "Durum" satırı bulundur.
3. [README.md](README.md) tablosuna **bir satır** ekle (yol + durum + tarih).
4. Belgeyi koda bağlayan bir yol varsa (üretici script, komut çıktısı) aynı commit'te güncelle.
5. Yürürlükten kalkan belgeyi silme; `arsiv/` altına taşı ve başına arşiv bandı koy.

## 8. Kod paket yapısı (2026-10-26 modülerleştirme)

> 2026-10-26: mega dosyalar (`main.py` 5096, `grafik.py`, `notifier.py`,
> `data.py`) `docs/tasarim/MODULERLESTIRME_PLANI_2026-10-26.md` planına göre
> bölündü. **Giriş sözleşmesi aynı:** `python main.py`. Davranış farkı sıfır.
> Ayrıntı + sapma kaydı: planın başındaki DURUM notu.

```
main.py                 # İNCE başlatıcı (60 satır): stdlib + `from bot import *`
bot/
├── __init__.py         # namespace yüzeyi: import bloğu + tüm modüllerin yeniden
│                       #   bağları + __all__ (yama yüzeyi main namespace'inde)
├── statestore.py       # süreç ref'leri + durum kalıcılığı + sayaç depoları
├── counters.py         # günlük sayaçlar, reset_daily_if_needed
├── heartbeat.py        # write_heartbeat + _heartbeat_*
├── commands.py         # Telegram komutları/webhook, /grafik işi, /tarama isteği
├── lifecycle_events.py # olay sınıflandırma/kayıt/invalidation
├── scan.py             # scan_all_stocks + tarama hattı
├── security.py         # alarm izin/politika kapıları
├── summary.py          # özet/gönderim/gece bakımı
└── app.py              # setup_logging, signal_handler, main_loop
grafik/                 # 10 modül (Faz 2)
notifier/               # api, format_kart, format_summary, util (Faz 1)
data/                   # fetch → replay → backfill → seed_cache + __main__.py
```

**Geç bağlama kuralı (plan §3):** yamalı adlar `main` namespace'inde tek
sahipli; `bot/*` çağrı anında `_pkg.X` okur, global rebind'ler
`setattr(_pkg, ...)` yazar → `monkeypatch.setattr(main, X)` yamaları (579)
aynen yakalanır. Kırık test yaması YOK (`test_patch_yuzeyi.py` güvencesi).

**Girişler:** `python main.py` (AYNI) · `BOT_HEALTH_SMOKE_ONLY=1` (AYNI) ·
`python -m data` (eski `python data.py` dumanı) · `python deploy_check.py` (AYNI).
