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
| Telefondan NATIVE 1h/2h/4h/1d arşiv verisi çekeceğim | [kurulum/TERMUX_BACKFILL.md](kurulum/TERMUX_BACKFILL.md) |
| Native veri arşivi geldi mi / doğrulama sayıları | [denetim/NATIVE_VERI_GELISI_2026-11-19.md](denetim/NATIVE_VERI_GELISI_2026-11-19.md) · [Termux çekim rehberi](kurulum/TERMUX_BACKFILL.md) |
| Canlıya geçiş / güncel deploy ve rollback | [kurulum/DEPLOY_CANLI_ONCESI_2026-11-06.md](kurulum/DEPLOY_CANLI_ONCESI_2026-11-06.md) (eski plan: [arşiv](operasyon/CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md)) |
| Grup hedefi ve komutlar | [Render rehberi](kurulum/RENDER_DEPLOY.md) · geçmiş kararlar: [kanal paketi](operasyon/KANAL_ACILIS_PAKETI.md), [grup hazırlık analizi](operasyon/PUBLIC_GRUP_HAZIRLIK.md) |
| Formasyon mantığı / Pine farkı | [tasarim/FORMASYON_MANTIGI.md](tasarim/FORMASYON_MANTIGI.md) · [tasarim/PINE_FARK_ANALIZI.md](tasarim/PINE_FARK_ANALIZI.md) |
| Veri kaynağı / TF geçiş kapısı | [tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md](tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md) (2026-11-18: üretime uygulandı + native replay kararı) · [NATIVE 1h/2h/4h/1d replay veri planı](arastirma/NATIVE_TF_REPLAY_PLANI_2026-11-18.md) · [tam TV + Yahoo deploy yolu](denetim/DEPLOY_HAZIRLIK_2026-11-18.md) · [son genel kontrol](denetim/GENEL_KONTROL_2026-11-18.md) · [native veri gelişi doğrulaması](denetim/NATIVE_VERI_GELISI_2026-11-19.md) |
| Deploy + bildirim kuyrukları denetimi | [denetim/DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md](denetim/DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md) · [Render rehberi](kurulum/RENDER_DEPLOY.md) |
| Grafik tasarım sözleşmesi | [tasarim/GRAFIK_TASARIM.md](tasarim/GRAFIK_TASARIM.md) · [tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md](tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md) |
| Telegram kart/bildirim kuralları | [tasarim/TELEGRAM_KART_FORMAT.md](tasarim/TELEGRAM_KART_FORMAT.md) · [tasarim/BILDIRIM_TESLIM_POLITIKASI.md](tasarim/BILDIRIM_TESLIM_POLITIKASI.md) |
| **174 hisse kırılım ve teyit Replay'i** | [Ayrıntılı sonuç, yöntem ve veri rehberi](arastirma/KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md) |
| **Stabil domain, direnç ve yerel teslim doğrulaması** | [Stabil ana rehberi](arastirma/STABIL_REHBERI.md) · [7 Kasım genel kontrol](denetim/STABIL_DIRENC_GENEL_KONTROL_2026-11-07.md) · [direnç görsel/teslim denetimi](tasarim/STABIL_DIRENC_GORSEL_TESLIM_DENETIMI_2026-11-07.md) · [kanıt/kurtarma durumu](arastirma/STABIL_DOSYA_ENVANTERI.md) |
| Replay ve piyasa pilot sonuçları | [arastirma/SON_REPLAY_SONUCLARI.md](arastirma/SON_REPLAY_SONUCLARI.md) |
| **Stop & sermaye koruma replay'i** | **[arastirma/STOP_SERMAYE_REPLAY_2026-11-09.md](arastirma/STOP_SERMAYE_REPLAY_2026-11-09.md)** · [çıktılar: sonuclar/stop_sermaye/](arastirma/sonuclar/stop_sermaye/) · [betik](../scripts/stop_sermaye_replay.py) |
| **Gölge zincir replay'i (Faz 0–5)** | **[arastirma/GOLGE_ZINCIR_REPLAY_2026-11-09.md](arastirma/GOLGE_ZINCIR_REPLAY_2026-11-09.md)** · [giriş/çıkış incelemesi](arastirma/GOLGE_ZINCIR_GIRIS_CIKIS_INCELEMESI_2026-11-10.md) · [plan](tasarim/5_FAZLI_KODLAMA_PLANI_2026-11-09.md) · [sözleşme](tasarim/SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md) · [çıktılar: sonuclar/golge_zincir/](arastirma/sonuclar/golge_zincir/) · betikler: `research/golge_{zincir,olcum,kapi,inceleme}.py` |
| **Gölge v2 (domain-denetimli plan + işlem-içi süreç)** | **[arastirma/GOLGE_V2_INCELEME_VE_SUREC_2026-11-14.md](arastirma/GOLGE_V2_INCELEME_VE_SUREC_2026-11-14.md)** · [ana rapor](arastirma/sonuclar/golge_v2/RAPOR_GOLGE_V2.md) · [işlem-içi süreç ölçümü](arastirma/sonuclar/golge_v2/surec_olcum/RAPOR.md) · [sonuç anatomisi (kim kazandı, kim nasıl kaybetti)](arastirma/sonuclar/golge_v2/sonuc_anatomisi/RAPOR.md) · [endeks rejimi filtresi](arastirma/sonuclar/golge_v2/endeks_filtresi/RAPOR.md) · [kâr görüp dönenlerin domain dökümü](arastirma/sonuclar/golge_v2/kar_gorup_donen/RAPOR.md) · [tepki ölçümü (gözleme tepki verilseydi)](arastirma/sonuclar/golge_v2/tepki_olcum/RAPOR.md) · [karantina duyarlılığı](arastirma/sonuclar/golge_v2/karantina_duyarlilik/RAPOR.md) · [çıktılar: sonuclar/golge_v2/](arastirma/sonuclar/golge_v2/) · betikler: `research/golge_v2{,_surec_olcum,_sonuc_anatomisi,_endeks_filtresi,_kar_gorup_donen,_tepki_olcum,_karantina_duyarlilik,_iptal_olcum,_mtf_olcum,_donus_anatomisi}.py` |
| **Ölçüm: zone'lar piyasada ne yapıyor?** | **[arastirma/](arastirma/README.md)** |
| Neden bu karar verildi? (denetimler) | [denetim/](denetim/) tablosu |
| Projeyi başka birine/AI'ya devredeceğim | [rehber/MASTER_PROMPT.md](rehber/MASTER_PROMPT.md) · [rehber/AI_PROJE_TANITIMI.md](rehber/AI_PROJE_TANITIMI.md) |
| Eski planlar / kapanmış iş listesi | [arsiv/](arsiv/README.md) |

