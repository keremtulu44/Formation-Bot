# Genel İnceleme ve Yol Haritası — 16 Ekim 2026

> **Kapsam:** Kod tabanının uçtan uca okunması (`main.py`, `notifier.py`, `grafik.py`,
> `data.py`, `patterns/`, `domain_engines/`, `state/`, `karne.py`, `telegram_commands.py`,
> `health_server.py`, CI/deploy zinciri) + ürün kararı belgeleri. İnceleme anı:
> `42a19c4` (dal `arena/92cb4b08-formation-bot`). Bu belge **kişisel görüş ve öneri**
> içerir; hiçbir kod bu belge yüzünden değişmez.
>
> **Biçim:** önce güçlü/yetersiz bulduklarım (gerekçeli), sonra **neler eklenebilir**
> (ürün + teknik), en sonda **neler yapılabilir** (önceliklendirilmiş iş listesi).

---

## 0. Kısa özet (5 madde)

1. Proje, "hobicem bot yazdım" seviyesinden **ürün disiplini** seviyesine geçmiş durumda:
   tek kaynak kapanış kuralı, fail-closed takvim, dayanıklı teslim kuyruğu, güven şeridi,
   1300+ regresyon testi ve Render-parite CI. Bu birikimin Türkiye'deki Telegram sinyal
   botları arasında ayırt edici olduğunu düşünüyorum.
2. En büyük teknik borç **dosya boyutları**: `grafik.py` 4.641, `main.py` 4.343,
   `notifier.py` 3.293 satır. Şimdilik yönetilebilir; ama her yeni özellik bu üç dosyanın
   "ağırlık merkezini" artırıyor. Bölünme, kod yazmayı değil **kod okumayı** kolaylaştıracak
   en yüksek getirili iş.
3. Veri tarafı **tek sağlayıcıya** (Yahoo) bağlı ve bu bağımlılık kodda soyutlanmamış.
   Pacing kültürü mükemmel; ama sağlayıcı политika değiştirirse (rate-limit, sembol adı,
   veri şeması) tek noktadan çöküş var. Sağlayıcı arayüzü + ikinci kaynak, ürünün
   "çalışıyor" müjdesinin sigortasıdır.
4. Doğruluk tarafı iyi durumda ama **ileri adım** eksik: karne ATR-bazlı ilk dokunuş
   yarışıyla ölçüyor (doğru tercih); buna yürüyen pencere (walk-forward) kararlılığı ve
   güven aralığı eklenmeden "profilim hassas, daha iyi" cümlesi istatistiksel olarak
   savunulamaz. Kanala yayınlanabilir **şeffaflık karnesi** bu projenin en güçlü pazarlama
   aracı olur.
5. Kullanıcı gözünde bot hâlâ **"bana haber veren"**; asıl sıçrama **"bana yol gösteren"**
   olmasında: izleme listesi, hedef ilerleme takibi, çoklu TF uzlaşısı ve haftalık özet
   yayını. Hepsi mevcut altyapının (state, karne, grafik zinciri) üzerine eklenir — yeni
   motor gerekmez.

---

## 1. Güçlü bulduklarım (kanıtlarla)

### 1.1 "Uydurma yok" ilkesi gerçekten uygulanıyor
Bu repoda en değerli şey desen algoritması değil, **dürüstlük disiplini**:
- Grafik katmanı motoru yeniden çalıştırmıyor (§14.2); verisi olmayan katman çizilmiyor ve
  dipnot **yalnız veri sorununda** yazılıyor (§0.12w).
- `/grafik` komutu formasyon bulamazsa uydurmuyor; "tarama: … formasyon yok" uyarısıyla
  çiziyor. `grafik_uret.py --demo` sentetik veriyi `bot_data/` içine yazmayı **reddediyor**
  (canlı taramayı zehirlemesin diye, §22 sapma kaydıyla).
