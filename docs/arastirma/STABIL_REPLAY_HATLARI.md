# Stabil hangi replay sistemini kullandı?

**Güncelleme:** 2026-11-04 · [Ana rehber](STABIL_REHBERI.md) · [güncel sonuç dizini](SON_REPLAY_SONUCLARI.md).

## 1. Bugün depoda bulunan genel araştırma altyapısı

| Katman | Gerçek dosya | Görev |
|---|---|---|
| Arşiv | [research/arsiv.py](../../research/arsiv.py) | CSV.gz okur; native günlük ve seansa hizalı 1H→2H/4H çerçeveleri |
| Native bölge replay | [directional_zone_replay.py](../../directional_zone_replay.py) | OB/FVG motorlarını sırayla update eder; bölgeleri/temasları nedensel toplar |
| DZ koşucu | [run_directional_zone_replay.py](../../run_directional_zone_replay.py) | Yerel cache üzerinde çevrimdışı OB/FVG koşusu |
| Ortak fiyat ölçümü | [research/olcum.py](../../research/olcum.py) | ATR yolları, sabit ufuklar/eşikler, tepki şekli ve sansür |
| Gözlem/rapor | [research/kayit.py](../../research/kayit.py), [research/rapor.py](../../research/rapor.py) | Native çıktıyı gözlem ve rapora çevirir |
| Genel koşu | [arastirma_kosu.py](../../scripts/backfill/arastirma_kosu.py) | Sembol bazında JSONL, hata izolasyonu, tamamlanan işi atlama |
| Ayrı cevaplayıcı | [research/soru_cevaplama.py](../../research/soru_cevaplama.py) | Mevcut gözlemlerden S01–S32 cevaplarını üretir; her soruda motoru tekrar çalıştırmaz |
| Eski yayın denetimi | [research/soru_kapisi.py](../../research/soru_kapisi.py) | Eski soruların baseline/kapı denetimi; Stabil için otomatik yetki değildir |
| Stabil native history + 100-sembol replay | [research/stabil_replay.py](../../research/stabil_replay.py) | Tek geçişli causal Stabil geçmişi; tamamlanmış H4 checkpoint ve ileri ölçüm tabloları |
| 48 soru cevaplayıcı | [research/stabil_bhv48.py](../../research/stabil_bhv48.py) | Var olan checkpoint/olay çerçevelerinden 48 tanımlı sorunun aggregate tablolarını üretir |
| Ayrı canlı-evren testi | [research/stabil_live_systematic.py](../../research/stabil_live_systematic.py) | `config.BIST_50` içindeki arşivde bulunan non-macro sembollerin ayrı 4h systematic ölçümü |
| 48-soru aggregate çıktıları | [stabil_100_sonuclar/](stabil_100_sonuclar/) | Manifest + JSON/CSV/Markdown mevcut; tam native checkpoint arşivi bu dizinde yok |
| Ayrı 50/53 systematic sonuç | [stabil_live_systematic_results.json](stabil_live_systematic_results.json) | 50/53 arşiv-kapsama sonucu; 100 sembol/48 soru çalışmasına eklenmez |

Yöntem kaynağı: [ARASTIRMA_HATTI.md](ARASTIRMA_HATTI.md).
Depodaki arşivde bu güncellemede **177 adet 1H ve 177 adet 1D dosyası** sayıldı.
Eski ~60 dakika / 176×4 seri ifadesi bu genel hattın tarihsel belge kaydıdır;
Stabil'e veya bugünkü makineye süre garantisi değildir.

## 2. Birbirinden farklı replay türleri

- **OB/FVG/DZ:** yukarıdaki bölge update motoru; doğrudan Stabil çalıştırmaz.
- **Genel araştırma:** gözlem üretimi → ayrı cevaplama → eski yayın kapısı.
- **Kırılım/teyit araştırması:** farklı formasyon olayları/aday/teyit çapaları;
  [sonuç dizinindeki](SON_REPLAY_SONUCLARI.md) ayrı evren.
