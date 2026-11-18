# Senaryo Motoru — Brifing, Toplu Yorum ve İşlem Döngüsü Sözleşmesi

**Tarih:** 2026-11-09 · **Durum:** **TASARIM** (kod yok, canlı karar değiştirmez)
**Kapsam:** Eğitim/araştırma odaklı mevcut sistem korunarak, kullanıcı hazır olduğunda
kontrollü biçimde işlem-planning katmanına geçiş için zemin.
**Günlük kural:** Bu belge yatırım tavsiyesi değildir; ölçüm kaynakları
`docs/arastirma/` altındaki tarihli replay kayıtlarıdır. Burada üretilen çıktı
**plan**tır, **sinyal** değildir; buton kullanıcıdadır.

> İlgili belgeler: [TAHMIN_KATMANI](TAHMIN_KATMANI.md) (beklenti hükmü sözleşmesi) ·
> [GRAFIK_TASARIM](GRAFIK_TASARIM.md) (uydurma-alan yasağı) ·
> `docs/arastirma/ARASTIRMA_SONUCLARI.md` (ölçümler) ·
> `docs/arastirma/STABIL_OK_BAGLAM_VE_IKILI_DINAMIK_SENTEZI_2026-11-09.md` (katman kanıtları).

---

## 0. Neden bu belge — tek paragraf

Mevcut sistem **grafik okuma ve alarm** ürünüdür; amacı kullanıcının kararını
beslemektir. Kullanıcı, sistemin doğrudan al-sata yönlendirme yapmasından
bilinçli olarak kaçınmıştır; geçiş **kullanıcı hazır olduğunda** ve **kanıt
biriktiğinde** yapılacaktır. Bu belge o geçişin zeminini kurar: katmanların
zengin çıktısını **kaybetmeden** sırayla konuşturan bir brifing modeli, zamanı
gelince toplu olarak "uygun" hükmü veren bir yeniden-yorum turu, küçük zaman
dilimlerinde bloklarla hassas giriş, ve aç-kapat olmayan **işlem yaşam
döngüsü** (korunma, hedef, sermaye). Şimdilik tek çıktı yeri **gölge defter +
replay raporudur**; canlı yayın yoktur.

---

## 1. Kırmızı çizgiler (bozulmaz)

1. **Ana sistem değişmez.** Motor yan okuyucudur (karne/outcome_link kalıbı);
   tarama, alarm, kart, bildirim kapıları aynen kalır.
2. **Katman çıktısı kırpılmaz.** Hiçbir katman "yukarı/aşağı" tek bitine
   indirgenmez; native export ne taşıyorsa brifing o zenginliği taşır.
3. **Yön iddiası bir girdi değil, bir çıktıdır.** Yon yalnız katmanların tam
   durumlarından doğar; sistemin başına empoze edilmez.
4. **Blok işlem engellemez.** Küçük TF blokları yalnızca **giriş yerini
   güzelleştirir**; işlem, blok yüzünden açılmaz da blok yüzünden **ertelenmez
   de** — yalnız daha güzel bir yerde açılır. Uzun TF'de **geniş güçlü bloklar**
   (≥2 ATR vb.) destek/direnç olarak değerli sayılır.
5. **Derin filtre ağacı kurulmaz** (sentez belgesi §2.3): kapılar az ve sığdır.
6. **Sıfat yasak, sayı var:** n < 30 sayılmaz; hüküm tek kelime, güç sayıdır
   (TAHMIN_KATMANI kuralı).
7. **Sessizlik varsayılandır** — ve sessizlik, kaydın silinmesi değildir:
   sessizken bile bildiri deftere yazılır.
8. **Canlı karar değişmez;** gerçek boyut/gerçek para yalnız ayrı ve son
   aşamada, gölge defter istatistiği kapıyı geçtikten sonra düşünülür.

---

## 2. Masa: sırayla konuşan katmanlar

Katmanlar **oy vermez**; kendi dillerinde **bildiri** bırakır. Sıra sabittir,
içerik zengindir.