- Güven şeridi (`chart-trust-focus-v3`) "demo · sentetik", "RVOL: yerel hesap", "2/4 bölge ·
  2 gizli" gibi **kendi eksikini itiraf eden** etiketler taşıyor. Sinyal satan ekosistemde
  bu, kullanıcı güvenini kuran asıl özellik.

### 1.2 Tek kaynak doğruluk zinciri
Kapanış kuralı (`mum_kapanis_anlari`) tek yerde; tarama, bildirim, grafik ve testler aynı
fonksiyonu çağırıyor. Tatil/yarım gün `exchange-calendars` XIST takviminden geliyor ve
**bilinmeyen tarih fail-closed**. "Kapanmamış bar bildirime kaynak olamaz" kuralının
`bar_kapandi_mi` güvenlik kapısıyla çift katmanlı olması, canlıda en pahalı hata türünü
(kısmi bar sinyali) baştan eliyor.

### 1.3 Teslim katmanı üretim kalitesinde
Kalıcı kuyruk + restart sonrası devam, kısmi teslimin yeniden denenmesi, metin+albüm
sıralı teslim, MTF birleştirme penceresi (4 saat), geçersizleşme için 3 ardışık kapanmış
bar onayı… Bunlar "bildirim gönderen script" değil, **dağıtık sistem disiplini**. 16 Ekim
notlarındaki uygulama listesi bunların bilinçli kararlarla geldiğini gösteriyor.

