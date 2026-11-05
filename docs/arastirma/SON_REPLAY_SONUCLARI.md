# Replay araştırmaları ve sonuç dosyaları

## Stabil — kaynak, entegrasyon ve iki ayrı araştırma

**[Stabil ana rehberi](STABIL_REHBERI.md)** · [Replay yöntemleri](STABIL_REPLAY_HATLARI.md) ·
[Davranış modeli](STABIL_DAVRANIS_MODELI.md) · [48 soru](STABIL_DAVRANIS_SORULARI.md) ·
[Çalışma geçmişi](STABIL_CALISMA_GECMISI.md) · [Dosya durumu](STABIL_DOSYA_ENVANTERI.md).

**2026-11-04 checkout durumu:** Stabil runtime, `research/stabil_replay.py`,
`research/stabil_bhv48.py` ve 48-soru aggregate sonuçları mevcut. Bu, önceki
100 sembol/27 soru sonuç paketinin veya 48-soru koşusunun tam native checkpoint
arşivinin mevcut olduğu anlamına gelmez; mevcut manifestte kaynak hashleri ve
kesin veri kesimi eksik. Daha önce konuşmada raporlanan sayılarla current manifesti
karıştırmayın; ayrıntı ve sayım farkları [çalışma geçmişinde](STABIL_CALISMA_GECMISI.md)
ve [envanterde](STABIL_DOSYA_ENVANTERI.md) açıklanır. 50/53 systematic raporu
ayrı popülasyondur. Diğer replay evrenleri de birbirine eklenemez.

**Durum:** Tarihsel araştırma kayıtları; canlı alarm veya yatırım tavsiyesi değildir.
Makro kaynakların gerçek kapanış saatleri doğrulanmadı: varsayımlı sonuçlar kesin
bulgu olarak kullanılmamalıdır. Gram/TL OHLC bulunmadığından gram sonuçları yoktur.

**İç alarm/istek bağlamı prototipi:** [API ve yorumlama planı](ALARM_CONTEXT_API_PLANI.md) ·
[ASTOR no-lookahead sample](samples/ALARM_CONTEXT_ASTOR_2026-10-16.md) ·
[10 sembolün yorum raporu](samples/ALARM_CONTEXT_10_SEMBOL_INCELEME_2026-10-16.md) ·
[10 tam JSON çıktısı (ZIP)](samples/ALARM_CONTEXT_10_SEMBOL_2026-10-16.zip). Bu belgeleme
mevcut live alarm davranışını, depolamayı veya Supabase'i değiştirmez.

## Stabil — birbirinden ayrı replay/araştırma popülasyonları (2026-11-04)

| Çalışma | Kaydedilmiş kapsam | Checkout çıktısı | Durum / sınır |
|---|---|---|---|
| 48 davranış sorusu | 100 hisse; 107.441 H4 checkpoint; 10.417 ilk-görülen destek olayı; 48 soru; 642 tablo satırı; manifest 2026-11-01 | [Manifest](stabil_100_sonuclar/STABIL_DAVRANIS_48_MANIFEST.json), [sonuç JSON](stabil_100_sonuclar/STABIL_DAVRANIS_48_SONUCLAR.json), [CSV](stabil_100_sonuclar/STABIL_DAVRANIS_48_TABLO.csv), [yanıt raporu](stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md) | Aggregate çıktılar mevcut; tam native checkpoint arşivi, kaynak SHA/hash ve manifestte kesin veri kesim zamanı yok. Aday rejim eşlemesi kullanıcı teyitli değil. |
| İlk 100 sembol / 27 soru | Önceki oturumda tamamlandığı raporlandı | Özgün tam çıktı/native paket bu checkout'ta bulunamadı; [envanter](STABIL_DOSYA_ENVANTERI.md) | Sayılar tarihsel konuşma kaydıdır; 48-soru mevcut dosyalarıyla birleştirilmez. |
| Canlı evren sistematik değerlendirmesi | 53 canlı non-macro sembolden 50 arşivde; 2025-05-07 .. 2026-10-19; 284 sinyal | [Sonuç JSON](stabil_live_systematic_results.json), [üretici](../../research/stabil_live_systematic.py) | 50/53 popülasyonu ve sinyal ölçümü; 100-sembol/48-soru davranış replay'inden ayrıdır. |

2026-11-04 incelemesinde ASTOR 4h için tek sembol/48-soru spot-check de yapıldı;
bu 100-sembollük tam replay'in yeniden koşusu değildir. Mevcut manifest sayımları
107.446 checkpoint / 4.074 satır olarak geçen önceki konuşma kayıtlarından farklıdır;
bu farklı sürümleri sessizce birleştirmeyin. Ayrıntı: [çalışma geçmişi](STABIL_CALISMA_GECMISI.md).

## 174 hisse kırılım ve teyit Replay'i

