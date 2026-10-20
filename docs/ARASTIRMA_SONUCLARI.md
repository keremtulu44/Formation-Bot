# Araştırma Sonuçları — Soruların Cevapları

`docs/ARASTIRMA_BULGULARI.md` içindeki tabloların yorumu. Ölçüm tabanı:
**176 sembol × 4 zaman dilimi = 704 seri, 994.142 gözlem satırı**, 365 günlük
gerçek arşiv (`backfill_data/`). Her sayı o rapordaki bir tablodan alınmıştır;
tüm hücreler `n>=30` (YETERLI) güvenindedir aksi belirtilmedikçe.

> **Ölçüm birimi ve yön kuralı.** OB/FVG'de iki eksen birlikte ölçüldü:
> *yön-ancored* (zone'un kendi yönü) ve *kenar-ancored* (dokunulan kenardan
> uzağa: üst kenar → aşağı, alt kenar → yukarı). Tüm uzanımlar **ATR**
> cinsindendir. Sağdan sansürlü gözlemler başarı sayılmamıştır.

---

## 1. OB/FVG tek denemede mi doluyor, çok denemede mi?

**OB tekrar tekrar denenir; FVG pratikte tek denemeliktir.**

| | tek deneme | 2 deneme | 3+ deneme | hiç denenmedi | ort. epizot |
|---|---|---|---|---|---|
| OB (1h/2h/4h/1d) | %59.4–59.9 | %19.1–21.3 | %10.7–13.3 | %5.4–10.3 | 1.37–1.53 |
| FVG (2h/4h/1d) | %71.4–77.9 | %0.6–1.1 | **%0.0** | %20.9–27.9 | 0.73–0.80 |

FVG'de 3+ deneme oranı raporda **%0.0** görünür; ham sayı 55.145 zone'da
**4 adettir (%0.007, en fazla 5 epizot)**. Yani yuvarlama sıfır değil ama
pratik olarak sıfır: FVG zone'u ya tek temasta çözülüyor ya da hiç temas
almıyor. OB'de ise aynı oran **%12.9** (17.048 zone, en fazla 20 epizot) ve
zone'ların ~%24'ü iki veya daha fazla ayrı epizotla deneniyor.

Ayrıca FVG zone'larının **%23.0'ı (12.680) hiç temas almıyor** — yani doğup
ömrünü tamamlayan, fiyatın hiç geri dönmediği boşluklar. Bu oran OB'de %6.7
(8.797).

**Sonuç:** "kaç denemede doldu" sorusu OB için anlamlı, FVG için anlamsız;
FVG'de doğru soru "temas aldı mı, almadı mı".

## 2. %kaçı geçildi, %kaçı tepki aldı?

İki seviyede iki farklı cevap var ve ikisi birlikte okunmalı.

**Zone seviyesi (n=187.046):**

| | temas aldı | geçildi (fiyat ihlali) | tam dolum |
|---|---|---|---|
| OB | %89.7–94.6 | **%85.4–93.6** | %0.0 * |
| FVG | %72.1–79.1 | — | **%40.3–42.6** |

\* OB'de `native_full_fill` yapısal olarak her zaman `False`'tır
(`replay_ob_zones` kaldırma anında sabit `False` yazar). OB için geçerli
geçilme göstergesi `native_price_violation`'dır (`gap_through` +
`fill_cancel_threshold`). Bu bir ölçüm hatası değil, motorun kayıt sözleşmesi.

**Dokunuş seviyesi (n=240.484):** beklenen yönde ≥1 ATR tepki **%65.0–66.5**,
0.25–1 ATR arası %14.9–18.1, hiç tepki yok %4.1–4.8, **ters yönde %11.2–14.8**.
Ortalama uzanım ~2.0 ATR (h12).

