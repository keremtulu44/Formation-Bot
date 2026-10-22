# Belgeler — tek giriş noktası

> **Kural:** Bir belgenin güncel olup olmadığı dosya adından değil, bu tablodaki
> **Durum** ve **Tarih** sütunlarından okunur. Yeni belge eklerken buraya bir satır
> eklenir (bkz. [YAPI.md](YAPI.md) §7).

**Durum etiketleri:** `Yürürlükte` = bugün de geçerli kural/sözleşme ·
`Kayıt` = tarihli ölçüm/denetim, karar gerekçesi olarak yaşar (güncel durum iddiası yok) ·
`Arşiv` = yürürlükten kalkmış plan/not (silinmez, `arsiv/` altında) ·
`Üretilen` = bir script tarafından yazılır, elle düzenlenmez.

## Ne arıyorsan buraya

| İhtiyaç | Belge |
|---|---|
| Botu kuracağım / çalıştıracağım | [kurulum/LOCAL_SETUP.md](kurulum/LOCAL_SETUP.md) |
| Render'a (canlıya) çıkaracağım | [kurulum/RENDER_DEPLOY.md](kurulum/RENDER_DEPLOY.md) |
| Telefondan arşiv verisi çekeceğim | [kurulum/TERMUX_BACKFILL.md](kurulum/TERMUX_BACKFILL.md) |
| Canlıya geçiş adımları / runbook | [operasyon/CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md](operasyon/CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md) |
| Kanal/grup açacağım | [operasyon/KANAL_ACILIS_PAKETI.md](operasyon/KANAL_ACILIS_PAKETI.md) · [operasyon/PUBLIC_GRUP_HAZIRLIK.md](operasyon/PUBLIC_GRUP_HAZIRLIK.md) |
| Formasyon mantığı / Pine farkı | [tasarim/FORMASYON_MANTIGI.md](tasarim/FORMASYON_MANTIGI.md) · [tasarim/PINE_FARK_ANALIZI.md](tasarim/PINE_FARK_ANALIZI.md) |
| Grafik tasarım sözleşmesi | [tasarim/GRAFIK_TASARIM.md](tasarim/GRAFIK_TASARIM.md) · [tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md](tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md) |
| Telegram kart/bildirim kuralları | [tasarim/TELEGRAM_KART_FORMAT.md](tasarim/TELEGRAM_KART_FORMAT.md) · [tasarim/BILDIRIM_TESLIM_POLITIKASI.md](tasarim/BILDIRIM_TESLIM_POLITIKASI.md) |
| **Ölçüm: zone'lar piyasada ne yapıyor?** | **[arastirma/](arastirma/README.md)** |
| Neden bu karar verildi? (denetimler) | [denetim/](denetim/) tablosu |
| Projeyi başka birine/AI'ya devredeceğim | [rehber/MASTER_PROMPT.md](rehber/MASTER_PROMPT.md) · [rehber/AI_PROJE_TANITIMI.md](rehber/AI_PROJE_TANITIMI.md) |
| Eski planlar / kapanmış iş listesi | [arsiv/](arsiv/README.md) |

## Yürürlükteki belgeler

### `arastirma/` — ölçüm çıktısı
| Dosya | Durum | Tarih | İçerik |
|---|---|---|---|
| [arastirma/README.md](arastirma/README.md) | Yürürlükte | 2026-10 | Giriş: kilit bulgular + açık MS bulgusu |
| [arastirma/ARASTIRMA_SONUCLARI.md](arastirma/ARASTIRMA_SONUCLARI.md) | Yürürlükte | 2026-10 | Soru bazında cevaplar ve yorum |
| [arastirma/ARASTIRMA_HATTI.md](arastirma/ARASTIRMA_HATTI.md) | Yürürlükte | 2026-10 | Yöntem, modüller, anti-lookahead |
| [arastirma/YASAM_TABLOSU.md](arastirma/YASAM_TABLOSU.md) | Yürürlükte | 2026-10-20 | Domain bazında soru sicili: OB/FVG/formasyon yaşam tablosu + cevap formatı |
| [arastirma/KOLON_SOZLUGU.md](arastirma/KOLON_SOZLUGU.md) | Yürürlükte | 2026-10-21 | Ortak kolon dili: anlam + birim + `n` birimi + formasyon tablosu taslağı |
| [arastirma/FORMASYON_SONUCLARI.md](arastirma/FORMASYON_SONUCLARI.md) | Üretilen | 2026-10-21 | Formasyon FRM-01…20 cevap kartları (arşiv replay) |
| [arastirma/AMPIRIK_REFERANS.md](arastirma/AMPIRIK_REFERANS.md) | Yürürlükte | 2026-10-21 | Ölçümü canlı metne bağlayan katman: hangi sayı kartta hangi koşulda görünür (`ampirik_referans.py`) |
| [arastirma/REPLAY_OZET_2026-10-21.md](arastirma/REPLAY_OZET_2026-10-21.md) | Kayıt | 2026-10-21 | Son doğrulanmış replay'in okunur özeti: tek tabloda MFE/MAE/NET, örneklem güvenilirliği, açık uçlar |
| [arastirma/ARASTIRMA_BULGULARI.md](arastirma/ARASTIRMA_BULGULARI.md) | Üretilen | 2026-10 | Ham tablo eki (`arastirma_kosu.py --agrega`) |
| [arastirma/ARASTIRMA_RAPORU_DUZMETIN.txt](arastirma/ARASTIRMA_RAPORU_DUZMETIN.txt) | Yürürlükte | 2026-10 | Düz metin dışa aktarım |
| [arastirma/arastirma_ms_hatali_seriler.txt](arastirma/arastirma_ms_hatali_seriler.txt) | Kayıt (açık bulgu) | 2026-10 | MS motorunun patladığı 35 seri |

