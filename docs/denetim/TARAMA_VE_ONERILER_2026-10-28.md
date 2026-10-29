# Tarama, düzeltme ve öneriler — 2026-10-28

**Durum:** Kayıt (tarihli inceleme + yol haritası önerisi) · **Kapsam:** tüm depo ·
**Yöntem:** tam suite + statik kapı + bağımsız regresyonlar, arşiv üzerinden kök-neden
izleme, veri envanteri, açık maddelerin bugünkü durum denetimi.

Bu belge **o günün** fotoğrafıdır; "öneriler" kısmı karar bekleyen, **uygulanmamış**
tavsiyelerdir. Her öneri mevcut bir ölçüme/deftere/mekanizmaya dayanır; genel geçer
"ML/daha çok veri" tavsiyesi **verilmez**.

## 1. Tarama sonucu

| Kontrol | Sonuç |
|---|---|
| `ruff check .` (F / E9 / S110 kapısı) | ✅ temiz |
| `pytest -q` | ✅ **2726 passed / 0 failed** (43 skipped; yeni MS koruma testleri dahil) |
| `test_tarama_zamani.py` | ✅ 102/102 |
| `test_triangle/breakout/flag/pennant.py` | ✅ yeşil |
| `compileall` (tüm depo) | ✅ temiz |
| **MS kilitli-referans çökmesi (35 seri)** | ✅ **çözüldü** → [MS_KILITLI_REFERANS_DUZELTME_2026-10-28.md](MS_KILITLI_REFERANS_DUZELTME_2026-10-28.md) |

2026-10-26 kod denetiminin açık önerileri tek tek denetlendi:

| # | Öneri | 2026-10-28 durumu |
|---|---|---|
| 1 | CI'a bağımsız regresyon scriptleri | ✅ `ci.yml`de (triangle/breakout/flag/pennant + tarama_zamani) |
| 2 | S110 sessiz yutma incelemesi | ✅ kapı temiz; kalan yutmalar `noqa: S110 - gerekçe` ile işaretli |
| 3 | Ruff'ı CI'a sabitle | ✅ `ruff.toml` + pinli sürüm + "Statik kapı" adımı |
| 4 | `test_p2_*` içindeki F811 | ✅ F kapısı geçiyor (fixture temizliği yapılmış) |
| 5 | Mega dosya bölme | ✅ uygulanmış (`main.py` 87 satır; `bot/`, `grafik/`, `notifier/`, `data/` paketleri) |
| 6 | Repo ağırlığı (backfill + görseller) | ℹ️ bilgi olarak geçerli; `.git` ~15 MB, acil değil |

**Tarama boyunca başka kritik bulgu çıkmadı:** sözdizimi, env drift, tanımsız-ad sınıfı
ve test yüzeyi temiz; tek kritik açık madde MS çökmesiydi (yukarıda çözüldü).

### Bu önerilerde OLMAYANLAR (mevcut plana dahil, tekrar edilmedi)

Aşağıdakiler `docs/arastirma/PUANLAMA_MIMARISI_2026-10-25.md` §8'in kendi
sıradaki adımlarıdır; **onlar zaten planlı**, burada yeniden ısıtılmadı:
gölge mod doğrulaması (6 hafta), üçgen negatifliğinin ayrıştırılması, TF bazlı
ağırlık, `PUBLIC_MIN_DEVLAMLILIK` hacim musluğu kararı, eski puanın kenara alınması.

## 2. Elimizdeki veri envanteri (bugün ne var?)