Ayrı araştırma: arşivdeki 174 hisse × 1 saat/2 saat/4 saat/günlük = 696 seri. Aday, teyit, teyit sonrası hareket; yukarı/aşağı, keşif/ileri dönem ve veri/sansür sınırları ayrı kaydedildi. Bu evren aşağıdaki 48 deploy hissesi piyasa karşılaştırmasından farklıdır.

- **[Ayrıntılı ana dosya: bütün sonuçlar, yöntem, tablolar ve tekrar üretim](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md)**
- [İlk kırılım ve teyit raporu](KIRILIM_TEYIT_REPLAY_SONUCLARI_2026-10-30.md) · [Teyit sonrası hareket raporu](TEYIT_SONRASI_HAREKET_2026-10-30.md).
- [Adaylar](sonuclar/kirilim_replay/adaylar.csv.gz) · [teyit kontrolleri](sonuclar/kirilim_replay/teyit_kontrolleri.csv.gz) · [teyit nedenleri özeti](sonuclar/teyit_nedenleri/ozet.csv) · [teyit sonrası olaylar](sonuclar/teyit_sonrasi/teyit_sonrasi_olaylar.csv.gz).
- [Aynı olaylarda aday–teyit karşılaştırması](sonuclar/aday_teyit_karsilastirma/olaylar.csv.gz) · [grup özeti](sonuclar/aday_teyit_karsilastirma/ozet.csv) · [hisse/TF özeti](sonuclar/aday_teyit_karsilastirma/hisse_tf_ozet.csv) · [manifest](sonuclar/aday_teyit_karsilastirma/manifest.json).

## Deploy hisseleri ve piyasa karşılaştırmaları

Varsayılan deploy listesindeki 48 hisse ile endeks, ons altın/gümüş, Brent ve kur;
1/5/10 işlem günü. 12 tekli ve 66 ikili koşul, daha yüksek birleşimler bu pilotta
yoktur. Keşif/ileri dönem, eşikler ve kısıtlar raporda açıklanır.

- [Okunabilir sonuçlar ve yöntem](DEPLOY_PIYASA_PILOTU.md)
- [Tekli karşılaştırmalar — CSV](DEPLOY_TEKLI_PIYASA_HUCRELERI.csv)
- [Tekli ve ikili hücrelerin tamamı — sıkıştırılmış CSV](DEPLOY_PIYASA_PILOT.csv.gz)
- [Veri kapsamı ve kaynak kontrolleri — JSON](DEPLOY_PIYASA_PILOT_META.json)
- Yeniden üretim: `python scripts/deploy_piyasa_pilotu.py` (çıktı `var/`;
  tek hisse örneği: `python scripts/deploy_piyasa_pilotu.py ASTOR`).

## Genel çapraz piyasa ve XU100 + Brent

- [Çapraz piyasa araştırma hattı, yöntem ve ASTOR/THYAO pilotu](CAPRAZ_PIYASA_UYGULAMA.md)
- [Katı UNKNOWN pilot hücreleri](sonuclar/capraz_kati/cells.csv) · [kaynak ve kapsam](sonuclar/capraz_kati/summary.json)
- [İki gün gecikme varsayımlı pilot hücreleri](sonuclar/capraz_kesif/cells.csv) · [keşif adayları](sonuclar/capraz_kesif/selected.csv) · [kapsam](sonuclar/capraz_kesif/summary.json)
- [174 arşiv hissesiyle XU100 + Brent özel pilotu](XU100_BRENT_PILOT_NOTU.md) · [tüm hisse sonuçları](XU100_BRENT_PILOT_HISSELER.csv). Bu eski/geniş pilot, yukarıdaki 48 hisse pilotuyla karıştırılmamalıdır. Yeniden üretim: `python scripts/xu100_brent_pilotu.py`.
- [Ham 12 seri ve kaynak manifesti](../../capraz_piyasa_data/manifest.json) · [Termux veri çekme kılavuzu](../kurulum/TERMUX_CAPRAZ_PIYASA.md).

## Kaçırılan hareketler, DM ve diğer araştırmalar

- [Yükseliş/düşüş ayrı: gerçek Replay pilotu, alternatifler ve sistem şeması](KACIRILAN_HAREKETLER_PILOTU.md) · [özet](sonuclar/kacirilan_pilot/summary.csv) · [pencereler](sonuclar/kacirilan_pilot/windows.csv) · [kaynak özeti](sonuclar/kacirilan_pilot/metadata.json).
- [Telegram DM eğitim modu, davranış ve sınırlamalar](../tasarim/TELEGRAM_DM_REPLAY_EGITIM_MODU.md).
- [Kod/Supabase denetimi ve Replay önerileri](DENETIM_VE_REPLAY_ONERILERI_2026-10-29.md).
- [DZ Replay: 177 sembol × 4 zaman dilimi](DZ_REPLAY_SONUCLARI_2026-10-28.md) · [S01–S32 soru seti](REPLAY_SORU_SETI_2026-10-29.md) · [yanıtları](REPLAY_SORU_YANITLARI_2026-10-29.md).
- [Diğer araştırmaların dizini](README.md).