## Yürürlükteki belgeler

### `arastirma/` — ölçüm çıktısı
| Dosya | Durum | Tarih | İçerik |
|---|---|---|---|
| [arastirma/STABIL_REHBERI.md](arastirma/STABIL_REHBERI.md) | Yürürlükte | 2026-11-04+ | Domain/kaynak/replay haritası; mevcut runtime ve entegrasyon doğrulaması (canlı deploy kanıtı değil) |
| [denetim/STABIL_DIRENC_GENEL_KONTROL_2026-11-07.md](denetim/STABIL_DIRENC_GENEL_KONTROL_2026-11-07.md) | Kayıt | 2026-11-07 | Stabil direnç ve grafik teslimi: bulgular, testler ve canlı doğrulama sınırları |
| [tasarim/STABIL_DIRENC_GORSEL_TESLIM_DENETIMI_2026-11-07.md](tasarim/STABIL_DIRENC_GORSEL_TESLIM_DENETIMI_2026-11-07.md) | Kayıt | 2026-11-07 | Gerçek arşivli PNG ve sahte taşımalı bildirim yolları; gerçek Telegram/deploy değil |
| [arastirma/STABIL_REPLAY_HATLARI.md](arastirma/STABIL_REPLAY_HATLARI.md) | Kayıt | 2026-11-01 | Genel replay ile Stabil native motoru ayrımı ve önceki optimize yöntem |
| [arastirma/STABIL_DAVRANIS_MODELI.md](arastirma/STABIL_DAVRANIS_MODELI.md) | Kayıt | 2026-11-01 | Konuşmadan yeniden kayıt; dikey/yatay düzeltmesi ve kullanıcı hipotezleri |
| [arastirma/STABIL_SISTEM_INCELEMESI_2026-11-08.md](arastirma/STABIL_SISTEM_INCELEMESI_2026-11-08.md) | İnceleme | 2026-11-08 | Destek/direnç mantığı, ok kuralları, replay hattı, taze 40 sembol kanıtı, açık sorunlar ve düzeltmeler |
| [arastirma/STABIL_SORU_SETI_V2_2026-11-08.md](arastirma/STABIL_SORU_SETI_V2_2026-11-08.md) | Tasarım | 2026-11-08 | V2 ana soru seti: 8 soru, ölçüm sözleşmesi (günlük ATR, ikili başarı ölçüsü, sembol bölmesi), dallanma yöntemi, eksik kod işleri |
| [arastirma/STABIL_DESTEK_SONRASI_DAVRANIS_SORU_PLANI_2026-11-07.md](arastirma/STABIL_DESTEK_SONRASI_DAVRANIS_SORU_PLANI_2026-11-07.md) | Taslak | 2026-11-07 | Native Stabil desteğine göre davranış araştırması ve konuşulacak tanımlar; replay yapılmadı |
| [arastirma/STABIL_DAVRANIS_SORULARI.md](arastirma/STABIL_DAVRANIS_SORULARI.md) | Kayıt | 2026-11-01 | 48 soru sicili; konuşmadan yeniden kayıt, eski bayt-kopyası değil |
| [arastirma/STABIL_CALISMA_GECMISI.md](arastirma/STABIL_CALISMA_GECMISI.md) | Kayıt | 2026-11-01 | 27/48 soru koşularının konuşmada raporlanan sayıları; artefaktlar eksik |
| [arastirma/STABIL_DOSYA_ENVANTERI.md](arastirma/STABIL_DOSYA_ENVANTERI.md) | Kayıt | 2026-11-01 | Bugün mevcut dosyalar, eksik runtime/veri ve kurtarma listesi |
| [Stabil kaynak notu](../domain_engines/STABIL_KAYNAK_NOTU.md) | Kayıt | 2026-11-01 | Özgün TXT, SHA256 ve eksik entegrasyon kapsamı |
| [arastirma/README.md](arastirma/README.md) | Yürürlükte | 2026-10 | Giriş: kilit bulgular + açık MS bulgusu |
| [arastirma/ARASTIRMA_SONUCLARI.md](arastirma/ARASTIRMA_SONUCLARI.md) | Yürürlükte | 2026-10 | Soru bazında cevaplar ve yorum |
| [arastirma/ARASTIRMA_HATTI.md](arastirma/ARASTIRMA_HATTI.md) | Yürürlükte | 2026-10 | Yöntem, modüller, anti-lookahead |
| [arastirma/YASAM_TABLOSU.md](arastirma/YASAM_TABLOSU.md) | Yürürlükte | 2026-10-20 | Domain bazında soru sicili: OB/FVG/formasyon yaşam tablosu + cevap formatı |
| [arastirma/KOLON_SOZLUGU.md](arastirma/KOLON_SOZLUGU.md) | Yürürlükte | 2026-10-21 | Ortak kolon dili: anlam + birim + `n` birimi + formasyon tablosu taslağı |
| [arastirma/FORMASYON_SONUCLARI.md](arastirma/FORMASYON_SONUCLARI.md) | Üretilen | 2026-10-21 | Formasyon FRM-01…20 cevap kartları (arşiv replay) |
| [arastirma/AMPIRIK_REFERANS.md](arastirma/AMPIRIK_REFERANS.md) | Yürürlükte | 2026-10-21 | Ölçümü canlı metne bağlayan katman: hangi sayı kartta hangi koşulda görünür (`ampirik_referans.py`) |
| [arastirma/KOSULLU_CUMLE_OLCUMU.md](arastirma/KOSULLU_CUMLE_OLCUMU.md) | Ölçüm | 2026-10-22 | Koşullu tamamlanma cümlesi: çapraz tablo, aşım kovaları, "yazılmadı" kararı | 
| [arastirma/REPLAY_OZET_2026-10-21.md](arastirma/REPLAY_OZET_2026-10-21.md) | Kayıt | 2026-10-21 | Son doğrulanmış replay'in okunur özeti: tek tabloda MFE/MAE/NET, örneklem güvenilirliği, açık uçlar |
| [arastirma/DZ_REPLAY_SONUCLARI_2026-10-28.md](arastirma/DZ_REPLAY_SONUCLARI_2026-10-28.md) | Ölçüm + hat (legacy) | 2026-10-28 | 177 sembol × 4 TF tam replay (708/708, 0 hata): **2h/4h 1h'den türetilmiş** eski sonuçlar, `dz_*` depolama hattı ve kolon kapsam raporu; native replay için yenilenecek |
| [arastirma/NATIVE_TF_REPLAY_PLANI_2026-11-18.md](arastirma/NATIVE_TF_REPLAY_PLANI_2026-11-18.md) | Plan | 2026-11-18 | 170+ sembol için 1h/1d Yahoo + 2h/4h TradingView NATIVE çekimi; manifest/probe/rapor etiketleri, Termux akışı, replay sonraki tur |
| [denetim/NATIVE_VERI_GELISI_2026-11-19.md](denetim/NATIVE_VERI_GELISI_2026-11-19.md) | Kayıt | 2026-11-19 | 176 sembol × 4 native TF arşivinin Termux'tan gelişi; 704/704 dosya, 0 eksik, resample yok, probe 176/10, replay hazır ama koşulmadı |
| [arastirma/AI_SORU_URETICI_PROMPT.md](arastirma/AI_SORU_URETICI_PROMPT.md) | Yöntem | 2026-10-29 | Kod erişimi olmayan bir yapay zekâya verilecek tek parça soru-üretici prompt: tüm kolon/ölçek/eşik sözlüğü gömülü, depo yolları yalnızca dışlama satırı olarak |
| [arastirma/REPLAY_SORU_SETI_2026-10-29.md](arastirma/REPLAY_SORU_SETI_2026-10-29.md) | Soru seti | 2026-10-29 | Prompt'tan üretilen S01–S32 soru seti (kodla birebir karşılığı ve cevap sözleşmesi §0–§7 + açık uç sicili §8 E1–E16) |
| [arastirma/REPLAY_SORU_YANITLARI_2026-10-29.md](arastirma/REPLAY_SORU_YANITLARI_2026-10-29.md) | Üretilen | 2026-10-29 | `research/soru_cevaplama.py` ile S01–S32 cevapları (708 seri, 0 hata): §6 karar özeti 19 canlıya yazılır / 1 kart metni / 7 RED / 1 karar yok / 4 gözlem (S27 çırpınma kuralı yapısal taban nedeniyle RED'e çekildi) |
| [arastirma/AI_SONUC_YORUM_TALIMATI.md](arastirma/AI_SONUC_YORUM_TALIMATI.md) | Yöntem | 2026-10-29 | Dış AI'a verilecek tek parça sonuç-yorumu paketi: yalnız yorum kuralı (yeni soru/ölçüm istemez, sayı uydurmaz) + gömülü §0 eşik sözleşmesi |
| [arastirma/SORU_KOVA_BASELINE_2026-10-29.json](arastirma/SORU_KOVA_BASELINE_2026-10-29.json) | Üretilen | 2026-10-29 | `research/soru_kapisi.py` §6 kova bazeline: sonuç JSON'u bundan saparsa yayın durur (yenileme: `--kova-yaz`) |
| [arastirma/ARASTIRMA_BULGULARI.md](arastirma/ARASTIRMA_BULGULARI.md) | Üretilen | 2026-10 | Ham tablo eki (`arastirma_kosu.py --agrega`) |
| [arastirma/ARASTIRMA_RAPORU_DUZMETIN.txt](arastirma/ARASTIRMA_RAPORU_DUZMETIN.txt) | Yürürlükte | 2026-10 | Düz metin dışa aktarım |
| [arastirma/arastirma_ms_hatali_seriler.txt](arastirma/arastirma_ms_hatali_seriler.txt) | Kayıt (açık bulgu) | 2026-10 | MS motorunun patladığı 35 seri |

### `tasarim/` — yürürlükteki sözleşmeler
| Dosya | Durum | Konu |
|---|---|---|
| [tasarim/FORMASYON_MANTIGI.md](tasarim/FORMASYON_MANTIGI.md) | Yürürlükte | Pine v0.4.6 formasyon koşulları, kalite formülleri |
| [tasarim/PINE_FARK_ANALIZI.md](tasarim/PINE_FARK_ANALIZI.md) | Yürürlükte | Pine ↔ Python fark defteri, doğrulama listesi |
| [tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md](tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md) | Ölçüm sözleşmesi / uygulandı | 2026-11-18 | Yahoo birincil, tvDatafeed reaktif yedek ve gerçek 4s **üretim `data/fetch.py` + `bot/scan.py` hattında**. Ölçüm eşikleri, iki doğrulanmış dağıtım, kaynak etiketi ve `/health` izleme; uygulama durumu güncellendi; native replay arşivi 2026-11-19'da geldi |
| [tasarim/GRAFIK_TASARIM.md](tasarim/GRAFIK_TASARIM.md) | Yürürlükte | Grafik sözleşmesi G0→G5 (kodda `§` ile referanslı) |
| [tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md](tasarim/GRAFIK_GUVEN_ODAK_AYRINTI.md) | Yürürlükte | Güven şeridi, odak/bağlam, açıklanabilirlik (`chart-trust-focus-v3`) |
| [tasarim/TELEGRAM_KART_FORMAT.md](tasarim/TELEGRAM_KART_FORMAT.md) | Yürürlükte | Alarm kartı biçim sözleşmesi (22 Eki revizyonu: 7 blok, sade dil, public = DM) |
| [tasarim/KART_ORNEK_2026-10-22.md](tasarim/KART_ORNEK_2026-10-22.md) | Yürürlükte | Uygulanmış kart örnekleri: DM, geçersizleşme, kısa güncelleme, public bülten |
| [tasarim/BILDIRIM_TESLIM_POLITIKASI.md](tasarim/BILDIRIM_TESLIM_POLITIKASI.md) | Yürürlükte | MTF tekilleştirme, geçersizleşme, teslim kuyruğu |
| [tasarim/FAZ3_BACKTEST_VERI_ANALIZI.md](tasarim/FAZ3_BACKTEST_VERI_ANALIZI.md) | Yürürlükte | Backtest/analytics tasarımı (`analytics/backtest.py`) |
| [tasarim/PHASE2_TASARIM_NOTLARI.md](tasarim/PHASE2_TASARIM_NOTLARI.md) | Yürürlükte | Kimlik/mirror tasarım notları |
| [tasarim/MODULERLESTIRME_PLANI_2026-10-26.md](tasarim/MODULERLESTIRME_PLANI_2026-10-26.md) | Uygulandı | 2026-10-26 | Mega dosyaların (main/grafik/notifier/data) bölünme planı: hedef paket yapısı, geç bağlama kuralı, faz sırası (sonuç: [YAPI.md](YAPI.md) §8) |
| [tasarim/API_SENARYOLARI_VE_URUN_FIKIRLERI_2026-11-03.md](tasarim/API_SENARYOLARI_VE_URUN_FIKIRLERI_2026-11-03.md) | Fikir + local PoC | 2026-11-03 | Dışarıya salt-okunur API ile dış servis entegrasyonu ayrımı; ASTOR/Stabil HTTP kontratı yerelde sınandı, production API değil |
| [tasarim/SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md](tasarim/SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md) | Tasarım | 2026-11-09 | Sırayla konuşan katman brifingi, toplu yeniden yorum (TYR), bloklarla hassas giriş, işlem yaşam döngüsü + sermaye koruması; gölge defter/replay planı — kod yok, canlı karar değiştirmez |

### `kurulum/` — kur ve çalıştır
| Dosya | Durum | İçerik |
|---|---|---|
| [kurulum/LOCAL_SETUP.md](kurulum/LOCAL_SETUP.md) | Yürürlükte | Yerel/Termux kurulumu, bilinen build hataları |
| [kurulum/RENDER_DEPLOY.md](kurulum/RENDER_DEPLOY.md) | Yürürlükte | Render + Supabase + Telegram + keep-alive |
| [kurulum/TERMUX_BACKFILL.md](kurulum/TERMUX_BACKFILL.md) | Yürürlükte | Mevcut yerel klondan NATIVE 1h/2h/4h/1d çekimi, doğrulama, commit/push; **2026-11-19 koşusu tamamlandı**, replay ayrı turda |

### `operasyon/` — canlıya alma ve işletim
| Dosya | Durum | İçerik |
|---|---|---|
| [kurulum/DEPLOY_CANLI_ONCESI_2026-11-06.md](kurulum/DEPLOY_CANLI_ONCESI_2026-11-06.md) | Güncel | Kanıta dayalı deploy, canlı doğrulama ve rollback |
| [operasyon/CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md](operasyon/CANLI_DOGRLAMA_PLANI_VE_RUNBOOK.md) | Tarihsel | Önceki doğrulama planı; güncel state/teslim sözleşmesini yansıtmayabilir |
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
| [denetim/DEPLOY_HAZIRLIK_2026-11-18.md](denetim/DEPLOY_HAZIRLIK_2026-11-18.md) | 2026-11-18 | **Tam TV + Yahoo deploy yolu:** Yahoo birincil + tvDatafeed reaktif yedek üretim hattına ve `requirements*.txt`/`render.yaml`/CI'ye oturtuldu; kaynak etiketi, gerçek 4s, `/health`, `STRICT_UNKNOWN` kapıları; 39 yeni ağsız senaryo, **4525 passed / 43 skipped**, Python 3.12 CI `44346289337` success (15 dk 8 sn), ruff/pip check/compileall/diff/doktor/`health` smoke; PowerShell + Linux komutları, operatör adımları ve dürüst kanıt sınırı. İlk "TV deploy dışında" kararını geçersiz kılar |
| [denetim/DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md](denetim/DEPLOY_BILDIRIM_DENETIMI_2026-11-18.md) | 2026-11-18 | **Deploy + bildirim baştan sona denetim:** build/start/env parity, public-only doktor, TV/runtime env görünürlüğü, `/health.bildirim`, tarama dışı public bülten flush'ı, opt-in dar Supabase teslim yedeği, 120 sn shutdown, CI smoke assert'i ve global test-state izolasyonu; 16 yeni ağsız regresyon, **4557 passed / 43 skipped**, 102/102 timing, doktor/grafik 53 tamam / 0 hata, HTTP smoke; push `bef9008` CI `44366863050` success (9 dk 50 sn); gerçek deploy/PR ve canlı servis çağrısı yok |
| [denetim/GENEL_KONTROL_2026-11-18.md](denetim/GENEL_KONTROL_2026-11-18.md) | 2026-11-18 | TV/datafeed ekleri ve depo geneli: karar kapısının hacim/kısa-bar koşulları, naive yerel zamanın UTC'ye çevrimi, iki dağıtım/sürüm doğrulaması, WS kapanışı, ağsız `tanis`, eski dal `reset --hard` riski, aktif belge/kod çelişkileri; §8 ilk canlı ölçüm + ızgara/MultiIndex/`intersection` düzeltmeleri; §9 ikinci canlı ölçüm + `auto_adjust`/dinamik tolerans/WS yeniden deneme; §10 **TV + Yahoo tam üretim entegrasyonu** (`data/fetch.py`, `bot/scan.py`, pinler, `/health`, 39 senaryo, 4525 test) ve ilk "TV deploy dışında" kararının kapatılması |
| [denetim/NATIVE_VERI_GELISI_2026-11-19.md](denetim/NATIVE_VERI_GELISI_2026-11-19.md) | 2026-11-19 | **Native veri arşivinin gelişi:** `8a18fbd` + `6cb80eb` ile 176 sembol × 4 TF, 704/704 CSV.gz, `eksik=0`, `resample_kullanildi=false`, probe 176/10, 12 sembol yeniden probe ile kurtarıldı, manifest son koşu 704 `ok`; TCELL 2h/4h `+03:00` native bar örneği, 20M arşiv, replay hazır ama koşulmadı, PR/deploy/canlı ajan çağrısı yok |
| [denetim/GENEL_KONTROL_2026-11-16.md](denetim/GENEL_KONTROL_2026-11-16.md) | 2026-11-16 | Depo geneli kontrol: son commit (7cac9ce) iddialarının kod doğrulaması, CI statik kapısı (S110 ×2), 4.270/1 test sonucu, sağ şerit genişliği regresyonu ve bağlam zenginleştirmesinin çift çizelge maliyeti (+%90); §7: veri çekme hattında eksik çekilip geçilme denetimi (sessiz satır eleme, yutulan append reddi, onarılamayan seans içi boşluk, 1D cooldown kilidi, eksik seans tespiti); §8: genel kontrol (CI'nın 8 kapısı yerelde + GitHub Actions 12/12 yeşil, günlük sayaç şeması↔sıfırlama kayması düzeltmesi, tatil yanlış pozitifi doğrulaması); §9: `/grafik` her zaman çalışsın — seans-farkında tazelik (gecikme modeli), sağlayıcı geçici hatasında sınırlı yeniden deneme, yarım gün/tatil takvimi — düzeltmeler + açık riskler |
| [denetim/GRAFIK_OK_VE_CIZIM_INCELEMESI_2026-11-16.md](denetim/GRAFIK_OK_VE_CIZIM_INCELEMESI_2026-11-16.md) | 2026-11-16 | Grafikteki `▲`/`○` işaretleri: üç replay katmanının (tür kademesi 555 ok, bağlam halkası n=186/49, dikey bastırma) kod↔kanıt eşlemesi; canlı çizim yolu üzerinde piksel ölçümü (12 kare: komşu muma değme %27, kendi mumuna 0, 120 barlık 1G karelerde tarih etiketi çakışması); P1–P3 bulgular ve 7 maddelik onarım sırası — ölçüm betiği: `scripts/grafik_ok_ve_etiket_olcum.py`. §7.1–7.2: aynı gün uygulanan onarımlar (lejant `ok kademesi`, zayıf okun örtüsüz soluklaştırılması, türsüz momentumda nötr kademe, piksel komşuluklu eksen seyreltmesi 7/7→0, işaret geometrisi kalite kapısı, ok ofsetinin mumun dibine bağlanması; komşu muma değme %27→%39 ama dikey mesafe 12–57 px → 12–25 px) |
| [tasarim/KARNE_MASRAF_VE_OKUNURLUK_2026-11-16.md](tasarim/KARNE_MASRAF_VE_OKUNURLUK_2026-11-16.md) | 2026-11-16 | Haftalık karneye masraf katmanı (komisyon binde 2,1 + kayma 0,05 ATR; brüt/net yüzde, haftalık kovalar ve ortanca) ve performans bloğunun sadeleştirilmesi (Sonuç / Para / Son N hafta / Güven); başabaş isabet oranı %40 → %46,4; mesajın hangi bildirimde göründüğü |
| [denetim/OK_BAGLAM_DOGRULAMA_VE_UYGULAMA_2026-11-15.md](denetim/OK_BAGLAM_DOGRULAMA_VE_UYGULAMA_2026-11-15.md) | 2026-11-15 | Ok bağlam profili (güçlü/zayıf/çok güçlü) doğrulaması ve görsel uygulaması; bootstrap güven aralıkları ve sınırlar |
| [denetim/GRAFIK_ADIMLARI_VE_STABIL_OK_REPLAY_2026-11-15.md](denetim/GRAFIK_ADIMLARI_VE_STABIL_OK_REPLAY_2026-11-15.md) | 2026-11-15 | Dinamik sağ şerit, veri rozeti, ok türü taşıma/kademesi: kayıtlı replay sayıları ve uygulama kararları |
| [denetim/BILDIRIM_VE_GRAFIK_INCELEME_2026-11-15.md](denetim/BILDIRIM_VE_GRAFIK_INCELEME_2026-11-15.md) | 2026-11-15 | Bildirim hattı + grafik görünümü incelemesi ve uygulanan düzeltmeler |
| [denetim/MS_KILITLI_REFERANS_DUZELTME_2026-10-28.md](denetim/MS_KILITLI_REFERANS_DUZELTME_2026-10-28.md) | 2026-10-28 | MS motorunun 35 seride sessiz çökmesinin kök nedeni (kilitli geçici referansın fork'ta kaybı) + üç katmanlı düzeltme + 35/35 hedef regresyon |
| [denetim/TARAMA_VE_ONERILER_2026-10-28.md](denetim/TARAMA_VE_ONERILER_2026-10-28.md) | 2026-10-28 | Depo geneli tarama (suite/statik/kapılar), 2026-10-26 açık önerilerin durumu, veri envanteri ve Ö1–Ö7 yol haritası: süzgeç kaçakları karnesi, iki yıllık sağlamlık matrisi, seviye-test `◇` satırı, hacim faz ayrımı, üçgen kanal denei, motor sağlık sicili, karne bant sağlığı |
| [denetim/KOD_DENETIMI_2026-10-26.md](denetim/KOD_DENETIMI_2026-10-26.md) | 2026-10-26 | Depo geneli kod/hata denetimi: DM musluğu kullan-önce-ata (B1), env drift, yeni AST koruma testi + açık öneriler |
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