**Bu iki bulgu birlikte hattın en önemli sonucu:** dokunuş anında zone'ların
üçte ikisi gerçekten tepki veriyor, ama zone'ların **~%90'ı eninde sonunda
geçiliyor**. Yani OB/FVG bir **bariyer değil, zamanlama aracıdır**. "Buradan
döner mi?" sorusunun cevabı %65 evet; "Burada kalıcı mı durur?" sorusunun
cevabı %90 hayır. Bot stratejisi bu ayrıma göre kurulmalı: zone teması giriş
zamanlaması için değerli, kalıcı destek/direnç olarak değersiz.

Zaman dilimleri arasında fark **şaşırtıcı derecede küçük** (%65.0–66.5 bant
içinde). Tepki oranı timeframe'den çok zone'un varlığına bağlı.

## 3. Kenar-ancored tepki: destek mi direnç mi daha güçlü?

**Destek tarafı (alt kenar) direnç tarafından daha büyük tepki üretiyor.**

| OB | ALT_KENAR (→yukarı) | UST_KENAR (→aşağı) | fark |
|---|---|---|---|
| 1h ort. h12 | 1.983 ATR | 1.779 ATR | +0.20 |
| 4h ort. h12 | 2.117 ATR | 1.869 ATR | +0.25 |
| 1d ort. h12 | 2.187 ATR | 1.660 ATR | **+0.53** |

FVG'de fark daha küçük ve 1d'de tersine dönüyor (ALT 1.842 / UST 1.812).
CALISTI oranları ise iki kenarda yakın (%54–63). Yani asimetri **sıklıkta
değil büyüklükte**: destek temasları daha sık değil ama daha sert tepki veriyor.

**Eşik ızgarası (h12 içinde aşım oranı):**

| | ≥0.25 ATR | ≥0.5 ATR | ≥1 ATR | ≥1.5 ATR | ≥2 ATR |
|---|---|---|---|---|---|
| 1h | %74.5 | %69.4 | %58.6 | %48.0 | %38.5 |
| 2h | %74.7 | %69.2 | %58.0 | %47.3 | %37.7 |
| 4h | %75.2 | %69.9 | %59.3 | %49.3 | %39.8 |
| 1d | %77.1 | %72.0 | %60.7 | %49.5 | %39.2 |

Dört zaman dilimi neredeyse üst üste. Pratik eşik olarak **1 ATR**: temasların
~%59'u en az 1 ATR tepki veriyor, ~%39'u en az 2 ATR.

> **Dürüst sınır:** temasların önemli bir kısmında yön belirlenemiyor. Çapa
> barı zone'un iki kenarına birden değdiğinde (`TUM_ZONE`) kenar-ancored ölçüm
> yapılamaz; bu pay 1h OB'de %21.5 (19.440/90.485), 4h OB'de ~%23. Bu
> satırlar ne yukarı ne aşağı sonuca karıştırıldı, `OLCULEMEDI` olarak ayrı
> duruyor. Yani kenar-ancored sonuçlar temasların ~%77'sine dayanıyor.

## 4. Yüksek zone ayırt edici mi? Tepki anlık mı, yavaş ama kalıcı mı?

**Evet, ayırt edici — ve cevap net: yüksek zone tepkisi anlık ve kalıcı;
alçak zone tepkisi yavaş gelişiyor ve geri veriyor.**

Zone yüksekliği arttıkça üç gösterge de **monotonik** aynı yönde hareket
ediyor (1d FVG örneği, n=6.285):

| yükseklik | n | h12_decay | uzun/ana tepe oranı | tepe_h12 | CALISTI |
|---|---|---|---|---|---|
| 0–0.5 ATR | 3.276 | 2.418 | 3.307 | 1.912 | %64.3 |
| 0.5–1 ATR | 1.989 | 1.956 | 3.338 | 1.989 | %64.7 |
| 1–2 ATR | 858 | 1.747 | 2.426 | 1.985 | %67.8 |
| **≥2 ATR** | 162 | **1.248** | **1.656** | **2.304** | **%71.0** |