- **Telegram replay eğitimi:** kullanıcı soru/cevap oturumu; ölçüm koşusuyla aynı
  şey değil. Eğitim tasarımı [ilgili belgede](../tasarim/TELEGRAM_DM_REPLAY_EGITIM_MODU.md).
- **Stabil:** aşağıda tarif edilen ayrı native geçmiş tüketicisi; genel hattın
  arşiv/ölçüm/cevaplama ilkelerini yeniden kullanması raporlandı.

## 3. Stabil yaklaşımı — güncel uygulama ve tarihsel performans kaydı

Mevcut checkout'ta `research/stabil_replay.py` doğrudan `domain_engines.stabil`
üzerindeki `build_single_pass_history` yolunu kullanır; bir sembolde history bir
kez oluşturulur, her tamamlanmış H4 kapanışında günlük/haftalık bilinirlik sınırı
uygulanır, destek olayları first-seen sequence ile izlenir ve ileri ufuklar açık
sağ-sansürle ölçülür. `research/stabil_bhv48.py` bu çerçeveleri ayrı cevaplayıcıda
48 soruya döker; 50/53 systematic çalışması ise `research/stabil_live_systematic.py`
ile farklı sembol evreninde üretilmiştir.

İlk denemede her 4H kapanışında kaynak motor bütün prefix üzerinde tekrar
çalıştırılmıştı: `1 → 2 → … → 1079` mum, yaklaşık 582 bin kümülatif işlem.
Bu nedenle 803 saniye/simge ve 22 saat/100 tahmini çıkmıştı. **Bu tahmin
Stabil'in doğal maliyeti değil, terk edilen verimsiz uygulamaya aittir.**

Düzeltmede şu yapı raporlandı:

1. Daily ve H4 native loop'larından isteğe bağlı observer ile geçmiş
   snapshot'ları tek geçişte almak; formüllere dokunmamak.
2. Haftalık native sonucu tamamlanmış hafta başına bir kez hesaplamak.
3. Günlük ham duruma, o checkpoint'te bilinen haftalık bağlamı native saf
   eşlemeyle uygulamak. Bağlam ham günlük hesaplara geri beslenmemeli.
4. Destek lifecycle'ını günlük prefix başına önbelleklemek; tüm olayları korumak.
5. Her 4H kapanışına sadece gerçek kapanışı geçmiş rol verisini projekte etmek.
6. Ortak fiyat ölçümünü bir kez üretip soruları ayrı tüketicide cevaplamak.

### Mevcut çıktı kanıtı ve tarihsel eksiklerin ayrımı

| Mevcut yol | Checkout'taki rol / kanıt |
|---|---|
| `domain_engines/stabil/` + `domain_engines/runner.py` | Native runtime; `run_stabil_domain` ayrı sonuç döndürür |
| `research/stabil_replay.py` | Güncel tek-geçişli replay/data-frame üreticisi; tam 100-sembol koşunun native checkpoint paketi değildir |
| `research/stabil_bhv48.py` | 48 soru için aggregate cevaplayıcı |
| `docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_MANIFEST.json` | 2026-11-01 manifest; 100 sembol, 107.441 H4 checkpoint, 10.417 ilk-görülen destek olayı, 48 soru, 642 sonuç satırı; `user_confirmed_regime=false` |
| `STABIL_DAVRANIS_48_SONUCLAR.json`, `STABIL_DAVRANIS_48_TABLO.csv`, `STABIL_DAVRANIS_48_YANITLARI.md` | Aggregate JSON/CSV/Markdown cevapları mevcut; tam native checkpoint/fiyat paketi değil |
| `research/stabil_live_systematic.py` + `stabil_live_systematic_results.json` | Ayrı 50/53 canlı non-macro sembol systematic popülasyonu |

Önceki 100-sembol/27-soru hat için konuşmada adı geçen
`research/stabil_sorular.py`, `stabil_kosu.py` ve `stabil_olay_duzelt.py` gibi
araçlar bu checkout'ta bulunmuyor. Bunları mevcut 48-soru cevaplayıcısıyla veya
50/53 systematic koşusuyla aynı çalışma gibi göstermeyin. Eski 80 MB native
checkpoint paketi ve özgün 27-soru tabloları da hâlâ mevcut değil.