### `tasarim/` — yürürlükteki sözleşmeler
| Dosya | Durum | Konu |
|---|---|---|
| [tasarim/FORMASYON_MANTIGI.md](tasarim/FORMASYON_MANTIGI.md) | Yürürlükte | Pine v0.4.6 formasyon koşulları, kalite formülleri |
| [tasarim/PINE_FARK_ANALIZI.md](tasarim/PINE_FARK_ANALIZI.md) | Yürürlükte | Pine ↔ Python fark defteri, doğrulama listesi |
| [tasarim/GRAFIK_TASARIM.md](tasarim/GRAFIK_TASARIM.md) | Yürürlükte | Grafik sözleşmesi G0→G5 (kodda `§` ile referanslı) |
| [tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md](tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md) | Yürürlükte | Güven şeridi, odak/bağlam, açıklanabilirlik (`chart-trust-focus-v3`) |
| [tasarim/TELEGRAM_KART_FORMAT.md](tasarim/TELEGRAM_KART_FORMAT.md) | Yürürlükte | Alarm kartı biçim sözleşmesi |
| [tasarim/BILDIRIM_TESLIM_POLITIKASI.md](tasarim/BILDIRIM_TESLIM_POLITIKASI.md) | Yürürlükte | MTF tekilleştirme, geçersizleşme, teslim kuyruğu |
| [tasarim/FAZ3_BACKTEST_VERI_ANALIZI.md](tasarim/FAZ3_BACKTEST_VERI_ANALIZI.md) | Yürürlükte | Backtest/analytics tasarımı (`analytics/backtest.py`) |
| [tasarim/PHASE2_TASARIM_NOTLARI.md](tasarim/PHASE2_TASARIM_NOTLARI.md) | Yürürlükte | Kimlik/mirror tasarım notları |

### `kurulum/` — kur ve çalıştır
| Dosya | Durum | İçerik |
|---|---|---|
| [kurulum/LOCAL_SETUP.md](kurulum/LOCAL_SETUP.md) | Yürürlükte | Yerel/Termux kurulumu, bilinen build hataları |
| [kurulum/RENDER_DEPLOY.md](kurulum/RENDER_DEPLOY.md) | Yürürlükte | Render + Supabase + Telegram + keep-alive |
| [kurulum/TERMUX_BACKFILL.md](kurulum/TERMUX_BACKFILL.md) | Yürürlükte | Telefondan 365 günlük arşiv çekimi |

### `operasyon/` — canlıya alma ve işletim
| Dosya | Durum | İçerik |
|---|---|---|
| [operasyon/CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md](operasyon/CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md) | Yürürlükte | Kontrollü canlı doğrulama adımları, rollback |
| [operasyon/KANAL_ACILIS_PAKETI.md](operasyon/KANAL_ACILIS_PAKETI.md) | Yürürlükte | Kanal açılış metinleri ve adımları |
| [operasyon/PUBLIC_GRUP_HAZIRLIK.md](operasyon/PUBLIC_GRUP_HAZIRLIK.md) | Kayıt (politika) | Public grup yayın hattı ve dil kararları |

### `rehber/` — devir teslim
| Dosya | Durum | İçerik |
|---|---|---|
| [rehber/MASTER_PROMPT.md](rehber/MASTER_PROMPT.md) | Yürürlükte | Projeyi başka bir AI oturumuna aktarma metni |
| [rehber/AI_PROJE_TANITIMI.md](rehber/AI_PROJE_TANITIMI.md) | Yürürlükte | Dosya göremeyen bir AI'ya görsel tarafı anlatma paketi |

## Kayıt: tarihli denetimler (`denetim/`)

Bu belgeler **o günkü** durumu ölçer; bugünün doğrusu değildir. Bir madde hâlâ açık mı
diye bakmadan önce kodun kendisine ve [YAPI.md](YAPI.md) §6'ya bakın.