Okuma:
- **`h12_decay` düşüyor** (2.418 → 1.248): yüksek zone'larda tepkinin çok daha
  azı pencere sonunda geri veriliyor.
- **`uzun/ana tepe oranı` düşüyor** (3.307 → 1.656): alçak zone'larda 40 barlık
  tepe 12 barlık tepenin 3.3 katı — yani hareket **sonradan** gelişiyor.
  Yüksek zone'larda oran 1.66 — hareket zaten ilk 12 barda gerçekleşmiş.
- **CALISTI artıyor** (%64.3 → %71.0) ve en yüksek kova en büyük tepeyi veriyor.

Aynı desen OB'de de var (1h: decay 2.130→1.853→1.572→**1.213**, oran
2.811→2.817→2.604→**2.180**) ve 2h FVG'de en belirgin haliyle: ≥2 ATR
kovasında tepe_h12 **2.839**, uzun tepe **4.926**, CALISTI **%71.7** — tüm
kovaların en yükseği.

**Pratik karşılığı:** yüksek zone (≥2 ATR) temasında tepki hızlı gelir ve
tutulur → kısa ufuklu hedef yeterli. Alçak zone (<0.5 ATR) temasında tepki
geç gelir ve geri verir → ya sabırlı ufuk ya da hiç girmemek.

## 5. MS: BOS/CHOCH yönü ile tepki uyuşuyor mu? Ne kadar devam ediyor?

**Neredeyse her zaman uyuşuyor: %97–98.** Ters yönde tepki yalnız **%0.5–1.2**.

| 4h | n | uyumlu | CALISTI | DEVAM_YOK | TERS | ort. devam |
|---|---|---|---|---|---|---|
| EXTERNAL BOS | 3.387 | %98.0 | %71.0 | %7.5 | %0.9 | 2.500 ATR |
| EXTERNAL CHOCH | 1.300 | %97.9 | %70.8 | %8.2 | %0.8 | 2.403 ATR |
| INTERNAL BOS | 6.505 | %97.0 | %68.2 | %9.2 | %1.0 | 2.408 ATR |
| INTERNAL CHOCH | 2.455 | %97.9 | %70.0 | %7.5 | %0.8 | 2.407 ATR |

**İki belirgin asimetri:**

1. **Yön:** yukarı BOS aşağı BOS'tan daha fazla devam ediyor. 4h EXTERNAL BOS
   UP: CALISTI %75.0 / 2.827 ATR; DOWN: %67.3 / 2.189 ATR. INTERNAL'de aynı:
   UP %72.2 / 2.779 vs DOWN %64.6 / 2.069. Bu, BIST'in 365 günlük penceresinde
   yükseliş kırılımlarının düşüş kırılımlarından ~%8 puan daha güvenilir
   olduğu anlamına geliyor.
2. **Scope:** `INTERNAL` olaylar `EXTERNAL`'dan sistematik olarak **biraz daha
   zayıf** takip veriyor (4h BOS: %68.2 vs %71.0). Kullanıcının istediği
   internal analizi bu: internal yapı daha çok sinyal üretiyor (6.505 vs 3.387)
   ama her biri biraz daha az güvenilir. Sıklık × güvenilirlik çarpımı yine de
   internal'i değerli kılıyor.

**Devam sınıfları** (ön-tanımlı: ≥1 ATR CALISTI, 0.25–1 AZ_DEVAM, <0.25
DEVAM_YOK, negatif TERS): "az takip" %17.7–23.2, "çalıştı" %64.6–75.0. Yani
**BOS/CHOCH sinyallerinin ~%70'i gerçekten çalışıyor**; zone'lardaki %65'ten
belirgin şekilde yüksek. MS, OB/FVG'den daha güvenilir bir yön teyidi.

## 6. PH/PL direnç/destek olarak karakterize edilebilir mi?