| Sıra | Katman | Rolü | Sessizliği |
|---|---|---|---|
| **G1** | **Stabil (1g)** | **Yön kapısı + karakter.** Destek/direnç karakteri (yatay sabit · dikey-yükselen · dikey-düşen · yataya dönen), kademe hızı, mesafe, onay durumu, kırılım tipi. "Destek kırıldı" tek cümle değildir: **yatay zemin kırılımı ≠ dikey basamağın bozulması ≠ yataya dönme ≠ üstüne taşıma** — her biri ayrı olay/seri. | Durum PENDING/UNKNOWN/belirsiz → **motor bu sembolde susar**, G2–G5'e sıra gelmez (kayıt yine yazılır). |
| **G2** | **Formasyon (2s/4s)** | **Bağlam ve yol haritası.** Tip, faz (yeni/daralma yüzdesi/olgun), üst-alt sınıra mesafe, kırılım denemesi riski. "Biraz daha düşerse alt sınıra gelir, oradan tepki alabilir" — haber verir, izin vermez. | Formasyon yoksa bağlam satırı boş kalır; zincir devam eder. |
| **G3** | **Market Structure** | **Uyarı ve erteleme.** Taze BOS/CHoCH (yaş/süpürülme sınırı içinde), karşıt boşluklar ("1s'te aşağı boş, uğrama riski"), PH/PL test sayısı. "Bekleyelim" der — erken girişin panzehridir. | Taze-olmayan olay yazılmaz (eski BOS'ların %93–96'sı SUPERSEDED). |
| **G4** | **Toplu Yeniden Yorum (TYR)** | **Zaman olgunlaşınca tek hüküm:** birikmiş tüm canlı bildiriler + fiyat konumu + zaman ölçümleri yeniden okunur → `BEKLE` / `UYGUN` / `RET`. | TYR tetiklenmeden "uygunuz" cümlesi **yoktur**. |
| **G5** | **Bloklar (1s/2s/4s)** | **Giriş hassasiyeti — yalnız G4 `UYGUN` dedikten sonra devrede.** Geniş/gevşek OB/FVG/ENG bandı giriş çizgisini verir. Engelsiz, yalnız güzelleştirici. | G4 `BEKLE` iken bloklar yalnız **izleme seviyesi** olarak durur. |

**Brifing akışı:** `Birikim (G1–G3) → İzleme → TYR (G4) → UYGUN → bloklarla
hassas giriş (G5) → işlem döngüsü`. G1 sessizse hiç başlamaz; G4 `BEKLE`
derse bloklar susar ve zaman beklenir — kullanıcı tarif ettiği gibi:
*"zaman uygunlaşmaya başladı, sistem toplu yorumladı: tamam uygunuz, bloklar
devreye girebilir."*

---

## 3. Bildiri (statement) şeması — katmanın "konuşma" nesnesi

Her katman bir cümle değil, **ölçümlü bildiri** bırakır:

| Alan | İçerik | Zorunlu |
|---|---|---|
| `kim` | `stabil` · `formasyon` · `ms` · `blok` | ✅ |
| `iddia` | `uyari` · `izle` · `bekle` · `olasi_tepki` · `onay_bekliyor` · `konfluans` · `onay` · `bozulma` | ✅ |
| `kosul` | İddianın koşulu ("onay yokken", "taze boşken", "daralma %60'ken") | ✅ |
| `kaynak` | Replay tablo adı + **n** (ör. `ARASTIRMA_SONUCLARI Soru 6 · n=…`); uydurma yok | ✅ |
| `seviyeler` | İzlemeye alınan fiyatlar (alt sınır, destek hattı, OB bandı) | varsa |
| `uyari_metni` | "aşağı sarkma mümkün", "kırılım denemesi olabilir" | varsa |
| `gecerlilik` | Bitiş (bar/saat); eskiyince bildiri söner, **seviyeler kalır** | ✅ |
| `dogrudan` | `bekle` · `takip_et` · `haber_ver` — karar değil **görev** | varsa |

**Kural:** Bildiri bir **görev + seviye** verir; **karar vermez.** Motorun işi
görevi uygulamak: `takip_et` gelince o seviyeye abone olmak, fiyat gelince
**ilgili katmanı yeniden konuşturmak** (onay ya da bozulma). Konuşma böyle
döngüye girer.

### 3.1 Bildiri kaynakları (uydurma yasağı — hangi cümle hangi ölçümle beslenir)