### 1.4 Test kültürü ve CI paritesi
- ~1.277 test fonksiyonu; `pytest.ini` + `conftest.py` veri izolasyonu (testler kalıcı
  DATA_DIR'i kirletmiyor) — bu detay çoğu projede atlanır.
- CI, Render'ın Build Command'ını ve `.python-version`'ı birebir takip ediyor; "Render'da
  patlayan build'i CI'da yakala" fikri (cp314 tekerlek tuzağı) deneyimden süzülmüş.
- Determinizm piksel hash'ine değil `girdi_ozeti`/meta'ya bağlanıyor (§12.19) — doğru
  karar: piksel hash'i ortam kırılganlığı üretir.

### 1.5 Ölçüm kültürü
Karne ATR-bazlı hedef/stop yarışı, aynı barda ikisi de olursa **muhafazakâr** sayma,
`n<30` uyarısı, huni görünürlüğü, `/panel`'de dolu slot oranı… "Bot ne üretti, neydi
sonucu" sorusunun cevabı repoda duruyor. FAZ3 backtest analizi de parametre tartışmasını
veriye oturtmuş.

---

## 2. Riskler ve eleştiriler (kişisel görüş)

Buradan sonrası kusursuzluk iddiası değil; hangi sırayla düzeltilirse en çok getiri
vereceğine dair **benim** okumam.

### 2.1 Üç dev dosya, her yeni özelliğin ağırlık merkezi
`grafik.py` 4.641 satır (çizim + zone havuzu + yapı verisi + ölçüm + politika tek dosyada),
`main.py` 4.343 (döngü + komutlar + heartbeat + sayaçlar), `notifier.py` 3.293 (mesaj
şablonları + kotalar + teslim). Bu bölümünmeli yapısı şunu doğuruyor:
- Yeni katman eklemek "nereye dokunsam başka şey bozulur" hissi veriyor; incelemesi
  uzun sürüyor.
- Aynı dosyada çalışan iki dal (ör. bir görsel düzeltmesi + bir teslim düzeltmesi) merge
  çatışması üretiyor.
- Testler davranışı koruyor (iyi) ama **okunabilirlik testi yok** — 6 ay sonra tek kişi
  (sen) bu dosyaların tamamını kafada tutmak zorunda kalıyorsun.

Repodaki C2 maddesi bunu zaten biliyor; benim ek görüşüm: **büyük yeniden düzenleme
yapma**. Bunun yerine "her dokunduğun konuyu kendi modülüne taşı" kuralıyla sınırlı,
artımlı bölme (bkz. §5 Y1–Y3) daha güvenli. Mevcut test ağının yoğunluğu tam da bu
noktada refactoring sigortası.

### 2.2 Tek veri sağlayıcı, soyutlama yok
`data.py` Yahoo'ya özgü davranışlarla dolu (`.IS` eki, pacing, cache kuralları) ve bu
sabitler motor koduna serpiştirilmiş (C1 maddesi de bunu söylüyor). Risk tablosu:
| Tetik | Etki |
|---|---|
| Yahoo rate-limit politikası sıkışırsa | 48 sembol × 4 TF tarama temposu düşer, gün içinde veri eksiği büyür |
| Sembol adlandırma değişirse | sessiz veri kaybı (KOZAL/KOZAA precedansı var) |
| Şema değişirse (kolon adı) | açılışta patlar (iyi ki patlıyor — sessiz değil) |

Görüşüm: ikinci kaynak eklemek **önce** görünürlük, sonra yedek işi. En azından
`veri_kalitesi_gunlugu` (sembol başına son başarılı fetch, yaş, satır sayısı) tek yerden
raporlanmalı; `/durum` bunun özetini görmeli.

### 2.3 Karne güçlü ama "istatistiksel özgüven" katmanı yok
`/karne 30` ile `/karne 7` arasındaki fark yalnız örneklem büyüklüğü; ama kullanıcı
"geçen hafta %70 tuttu" mesajından "bu sistem tutarlı mı" sonucunu çıkarıyor. Aynı
karnenin **aynı periyotta farklı zaman dilimlerinden** alınmış kesitleri (ör. son 90 günün
kaydıran 30 günlük pencereleri) arasındaki dalgalanma gösterilmedikçe, 30 günlük tek
sayı yanıltıcı olabilir. Buna küçük bir "stabilite" satırı eklemek (min–medyan–max)
karneyi hem daha dürüst hem daha satılır yapar.

### 2.4 Dokümantasyon hacmi kendi kendini eskitiyor
Kök dizinde 25+ denetim/plan belgesi var; içerik kalitesi yüksek ama **giriş noktası
dağınık**. Yeni bir okuyucu (ya da 6 ay sonraki sen) hangi belgenin güncel olduğunu
dosya adından çıkaramıyor (`*_2026-10-15`, `*_2026-10-16` tarihli olanlar tabii ki
güncel, peki ya geri kalanlar?). README zaten uzun. Görüşüm: kökte yalnız 3 belge kalsın
(README, YOL_HARİTASI, RUNBOOK); geri kalan `docs/` altına tarih etiketiyle taşınıp
README'ye tek tabloluk "belge haritası" eklensin. Bu, mevcut `docs/archive` adımının
tamamlanmış hâli.

### 2.5 Lint/statik analiz yok
CI'da pytest var; `ruff`/`mypy`/`pyproject.toml` yok. Test kültürü davranışı koruyor ama
**kalıp hatalarını** (kullanılmayan import, ölü dal, tip tutarsızlığı) yakalayan bir
katman yok. `ruff` tek başına (kurulum 1 satır, CI'da ~10 sn) bu boşluğun %80'ini kapatır
ve dev dosyalarda "bu fonksiyon kimse çağırmıyor" türü bulguları bedavaya listeler.

### 2.6 Tek sohbet kilidi bilinçli bir sınır — ama belgelenmeli
Komutlar tek `TELEGRAM_CHAT_ID`'den kabul ediliyor; public kanal yalnız yayın alıyor.
Bu, kişisel bot için doğru tasarım. Ancak "bir gün abonelikli çalışsın" fikri varsa,
yetki modeli (`chat_id` → rol) ileride en çok dokunulacak yer olacak; şimdiden
`telegram_commands.py` içinde tek bir `yetki()` fonksiyonuna toplamak ileriyi ucuzlatır.

### 2.7 Küçük ama can sıkıcı: ölçüm kalıntıları
Ölçüm günlüklerinde tarama başına ~4 MB yazım bildirilmişti (B5). Buna ek olarak bazı
hesaplanıp kullanılmayan ifadeler tarihsel olarak raporlanmış (A3-d). Bu tür kalıntılar
ünretimi etkilemez ama **okuma hızını** düşürür; ruff + bir günlük temizliği turu bunları
ayıklar.

---

## 3. Neler eklenebilir — ürün tarafı

Buradaki her öneri mevcut mimariye **eklenen**, onu bozmayan işler olarak seçildi.

### P1 — İzleme listesi (`/izle THYAO`, `/izleme`)
Kullanıcı kendi listesindeki semboller için (a) formasyon durum değişikliklerinde öncelikli
haber, (b) günlük özette ayrı bölüm. Şu an "48 sembolün hepsi aynı derecede önemli".
Gerçekte kullanıcı 5–10 sembol izler. Uygulama: `chat_id` başına liste +
`notification_context`'te tek filtre. Yetki modeli tek kişide kalır (yalnız kayıtlı DM).
**Getiri/yük oranı bu listedeki en yüksek özellik.**

### P2 — Hedef ilerleme takibi ("kırıldı, sonra ne oldu?")
`KIRILIM_TEYITLI` sonrası ölçülü hareket hedefi (formasyon yüksekliği / ATR katı) zaten
karnede hesaplanıyor ama **olay anında** kullanıcıya geri dönmüyor. Eklenecek:
- Hedefe %50/%100 yaklaştığında kısa mesaj ("🎯 THYAO 4s hedefe 0,4 ATR kaldı").
- Stop oldumuğunda tek satırlık kapanış mesajı ("🛑 hedefe ulaşmadan stop").
Defter (`karne_defteri`) bu olayları zaten biliyor; eksik olan yalnızca "ilerleme"
bildirim türü. Bu, karnenin **canlı** yüzü olur ve "bana yol gösteren bot" algısını kurar.

### P3 — Çoklu TF uzlaşı kartı
Aynı semboldün farklı TF'lerinde aynı yönde formasyon varsa tek kartta birleştirilmiş
görsel/skor ("THYAO: 1g teyitli ↑ · 4s aday ↑ · 2s nötr"). MTF birleştirme penceresi
(zaten var) olay **bastırmak** için; bu ise bilgiyi **yükseltmek** için. Uzlaşılı
sinyaller karnede ayrı satır olarak da izlenmeli — hipotez: uzlaşılı kırılımların
tutarlılığı daha yüksek. (Bu test edilebilir bir önermedir; karne verisi cevap verir.)

### P4 — Haftalık kanal yayını paketi
Cuma günü sonunda public kanala otomatik: (a) haftalık karne özeti (şeffaflık), (b)
haftanın en iyi 3 karesi **gerçek veriden** (`grafik_uret` zinciri — yeni örnek galeri
sisteminin ürettiği DEMO kareler değil!), (c) haftaya dair tek paragraf özet.
`kanal_acilis.py` + karne + grafik zinciri zaten var; eksik olan yalnızca haftalık
zamanlayıcı ve kanal karne biçimlendiricisi. Bu, kanalı canlı tutan en düşük eforlu
mekanizma.

### P5 — Yeni formasyon aileleri (uzun vadeli)
Mevcut aile: üçgen/kama/bayrak/flama (+ OB/FVG/yapı bağlamı). Doğal sıradakiler:
1. **İkili tepe/dip** — sık istenir, pivot altyapısı hazır.
2. **Omuz-baş-omuz** — yapı motoru (PH/PL) bunu zaten "görüyor" ama formasyon olarak
   ifade etmiyor.
3. **Kanal kırılımı** — trend kanalı sınırları `zone_scoring` ile ortak dil kullanabilir.
Her biri yeni bir `patterns/` katmanı + karne türü demek; **ayrı dalda, karneden
doğrulanarak** eklenmeli (yeni formasyonun kanıt yükü olmadan kanala girmesi güven
serefiyesini yakar).

### P6 — Sessiz saatler / öncelik katmanları
Öğle arası (12:00–13:00) ve mesai dışı (ör. 19:00–08:30) için kullanıcı tercihi: acil
olmayanlar ertesi pencereye, acil olaylar (teyit/geçersizleşme) her zaman. Kap/pacing
altyapısı zaten var; bu yalnızca bir zaman filtresi.

### P7 — Sembol sayfası (statik web arşivi)
`chart_report.py` zaten HTML ayrıntı yazıyor. Her gün kapanışta sembol başına tek HTML
(kare + bölge JSON'u + yapı zaman çizelgesi) üretip GitHub Pages'e koyan bir workflow,
bedava bir "geçmiş arşiv" sitesi verir: kanalda "ayrıntılar: site/thyao" linki → Telegram
4096 karakter sınırı problemi de çözülür. (Gizlilik: yalnız public veri, tek yönlu yayın.)

### P8 — Eğitim mikro-içerikleri
Her formasyon türü için bir kez gönderilen, kanala sabitlenen kısa açıklama kartı
("Simetrik üçgen nedir, bu bot neyi bildirir, neyi bildirmez"). `KANAL_ACILIS_PAKETI`
bunu zaten kapsıyor ama **kalıcı eğitim katmanı** değil. Yeni takipçiler için otomatik
"başlangıç seti" mesajı düşük eforlu, yüksek algısal getiri.

---

## 4. Neler eklenebilir — teknik tarafı

### T1 — Veri sağlayıcı arayüzü + kalite panosu
`data.py` içinde Yahoo'ya özgü her şey tek bir `Saglayici` sözleşmesinin arkasına
alınmalı: `sembol_kimligi()`, `cek()`, `hata_sınıflandır()`. Sonrasında ikinci kaynak
(ör. bir BIST API'si ya da tvdatafeed opsiyonel kanalı) **deneme amaçlı** bağlanabilir;
birincil kaynak kalır, ikincil yalnız tutarsızlık raporu üretir. Ayrıca
`/durum`'a veri kalitesi satırı: 48 semboldün kaçında bugün veri geldi, en eski cache yaşı
kaç. (B6/B8 maddelerinin görünür yüzü.)

### T2 — ruff + pyproject + CI'ya lint adımı
10 dakikalık iş: `pyproject.toml` (ruff config, E+W kuralları, satır uzunluğu mevcut
stile uygun 100), CI'ya `ruff check .` adımı. İlk koşuda çıkan bulguları tek commit'te
temizle. Daha sonra `ruff format --check` (opsiyonel; diff kültürünü bozmasın diye
başta kapalı).

### T3 — Yapısal olay günlüğü (structured event log)
Tarama döngüsü zaten sayıları logluyor; buna ek olarak makine-okunur **olay dosyası**
(JSONL, gün başına bir dosya): `tarama_basladi`, `formasyon_olustu`, `bildirim_gitti`,
`gecersizlesti`… Sonra bu dosya (a) karne ile çapraz doğrulama, (b) "dün kaç olay
kaçtı/neden düştü" sorusuna tek `jq` ile cevap verir. `logs/` zaten gitignore'da.

### T4 — Görünüm/regresyon galerisini CI'ya taşı
Bu oturumda eklenen `scripts/ornek_gorsel_uret.py` katalogdaki 6 senaryoyu üretiyor.
CI'ya eklenecek bir adım bu PNG'leri **artifact** olarak yüklerse her PR'da görsel
dilin farkı resimde görünür (piksel assert'i değil, insan gözü için). `docs/ornek_galeri`
içindeki dosyalar da tek komutla tazelenir.

### T5 — Test süresi yönetimi
1.300+ test ~4 dakika — henüz sorun değil. 2.000'e yaklaşınca: pytest marker'larıyla
`hizli` (birim) / `yavas` (çizim+simülasyon) ayrımı; CI'da hızlı her PR'da, yavaş
gecelik. Şimdilik yalnızca marker altyapısını kurmak yeter (etiket koymak sonradan da
olur).

### T6 — Şema sürümlemesi
`state/formation_schema.py` var; kalıcı dosyaların hepsine `surum` alanı + açılışta
bilinmeyen sürümde **uyarı** (fail-closed değil, ama log + `/durum` görünür). Render
redeploy'larda `/tmp` silinmesi zaten tolere ediliyor; sürüm notu migration'ları
belgeler.

### T7 — Günlük öz-denetim mesajı (self-check)
Bot her sabah 09:00'da kendine bir sağlık raporu üretsin: dün kaç tarama, kaç bildirim,
hata var mı, cache yaşları, karne defteri son kayıt tarihi. Bu mesaj DM'e gider; bir şey
bozulduğunda **botun sessizliği** ilk sinyal olur (şu an sessizlik ancak keep-alive
workflow'unun yakalayabildiği kadar fark ediliyor).

---

## 5. Neler yapılabilir — önceliklendirilmiş iş listesi

Öncelik: ★★★ kısa vadede yap · ★★ planla · ★ fırsat buldukça. Efor: **1s** dakikalar ·
**K** yarım gün · **O** 1–2 gün · **B** yapısal (birkaç gün, ayrı dal).

| ID | ★ | İş | Nerede | Efor |
|---|---|---|---|---|
| Y1 | ★★★ | `ruff` + `pyproject.toml` + CI lint adımı; ilk bulguların temizliği | yeni `pyproject.toml`, `.github/workflows/ci.yml` | K |
| Y2 | ★★★ | Kök belge haritası: 3 belge kökte, gerisi `docs/` (tarih etiketli) + README'ye tablo | kök `*.md`, `README.md` | K |
| Y3 | ★★★ | `/izle` izleme listesi + günlük özette ayrı bölüm | `telegram_commands.py`, `notification_context.py`, yeni `watchlist.py` | O |
| Y4 | ★★★ | Hedef ilerleme bildirimleri (teyit sonrası hedef/stop takibi) | `karne.py` (defter), `notifier.py` (yeni mesaj türü) | O |
| Y5 | ★★ | Veri sağlayıcı arayüzü + `/durum` veri kalitesi satırı | `data.py`, yeni `providers/` | O–B |
| Y6 | ★★ | Haftalık kanal yayını (karne özeti + gerçek-veri haftanın kareleri) | `kanal_acilis.py`, `karne.py`, `grafik_uret.py` | O |
| Y7 | ★★ | Karneye stabilite satırı (kayan pencereler min–medyan–max) | `karne.py`, `test_karne.py` | K |
| Y8 | ★★ | Yapısal olay günlüğü (JSONL) + sabah öz-denetim mesajı | `main.py`, yeni `events.py` | O |
| Y9 | ★★ | Çoklu TF uzlaşısı: kart + karne kırılımı | `notification_context.py`, `karne.py` | O |
| Y10 | ★★ | Galeriyi CI artifact'ına bağla + `docs/ornek_galeri` tazeleme adımı | `ci.yml` | 1s |
| Y11 | ★ | Sessiz saatler tercihi | `notifier.py` (zaman filtresi) | K |
| Y12 | ★ | `main.py`'den komut katmanının ayrıştırılması (yalnız bu parça, tamamı değil) | `main.py` → `commands.py` | O |
| Y13 | ★ | Sembol sayfası statik site (GitHub Pages) | yeni workflow + `chart_report.py` | O |
| Y14 | ★ | pytest marker altyapısı (`hizli`/`yavas`) | `pytest.ini`, `conftest.py` | K |
| Y15 | ★ | İkili tepe/dip formasyonu (ayrı dal, karne doğrulamalı) | `patterns/`, `karne.py` | B |
| Y16 | ★ | Omuz-baş-omuz (yapı motoru PH/PL üzerine) | `domain_engines/market_structure/` + `patterns/` | B |

### Sıralama gerekçem
- **Y1–Y2 önce**, çünkü sonraki her işi ucuzlatıyorlar (lint, bulunabilir dokümantasyon).
- **Y3–Y4 ürün algısını değiştirir**: bot "haber veren"den "yol gösteren"e geçer; ikisi de
  mevcut state/karne üzerinde, yeni doğruluk riski taşımaz.
- **Y5 riski kapatır**: tek sağlayıcı bağımlılığı ürünün en büyük dışsal riski.
- **Y6 kanalı besler**: public kanal düzenli içerik olmadan büyümez; karne şeffaflığı
  güveni kurar.
- **Y15–Y16 en son**: yeni formasyon ailesi ancak mevcut ailenin karne karşılığı
  oturduktan sonra anlam taşır — yoksa "daha çok sinyal, aynı kanıt" olur.

---

## 6. Bu oturumda eklenen: örnek görsel üretim sistemi

İsteğe üzerine repoya **içeride görsel üretebilen bir örnek sistem** eklendi
(kullanıcı görünüm değişikliklerini botu çalıştırmadan görsün, tanıtım/kanal paketi
hazırlığı, görsel değişiklik kontrolü):

- `scripts/ornek_gorsel_uret.py` — 6 senaryoluk DEMO kataloğu (üçgen teyit, bayrak
  aday, flama teyit, kama hazırlık, geçersizleşme, retest). Projenin **kendi** çizim
  zincirini kullanır (`grafik.anlik_goruntu` → `grafik.ciz`); ayrı demo çizicisi yok.
  `bot_data/` yasağı, deterministik veri, kapanış kuralı tek kaynaktan.
- `docs/ornek_galeri/` — üretilen 6 örnek kare + README (nasıl yeniden üretilir,
  katalog tablosu, kurallar).
- `test_ornek_gorsel_uret.py` — 6 regresyon: üretim, alarm çizgisi, determinizm,
  bot_data koruması, "demo · sentetik" dürüst etiketi.

Kullanım: `python scripts/ornek_gorsel_uret.py --senaryo hepsi`

Ayrıca Y10 (CI artifact) için hazır bir kanal açıldı; Y6'daki "haftanın kareleri"
işinde **gerçek veri** tarafı `grafik_uret.py` zinciriyle yapılmalı, DEMO kareler yalnız
görünüm örneklemesi için kullanılmalı.

---

## 7. Kapanış görüşü

Bu proje benim gördüğüm kadarıyla üç fazdan geçmiş: (1) Pine port'u — motor doğruluğu,
(2) güvenlik/kararlılık — kapanış kuralı, teslim kuyruğu, takvim, (3) güven/dürüstlük —
güven şeridi, odak görünümü, karne. Dördüncü fazın **kullanıcı yüzü** olması gerektiğini
düşünüyorum: izleme listesi, hedef takibi, haftalık yayın. Motor artık yeterince iyi;
fark yaratacak olan onu **anlatma ve kullanışlı hâle getirme** hızı.

İkinci gözlemim: repodaki belge/test disiplini, bu projeyi tek kişilik bir bot olmaktan
çıkarıp **sürdürülebilir bir ürüne** çeviren asıl varlık. Kodu kimse okumasa bile
`YAPILACAKLAR.md` + karne + denetim belgeleri projenin hafızası. Bu yüzden önerilerimin
ilk sırasında belge haritası ve lint var: hafızası düzenli projeler hız kaybetmez.

Son olarak bir uyarı-tavsiye: yeni formasyon/parametre eklerken **karne kapısı**
kuralını (yeni sinyal türü kanala girmeden önce en az N örnek karne doğrulaması)
yazılı hâle getirmek, bu ürünün uzun vadeli itibarını koruyacak tek politika.
"Daha çok sinyal" her zaman daha çok değer değildir; **hesap verebilir sinyal** değerdir.