**Evet, ama asimetrik: çok denenen korunan-tepe (PH) çöker, çok denenen
korunan-dip (PL) büyük ölçüde tutar.**

Engelleme oranı, deneme sayısına göre (0.25 ATR yaklaşma bandı):

| deneme | PH 1d EXT | PH 1d INT | PH 4h EXT | PL 1d EXT | PL 1d INT |
|---|---|---|---|---|---|
| 1 deneme | %36.0 | %34.1 | %31.3 | %37.5 | %37.7 |
| 2–3 deneme | %22.6 | %21.0 | %23.0 | %28.9 | %30.0 |
| 4+ deneme | **%8.0** | **%19.8** | **%17.2** | **%33.3** | **%26.5** |

PH'da 1 → 4+ deneme arasında engelleme **%36'dan %8'e** düşüyor (1d external,
n=1.176). PL'de aynı aralık %37.5 → %33.3, yani **neredeyse hiç bozulmuyor**.

**Pratik karşılığı:** tekrar tekrar test edilen bir korunan tepe artık direnç
değildir — 4+ denemede %92 olasılıkla kırılır ve bot bunu tersine (kırılım
beklentisi) kullanabilir. Tekrar test edilen bir korunan dip ise güvenilir
kalmaya devam ediyor.

> **Okuma uyarısı:** `0_deneme` kovası %100 "engelledi" gösterir ama bu
> **tanımsal bir boşluktur** — seviyeye hiç yaklaşılmadığı için kırılmamıştır,
> başarılı direnç olduğu anlamına gelmez. Bu satırlar (1d EXT PH için n=664)
> yorum dışı bırakılmalıdır; asıl bilgi 1/2-3/4+ kovalarındadır. İlginç olan,
> bu hiç-test-edilmemiş seviyelerin rol süresinin uzun olması (ort. 20–43 bar):
> piyasa uzak seviyeleri uzun süre "korunan" etiketiyle taşıyor.

PH/PL sorusu **yalnız bu hat sayesinde cevaplanabildi**: motorun final
snapshot'ında `structural_role` zamanla sıfırlandığı için 359 swing içinde
yalnız 2 PROTECTED_HIGH ve 0 PROTECTED_LOW görünüyordu. Bar bar rol izlemesi
382.395 swing satırı ve 273.583 rol aralığı üretti.

## 7. WH/WL: %kaçı ziyaret/süpürüldü ve ne kadar sürede?

**Çoğu süpürülüyor ve çok hızlı: ortanca 3 bar.**

| 4h | n | ziyaret | süpürüldü | hiç ulaşılmadı |
|---|---|---|---|---|
| EXTERNAL WH | 3.854 | %70.5 | %59.3 | %40.7 |
| EXTERNAL WL | 4.126 | %71.2 | %60.4 | %39.6 |
| INTERNAL WH | 8.327 | %77.2 | %65.3 | %34.7 |
| INTERNAL WL | 8.190 | %80.9 | %69.9 | %30.1 |

**Seviyeye ulaşma süresi (rol atamasından itibaren, native bar):**

| | q25 | ortanca | q75 | ortalama |
|---|---|---|---|---|
| 1h WH / WL | 1 / 2 | **3 / 3** | 6 / 7 | 5.6 / 6.0 |
| 2h WH / WL | 1 / 2 | **3 / 3** | 6 / 7 | 5.4 / 5.6 |
| 4h WH / WL | 1 / 1 | **3 / 3** | 6 / 6 | 5.1 / 5.4 |
| 1d WH / WL | 1 / 1 | **3 / 3** | 5 / 6 | 4.9 / 4.7 |

Ortanca **her zaman diliminde tam 3 bar**. Bu, zayıf seviyelerin "er ya da
geç" değil **neredeyse hemen** test edildiği anlamına geliyor: WL/WH bir
hedef olarak kullanılacaksa ufuk 3-6 native bar olmalı, 20 değil.