| Bildiri tipi | Ölçüm kaynağı (örnek) |
|---|---|
| "onay almadı, sarkıp toparlanabilir" | Destek onay/tepsii ayrımı: koşulsuz testte kırılma %51,6 / tepki %41,3; **onaylı** tutunma lift'i +14 puan (OK sistemi §12) |
| "aşağı boş, uğrama riski" | Zone/FVG zamanlama ölçümleri (dokunuş %65; FVG tam dolum ~%40) |
| "geniş blok güçlü destek olabilir" | Zone yüksekliği kovaları (≥2 ATR: %71 tepki, hızlı+kalıcı) |
| "daralma %60, sınıra yakın" | Formasyon faz ölçümleri (medyan daralma %76,6; genişlik 0,34–0,52 ATR) |
| "taze BOS, yön uyumu" | MS devam tablosu (uyum %97–98, devam ~%70; yaş/süpürme kuralları) |
| "dikey/yatay karakter" | Stabil V2 geçiş tabloları (STEPPING_UP: %62 dik / %23 yataya dönüş; yön kovaları) |

---

## 4. Brifing yaşam döngüsü

1. **Birikim:** Yeni bildiri eskisini **ezmez**; onu günceller/şerhler
   (MS "bekleyelim" derken formasyon "haber ver" diyebilir — ikisi birden durur).
2. **Çelişki sayacı:** Katmanlar çelişirse taraf tutulmaz; yan yana ve
   `çelişki: k` sayacıyla yazılır (beklenti katmanının lehte/aleyhte kuralı).
3. **Sona erme:** `gecerlilik` biten bildiri söner; **süresiz kalan tek şey
   seviyelerdir** (destek hattı, OB bandı — fiyat gelene kadar).
4. **Konfluans:** İki+ bağımsız katmanın seviyesi ATR içinde çakışınca brifing'e
   tek satır: `konfluans: k kaynak · [a–b bandı]`. Bu bir **davettir**, giriş değil.
5. **TYR tetikleri:** (a) izleme TF'inde yeni kapanmış mum, (b) fiyat herhangi
   bir izleme seviyesine X ATR içinde yaklaştı, (c) önemli bildiri geldi/söndü,
   (d) günlük açılış. TYR, canlı bildirileri **toplu** yeniden okur.
6. **TYR hükmü (tek):**
   - **`BEKLE`** — yön/koşul oturmamış (G1 onaysız, MS taze uyarı sürer,
     formasyon olgunlaşmamış). Bloklar yalnız izlemede.
   - **`UYGUN`** — yön kapısı açık + uyarılar/çelişkiler kabul edilebilir
     sınıfta + zaman/koşul olgunlaştı (daralma, mesafe, tazelik). **Artık
     G5 blokları devreye girer:** küçük TF'de giriş bandı çizilir.
   - **`RET`** — tez bozuldu (onaysız kırılım, ters BOS iptali, G1 kapanışı).
     Brifing kapanır, seviyeler arşive.
   TYR çıktısı tek satır hüküm + kanıt sayacıdır (`UYGUN · 2 lehte · 1 çelişki`);
   sıfat yoktur.

---

## 5. İşlem yaşam döngüsü — "aç-kapat" değil, **tez yaşar veya ölür**

| Evre | Kural | Ölçüm dayanağı |
|---|---|---|
| **Giriş** | G4 `UYGUN` + G5 blok bandında **onaylı tepki**; giriş = tetik barının **kapanışı** (mevcut mum-kapanış kuralı aynen) | teyidin %76'sı ilk barda |
| **Stop (tez ölümü)** | Onaylı destek/bozulma noktasının dışı — **sabit ATR değil, tezin öldüğü yer** (karaktere göre: yatay zemin altı vs dikey basamak bozulması farklı durumlarda farklı durum) | destek koşulsuz kırılıyor %51,6 → korunma onaya bağlı |
| **Gürültü toleransı** | Stop ile tipik dalgalanma arasında ölçülü mesafe: pencere içi normal MAE ~2 ATR; başarısız kırılımda ters MAE 2,83 ATR | aşırı dar stop gürültüde yer · **Faz 0:** hedefe (+1,5) varanların önceki kısıtsız MAE p90 = 1,48 ATR (n=8.326); ama durdurulmuşların %73–82'si geniş stopla da kazanca dönüşmüyor → 1,0 ATR stopu korunur |
| **Zaman stopu** | X bar'da ilerleme yoksa tez zayıf: BOS'un %60'ı ilk 3 bar (medyan tepe 6. bar); WH/WL 3–6 barda süpürülür | hareket geç geldiyse beklenti çöker |
| **Nedensel iptal** | Giriş sonrası **1–3 barda ters BOS** → tez ezildi, kapat | OK sentezi §3.3 |
| **Hedef** | **Yakın karşıt yapı:** Stabil direnç / formasyon üst sınırı / PH. Kartta `R = (hedef−giriş)/(giriş−stop)` yazılır. Formasyon **hedef değildir** — bağlamdır. | MFE≈2 ATR ama yönle birlikte geçerli |
| **Korunma (son tur)** | Hedefe gidişte stop taşıma / kısmi çıkış: **önce gölge defterde yarışır**, kazanan kurala girer | şimdilik kanıt yok, yasak |

