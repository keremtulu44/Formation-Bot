# Stabil hangi replay sistemini kullandı?

**Güncelleme:** 2026-11-01 · [Ana rehber](STABIL_REHBERI.md).

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

## 3. Stabil'e uyarlanan yaklaşım — önceki oturum kaydı

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

### Önceki modül adları ve işleri

Bu dosyalar **bugün mevcut değildir**; aşağıdaki adlar kurtarma envanteridir,
çalıştırılabilir bağlantı/komut değildir:

| Önceki modül | Raporlanan görev |
|---|---|
| `research/stabil_replay.py` | `native_history`, `measure_symbol`, ileri fiyat ölçümü |
| `research/stabil_sorular.py` | 27 STB soru/referans grubu; eski S01–S32'den ayrı |
| `research/stabil_kosu.py` | Timeout'lu worker, atomik sembol dizini, resume, toplu sonuç |
| `research/stabil_olay_duzelt.py` | Kaydedilmiş event sequence'den olay eşlemesini yeniden çıkarma |
| `research/stabil_davranis.py` | 48 davranış başlığı için çapa/özellik/yarış sonuçları |
| `research/stabil_davranis_finalize.py` | Native motoru çağırmadan son özellik/sansür türetimi |
| `research/stabil_davranis_paket.py` | Native + fiyat + soru indeksi paketi; referanstan geri kurma |

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

Yalnız `/home/user/...` veya ignore edilmiş geçici dizinin varlığı, gelecekte
kalıcılık kanıtı değildir. Önceki paket bu checkout'ta bulunamadı. Gerçek
kalıcı dosya/uygun harici arşiv doğrulanmadan “yeniden koşmaya gerek kalmaz”
garantisi verilmemeli. Bu belgeleme turunda yeni koşu veya veri üretimi yapılmadı.