`INTERNAL` seviyeler `EXTERNAL`'dan daha sık süpürülüyor (%77–81 vs %65–71) —
internal yapı daha gürültülü ve daha çabuk tüketiliyor. WL, WH'den her
timeframe'de ~3–5 puan daha sık süpürülüyor (BIST'in yukarı yönlü sürüklenmesi
düşükleri daha çabuk alıyor).

## 8. Hacim — koşullandırma değişkeni

**Sezginin tersi bir sonuç: dokunuş anında hacim ne kadar yüksekse, zone'un
beklenen yönündeki tepki o kadar ZAYIF.**

| rvol çeyreği | 1h CALISTI | 2h CALISTI | 4h CALISTI | 4h ort. h12 |
|---|---|---|---|---|
| Q1 (düşük) | %66.6 | %69.6 | **%70.1** | **2.272 ATR** |
| Q2 | %71.9 | %67.8 | %67.7 | 2.115 ATR |
| Q3 | %67.3 | %65.9 | %66.1 | 2.081 ATR |
| Q4 (yüksek) | **%61.3** | **%60.4** | **%61.0** | **1.868 ATR** |

Q4 her üç intraday zaman diliminde de **en düşük** tepki oranına sahip
(%60.4–61.3) ve Q1–Q4 farkı ~9 puan. Ortalama uzanım da aynı yönde düşüyor
(4h: 2.272 → 1.868 ATR).

Yorum: dokunuş anında yüksek göreli hacim, zone'un **zaten güçle
tüketilmekte** olduğunu gösterir — yani hacim burada "teyit" değil, "ihlal
mekte olan hareket" işaretidir. Sessiz (düşük rvol) temaslar ise zone'un
gerçekten test edilip dönüldüğü durumlar.

Bu, "hacim teyit eder" varsayımıyla filtre kuran bir stratejinin **ters
çalışacağını** söyler. En azından zone teması bağlamında hacim filtresi
tersine kullanılmalı ya da hiç kullanılmamalı.

1h'de Q2'nin Q1'den yüksek olması (%71.9 vs %66.6) desenin tam monotonik
olmadığını gösteriyor; sağlam olan kısım **Q4'ün her zaman en kötü olması**.

> `KULLANILAMAZ` satırları `volume_usable=False` gözlemlerdir (XU100/XU30
> gibi hacmi olmayan endeksler). Düşürülmedi, ayrı gösterildi: payda kaybı
> görünür olmalı.

---

## Ölçüm sırasında bulunan iki yapısal tuzak