---

## 6. Sermaye koruma katmanı (işlem psikolojisinin sayısal hâli)

1. **Boyut = stopa göre:** sabit %risk (ör. %1); stop uzunsa pozisyon küçük.
2. **Eşzamanlı tavan** (ör. 3 açık işlem) — tüm evreni taşımak yok.
3. **Aynı gün ikinci stop → günlük dur** (intikam işlemi yasağı; his değil, sayı).
   *Faz 0 ölçümü (2026-11-09): sembol-bazlı günlük 2+ stop bu veri yapısında hiç
   tetiklenmedi — gerçek risk üst üste serilerde (%60,7 seri ≥3, maks 10). Ölçülen
   karşılığı: **sembol×TF'de 3 üst üste stop → sıradaki işlemi atla** (toplam
   beklentiye maliyeti −%1,7, `seri_kural_ozet.json`); portföy-birleşik DD sürümü
   gölge defterde ölçülecek.*
4. **Rejim mührü:** G1 sessizse **yeni** giriş yok; açık işlem taşınabilir.
5. **Çift ölçüm:** motorun kendi stopu + karne'nin evrensel
   `1,5 hedef / 1,0 stop / 10 bar` yarışı **aynı anda** yazılır; çelişki
   defterde görünür (bilinen ölçüm-semantik uyumsuzluğu kapatılmadan
   hangisinin birincil olduğu **iddia edilmez** — FAZ3 notundaki uyarı geçerli).
6. **"Şu an bilinmeyen" satırı** her plan kaydında zorunlu:
   örn. *"direnç tepkisi ölçülmüş değil"*, *"MS tazeliği 4 bar, sınırda"*.
   Amaç güven değil **netlik** — kullanıcının korktuğu "AI direkt yönlendiriyor"
   tuzağının panzehri: motor **plan verir, yön garanti etmez.**

---

## 7. Örnek tam masa (kullanıcı senaryosunun kayıtlı hâli)

```
[1] STABIL (1g): "Fiyat henüz destekten ONAY ALMADI; destek yakın,
     aşağı sarkıp toparlanma ihtimali var."          → izle · onaysız-kayıt
[2] MS (1s):     "Haklısın — taze aşağı boş; uğrama mantıklı,
     BEKLEelim."                                     → uyari · erteleme
[3] FORMASYON:   "Biraz daha düşerse alt sınıra gelirim; oradan
     tepki alabilir. DİKKAT: sarkma + kırılım denemesi olabilir."
                                                        → izle · seviye
[4] BLOK (4s):   "Formasyon alt sınırı + Stabil desteğin KESİŞİMİNDE
     geniş (≥2 ATR) pozitif OB — sağlam, TAKİP."      → konfluans kaydı
     [motor: GİRİŞ YOK · izlemede 2 seviye]

… zaman geçer, daralma olgunlaşır, fiyat hatta yaklaşır …

[5] TYR (toplu yorum):
     "UYGUN · 2 lehte · 1 çelişki (MS taze boş hâlâ açık)
      yön: Stabil destek karakteri KORUNALI · zaman: olgun
      → G5 blokları devrede: giriş bandı 46,10–46,35"
[6] ONAY: fiyat banda gelir, tepki onayı → PLAN:
     giriş 46,25 · stop 45,55 (destek altı, tez-death) ·
     hedef 48,60 (yakın karşıt yapı) · R=2,1 · zaman-stopu 10 bar
     · bilinmeyen: "1s boş hâlâ dolmadı"
```

---

## 8. Replay planı (canlı yok, sıralı turlar)

