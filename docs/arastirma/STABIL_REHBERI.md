# Stabil — kaynak, entegrasyon ve replay ana rehberi

**Güncelleme:** 2026-11-04 · **Durum:** Belge haritası, tarihli kurtarma kaydı, replay çıktısı ve mevcut checkout doğrulaması.

> **Önemli durum ayrımı:** 2026-11-01 tarihli kurtarma kaydı, o gün açılan çalışma
> alanında bazı entegrasyon dosyalarının ve sonuçların bulunmadığını söylüyordu.
> Bu, yalnız o tarihli snapshot'ın bulgusudur; bugünkü branch için geçerli bir
> yokluk iddiası değildir. 2026-11-04 tarihli mevcut checkout'ta Stabil kaynak/
> runtime, runner, replay kodu, aggregate sonuçlar, gerçek arşiv ve testler vardır.
> Kodun bulunması önceki 48 araştırma sonucunu ya da canlı deploy'u kendiliğinden
> doğrulamaz; bu iki iddia ayrı kanıt ister.

## 2026-11-04 mevcut checkout doğrulaması

- Native kaynak `domain_engines/05_stabil.txt`; uygulama `domain_engines/stabil/` altında. `domain_engines/runner.py::run_stabil_domain` ayrı Stabil sonucu döndürür ve `as_of_close`/`isolated` seçeneklerini destekler.
- Arşiv erişimi `research/arsiv.py::tf_frame` ile sağlanır. `test_stabil_domain_and_integration.py` gerçek ASTOR arşivinde kaynakla parity, prefix-kesit eşitliği, haftalık kapanış nedenselliği, rol hazırlığı ve grafik/Telegram tüketimini sınayan testler içerir.
- `scripts/diagnostics/stabil_api_poc.py` yeni bir public entegrasyon değildir: loopback-only, ASTOR-arşivli, salt-okunur HTTP PoC'dir. `test_api_readonly_contract_poc.py` gerçek HTTP isteğiyle `as_of`, timezone, auth, hatalı parametreler ve gelecekteki OHLCV mutasyonuna karşı look-ahead davranışını doğrular.
- 48-soru aggregate çıktıları `stabil_100_sonuclar/` altında mevcuttur. 2026-11-01 manifesti: 100 sembol, 107.441 H4 checkpoint, 10.417 ilk-görülen destek olayı, 48 soru, 642 satır; `user_confirmed_regime=false`. Tam native checkpoint paketi, kaynak hashleri ve kesin veri kesim zamanı yoktur.
- `stabil_live_systematic_results.json` ayrı 50/53 non-macro canlı-universe çalışmasıdır; 100-sembol davranış replay'iyle birleştirilmez.
- Bu kanıtlar runtime/kod ve mevcut aggregate dosyaları gösterir; eski konuşma sayılarını, her geçmiş ölçümün üretimini, canlı veri kalitesini veya production deploy'u doğrulamaz. Önceki 107.446 checkpoint / 4.074 satır konuşma sayımı ile mevcut manifest farklıdır.
- Bu oturumun salt-okunur [alarm/istek context planı](ALARM_CONTEXT_API_PLANI.md) ve [ASTOR tarihsel örneği](samples/ALARM_CONTEXT_ASTOR_2026-10-16.md) ayrı prototiptir; canlı alarm davranışını değiştirmez.

## Nereden başlamalı?

| Amaç | Belge |
|---|---|
| Stabil'in özgün matematik kaynağı | [05_stabil.txt](../../domain_engines/05_stabil.txt) · [kaynak/entegrasyon notu](../../domain_engines/STABIL_KAYNAK_NOTU.md) |
| Hangi replay sistemi, hangi iş için kullanıldı? | [Replay hatları ve yeniden kullanım sözleşmesi](STABIL_REPLAY_HATLARI.md) |
| Fiyat ile çizgi ilişkisi hakkında kullanıcının gözlemi | [Davranış modeli](STABIL_DAVRANIS_MODELI.md) |
| Bu gözlemi sınayacak ayrıntılı sorular | [48 soruluk sicil](STABIL_DAVRANIS_SORULARI.md) |
| Hangi koşu yapıldığı söylendi, ne sonuç raporlandı? | [Çalışma geçmişi ve sonuç kayıtları](STABIL_CALISMA_GECMISI.md) |
| Hangi dosya var, hangisi kurtarılmalı? | [Dosya/kanıt envanteri](STABIL_DOSYA_ENVANTERI.md) |
| Projenin genel araştırmaları | [Araştırma dizini](README.md) · [tüm replay sonuç dizini](SON_REPLAY_SONUCLARI.md) |
| Projeye/belge haritasına dönüş | [Proje README](../../README.md) · [belge README](../README.md) |

## Stabil'in rolü

Stabil bir web domain'i değil, OB/FVG gibi **analitik domain** olarak tasarlandı.
Özgün TXT iki bağımsız native bileşen içeriyor:

1. **Trend bağlamı:** haftalık yapı, günlük durum, 4H toparlanma ve kanıt yaşı.
2. **Günlük destek yaşam döngüsü:** destek/floor, test, tutunma, kayıp,
   geri alım, yukarı/aşağı yeniden seviyelenme, mesafe ve süreler.

Trend ile destek hazır oluşu ayrı tutulmalı. Destek üstünde bulunmak,
yükseliş trendi veya alım sinyaliyle eşitlenmemeli. TXT sözleşmelerindeki
nihai resolver/health/risk iddiaları, kaynakta uygulanmış kabul edilmemeli.
Python TXT matematik kaynağıdır; Pine yalnız görsel referans olarak istendi.

## Önceki entegrasyon kapsamı — konuşma kaydı, mevcut kod doğrulaması değil

- Native çıktıların eksiksiz korunması; tek çizgiye/tek skora indirgenmemesi.
- Sembol başına derin günlük ve 4H veri; tamamlanmış haftaların günlükten
  takvimle türetilmesi; tüm rollerde gerçek kapanış/bilinirlik sınırı.
- Normal/alarm/eğitim görsellerinde aynı günlük destek; 1s/2s/4s/1g üzerine
  nedensel projeksiyon, geçmiş native renkleri, stepline, etiket/yardımcı yok.
- Eğitimde soru anının kesiti; sonuç grafiğinde o katmanın dondurulması,
  gelecek/live registry'den yeniden hesaplamama.
- Kartın YAPI bölümünde tek bilgi satırı: “Stabil: destek üstünde/altında”;
  eşitlikte “destekte”; veri yoksa satır yok. Fiyat alarm kapanışı, destek
  o anda bilinen günlük seviye. Seviye/olasılık/puan eklenmediği raporlandı.
- Alarm filtresi, birleşik skor, teslim/tekrar kuralı veya araştırmanın
  canlı veritabanına biriktirilmesi kapsam dışıydı.

Yukarıdaki maddeler **önceki oturumda raporlanan kapsamın tarihsel kaydıdır**;
2026-11-01 snapshot'ında dosyalar bulunamadığı not edilmişti. 2026-11-04
checkout'unda runtime, replay kodu ve aggregate sonuçlar bulunduğu doğrulandı. Bu, canlı doğrulama
veya deploy kanıtı değildir; release kararı için ayrı regresyon, veri ve canlı
operasyon kontrolleri gerekir.

## Kullanılan araştırma yaklaşımı

Doğru zincir:

`yerel arşiv → tek geçişli native geçmiş → kapanışta bilinen checkpoint
→ fiyat ölçümleri → ayrı soru cevaplayıcı → doğrulama/sınırlar → rapor`

Her kapanışta bütün geçmişi baştan çalıştıran ilk yöntem terk edildiği
raporlandı. Mevcut genel araştırmanın arşiv, ölçüm ve raporlama sözleşmesi
kullanıldı; fakat OB/FVG'nin update motoru doğrudan Stabil motoru değildir.
Ayrıntılar [replay hatları](STABIL_REPLAY_HATLARI.md) dosyasında.

## Sonuçların yorumu ve yayın durumu

Önceki 48 başlığın raporlanan dağılımı **33 operasyonel ölçüm / 8 proxy /
7 açık tanım-veri-doğrulama ihtiyacı** idi. Bu, 48 sorunun bütünüyle çözüldüğü
anlamına gelmez. Özellikle görsel dikey→yatay ayrımı kesin native rejim gibi
ilan edilmemeli. Genel eski S01–S32 yayın kapısı Stabil'e aktarılmaz.

Mevcut kayıtta canlı doğrulama/deploy kanıtı yok. 2026-11-04 turunda yerel
ASTOR arşiviyle Stabil runner ve HTTP `as_of` kontratı sınandı; canlı veri,
Telegram gönderimi, Supabase işlemi veya alarm/kart kodu değişikliği yapılmadı.

## Devir teslim kontrol listesi

1. [Envanterdeki](STABIL_DOSYA_ENVANTERI.md) tarihsel eksik **araştırma artefaktlarını** güncel checkout'ta ayrıca kontrol et; var olan runtime'ı yeniden kurtarma işi gibi ele alma.
2. Özgün TXT hashini ve kaynak/runtime parity testini denetle.
3. Native prefix eşitliği ve gelecek-mum mutasyonu testlerini çalıştır; API kontratı için `test_api_readonly_contract_poc.py` yalnız yerel ASTOR kanıtıdır.
4. Gerçek kapanış, sol/sağ sansür, olay sequence görünürlüğü ve bilinmeyen yaşları doğrula.
5. Tarihsel sonuç/native/fiyat/soru indekslerini kurtarırsan paketle; MANIFEST ve geri kurma testi yap.
6. Kod ve veri gerçekten mevcut olduktan sonra durumları güncelle. Sırf geçmiş
   konuşmadaki sayı var diye “doğrulandı” etiketini yükseltme.
7. Yeni bir domain eklendiğinde de aynı sözleşmeyi uygula: bağımsız native
   kaynak, salt-okunur tüketiciler, ayrı araştırma ve ayrı canlı yayın kararı.