| Dosya | Tarih | Ne ölçtü |
|---|---|---|
| [denetim/GENEL_INCELEME_VE_YOL_HARITASI_2026-10-16.md](denetim/GENEL_INCELEME_VE_YOL_HARITASI_2026-10-16.md) | 2026-10-16 | Uçtan uca inceleme + önceliklendirilmiş iş listesi (Y1–Y16) |
| [denetim/TELEGRAM_PRODUCT_AND_LIVE_READINESS_AUDIT.md](denetim/TELEGRAM_PRODUCT_AND_LIVE_READINESS_AUDIT.md) | 2026-10 | Canlıya hazırlık denetimi (NO-GO gerekçeleri) |
| [denetim/TELEGRAM_SYSTEM_AUDIT.md](denetim/TELEGRAM_SYSTEM_AUDIT.md) | 2026-10-08 | Bildirim yaşam döngüsü, 100 sembole ölçek tahmini |
| [denetim/TELEGRAM_FORMAT_COMPARISON_EXAMPLES.md](denetim/TELEGRAM_FORMAT_COMPARISON_EXAMPLES.md) | 2026-10 | A/B/C/D/E format örnekleri (karar verilmedi) |
| [denetim/SORUN_RAPORU.md](denetim/SORUN_RAPORU.md) | 2026-09 | Üretim→Telegram hunisi, bastırılan adaylar (S1–S11) |
| [denetim/ZONE_SCORING_AUDIT.md](denetim/ZONE_SCORING_AUDIT.md) | 2026-10-11 | FVG/OB puanlama prototipi denetimi |
| [denetim/GRAFIK_YEREL_DOGRULAMA_RAPORU.md](denetim/GRAFIK_YEREL_DOGRULAMA_RAPORU.md) | 2026-10-14 | Grafik katmanı yerel doğrulaması |
| [denetim/GRAFIK_BILDIRIM_DENETIMI_2026-10-15.md](denetim/GRAFIK_BILDIRIM_DENETIMI_2026-10-15.md) | 2026-10-15 | Grafik yerleşimi + bildirim zamanlaması |

## Görseller (`gorseller/`)

| Yol | İçerik |
|---|---|
| [gorseller/ornek_galeri/](gorseller/ornek_galeri/README.md) | **Sentetik** DEMO alarm kartları (6 senaryo) — `scripts/ornek_gorsel_uret.py` üretir |
| `gorseller/ornek_*.png` | Tasarım kararlarının kanıt kareleri (önce/sonra, rozet, sağ boşluk) |
| `gorseller/AKBNK_ODAK_MOBIL.png` | Mobil odak görünümü referansı |

## Arşiv (`arsiv/`)

Yürürlükten kalkmış plan ve notlar: [arsiv/README.md](arsiv/README.md).
Hiçbiri silinmedi; her birinin başında "ARŞİV" bandı vardır.

## Taşıma haritası (2026-10-20)

Kök dizindeki 25 belge `docs/` altına taşındı; kod, test ve davranış değişmedi.
Eski bir bağlantı/yol arıyorsan:

| Eski konum | Yeni konum |
|---|---|
| `RENDER_DEPLOY.md` · `LOCAL_SETUP.md` | `docs/kurulum/…` |
| `GRAFIK_TASARIM.md` · `TELEGRAM_KART_FORMAT.md` · `FORMASYON_MANTIGI.md` · `PINE_FARK_ANALIZI.md` · `FAZ3_BACKTEST_VERI_ANALIZI.md` · `PHASE2_TASARIM_NOTLARI.md` | `docs/tasarim/…` |
| `CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md` · `KANAL_ACILIS_PAKETI.md` · `PUBLIC_GRUP_HAZIRLIK.md` | `docs/operasyon/…` |
| `GENEL_INCELEME_VE_YOL_HARITASI_2026-10-16.md` · `SORUN_RAPORU.md` · `ZONE_SCORING_AUDIT.md` · `TELEGRAM_*_AUDIT.md` · `GRAFIK_*_RAPORU.md` | `docs/denetim/…` |
| `MASTER_PROMPT.md` · `docs/AI_PROJE_TANITIMI.md` | `docs/rehber/…` |
| `YAPILACAKLAR.md` · `KODLAMA_PLANI.md` · `ASAMA4_…` · `MERGE_MAIN_…` · `BILDIRIM_INCELEME_…` | `docs/arsiv/…` |
| `docs/ARASTIRMA_*` · `docs/arastirma_ms_hatali_seriler.txt` | `docs/arastirma/…` |
| `docs/*.png` · `docs/ornek_galeri/` · `AKBNK_ODAK_MOBIL.png` | `docs/gorseller/…` |
| `docs/archive/` | `docs/arsiv/` |
| `docs/TERMUX_BACKFILL.md` | `docs/kurulum/TERMUX_BACKFILL.md` |
| `docs/BILDIRIM_TESLIM_POLITIKASI.md` | `docs/tasarim/BILDIRIM_TESLIM_POLITIKASI.md` |
| `docs/GRAFIK_GUVEN_ODAK_AYRINTI.md` | `docs/tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md` |