| Tur | İş | Çıktı |
|---|---|---|
| **T1 — Gölge zincir** | 177 sembol arşivinde G1→G5'i **as-of** koş; her bildiri, TYR hükmü ve plan gölge deftere düşsün. Ana sistem aynen çalışır. | `golge_defter` (olay bazlı) |
| **T2 — Ölçüm** | Hedef/stop/nötr dağılımı, R katsayısı, **stopa varmadan önce tipik MAE**, hedefe süre, rejim kırılımı, G1-sessiz dönemde kaçan kurulumlar (negatif kontrol). | rapor + kova tabloları |
| **T3 — Kapı** | Ön-kayıtlı eşikler + kova bazeline göre kapı (soru-kapısı kalıbı). Geçen tek çıktı: **plan kartı metni** (`◇ plan: …`), sinyal değil. | kapı kararı |
| **T4 — Korunma** | Stop-taşıma/kısmi çıkış varyantları gölge defterde yarışır; kazanan kurala girer. | kural |
| **B4 — Bildiri notlaması** | Her bildiri tipinin kendi geçmişi ölçülür (izleme seviyesi tuttu mu, kaç bar) — cümleler de hedef/stop gibi notlanır. | cümle sicili |

**Anti-lookahead:** tüm turlar mevcut araştırma hattının sözleşmesine bağlıdır
(çapa sonrası ölçüm, sansür, n≥30, keşif/ileri bölme, sembol-kümeli GA).

---

## 9. Uygulama sırası (kod işi çıktığında)

**Faz 0 tamamlandı (2026-11-09):** [domain sözlüğü](DOMAIN_CIKTI_SOZLUGU_2026-11-09.md) +
[stop/sermaye raporu](../arastirma/STOP_SERMAYE_REPLAY_2026-11-09.md) (15.808 işlem;
çıktılar `docs/arastirma/sonuclar/stop_sermaye/`, betik `scripts/stop_sermaye_replay.py`).
Gölge motorun varsayılan sözlüğü ölçümden geliyor:

| Gölge varsayılanı | Ölçüm | Durum |
|---|---|---|
| stop 1,0 ATR (tez ölümü) / hedef 1,5 ATR / 10 bar | beklenti +0,090 keşif ↔ +0,087 doğrulama; durdurma %42,8 | doğrulandı |
| TF-bazlı varyant (1d: 0,5/1,0) | 1d'de 1,0/1,5 → +0,025; 0,5/1,0 → +0,102 | izinli (tek küresel değer değil) |
| maliyet 0,05–0,10 ATR varsayımı | 0,10'da baz hücre −0,010 → Faz 2'de maliyet modeli zorunlu | şart |
| streak kuralı (3 üst üste → atla) | "günde 2 stop" hiç tetiklenmedi; seri ≥3 %60,7 | kural metni §6.3'e işlendi |

1. **Bildiri + brifing defteri** (yan okuyucu, atomik dosya; karne kalıbı).
2. **TYR fonksiyonu** (saf: canlı bildiriler + anlık durum → hüküm).
3. **Gölge zincir koşucusu** (replay üzerinde, `research/` altında; canlı
   registry'den bağımsız).
4. **Ölçüm + kapı** (mevcut `soru_kapisi` kalıbıyla).
5. **Plan kartı satırı** (opsiyonel, kapıdan sonra; `TELEGRAM_KART_TAHMIN`
   gibi tek anahtarla kapatılabilir).
6. **Korunma kuralları** (T4 sonrası).

Her adım ayrı commit + tam test yeşil; hiçbir adım mevcut alarm/kapı
davranışını değiştirmez.

---

## 10. Sınırlar (dürüst kayıt)

- Tek 365 günlük rejim penceresi; yön/karakter bulguları rejimle dönebilir.
- `MFE ≈ MAE ≈ 2 ATR, NET ≈ 0`: bu motor **yön garantisi vermez**; yön
  iddiası yalnız G1'in tam durumundan ve kanıt sayacıyla yazılır.
- Hacim verisi kirli (sıfır hacim/09:30); hacim temelli hiçbir bildiri
  kesinleştirilmez.
- Kırılım replay kontrolü eşleşmiş değil → nedensellik iddia edilmez.
- Karne vs outcome_link bar-semantik farkı kapatılmadan "başarı oranı"
  tek sayı olarak sunulmaz.
- Bu belge bir **tasarımdır**; uygulaması ayrıca test edilmeden canlıya
  bağlanmaz.