| Varlık | Miktar | Durum |
|---|---|---|
| `backfill_data/` 1h | **177 sembol × 572.059 bar** · 2025-05-07 → 2026-10-19 (~17 ay) | kullanılıyor (ölçüm/replay/seed) |
| `backfill_data/` 1d | **177 sembol × 88.445 bar** · 2024-10-21 → 2026-10-19 (**2 yıl**) | kullanılıyor; **ama ölçüm hattı hâlâ tek 365 günlük rejim koşuyor** (bkz. Ö2) |
| Endeks/makro | `XU100` + `BRENT` (1h+1d) arşivde | kısmen |
| Araştırma ölçümü | 704 seri / 994.142 gözlem · FRM-01…20 · zone/OB/FVG/MS/VH tabloları | üretilmiş, canlı metne `◇` ile bağlı |
| Özellik deposu | `scripts/ozellik_deposu.py` — **10 özellik ailesi** | üretilmiş, puanlamaya bağlı |
| Puanlama | `devamlılık.py` canlıda (3 bayrak) + `scripts/puan_*.py` + §10 doğrulaması yapıldı | gölge/`/evet` geçişi bekliyor |
| Canlı karne | `karne_defteri.json` — formasyon/kırılım/olay outcome + huni sayıları | canlı, haftalık |
| Outcome bağı | `state/outcome_link.py` — `stable_id` ile history↔karne | kurulu |
| Süzgeç sayaçları | `daily_stats` (`alerts_deferred`, `alerts_engel_tekrar`, `alerts_engel_kap`, `alerts_bar_kapanmadi`…) | **sadece sayı — sonuçları izlenmiyor** (bkz. Ö1) |

**Değerlendirme:** ham veri ve ölçüm yeterli; zayıf nokta miktar değil — dört somut
eklenti: (1) bastırılan adayların **sonucu** bilinmiyor, (2) bulgular hâlâ **tek rejimde**
doğrulanmış, (3) en güçlü bulgulardan biri (korunan seviye test asimetrisi) **karta ve
süzgeçe bağlı değil**, (4) hacim işaretinin **aşamaya göre** değiştiği ölçüldü ama tek
genel "hacim teyit" dili hâkim.

## 3. Öneriler — projenin kendi makinelerine çakılı, ölçümlü

### Ö1 — Süzgeç kırılımı: "gönderilen" ile "süzgeçte kalan" ayırt edilsin (kapalı döngü gözü)

