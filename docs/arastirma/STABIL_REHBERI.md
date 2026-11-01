# Stabil — kaynak, entegrasyon ve replay ana rehberi

**Güncelleme:** 2026-11-01 · **Durum:** Yürürlükteki belge haritası ve kurtarma kaydı.

> **Önemli durum ayrımı:** Önceki konuşmada Stabil entegrasyonu ve iki araştırma
> koşusu tamamlanmış olarak raporlandı. Bu güncellemede açılan çalışma alanında
> o kodlar, sonuç dosyaları ve native veri paketi **bulunamadı**. Git reflog ve
> erişilebilir nesnelerden de kurtarılamadı. Bu rehber geçmişte raporlananı,
> bugün bulunanı ve eksik olanı birbirine karıştırmaz. Dosyası olmayan sonuç
> yeniden doğrulanmış sayılmaz; olmayan dosyaya tıklanabilir bağlantı verilmez.

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

**Bu entegrasyon dosyaları şu an yoktur.** Buradaki anlatım runtime özelliğinin
şu checkout'ta çalıştığı veya deploy edildiği iddiası değildir. Kurtarma ve
regresyon olmadan canlı kullanıma hazır diye işaretlenmemeli.

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

Mevcut kayıtta canlı doğrulama/deploy kanıtı yok. Bu belgeleme turunda replay,
Telegram gönderimi, Supabase işlemi veya alarm/kart kodu değişikliği yapılmadı.

## Devir teslim kontrol listesi

1. [Envanterdeki](STABIL_DOSYA_ENVANTERI.md) eksik kod/veriyi gerçek dosyadan kurtar.
2. Özgün TXT hashini ve observer-normalize kaynak eşitliğini denetle.
3. Native prefix eşitliği ve gelecekteki fiyat mutasyonu testlerini çalıştır.
4. Gerçek kapanış, sol/sağ sansür, olay sequence görünürlüğü ve bilinmeyen yaşları doğrula.
5. Sonuç/native/fiyat/soru indekslerini paketle; MANIFEST ve geri kurma testi yap.
6. Kod ve veri gerçekten mevcut olduktan sonra durumları güncelle. Sırf geçmiş
   konuşmadaki sayı var diye “doğrulandı” etiketini yükseltme.
7. Yeni bir domain eklendiğinde de aynı sözleşmeyi uygula: bağımsız native
   kaynak, salt-okunur tüketiciler, ayrı araştırma ve ayrı canlı yayın kararı.