**Sayım uyuşmazlığı:** önceki konuşma kaydı 107.446 checkpoint ve 4.074 satır
aktarırken mevcut 48-soru manifesti 107.441 checkpoint ve 642 satır kaydediyor.
Bunlar sürüm/çıktı olarak ayrıdır; oranlar, satırlar veya çalışma süreleri
birleştirilmemiştir. Manifest kaynak hashlerini ve kesin veri kesim zamanını
içermediğinden tam yeniden üretilebilirlik iddiası yoktur.

## 4. Ölçüm/cevap sözleşmesi

- Ufuklar: 1/4/8/10/12/16 **4H mum**. Takvim saati veya doğrudan işlem süresi değil.
- Ortak eski hatla uyumlu eşikler: 0,25/0,5/1/1,5/2 ATR; başlangıçta bilinen
  günlük ATR sabit. Başlangıç fiyatı olayın bilinebildiği checkpoint kapanışı.
- Olay mumunun kendi high/low'u geleceğe dahil değil.
- Kapanış getirisi gerçek close; high/low yolunun son değeri close diye sunulmaz.
- Aynı mumda çift eşik/çift yarış sonucu belirsizdir. Sağ sansür başarı değildir.
- Sol sansürlü ilk yatay yaş/temas sırası/altta kalma epizodu UNKNOWN kalır.
- Seviye yaşı, pivot köken yaşı ve teyit yaşı birbirinin yerine geçmez.
- Native lifecycle'ın source-label `available_at` alanını sertifikalı kapanış
  sanmak hata verir. Olay geçmişine yeni sequence'nin ilk girdiği checkpoint
  nedensel tüketim sınırıdır; ilk checkpoint'in eski olayları yeni sayılmaz.
- Duruma giriş örneğiyle her kapanış referansı aynı n birimi değildir.
- Proxy, örnek sayısı etiketi ve nedensel/istatistiksel doğrulama ayrı kavramlar.
- Mevcut 100 semboldeki sonuç görülmüşse aynı evren kör test ilan edilemez.

## 5. Kalıcılık ve yeniden üretim şartı

Kurtarılacak paket şu öğeleri taşımalı:

- Plan: tam sembol listesi, seçim kuralı, kod/ayar hashleri ve çalışma sürümü.
- Birebir 1H/1D kaynakları, gerçekten kullanılan kapanış sertifikalı 4H seri.
- Her checkpoint'in tam W/D/H4 ve destek çıktıları, referans fiyatı/ATR'si.
- Tekilleştirilmiş olay tablosu + snapshot'ın prefix uzunluğu (kayıpsız).
- Soru indeksi + native checkpoint'ten okunabilen outcomes; tekrar veriyi
  silmek değil, aynı veriyi referansla saklamak.
- Bütün cevaplar, n/sansür, sembol/yıl kırılımları, sapma/sınır notları.
- MANIFEST SHA256, tüm üye kontrolü ve motor çağırmadan gerçek geri kurma testi.

Aggregate 48-soru tablolarının mevcut olması, önceki yaklaşık 80 MB'lık tam native
checkpoint/fiyat paketinin mevcut olduğu anlamına gelmez. Manifest kaynak SHA256
ve kesin veri sonunu da taşımadığından mevcut dosyalar descriptively readable,
fakat eksiksiz byte-for-byte rerun archive değildir. “Yeniden koşmaya gerek
kalmaz” garantisi verilmemeli.

2026-11-04 doğrulamasında bir sembol ASTOR için replay/48-soru spot-check
(48 soru, 552 satır) ve tarihsel 4h domain-context örneği üretildi; 100-sembol
koşu tekrar çalıştırılmadı, paket veya canlı kalıcılık eklenmedi. Bu spot-check
manifestteki eski çalışma sayımlarıyla aynı run değildir.