* **Sorun (kodda doğrulandı — önceki taslaktan daha dar ve daha doğru):**
  Karne kaydı **gönderim kararından ÖNCE** düşüyor (`bot/scan.py` ~678, `if active`
  bloğu): yani DM musluğunda kalan adayın da kaydı defterde var — ama kayıtta
  **"gönderildi mi" etiketi yok**. `karne_hesapla` bu yüzden gönderten ile
  "bilinçli DM'e söylememe" kararında kalanı **ayırt edemiyor**, tek havuzda
  topluyor. Karşı tarafta `ileri_test` gölge defteri **yalnız gönderilenleri**
  alıyor (öyle tasarlı). Aradaki kesişim bilinmiyor: DM muslukları
  (`dm_gecersiz_engel` / `dm_dev_engel` — bugün sayacı bile yok, yalnız log)
  ve `alerts_state_disabled` adaylarının outcome'u ölçülmüyor.
  (Not: `alerts_engel_tekrar` tekrar mührü **kayıp aday değildir** — zaten
  bildirilen olayın dedup'u; `cooldown/kap` ise kuyruğa girip gönderiliyor.)
* **Ne:** Gönderim kararı verilen noktada (scan.py ~1138-1190) karne kaydına
  `gonderim` etiketi yazılsın: `evet · dm_musluk · state_kapali · kuyruk`
  (`stable_id` ile eşleme; defter kayıtları zaten `stable_id` taşıyor).
  `karne_hesapla` ikiye bölsün; haftalık karneye blok:
  `🛈 Süzgeç kırılımı: gönderilen 31 → hedef %32 · DM musluğunda 19 → hedef %41
  (n<30 → ölçüm yok)`.
* **Neden anlamlı:** Eldeki huni sayaçları "kaç tane"yi veriyor; soru bugün
  cevapsız: "musluk iyi mi eliyor?" Cevap n≥30 ile gelince musluk kararı
  (`DM_MIN_DEVLAMLILIK` / `PUBLIC_MIN_DEVLAMLILIK`) sezgiyle değil karneyle açılır.
* **Risk/geri dönüş:** etiketleme salt-okunur; `SUZGEC_ETIKET=0` ile kapalı.
  Kart/alarm davranışı **değişmez** — değişen tek şey karne bloğu.

### Ö2 — İki yıllık pencerede bulgu sağlamlık matrisi (tek-rejim riskini kapat)

* **Sorun (belgeden, kendi sınır maddesi):** `arastirma/README` "Tek 365 günlük rejim;
  rejim değişiminde özellikle **yön asimetrisi** dönebilir" diyor. Oysa 1d arşiv artık
  **2024-10-2026-10** (2 yıl), 1h 17 ay.
* **Ne:** `scripts/backfill/arastirma_kosu.py`'ye `--pencere BASLANGIC/BITIS` eklensin;
  aynı runner iki **örtüşmeyen** pencerede (1d: 2024-10→2025-10 ve 2025-10→2026-10;
  1h: ilk/ikinci yarı) koşsun; çıktı **sağlamlık matrisi** olsun: her başlık bulgu için
  iki pencere yan yana, aynı GA kurallarıyla, tek kelime sınıfı: **stabil / dönen /
  belirsiz**. Aday bulgular (ölçüm zaten hazır, soru kilitli):
  1. destek/yön asimetrisi (1d dokunuş tepkisi **+0,53 ATR**),
  2. Q4 dokunuş tükenmesi (**%60–61 vs %67–70**),
  3. PH/PL test asimetrisi (**%36→%8** vs **%37,5→%33,3**),
  4. BOS devamı (~**%70**) ve zone geçilme (**%85–94**).
* **Neden anlamlı:** Bu, mevcut ölçüm hattının **kendi belgelediği tek numaralı
  güvensizliğinin** ve yeni uzayan verinin tam kesişimi. Çıktı: tarihli
  `docs/arastirma/SAGLAMLIK_MATRISI_*.md`. **Ö3'ün ve tüm kural dönüşümlerinin ön
  koşulu burası** (repo kuralı: keşif bulgusu ayrı pencerede tekrar test edilmeden
  kural olmaz).
* **Maliyet:** runner'a pencere argümanı + toplulaştırma (~yarım gün), iki tam koşu
  (mevcut tam koşu ~60 dk × 4 koşu). Ağ gerekmez, arşiv yerel.

### Ö3 — Korunan seviye test-sayacı: `◇` satırı ve süzgeç (Ö2'ye bağlı iki aşama)

* **Ölçüm zaten var:** ARASTIRMA Soru 6 — 0,25 ATR yaklaşma bandında engelleme:
  PH 1d EXT **1 deneme %36,0 → 4+ deneme %8,0** (n=1.176); PL aynı aralıkta
  **%37,5 → %33,3** (yani tepe çöker, dip tutar). Metin "bot bunu tersine (kırılım
  beklentisi) kullanabilir" diyor ama bugün **hiçbir yerde bağlı değil**
  (`ampirik_referans.py`'de bu tablo yok — doğrulandı).
* **Aşama (a) — kart referansı:** Kurulum en yakın PH/PL'ye 0,25 ATR içindeyse ve
  o seviyenin deneme sayısı biliniyorsa, `◇` satırı kova oranını bassın
  (`_seviye_test_satiri`, `Kurulum.ph/pl` zaten besleniyor). Bu **kural değil,
  referanstır** — `AMPIRIK_REFERANS` mekanizmasının birebir kendi mantığı.
* **Aşama (b) — canlı deneme sayacı:** Araştırmanın bar-bar rol izlemesinin canlı
  karşılığı: MS olay/rol defterinden, o kimliğe (source_bar) yapılan **yaklaşma**
  sayacı tutsun (tepede direnç denemesi = yüksek/low'un role erişimi). Yeni alan
  `Kurulum.seviye_deneme` + `test_ms_kilitli_referans.py`-tarzı sentetik test.
* **Aşama (c) — gölge süzgeç (yalnız Ö2 "stabil" derse):** "4+ denenen tepe + aşağı
  kırılım beklentisi" adayını demote eden musluk; env ile, karne süzgeç bloğu (Ö1)
  izler, kalıcı karar `/evet` ile. **PL tarafına asla aynı şey uygulanmaz** (ölçüm
  bunu yasaklıyor — asimetri korunur).

### Ö4 — Hacim işaretini aşamaya bölmek: tek imza ölçümle çelişiyor

* **Ölçüm (üçü de var, üçü de farklı yön):**
  * **zone teması anı:** Q4 en **kötü** (%60,4–61,3; Q1 ~%67–70; 4h ort. uzanım
    2,272→1,868 ATR) → "hacim = tükenme", `zone_rvol` `◇` satırı bu tabloyu kullanıyor ✅;
  * **teyit barı (FRM-10):** Q4 hafif **iyi** (%54,7 vs Q1 %52,4; n=28.611);
  * **retest barı (FRM-14):** yüksek rvol **iyi** (+4,6 puan, GA +2,5…+6,9; n=9.336).
* **Ne:** Karta `◇` teyit/retest hacim satırları eklensin (`ampirik_referans._rvol_satiri`'nın
  FRM-10/FRM-14 kolları — tablolar hazır, bağlam alanı eklenecek). Aynı zamanda
  `devamlılık`/puan özniteliklerinin **hangi aşamanın hacmi** olduğu bir satırla
  sabitlensin: zone temas tersi, teyit/retest hafif pozitif — **tek genel "hacim teyit
  eder" imzası ölçümün tersidir ve tek-genel-kural olarak asla yazılmaz.**
* **Neden anlamlı:** En sık yapılan hata bu: bir alanda ölçülmüş hacim etkisini tüm
  sisteme yaymak. Burada doğru ham veri üçüncü fazda hazır; iş yalnız bağlam ayrımı.

### Ö5 — Üçgen kuyruğu için kanal ayrımı deneyi (ürün, ölçümle)

* **Ölçüm:** PUANLAMA §10.4 — kama içinde puan yayılması **+7,9 puan** (en iyi %20);
  üçgen içinde yayılma **+0,5 / −3,2 ve tamamı negatif**. Yani üçgenlerde skor "hangisi
  daha az kötü"ü bile söylemiyor, DM Top-12'de zaten iyileri var (üçgenlerin skor
  maddesi −1,3 aşırı) — yine de üçgenler **aynı DM akışında** yarışıyor.
* **Ne (2 haftalık dene, geri dönüşlü):** Üçgen ailesinin **ilk doğruluşları** DM'den
  çıkarılıp günlük `📋 Günlük Özet` + `public_kuyruk` "izleme" bandına alınsın
  (`public_kuyruk` zaten var, disk'ten geri yükleniyor, limit 40). Karne'de iki sayı
  kıyaslanır: DM hedef oranı (arttı mı?) ve örneklem kaybı (kaç aday özete indi).
  Kalıcı karar yalnız bu sayıyla; tek env (`UCGEN_DM=0`) ile geri.
* **Neden anlamlı:** Mesaj sayısını/kalitesini ölçülmüş bir aile özelliğine göre
  böler; silme yok, **kanal değişimi** var; karne tam bu iş için kurulu.

### Ö6 — Motor sağlık sicili: boş-domain'in sessiz sınıfını kalıcı iz

* **Sorun (kodda doğrulandı):** `_ms_hata_sayaci` yalnız bellekte, yalnız MS'e özel,
  dökümü yok; `/durum` tek satır toplam veriyor. Veri sağlığı sorunları **elle**
  çözülüyor (KOZAL/KOZAA `config.py` yorumunda elle çıkarıldı — veri sağlayıcı
  doğrulaması bekliyor). MS kök-nedeni düzeldi (denetim kaydı); geri kalan boş-domain
  vakaları (boş/kısa cache, desteklenmeyen TF, Yahoo bozuk bar) bugün **izlenmiyor**.
* **Ne:** `DATA_DIR/motor_sagligi.json` — sembol×domain×TF kırılımında okuma/başarı/hata
  sayacı (atomik yazım, karne_defteri deseni). `/durum`'a detay satırı: `en kötü 5
  sembol×domain (son 7 gün)`. **N ardışık taramada boş-kalan domain** için sembol
  bandı: karneye `⚠️ veri sağlığı: X/Y` uyarısı — elle KOZAL çıkarmak yerine veriyle
  görme. Kapatılabilir (`MOTOR_SAGLIK=0`).
* **Neden anlamlı:** Bu sınıf hatalar tam da "sessiz boşluk" sınıfı; MS'te göründü,
  domainlerde görünmeye devam edebilir. Erken uyarı, korkuluk değil.

### Ö7 — Karne puan-bantı sağlığı satırı (puan için canlı geri besleme)

* **Zemin:** `devamlılık_puani` bantlarının arşiv karşılığı ölçüldü (§10.1): yüksek
  **+14,1** · iyi **+4,8** · normal **−0,7** · zayıf **−2,1** (fazla). Karne zaten
  **kalite performansını** hesaplıyor (`karne_hesapla` bant tablosu, `n≥30` kuralı).
* **Ne:** Karneye tek kontrol satırı: canlıda bant **sırası tersine dönmüş mü**
  (zayıf bant, iyi banda karşı kazanıyor mu, n≥30)? Dönmüşse: `⚠️ puan bantları
  canlıda ters — gölge mod doğrulamasını başlat`. Yani PUANLAMA §8.2 "gölge mod
  doğrulaması"nın **tetikleyicisi** karne olsun; kör 6 hafta beklemek yerine.
* **Neden anlamlı:** Puan kartta "öncelik" olarak sunuluyor (AUC 0,507 gerçeği
  biliniyor); bant-sırası canlı testi, puanın **kendi** sağlığını tek satırda ölçer.

### Yapılınca ne değişir — tek ekranda önce/sonra

| | **BUGÜN** | **YAPILINCA (nasıl)** | **Değişmeyen** |
|---|---|---|---|
| **Ö2** | Koşucuda pencere kontrolü yok; rapor "365 gün" der, arşiv 1d'de 2 yıla uzanır; `(symbol,tf)` idempotent olduğu için eski ölçüm zaten tekrarlanmaz | `--pencere A/B` + `--cikti …_P1/P2 --zorla` iki ayrı koşu, `--saglamlik`/`--agrega` üretici → `SAGLAMLIK_MATRISI_*.md`: satır = 4 başlık bulgu, sütun = P1 · P2 · sınıf (stabil/dönen/belirsiz), aynı GA | **Canlı bot, kart, alarm: sıfır değişiklik**; tek etki bulgu etiketleri + Ö3c kapısı |
| **Ö1** | Karne kaydı var ama `gonderim` etiketi yok → gönderten/süzgeçte kalan ayrılamıyor; DM musluğu sayacı bile yok | Send kararında `gonderim` etiketi (`stable_id` eşleşmesi) → `karne_hesapla` iki sütun → haftalık karneye `Süzgeç kırılımı` bloğu | Kart/alarm/mesaj sayısı aynen; `SUZGEC_ETIKET=0` ile blok bile kapalı |
| **Ö4** | `◇` katmanı canlı; **FRM ailesi** yalnız `uyum/detay/temel/hareket` basar → formasyon kartında **hacim satırı yok**; hacim satırı (`%61 tepki verdi`) yalnız **ZONE** kartında ve yalnız zone teması tablosu | `FRM_TEYIT_HACIM` (FRM-10) + `FRM_RETEST_HACIM` (FRM-14) sabitleri + iki üretici (`Kurulum.rvol` zaten alarm barının rvol'u — yeni veri GEREKMEZ) → `AILE_OLCU["FRM"]` + ONCELIK + kanıt tabanı + `/olcum` girdisi; en fazla 3 satır sınırı korunur, aile süzgeci zone tablosuyla karışmayı imkânsız kılar | Kapılar, skorlar, mesaj sayısı; yalnız 1 `◇` satırı ve `/olcum` sözlüğü değişir |
| **Ö3** | `Kurulum.ph/pl` var (yakınlık/uyum ölçülüyor); **deneme sayısı yok**; Soru 6 tablosu (`PH %36→%8`, `PL %37,5→%33,3`) hiçbir yerde bağlı değil | **(a)** `◇ seviye` satırı (ph/pl 0,25 ATR içindeyse kova tablosu) · **(b)** MS rol defterinde PH/PL başına canlı yaklaşma sayacı → `Kurulum.seviye_deneme` · **(c)** `SEVIYE_TEST_SUSME=1` (varsayılan 0): 4+ denenen **tepe** altındaki LONG aday DM→özete; **PL'ye asla**; efekti Ö1 ölçer, kalıcı karar Ö2 stabil + `/evet` | Varsayılan: yalnız (a) satırı görünür; (c) kapalı; sinyal akışı Ö2+Ö1 ölçümü geçmeden değişmez |
| **Ö6** | MS hatası yalnız log + bellek içi `_ms_hata_sayaci` (restart'ta sıfır); başka domain boşlukları görünmez; KOZAL/KOZAA elle çıkarıldı | `_execute_domain` hata/boş-domain → `DATA_DIR/motor_sagligi.json` (son 7 gün, sembol×TF×domain, atomik) → `/durum` detay satırı + haftalık karne `veri sağlığı` uyarısı; `MOTOR_SAGLIK_BAND=N` ile elle çıkarmaya veri dayanağı | Tarama/evren/sinyal **aynen**; otomatik çıkarma YOK (yalnız uyarı) |

Ortak ilke: **hiçbiri varsayılan sinyal akışını değiştirmiyor**; değişiklik ya
ölçüm/kart referansı (Ö2, Ö4, Ö3a) ya da kapatılabilir musluk/uyarı (Ö1, Ö3c, Ö6).
Sinyal akışına dokunacak tek madde (Ö3c) iki ön koşula bağlı: Ö2 "stabil" + Ö1'in
iki sütunu ve kalıcıleşme `/evet` ile.

## 4. Daha gelişmiş bir sistem — bu önerilerin toplamı olarak

"Daha gelişmiş" yeni motor/model değil; **mevcut felsefenin (ölç → kart referansı →
gölge musluk → karne izleme → `/evet` kalıcı) dört eksik dikişinin kapanması**:

```
Ö2 sağlamlık ──► kural dönüşümüne izin verir (repo kuralı zaten bunu istiyor)
Ö1 süzgeç takibi ──► muslukları bilgiyle aç/kapa
Ö3 seviye testi ──► en güçlü bulguyu karta/süzgeçe bağlar (asimetri korunur)
Ö4 hacim fazları ──► tek yanlış imzayı üç doğru bağlama ayırır
Ö5/Ö7 deneyleri ──► ürün/puan kararlarını karne verisine bağlar
Ö6 sağlık sicili ──► boş-domain sınıfını görünür kılar
```

**Yapılmaması gerekenler** (değişmedi): opak modelle kuralı değiştirmek (ret/red
dilini öldürür); tek-genel-kural çıkarmak (hacim bunun kanıtı — fazlara bölünür);
ölçü "stabil" demeden süzgeç kalıcılaştırmak; eldekini işlemeden daha fazla veri
indirmek; ağır ML altyapısı (bu iş CPU'da tabular veriyle dönüyor).

## 5. Önerilen öncelik sırası

| Sıra | İş | Bağımlılık | Tahmini |
|---|---|---|---|
| 0 | MS düzeltmesi (→ denetim kaydı) | — | ✅ tamamlandı |
| 1 | **Ö2 sağlamlık matrisi** (`--pencere`) | yok | ~1,5 gün (4 koşu dahil) |
| 2 | **Ö1 süzgeç kaçakları** (paralel yapılabilir) | yok | 1 gün |
| 3 | **Ö4 `◇` hacim faz satırları** | yok | ~yarım gün |
| 4 | **Ö3a seviye-test `◇` satırı** | yok (Ö3c için Ö2 şart) | ~yarım gün |
| 5 | **Ö6 sağlık sicili** | yok | ~yarım gün |
| 6 | Ö7 karne bant satırı + Ö5 kanal denei | Ö7 için 2 hafta canlı karne | karne döngüsü |
| — | PUANLAMA §8 kendi adımları (gölge mod vb.) | mevcut plan | ayrıca |

**İlk hafta:** Ö2+Ö1+Ö4 — bir taraftan bulguların sağlamlığı kapanır, diğer taraftan
"elemek iyi eliyor mu" sorusunun cevabı ve kartta hacim dili doğru bağlanır. Yeni motor
yazmadan, eldeki 660 bin bar + karne defteri + `◇` mekanizmasıyla sistemi daha
geliştiren şey **kapanmış döngü** — sayısız "yeni özellik" değil.