İkisi de motorların **final snapshot'ından** ölçüm yapmayı geçersiz kılar;
ikisi de bu hatta çözüldü ve ikisi de canlı botu etkilemez (canlı yol
snapshot'ı ölçüm için kullanmıyor), ama gelecekte snapshot'tan backtest
yapmaya kalkışan herkesi etkiler.

**1. OB motoru dolan zone'ları listesinden siliyor.**
`OrderBlockEngine._update_existing` bir zone dolduğunda kaydı
`self._records`'tan çıkarıyor; geçmişi tutan bir liste yok. THYAO 4h'de
`replay_ob_zones` ile **138 zone**, final snapshot ile **18 zone** — 7.7×
eksik sayım. Snapshot'tan "%kaçı geçildi" ölçülseydi cevap baştan belli
olurdu, çünkü örneklem yalnız *geçilmemiş* zone'lardan oluşurdu.

**2. `structural_role` zamanla mutate oluyor.**
`clear_role_if_matches` bir rolü yeni swing'e atarken eski sahibini
`NEUTRAL_*`'a sıfırlıyor. Replay sonundaki listede yalnız güncel sahipler
kalıyor. Bu yüzden PH/PL ve WL/WH soruları final snapshot'tan **hiç**
cevaplanamazdı (2 PH / 0 PL / 0 WH-WL). Bar bar rol izlemesiyle 273.583 rol
aralığı çıkarıldı.

## Canlı botta bulunan sessiz MS çökmesi

**704 serinin 35'inde (%5.0)** MS motoru
`ValueError: confirmed break references must still be active` ile patladı:
1h'de 20, 2h'de 6, 4h'de 4, 1d'de 5 seri. Etkilenen semboller arasında AEFES,
ALFAS, ALGYO, BERA, BIOEN, BRKVY, CEMAS, CVKMD, CWENE, DIRIT, EBEBK, EUPWR,
FROTO ve GARFA var; tam liste `arastirma_cikti/meta.jsonl` içindeki
`ms_hata` alanındadır. AEFES 1h, ALFAS 1h ve ALGYO 2h üzerinde motorun kendi
`replay()` yolu çağrılarak ayrıca doğrulandı — hata bu hatta özgü değil.

Bu, bu hattın kodundan kaynaklanmıyor: canlı runner'ın `_run_market_structure`
içinde kullandığı `engine.replay(frame)` yolu birebir aynı hatayı veriyor.
`market_structure_runtime_bridge` hatayı yakalayıp kurtarmayı deniyor ama
kurtarma yolu da başarısız olunca hata yukarı fırlıyor.

Canlı botta `_execute_domain` bunu yuttuğu için **bot çökmüyor**; bunun
yerine o sembolün MS domaini **sessizce boş kalıyor** — BOS/CHOCH sinyali
üretilmiyor ve kullanıcıya hiçbir uyarı gitmiyor. 1h'de 20 sembol demek,
botun her gün ~20 sembol için yapısal kırılım sinyali hiç üretmemesi demek.

Ölçüm hattı hatayı izole ediyor: MS başarısız olsa bile OB/FVG/VP ölçülüyor,
hata `meta.ms_hata` alanında taşınıyor ve raporda `ms_hatali_seri` sütununda
sayılıyor. AEFES 1h için bu, aksi halde kaybolacak 419 zone ve 710 dokunuş
epizodunu kurtardı.

**Bu, araştırma tarafının değil canlı botun bir kusuru ve ayrıca ele alınmayı
hak ediyor.** Önerilen ilk adım: `_execute_domain` hata yakaladığında Telegram
tarafına bir "MS domain devre dışı" uyarısı düşürmek; sessiz boşluk yerine
görünür degrade. Kök neden (`finalize_confirmed_break` içinde referans
swing'lerin aktif olmaması) ayrı bir iş.

---

## Sınırlar ve dürüstlük notları

- **Tek 365 günlük pencere.** Tüm bulgular Mayıs 2025 – Ekim 2026 arasına ait
  tek bir rejim örneğidir. Rejim değişiminde (ör. uzun ayı piyasası) özellikle
  5. bölümdeki yön asimetrisi tersine dönebilir.
- **Sembol havuzu BIST likit ~177 hisse.** Küçük/likit olmayan hisselerde zone
  davranışı farklı olabilir; arşiv bu havuzu temsil ediyor.
- **`BRENT` havuz dışı bırakıldı** (BIST seans yapısı yok, ~24 saat işlem).
- **Sansür:** zone ömrü ölçümlerinde %0.3–14.6 arası sağdan sansürlü
  (1d OB'de %14.6). Bunlar "başarılı direnç" sayılmadı.
- **`TUM_ZONE` payı ~%21–23:** kenar-ancored sonuçlar temasların ~%77'sine
  dayanıyor; kalanında yön tanımsız.
- **Motor parametreleri değiştirilmedi.** Ölçüm, botun canlıda kullandığı
  "Dengeli" profiliyle üretildi; farklı profil farklı zone popülasyonu verir.
- Bu bir **istatistiksel ölçümdür, işlem stratejisi backtest'i değildir.**
  Maliyet, kayma, pozisyon boyutu ve çıkış kuralı modellenmedi. "CALISTI
  %65" ifadesi kârlılık değil, ≥1 ATR'lik yönlü uzanım sıklığıdır.
