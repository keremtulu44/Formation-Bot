# Stabil Ok Sistemi (`▲` / `▼`), Yapısal Bağlam Hizalaması ve İkili `(S, R)` Koridor Dinamikleri — Kapsamlı Tasarım Püf Noktaları ve Tüm Geçmiş Replay Sentezi

**Tarih:** 2026-11-09  
**Statü:** Tasarım ve ampirik sentez referans belgesi; sonraki uygulama çalışmaları bu tarihten sonra kodu değiştirebilir. Yeni replay çalıştırılmamıştır.  
**Kapsam:** Konuşulan tüm grafik gözlemleri, mimari kırmızı çizgiler, sığ/nedensel bağlam kuralları, ikili `(Stabil S, Stabil R)` etkileşimleri ve depodaki **tüm geçmiş replay çalışmalarının** (alttan üste, üstten alta, destek, direnç, piyasa yapısı `MS`, formasyon ve kırılım/teyit) değiştirilmemiş gerçek sayılarıyla kurulan mantıksal sentez.

> **Sayısal Dürüstlük Sözleşmesi:** Bu belgedeki her oran, örneklem büyüklüğü (`n`), medyan ATR ve `p` değeri doğrudan `docs/arastirma/` altındaki kayıtlı replay raporlarından **hiçbir rakam değiştirilmeden veya uydurulmadan** alınmıştır. Geçmişte iki katmanın aynı bar üzerinde birlikte sayılmadığı (ör. `Stabil S` ve `Stabil R` aynı-bar koridor genişliği) kesitlerde sahte sayı üretilmemiş; doğrudan ölçülmüş iki ayrı bulgunun mekanik birleşimi ile henüz birlikte ölçülmemiş kesit açıkça ayrılmıştır.

---

> **Düzeltme / okuma rehberi:** Bu metindeki tasarım önerileri uygulanmış kurallar veya ispatlanmış performans değildir. Doğrudan ölçüm, gözlemsel ilişki ve birlikte ölçülmemiş hipotez birbirinden ayrılmalıdır. Özellikle ikinci temas otomatik alım onayı değildir; 7–8 mumun optimal olduğu ölçülmemiştir. Altı boş ve ikili S/R yorumları tüm TF’lerde araştırılacak gözlemlerdir, zorunlu piyasa yasaları değildir. Aşağıdaki eski başlıklarda geçen “kanıt” sözcüğü, yalnız atıf yapılan ölçümün kendi tanımı için okunmalıdır.

> **Son karar güncellemesi:** Önceki kapanışı destek altında olan fiyatın yalnız güçlü tek mumla üstüne çıkmasına dayalı `close_reclaim` oku kullanıcı isteğiyle iptal edilecek. Aynı mum fitil sarkması (`intrabar_sweep_reclaim`) iptal edilmedi. Bu karar, eski bölümlerdeki “mevcut çekirdek korunur” önerilerine üstün gelir; kod hâlâ değiştirilmemiştir. Ayrıntı §3.13.

## İçindekiler

1. [Mevcut Mimari Gerçeklik ve Katman Körlüğü](#1-mevcut-mimari-gerçeklik-ve-katman-körlüğü)
2. [Tasarım Felsefesi ve İki Kesin Kırmızı Çizgi](#2-tasarım-felsefesi-ve-iki-kesin-kırmızı-çizgi)
   - 2.1 [Hizalama Kapsamı: Yalnız `Stabil (S, R)` + `Market (MS)` + `Formasyon`](#21-hizalama-kapsamı-yalnız-stabil-s-r--market-ms--formasyon)
   - 2.2 [Kırmızı Çizgi 1: `Blok` (`OB` / `FVG`) İle Hizalama Yapılmaz](#22-kırmızı-çizgi-1-blok-ob--fvg-ile-hizalama-yapılmaz)
   - 2.3 [Kırmızı Çizgi 2: Çok Derin / İç İçe Filtre Ağaçları Kurulmaz](#23-kırmızı-çizgi-2-çok-derin--iç-içe-filtre-ağaçları-kurulmaz)
3. [Konuşulan Tüm Püf Noktalarının Ayrıntılı Teknik Analizi ve Replay Kanıtları](#3-konuşulan-tüm-püf-noktalarının-ayrıntılı-teknik-analizi-ve-replay-kanıtları)
   - 3.1 [Püf Noktası 1 — Yakın Tarihli Ters `BOS` / `CHoCH` Baskısı ve Zaman Dilimine Göre Değişken Mum Penceresi](#31-püf-noktası-1--yakın-tarihli-ters-bos--choch-baskısı-ve-zaman-dilimine-göre-değişken-mum-penceresi)
   - 3.2 [Püf Noktası 2 — Formasyon İçi Simetrik Sıkışma (`Stabil S ↔ upper_now`, `Stabil R ↔ lower_now`) ve Sınır Hizalaması](#32-püf-noktası-2--formasyon-içi-simetrik-sıkışma-stabil-s--upper_now-stabil-r--lower_now-ve-sınır-hizalaması)
   - 3.3 [Püf Noktası 3 — Ok Sonrası `1–3` Mumda Ters `BOS` İle Ezilme: Nedensel İptal / Sönümleme](#33-püf-noktası-3--ok-sonrası-13-mumda-ters-bos-ile-ezilme-nedensel-iptal--sönümleme)
   - 3.4 [Tekrar test: gözlem, tepki ve yorulma](#34-tekrar-test-gözlem-tepki-ve-yorulma-birbirinden-ayrılır)
   - 3.5 [Püf Noktası 5 — Evrensel / Fraktal "Altı Boş" (ve Aynası "Üstü Boş") Kuralı: Tüm Zaman Dilimlerinde Aynı Etki](#35-püf-noktası-5--evrensel--fraktal-altı-boş-ve-aynası-üstü-boş-kuralı-tüm-zaman-dilimlerinde-aynı-etki)
   - 3.6 [Püf Noktası 6 — `◇` (Kare / Eşkenar Dörtgen) İşaretinin Anlamsızlığı ve Kaldırılması](#36-püf-noktası-6----kare--eşkenar-dörtgen-işaretinin-anlamsızlığı-ve-kaldırılması)
   - 3.7 [Püf Noktası 7 — Aynı Bardaki İkili `(Stabil S, Stabil R)` Koridor Dinamikleri: Mesafe, Daralma ve Asimetrik Basamaklar](#37-püf-noktası-7--aynı-bardaki-ikili-stabil-s-stabil-r-koridor-dinamikleri-mesafe-daralma-ve-asimetrik-basamaklar)
   - 3.8 [Püf Noktası 8 — Dikey `R` + Altta Hizalı `S` (Kontrollü Düzeltme) vs Yatay `R` + Destek Kaybı (Kontrolsüz / Sert Düşüş)](#38-püf-noktası-8--dikey-r--altta-hizalı-s-kontrollü-düzeltme-vs-yatay-r--destek-kaybı-kontrolsüz--sert-düşüş)
   - 3.10 [Desteğin altına sarkıp tekrar üstüne çıkması](#310-desteğin-altına-sarkıp-tekrar-üstüne-çıkması-kaçırılan-olaylar)
   - 3.9 [Ek Mekanik Püf Noktası — 4S ve Alt Zaman Dilimlerinde Ok Gücü Birim Kayması (`ATR_TF` vs `ATR_1G`) ve `18:00` Kısa Kova Etkisi](#39-ek-mekanik-püf-noktası--4s-ve-alt-zaman-dilimlerinde-ok-gücü-birim-kayması-atr_tf-vs-atr_1g-ve-1800-kısa-kova-etkisi)
4. [Geçmişteki Tüm Replay Çalışmalarının Yön Farketmeksizin Bütüncül Kanıt Envanteri](#4-geçmişteki-tüm-replay-çalışmalarının-yön-farketmeksizin-bütüncül-kanıt-envanteri)
   - 4.1 [Alttan Üste (`Destek Geri Alımı`, `Temas`, `▲`, `Yükselen Basamak`) Bulguları](#41-alttan-üste-destek-geri-alımı-temas--yükselen-basamak-bulguları)
   - 4.2 [Üstten Alta (`Direnç Dönüşü`, `▼`, `üst -> alt` Geçişleri, `Alçalan Basamak`) Bulguları](#42-üstten-alta-direnç-dönüşü--üst---alt-geçişleri-alçalan-basamak-bulguları)
   - 4.3 [Simetrik Eş-Kural (`Destek` ↔ `Direnç`) Karşılaştırma ve Yol Bulguları](#43-simetrik-eş-kural-destek--direnç-karşılaştırma-ve-yol-bulguları)
   - 4.4 [`Market Structure` (`BOS`, `CHoCH`, `PH/PL`, `WH/WL`) ve `Formasyon` Yaşam Döngüsü Bulguları](#44-market-structure-bos-choch-phpl-whwl-ve-formasyon-yaşam-döngüsü-bulguları)
5. [Kanıt Sınırları: Doğrudan Ölçülenler, Mekanik Çıkarımlar ve Henüz Birlikte Sayılmamış Kesitler](#5-kanıt-sınırları-doğrudan-ölçülenler-mekanik-çıkarımlar-ve-henüz-birlikte-sayılmamış-kesitler)
6. [Sığ ve Yüksek İsabetli Hedef Mimari Özeti (Uygulama Öncesi Referans Tablosu)](#6-sığ-ve-yüksek-isabetli-hedef-mimari-özeti-uygulama-öncesi-referans-tablosu)

---

## 1. Mevcut Mimari Gerçeklik ve Katman Körlüğü

Canlı kod tabanında grafik üzerinde yan yana çizilen katmanlar çalışma anında birbirinden tamamen izoledir:

| Katman | Üreten Modül | Ne Üretir? | Kimi Görür / Görmez? |
|---|---|---|---|
| **Stabil Destek (`S`) ve `▲`** | `domain_engines/stabil/stabil_support_lifecycle.py` + `signals.py` | Günlük `daily_pivot_len = 4` ile teyitli son pivot dip (`S = last_l`), `support_floor = S - 0,35 × ATR_köken`, dolu `▲` (`close_reclaim`, `intrabar_sweep_reclaim`), boş `▲` (`momentum`), `◇` (`_DIKEY_UYARI_SOGUMA_BAR = 50`). | Yalnız hedef OHLCV ve kendi günlük `S` projeksiyonunu görür. **`Stabil R`'yi, `BOS/CHoCH`'u ve `Formasyon` sınırlarını hiç görmez.** |
| **Stabil Direnç (`R`) ve `▼`** | `domain_engines/stabil/resistance.py` + `chart_bridge.py` | Fiyat ekseninde aynalanmış (`O'=-O, H'=-L, L'=-H, C'=-C`) aynı günlük çekirdekten teyitli son pivot tepe (`R = last_h`), `resistance_ceiling`, dolu `▼` (`close_return_below`, `intrabar_sweep_rejection`), boş `▼`, `◇`. | `domain_engines/runner.py` içinde bile koşmaz; **yalnız grafik çizilirken** `chart_bridge.py` üzerinden eklenir. **`Stabil S`'yi, `MS`'i ve `Formasyon`'u hiç görmez.** |
| **Market (`MS`)** | `domain_engines/market_structure/market_structure_state.py` | `EXTERNAL` ve `INTERNAL` kapsamda `STATE_BULLISH/BEARISH`, `EVENT_BOS`, `EVENT_CHOCH`, `EVENT_SWEEP`, `EVENT_FALSE_BREAK` ve `PH / PL / WH / WL` yapısal rolleri. | Kendi OHLCV serisinde çalışır; Stabil oklarının o barda basılıp basılmadığını bilmez. |
| **Formasyon** | `patterns/lifecycle.py` (`ArgentEngine`) | Üçgen/kama/bayrak/kanal geometrisi (`upper_now`, `lower_now`, `progress`, `contraction`), yaşam döngüsü (`TANIMLANDI`, `OLGUNLASIYOR`, `SIKISMA_GUCLENIYOR`, `KIRILIM_HAZIRLIGI`, `KIRILIM_ADAYI`, `KIRILIM_TEYITLI`, `BASARISIZ_KIRILIM`, `FORMASYON_GECERSIZ`) ve TF-ölçekli geçersizleşme bar sayısı (`_invalidation_confirm_bars`: `1s/2s = 2`, `4s/1g = 1`). | Kendi sınırlarını ve teyit skorunu hesaplar; Stabil oklarını görmez. |
| **Grafik Birleştirici** | `grafik/tarama.py` + `grafik/render.py` | Bütün çıktıları aynı PNG karesi üzerine üst üste çizer (`▼` okunu aynı mum çakışmasını önlemek için `x + 0,16` sağa kaydırır). | Görsel üst üste bindirme yapar; katmanlar arası mantıksal çelişkileri süzmez. |

**Temel Teşhis:** Kullanıcı grafikte **aynı anda** hem formasyon sınırını, hem son `BOS`/`CHoCH` kırılımını, hem de hem yeşil `Stabil S` hem turuncu/kırmızı `Stabil R` çizgilerini tek bir bütün olarak okurken; ok motorları (`signals.py` ve `resistance.py`) tek bir çizgiye ve tek bir mumun gövdesine bakarak karar vermektedir. Katman körlüğü olası nedenlerden biridir; tüm yanlış veya kaçırılmış okların nedeni olduğu ölçülmemiştir.

---

## 2. Tasarım Felsefesi ve İki Kesin Kırmızı Çizgi

### 2.1 Hizalama Kapsamı: Yalnız `Stabil (S, R)` + `Market (MS)` + `Formasyon`

Stabil oklarının (`▲` / `▼`) anlamlı ve yüksek isabetli olması için bakılacak bağlam evreni **üç yapısal sütunla** sınırlıdır:
1. **İkili Stabil Çekirdeği (`S` ve `R` birlikte):** Çizginin yatay/dikey rejimi, iki çizgi arasındaki koridor açıklığı ve karşı duvar yakınlığı.
2. **Market (`market_structure`):** Yakın tarihli `BOS` / `CHoCH` yönü ve ok sonrası hızlı ters `BOS` ezilmesi.
3. **Formasyon (`patterns`):** Fiyatın aktif formasyonun içinde sıkışıp sıkışmadığı (`upper_now` / `lower_now` mesafesi) ve formasyon alt/üst sınırıyla Stabil çizgisinin hizalanması.

---

### 2.2 Kırmızı Çizgi 1: `Blok` (`OB` / `FVG`) İle Hizalama Yapılmaz

> **İlke:** `Order Block` (`OB`) ve `Fair Value Gap` (`FVG`) bölgeleri ok üretimine, ok bastırmasına veya çapraz filtrelemeye **kesinlikle dahil edilmez**. Blokların değerlendirilmesi tamamen kullanıcının görsel hassasiyetine ve takdirine bırakılır.

Bu karar kullanıcı tercihidir; aşağıdaki çalışmalar bazı kesitlerde ilave ayrımın sınırlı kaldığını gösterir, tüm blok türleri için istatistiksel zorunluluk veya nedensel kanıt değildir:

1. **174 Hisse 4S Stabil Ok Bağlam Replay'i (`stabil_ok_replay_2026_11_05/toplu_bulgular.md`, `555` geçerli `▲`):**
   - `▲` oku çıktığı anda hemen üstte **yakın aktif bearish `OB` (`≤ 1 ATR`, `n = 167`)** varken zayıf tepki oranı **`%25,1`**, `8×4s` medyan kapanış `-0,06 ATR`, `+1 ATR` önce **`%47,9`** / `-1 ATR` önce **`%46,7`**.
   - Bearish `OB` **uzaktayken (`> 1 ATR`, `n = 321`)** zayıf tepki oranı **`%25,9`**, `+1 ATR` önce **`%50,2`** / `-1 ATR` önce **`%42,4`**.
   - Seçili yakın `FVG` (`≤ 1 ATR`, `n = 83`) varken `+1 ATR` önce **`%47,0`** vs `FVG` yokken (`n = 343`) **`%50,1`**.
   - **Sonuç:** Öndeki yakın `OB` veya `FVG` varlığı Stabil `▲` okunun başarısını istatistiksel olarak **hiç ayrıştırmamaktadır** (`%25,1` vs `%25,9` zayıf tepki).
2. **176 Sembol Formasyon Çapraz Replay'i (`FORMASYON_SONUCLARI.md` FRM-19, `n = 32.137` kırılımlı formasyon):**
   - Kırılım anında fiyat canlı bir `OB`/`FVG` zone'u içindeyse tamamlanma **`%75,9` (`n = 11.905`)**, zone yoksa **`%77,0` (`n = 20.232`)**; fark **`-1,1` puan** (`OB` var `-1,4` puan, `FVG` var anlamlı fark yok).
3. **704 Seri Arşiv Zone Replay'i (`ARASTIRMA_SONUCLARI.md` Soru 2, `187.046` zone / `240.484` dokunuş & `REPLAY_SORU_YANITLARI` S07):**
   - Dokunuşta `%65,0–66,5` tepki görülse bile `OB` zone'larının **`%85,4–%93,6`'sı** ömrü içinde fiyat tarafından delinip geçilmektedir ve tüm dokunuşların **`%65,3`'ü (`158.789 / 243.256`)** temas barında zaten `terminal` olmaktadır.
   - Bu sonuçlar blokların değişken davranışını gösterir; otomatik eşlemenin kaybı doğrudan ölçülmemiştir. Kullanıcı kararıyla bloklar dışarıda kalır.

---

### 2.3 Kırmızı Çizgi 2: Çok Derin / İç İçe Filtre Ağaçları Kurulmaz

> **İlke:** 4–5 koşulu `VE` (`AND`) ile üst üste bağlayan derin filtreler (`gövde ∧ hacim ∧ kapanış yeri ∧ temas sayısı ∧ trend ∧ ...`) **kurulmaz**. Her ok kararı **sığ (1-katmanlı), nedensel ve doğrudan yapısal** kalmalıdır.

Depodaki doğrulama çalışmaları derin filtrelerin neden yanıltıcı olduğunu kesin rakamlarla kanıtlamıştır:

1. **Kompozisyon Yanılsaması Kanıtı (`STABIL_SORU_SETI_V2_2026-11-08.md` & `genel_okuma_2026_11_08.csv`, 119 sembol, `n = 5.530` olay):**
   - Tüm olaylar tek havuzda toplandığında (`A1 havuz`) yüksek hacim (`DOWN lift +4,9`, `p = 0,0007`), büyük gövde (`DOWN lift +4,3`, `p = 0,0002`) ve alt kapanış (`DOWN lift +6,2`, `p < 0,0001`) güçlü birer filtre gibi görünmektedir.
   - Ancak senaryo-stratifiye **Mantel–Haenszel (`A2 MH`)** testi uygulandığında bu ilişkinin `Cramér's V = 0,383` düzeyinde bir **senaryo karışımı yanılsaması** olduğu ortaya çıkmıştır: aynı senaryo içinde `rvol yüksek vs düşük` doğrulamada **`OR = 0,93` (`p = 0,5463`)**, `gövde büyük vs yönsüz` **`OR = 0,93` (`p = 0,6087`)**, `kapanış üst vs alt` **`OR = 0,85` (`p = 0,2802`)** ile tamamen sıfırlanmıştır.
   - Dahası mum filtresini tüm olaylara tek başına uygulamak (`A5 kontrol`) doğrulamada yalnız `+2,9` puan (`p = 0,0601`) verirken; **doğru yapısal geçiş ailesi (`OK-▼` ailesi) üzerine yalnızca tek bir sığ kapı (`rvol ≥ 0,8 & gövde ≥ 0,20`)** koymak `DOWN` isabetini keşifte **`%56,9` (`n = 466`, `lift +12,8`, `p < 0,0001`)** ve doğrulamada **`%57,4` (`n = 188`, `lift +14,0`, `p = 0,0001`)** seviyesine taşımıştır.
2. **8 Bayrak Denetimi (`OK_SISTEMI_2026-11-08.md` §11, 176 sembol, `748` dolu `▲`):**
   - `▲` oklarının üzerine eklenen ekstra mikro bayraklar (`SESSIZ`, `TEKRAR` vb.) keşifte `-5,4` puan iyi görünürken doğrulama kümesinde **`+11,0` puan ters yönde** (`temiz %47,7` vs `bayraklı %58,7`) sonuç vermiştir.
3. **Sonuç:** Güç, mikro mum kurallarını derinleştirmekten değil; **yanlış yapısal bağlamda (ters taze `BOS`, altı boş dikey basamak, formasyon tavan/taban sıkışması, karşı duvar dibi) ok basmamaktan** gelir.

---

## 3. Konuşulan Tüm Püf Noktalarının Ayrıntılı Teknik Analizi ve Replay Kanıtları

### 3.1 Püf Noktası 1 — Yakın Tarihli Ters `BOS` / `CHoCH` Baskısı ve Zaman Dilimine Göre Değişken Mum Penceresi

#### Grafik Gözlemi ve Mekanizma
Fiyat aşağı yönlü net bir yapı kırılımı (`DOWN BOS` veya `DOWN CHoCH`) yaptıktan hemen birkaç mum sonra, Stabil desteğine (`S`) çarpıp tek bir yeşil tepki mumu yaptığında mevcut motor bunu "güçlü geri alım (`▲`)" sanmaktadır. Oysa taze kırılımın satış dalgası henüz tükenmediği için bu tek yeşil mum yalnızca bir "tepki / likidite alma mumu" olmakta ve fiyat hemen ardından desteği kırıp düşüşe devam etmektedir. Aynı durum simetrik olarak yukarı `BOS` sonrası ilk kırmızı mumda çıkan erken `▼` için de geçerlidir.

#### Neden Sabit Mum Sayısı Değil, Zaman Dilimine (`TF`) Göre Değişken Pencere?
- `1 saatlik` grafikte 1 işlem günü **8–9 mum** sürerken, `2 saatlik` grafikte **~4–5 mum**, `4 saatlik` grafikte **3 mum**, `günlük` grafikte ise **1 mum** sürer.
- Örneğin sabit "son 6 mum" kuralı yazılsaydı: `1s` grafikte yalnızca yarım seansı (6 saati) kapsarken, `1g` grafikte tam 1,2 haftayı (6 işlem gününü) kapsardı.
- Nitekim `patterns/lifecycle.py` içindeki formasyon motoru da teyit/geçersizleşme penceresini zaman dilimine göre ölçeklemektedir (`_invalidation_confirm_bars`: `1s/2s` daha geniş, `4s/1g` daha sıkı).
- Bu nedenle "yakın tarihli ters `BOS` / `CHoCH`" bastırma penceresi `N_tf` mutlaka zaman dilimine göre kademelendirilmelidir:
  - **Örnek yapısal ölçek mantığı:** `1s` için daha geniş bar penceresi (ör. ~`8–12` bar ≈ 1–1,5 seans), `2s` için orta pencere (ör. ~`5–8` bar), `4s` için kompakt pencere (ör. ~`3–5` bar ≈ 1–1,5 gün), `1g` için kısa pencere (ör. ~`2–3` bar).
  - **Yapısal sıfırlama (erken çıkış) koşulu:** Pencere süresi dolmadan önce ok yönünde yeni bir karşı `CHoCH` / `BOS` oluşursa ters kırılım baskısı yapısal olarak sona ermiş sayılır (körü körüne bar sayılmaz).

#### Geçmiş Replay Kanıtları (Değiştirilmemiş Sayılarla)
1. **`BOS` / `CHoCH` Yön Uyumunun Gücü (`ARASTIRMA_BULGULARI.md` Soru 5, 176 sembol × 4 TF = 704 seri, `200.028` olay):**
   - Teyitli bir `BOS` veya `CHoCH` olayından sonra fiyatın kırılım yönüyle uyumu **`%93,2 – %98,2`** aralığındadır; tamamen ters yönde kalma (`TERS`) tüm zaman dilimlerinde yalnızca **`%0,5 – %4,0`**'tür!
   - `DOWN EXTERNAL BOS` sonrası `≥ 1 ATR` aşağı devam (`CALISTI`) oranı: `1s` **`%67,2`** (`n = 4.725`, ort. devam `2,129 ATR`), `2s` **`%64,3`** (`n = 2.696`, ort. `2,064 ATR`), `4s` **`%67,0`** (`n = 1.777`, ort. `2,180 ATR`), `1g` **`%60,1`** (`n = 928`, ort. `1,747 ATR`).
   - `UP EXTERNAL BOS` sonrası `≥ 1 ATR` yukarı devam oranı daha da yüksektir: `1s` **`%67,8`**, `2s` **`%69,8`**, `4s` **`%75,0`** (`ort. 2,843 ATR`), `1g` **`%77,2`** (`ort. 2,830 ATR`).
2. **İlk Barda ve İlk 3 Barda Momentum Yoğunlaşması (`REPLAY_SORU_YANITLARI_2026-10-29.md` S26, `n = 57.647` BOS):**
   - Bir `BOS` kırılımından sonraki 12 barlık toplam devam hareketinin **medyan `%60`'ı ilk `3` barda** gerçekleşmekte, hareketin medyan tepesi **`6.` barda** oluşmaktadır.
   - Yani taze bir ters `BOS`'tan sonraki ilk birkaç bar, karşı yönlü ok basmak için istatistiksel olarak **en tehlikeli darbe bölgesidir**.
3. **Neden "Statik MS Durumu" Değil, "Taze `BOS` Yaşı" Gerekir? (`stabil_ok_replay_2026_11_05` & `S25`):**
   - 174 hisse 4s ok replay'inde yalnızca statik `external_ms_state == BEARISH` etiketine bakıldığında (`n = 265`) zayıf ok oranı `%26,4` vs `BULLISH` (`n = 74`) `%24,3` çıkmıştır. Neden? Çünkü `S25` (`202.938` olay) göstermektedir ki geçmiş `BOS` olaylarının `%93,2–%96,4`'ü zaman içinde yaşlanıp `SUPERSEDED` olmaktadır; 40 bar önce `BEARISH` olmuş ve taban örmüş bir yapıyla, **2 bar önce taze `DOWN BOS` yapmış** bir yapı aynı kefeye konduğunda etki sulanmaktadır. Aynı şekilde `HORIZONTAL_AFTER_DROP` (düşüş sonrası ilk yataylaşma, `n = 213`) rejiminde basılan 4s `▲` oklarında `DOWN_FIRST` oranı **`%51,2`** ile `UP_FIRST` (`%45,5`) oranını geçmekte ve medyan kapanış **`-0,30 ATR`** olmaktadır.
4. **Çizgiye İlk Yaklaşmada Momentumun Üstünlüğü (`stabil_destek_direnc_karsilastirma_2026_11_06`, 174 hisse, Y2026 `8×4s`):**
   - Desteğe yukarıdan sert gelen `TEST` olaylarında (`n = 1.616`) tepki `%41,3` iken **aşağı kırılma `%51,6`**; dirence aşağıdan sert gelen `TEST` olaylarında (`n = 1.241`) aşağı tepki `%42,1` iken **yukarı kırılma `%51,6`**'dır. Bu TEST kesitinde taze BOS koşulu ayrı ölçülmemiştir; oran doğrudan BOS’a bağlanamaz.

---

### 3.2 Püf Noktası 2 — Formasyon İçi Simetrik Sıkışma (`Stabil S ↔ upper_now`, `Stabil R ↔ lower_now`) ve Sınır Hizalaması

#### Grafik Gözlemi ve Simetrik Mekanizma
Fiyat aktif bir üçgen, kama veya daralan kanalın (`ArgentEngine`: `TANIMLANDI`, `OLGUNLASIYOR`, `SIKISMA_GUCLENIYOR`, `KIRILIM_HAZIRLIGI`) içindeyken iki simetrik tuzak oluşur:
1. **Alttan Üste İç Tavan Sıkışması (`▲` Tuzağı):** Fiyat `Stabil S` desteğinden sekip `▲` üretir, fakat aktif formasyonun alçalan üst çizgisi (`upper_now`) hemen `0,2–0,4 ATR` tepededir. Fiyat formasyon üst sınırına çarpıp geri döner; ok formasyon içi gürültüde boğulur.
2. **Üstten Alta İç Taban Sıkışması (`▼` Tuzağı):** Fiyat `Stabil R` direncinden dönüp `▼` üretir, fakat aktif formasyonun yükselen alt çizgisi (`lower_now`) hemen altındadır. Aşağı hareket alanı (`runway`) yoktur.
3. **Buna Karşılık Sınır + Kırılım Hizalaması:** Eğer `▲` oku formasyonun yukarı kırılımıyla (`close > upper_now`, `KIRILIM_ADAYI` / `KIRILIM_TEYITLI`) veya alt sınır (`lower_now`) ile `Stabil S`'nin çakıştığı geniş bantlı bir yapıyla hizalıysa; ya da `▼` oku formasyonun aşağı kırılımıyla (`close < lower_now`) hizalıysa iki katman birbirini doğrular.

#### Geçmiş Replay Kanıtları (Değiştirilmemiş Sayılarla)
1. **Formasyon İç Bandının Doğal Darlığı (`FORMASYON_SONUCLARI.md` FRM-02 & FRM-04, `n = 33.964` formasyon):**
   - Depodaki `33.964` formasyonun doğum anındaki medyan genişliği bile oldukça dardır:
     - `Alçalan Üçgen` (`n = 9.794`, pay `%28,8`): medyan genişlik **`0,34 ATR`**
     - `Yükselen Üçgen` (`n = 7.736`, pay `%22,8`): medyan genişlik **`0,38 ATR`**
     - `Alçalan Kama` (`n = 6.556`, pay `%19,3`): medyan genişlik **`0,46 ATR`**
     - `Yükselen Kama` (`n = 6.862`, pay `%20,2`): medyan genişlik **`0,51 ATR`**
     - `Simetrik Üçgen` (`n = 2.971`, pay `%8,7`): medyan genişlik **`0,52 ATR`**
   - Üstelik `FRM-04`'e göre kırılıma kadar bu genişlik medyan **`%76,6`** (`ÇGA %63,4–%86,2`) oranında daha da daralmaktadır!
   - **Mekanik Sonuç:** Kırılım öncesi olgunlaşmış bir formasyonun üst ve alt çizgisi arasındaki toplam boşluk çoğu zaman **`0,10 – 0,40 ATR`** mertebesindedir. Bu daracık koridorun içinde kırılım olmadan basılan herhangi bir `▲` veya `▼` okunun karşı sınıra çarpmadan `1 ATR` yol alması geometrik olarak imkânsızdır.
2. **Yapısal Hizalamanın Tamamlanma Oranına Etkisi (`FRM-20`, `n = 31.960`):**
   - Formasyon kırılım yönü en yakın yapısal rol (`PH`/`PL`) yönüyle uyumlu olduğunda tamamlanma oranı **`%79,6` (`n = 17.103`)**, uyumsuz olduğunda **`%73,2` (`n = 14.857`)**; net fark **`+6,4` puan** (`%95 GA +5,3…+7,5`).

---

### 3.3 Püf Noktası 3 — Ok Sonrası `1–3` Mumda Ters `BOS` İle Ezilme: Nedensel İptal / Sönümleme

#### Grafik Gözlemi ve Nedensel Mekanizma (Üzerinde Tam Mutabık Kalınan Madde #2)
- Bir mum kapanışında tüm kurallar sağlandığı için `t₀` barında `▲` (veya `▼`) oku haklı olarak basılmış olabilir.
- Ancak piyasa hemen `t₀ + 1`, `t₀ + 2` veya `t₀ + 3` barında sert bir ters dalgayla hem okun seviyesini kırar hem de ters yönde teyitli bir **`BOS` / `CHoCH`** üretirse, o ok artık yapısal olarak **ezilmiş (invalidated)** demektir.
- **Anti-Lookahead (Nedensellik) Kuralı:** `t₀` anında ok silinmez (geçmiş yeniden yazılmaz); fakat `t₀ + k` (`k ∈ {1, 2, 3}`) barında ters `BOS` kapandığı andan itibaren okun durumu `IPTAL / EZILDI` olarak işaretlenir:
  - Canlı grafikte ezilmiş ok tam parlak sinyal gibi durmaz (soluklaşır veya iptal statüsü taşır),
  - Özet/kart/komut yüzeyinde "aktif geri alım / aktif dönüş" olarak raporlanmaz.

#### Geçmiş Replay Kanıtları (Değiştirilmemiş Sayılarla)
1. **Başarısız Kırılımın Yıkıcı Ters Uzantısı (`FORMASYON_SONUCLARI.md` FRM-17, `n = 6.186` & `KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md` §5):**
   - Bir kırılım denemesi tutunamayıp `BASARISIZ_KIRILIM` olduğunda (`n = 6.186`), sonraki 12 barda ters yöndeki medyan hareket (`MAE`) tam **`2,83 ATR`** (`ÇGA 2,00–4,00 ATR`)'dir!
   - `174` hisse kırılım/teyit replay'inde (`21.244` çakışmayan olay), ilk `1–2` bar içinde başarısızlığa düşen adayların 10 bar içinde ters yönde **`-2 ATR` darbe yeme oranı**:
     - `1 saat` yukarı başarısız: Keşif **`%70,7` (`181/256`)**, İleri dönem **`%83,3` (`95/114`)**; `1 saat` aşağı başarısız: Keşif **`%76,8` (`208/271`)**, İleri **`%67,7` (`67/99`)**.
     - `4 saat` yukarı başarısız: Keşif **`%65,3` (`77/118`)**, İleri **`%76,5` (`39/51`)**; `4 saat` aşağı başarısız: Keşif **`%72,0` (`85/118`)**, İleri **`%57,6` (`19/33`)**.
     - `Günlük` yukarı başarısız: Keşif **`%66,1` (`41/62`)**, İleri **`%78,1` (`25/32`)**.
2. **Neden Tam `1–3` Mumluk Pencere? (`FRM-09`, `FRM-11`, `S26` ve `RCL-06`):**
   - `KIRILIM_TEYIT_REPLAY` §1.4: `15.947` teyidin **`%76,3`'ü (`12.163`) 1. barda**, **`%23,7`'si (`3.784`) 2. barda** belli olmaktadır.
   - `FRM-11` (`n = 18.032`): Kırılım teyidi ile yapısal `BOS` arasındaki medyan gecikme tam **`3` bardır**.
   - `RCL-06` (`1.150` geri alım): Kıl payı (`< 0,12 ATR`) geri alımların **`%34,4`'ü daha ilk sonraki 4s mumda** çizgi altına geri düşmektedir; güçlü geri alımların ise ertesi barda tutunma oranı `%85,9–%91,5`'tir (`RCL-01`, `STABIL_CANLI_SEMBOL_SISTEMATIGI.md`).
   - Bu ayrı olayların zamanlaması 1–3 mumluk nedensel iptal fikrini motive eder; doğrudan ok sonrası ters BOS sıklığını veya kuralın etkisini ölçmez.

---

### 3.4 Tekrar test: gözlem, tepki ve yorulma birbirinden ayrılır

**Gözlem/hipotez:** Formasyon alt sınırı ile yatay `S` hizasında, arada kısa yataylaşma ve ikinci testten sonra tutunma grafiklerde dikkat çekebilir. Bu birleşim ve özellikle **7–8 mum aralığı** ayrı ölçülmemiştir; satış emiliminin veya güçlü yükselişin teyidi sayılamaz. İkinci temas otomatik `▲` onayı değildir. İlk testteki tepki, sonra yeni temasın davranışı ve yapısal bağlam ayrı okunmalıdır; <0,75 ATR da doğrulanmış evrensel eşik değil, aşağıdaki çalışmanın tanımıdır.

**Doğrudan betimsel sonuçlar:** [`STB-BHV-C02`](stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md) en az 0,35 ATR ayrılmayla sayılan bağımsız temasları karşılaştırır; formasyon hizası veya 7–8 mum şartı içermez. 8×4s için:

| Temas | Olay / hisse | Medyan getiri | Önce +1 ATR / önce −1 ATR |
|---|---:|---:|---:|
| İlk | 1.773 / 99 | −0,066 ATR | %30,0 / %25,9 |
| İkinci | 137 / 38 | +0,155 ATR | %35,0 / %23,4 |
| Üç ve üzeri | 33 / 5 | −0,376 ATR | %12,1 / %33,3 |

İkinci temasa yalnız ilk temastan sonra bu aşamaya ulaşan durumlar girer: seçilim/sağ kalım etkisi ve farklı örneklemler nedensel karşılaştırmayı engeller. 3+ grupta olayların %81,8’i tek hisseden; genelleme yapılamaz. 16×4s için 3+ grupta önce −1 ATR oranı %48,5'tir; **destek kırılması oranı değildir**.

[`STB-BHV-C04`](stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md): geçmişte tamamlanmış cılız tepkisi (<0,75 ATR) olan yeni temaslarda, 8×4s `n=55`, medyan −0,342 ATR ve önce −1 ATR %34,5; 16×4s önce −1 ATR %60,0, medyan −0,113 ATR. `n=55`, 18 hisse ve yoğunlaşma nedeniyle yalnız araştırma işaretidir; %60 destek kırılma oranı değildir.

174 hisseli karşılaştırmada farklı tanım ve örneklemlerle ikinci temas için PRE_2026 `n=60`, yukarı/aşağı ilk %50,0/%16,7, medyan +0,65 ATR; Y2026 `n=134`, %38,8/%23,9, medyan +0,24 ATR kaydedilmiştir ([kaynak](stabil_destek_direnc_karsilastirma_2026_11_06/toplu_bulgular.md)). Bunlar özel hizalı çift-test kuralının doğrulaması değildir. `PH/PL` ve `OB/FVG` temas çalışmaları ise farklı seviyeleri ölçer; Stabil temas sayısına veya optimum süreye doğrudan aktarılmaz ve Blok ok kararına dahil edilmez.

---

### 3.5 Püf Noktası 5 — "Altı Boş" / "Üstü Boş": Tüm Zaman Dilimleri İçin Hipotez

#### Grafik Gözlemi ve Önerilen Mekanizma
- Yalnız `1 saatlik` grafiğe özgü **değildir**; **`1s`, `2s`, `4s` ve `1g` dahil tüm zaman dilimlerinde incelenmesi gereken bir gözlemdir**.
- Fiyat yatay bir taban/konsolidasyon örmeden dik bir açıyla tırmandığında, arkadan gelen Stabil desteği de dikey basamaklarla (`STEPPING_UP` / ardışık `REBASED_HIGHER`) yukarı taşınır. Bu dikey tırmanışta çizginin **altı yapısal olarak boştur** (arada alıcıların maliyetlendiği yatay bir denge alanı yoktur).
- Bu evrede grafikte yukarı yönlü `BOS` basılsa bile, fiyat o hava boşluğuna (`air pocket`) geri çekilebilir; dikey basamak üzerindeki yukarı denemelere `▲` basmak yüksek oranda tepe yakalama hatası üretir.
- **Ayna Kural ("Üstü Boş" Dikey Direnç):** Sert şelale düşüşte `Stabil R` dikey basamaklarla aşağı inerken (`STEPPING_DOWN` / `REBASED_LOWER`), çizginin üstü boştur; yatay tavan oluşmadan dikey basamakta basılan erken dönüş işaretleri tepki sıçramalarına yakalanır.

#### Geçmiş Replay Kanıtları (Değiştirilmemiş Sayılarla)
1. **Günlük Zaman Diliminde İlgili Proxy Bulgusu (`STABIL_SORU_SETI_V2_2026-11-08.md`, 119 sembol, 1g):**
   - `STEPPING_UP` durumundaki **`4.205` günlük bar** ikiye ayrıldığında:
     - **Dikey kalmaya devam eden (`n = 1.415` günlük bar):** Sonraki 16 günde `UP_first %44,5`, **`DOWN_first %53,5`**, medyan getiri **`-0,29 ATR`**!
     - **Yataylaşan (`n = 2.790` günlük bar):** Sonraki 16 günde **`UP_first %58,2`**, `DOWN_first %39,6`, medyan getiri **`+0,11 ATR`**!
   - **59 Geçiş Testinde Doğrulanan Dikey Çöküş (`senaryo_dogrulama_sonuclari_2026_11_08.csv`):**
     - `ust+yukari -> alt+yukari` (destek hâlâ yukarı/dikey basamaklarken fiyatın desteği aşağı kırması): Keşif `n = 82` (`DOWN %53,7`, `DOWN lift +9,6`, `UP lift -11,5`), Doğrulama `n = 30` (**`DOWN %56,7`, `DOWN lift +13,2`, `UP lift -11,5`, `p_down = 0,0132`**) → tüm geçişler arasında istatistiksel doğrulamayı geçen **5 `OK-▼`** senaryosundan biridir!
   - Teşhis tablosunda (`senaryo_teshis_sonuclari_2026_11_08.csv`, 10 günlük pencere): `ust+yukari` durumundan `alt+sabit` durumuna düşen `479` gözlemde `down_first` **`%77,5`**, medyan **`-2,93 ATR`** olarak kaydedilmiştir.
2. **4 Saatlik Zaman Diliminde İlgili Proxy Bulgusu (`STB-BHV-B01`, `B03` ve `stabil_ok_replay_2026_11_05`):**
   - `STB-BHV-B01` (`100` hisse, 4s): `LONG_HORIZONTAL` (`n = 4.248`) `+1/-1 ATR` **`%40,0 / %26,5`** (`med +0,100 ATR`) verirken, `STEPPING_UP` (`n = 2.660`) `med -0,027 ATR` vermekte; `STB-BHV-B03` dik yükseliş (`> 2,5 ATR` tırmanış) sonrası ilk düzleşmede bile "altı boş" geçmişin etkisiyle `16×4s` eşit-hisse ortalaması **`-0,363 ATR`** olmaktadır!
   - `NEWLY_FLATTENED_AFTER_RISE` rejiminde basılan 4s `▲` oklarında (`174` hisse, `n = 170`) `8×4s` medyan kapanış **`-0,27 ATR`** iken `LONG_HORIZONTAL`'da (`n = 49`) **`+0,10 ATR`** (`+1/-1 ATR %55,1 / %32,7`)'dir.
3. **Tüm Zaman Dilimlerinde Ayrı MS Zamanlama Ölçümü (`ARASTIRMA_BULGULARI.md` Soru 7 & `REPLAY_SORU_YANITLARI` S26):**
   - Zayıf yapısal seviyelerin (`WH` / `WL`) süpürülme süresi `1s` (`n = 21.809`), `2s` (`n = 12.095`), `4s` (`n = 8.141`) ve `1g` (`n = 3.671`) zaman dilimlerinin **dördünde de ortanca tam `3,0` native bardır** (`q25 = 1–2`, `q75 = 5–7` bar).
   - Ani tek mumluk aşırı uzanımların (`pay_1 ≥ 0,8` olan `BOS` kırılımları, `S26`, `n = 12.425`) devamlılığı hem `EXTERNAL` hem `INTERNAL` yapıda tüm TF'lerde **`%87,0`'den `%25,9`'a (`-61,1` puan)** düşmektedir.
   - WH/WL süpürülme süresi farklı bir olaydır; altı boş Stabil kuralının her TF’de aynı şekilde çalıştığını kanıtlamaz.
4. **Önemli Proxy Sınırı Notu (`STABIL_SISTEM_INCELEMESI_2026-11-08.md` §4.4/3):**
   - Mevcut kodda kullanılan `STEPPING_UP` proxy'si (rebase sonrası 8 günlük bar boyunca her şeyi dikey saymak) gerçek görsel dikeylikten daha geniştir; bu yüzden 174 hissede bastırılan `838` eski adayın bir kısmı aslında yataylaşmış iyi adayları da kesmiştir (`+1 ATR %53,4`). Demek ki "altı boş" kuralı korunurken, dikeyliğin tanımı soyut sayaçtan ziyade **gerçek fiyat–çizgi boşluğu ve yatay taban eksikliği** ile hizalanmalıdır.

---

### 3.6 Püf Noktası 6 — `◇` (Kare / Eşkenar Dörtgen) İşaretinin Anlamsızlığı ve Kaldırılması

#### Grafik Gözlemi ve Tasarım Kararı
- Mevcut sistemde dikey destek/direnç proxy'si aktifken bir ok adayı bastırıldığında veya zayıf geri alım/temas oluştuğunda grafikte mumun üzerine **`◇` (eşkenar dörtgen / kare)** çizilmektedir.
- Kullanıcı açısından `◇` işareti ne "al", ne "sat", ne "teyitli dönüş", ne de "kesin iptal" anlamı taşımaktadır ("karenin çok anlamı yok gibi"). Bir ok bastırıldıysa doğru davranış **onun yerine başka bir şekil basmak değil, hiçbir işaret basmamaktır**.

#### Geçmiş Replay Kanıtları (Değiştirilmemiş Sayılarla)
1. **`%87,8` Oranında Görsel Kalabalık (`stabil_ok_replay_2026_11_05`, 174 hisse, `4.775` olay):**
   - 174 hissede toplam `4.775` olayın yalnızca **`584`'ü (`%12,2`) gerçek `▲` oku** iken, tam **`4.191`'i (`%87,8`)** dikey uyarı (`3.353` zayıf deneme + `838` bastırılmış aday) olarak üretilmiştir! Grafikteki ok sisteminin neredeyse 9/10'unu uyarı sembolleri kaplamıştır.
2. **İki Tur Seyreltmeye Rağmen Kalan Anlamsız Yük (`OK_SISTEMI_2026-11-08.md` §10 & §14.3, 50 sembol, 1g):**
   - İlk turda soğuma 3 bardan 20 bara çıkarılmış (`737 → 486`, `-%34`), ikinci turda `_DIKEY_UYARI_SOGUMA_BAR = 50` bara çıkarılmıştır (`486 → 364`, 3 bar'a göre `-%51`; dirençte 30 sembolde `378 → 294`).
   - Buna rağmen 50 sembolde hâlâ **`364` adet `◇`** (`175` zayıf + `189` güçlü bastırılmış) kalmıştır ve elenen zayıf `◇`'lerin `%26–27`'si zaten yakınlarında bir `▲` barındıran tekrar gürültüsüdür; ayrıca `OK_SISTEMI` §14.5'te açıkça belirtildiği gibi **`◇` işaretinin hiçbir öngörü değeri ölçülmemiştir ve kendisine bağlı hiçbir karar kuralı yoktur**.
3. **Ampirik Referansın Temel İlkesiyle Uyum (`AMPIRIK_REFERANS.md` §2 Madde 5):**
   - Depodaki dil sözleşmesi zaten *"Sessizlik yeğdir: koşul sağlanmıyorsa satır/işaret dönmez"* kuralına dayanır. Bastırılan bir okun yerine `◇` koymak yerine grafik yüzeyinden `◇` tamamen emekliye ayrılmalı; gerekiyorsa "dikey destek · altı boş" bilgisi yalnızca metin/kart teşhis satırında kalmalıdır.

---

### 3.7 Püf Noktası 7 — Aynı Bardaki İkili `(Stabil S, Stabil R)` Koridor Dinamikleri: Mesafe, Daralma ve Asimetrik Basamaklar

#### Grafik Gözlemi ve Matematiksel Simetri
`Stabil S` (`last_l`) ve `Stabil R` (`last_h`) aynı günlük `daily_pivot_len = 4` motorunun alt ve üst zarfıdır. Şu anda iki motor birbirini görmediği için aynı barda iki çizgi arasındaki koridor geometrisi hiç kullanılmamaktadır. Oysa aynı kapanmış mumda hem `S(t)` hem `R(t)` bilindiğinde dört temel yapısal bilgi doğar:

1. **Karşı Duvar Mesafesi (`Runway` / Hareket Alanı):**
   - `▲` adayında yukarı boşluk: `runway_up = (R(t) - close(t)) / ATR(t)`. Eğer `R(t)` aktif/geçerli ve `runway_up` çok darsa (ör. `< 0,75 – 1,0 ATR`), `▲` oku doğrudan üstteki Stabil direnç duvarının içine basılmaktadır.
   - `▼` adayında aşağı boşluk: `runway_down = (close(t) - S(t)) / ATR(t)`. Eğer `S(t)` aktif/geçerli ve `runway_down` çok darsa, `▼` oku doğrudan alttaki Stabil destek tabanının üstüne basılmaktadır.
2. **Koridor Genişliği (`Corridor Width = (R(t) - S(t)) / ATR(t)`):**
   - İki çizgi birbirine çok yaklaşmışsa piyasa sıkışma fazındadır; içerideki oklar yön koşusu değil, koridor içi pinpon üretir.
3. **Asimetrik Basamak Sıkışması (Makro Üçgen / Kama Tespiti):**
   - **`S` yukarı basamaklıyor + `R` yatay/sabit:** Alıcılar dipleri yükseltirken satıcılar sabit bir tavanda karşılıyor → makro **Yükselen Üçgen** yapısı (tavan aşınma adayı).
   - **`R` aşağı basamaklıyor + `S` yatay/sabit:** Satıcılar tepeleri alçaltırken alıcılar sabit bir tabanı savunuyor → makro **Alçalan Üçgen** yapısı (`S` kırılırsa sert aşağı çözülme riski).
   - **`S` uzun yatay + `R` uzun yatay:** Dengeli yatay kanal; her iki kenardan içe dönüşlerin (`▲` ve `▼`) en temiz çalıştığı rejim.

#### Geçmiş Replay Kanıtları (Değiştirilmemiş Sayılarla)
1. **Direnç ve Destek Yakınlığında Aşınma Asimetrisi (`stabil_direnc_replay_2026_11_06/toplu_bulgular.md` & `ARASTIRMA_BULGULARI.md` Soru 6):**
   - `21+` gün yatay kalmış dirence (`R`) fiyat geldiğinde (`n = 28`), aşağı tepki yalnız `%25,0` kalırken **yukarı kırılma (`+1 ATR` önce) `%67,9`** (`med +1,00 ATR`) olmaktadır (`LONG_FLAT_PROXY` direnç testinde de `n = 15`, yukarı kırılma `%73,3`).
   - Aynı bulgu `MS PH` (`1g EXTERNAL`) tablosunda da birebir görülür: korunan tepe 4+ kez test edildiğinde engelleme `%36,2`'den **`%11,1`'e** düşer (`%88,9` kırılım). Yani `S` yukarı basamaklayıp sabit `R`'yi defalarca sıkıştırdığında sabit `R` altında `▼` aramak tehlikelidir; tavan kırılmaya hazırlanmaktadır.
2. **Uzun Yatay Destek (`LONG_HORIZONTAL`) Gücü (`STB-BHV-B01`, `RCL-07`, `stabil_ok_replay`):**
   - Destek `LONG_HORIZONTAL` olduğunda: 4s temasta `+1/-1 ATR` **`%40,0 vs %26,5`** (`n = 4.248`); 4s geri alımda (`16+` gün yatay `S`, `RCL-07`) **`%42,9 vs %21,4`**; 4s `▲` oklarında (`n = 49`) **`%55,1 vs %32,7`**.
3. **Dürüstlük Notu:** Geçmiş replay'lerde `S` ve `R` aynı 174/50 hissede eş-kuralla koşulmuş (`stabil_destek_direnc_karsilastirma_2026_11_06`), fakat aynı bar üzerinde `(R - close) / ATR` çapraz tablosu ayrı bir kolon olarak basılmamıştır (§5'te açıkça işaretlenmiştir). Bununla birlikte `OK_SISTEMI` §12–§13'te `▲`'nın yalnız seviye tutma (`R3`), `▼`'nin ise `-1` ve `-2 ATR` koşu (`R1`, `R2`, `R3`) ürettiği kanıtlandığından, yakın karşı duvar hareket alanını sınırlayabilir; fiyatın o duvarı kırıp geçmesi de mümkündür ve okun başarısına etkisi ayrıca ölçülmemiştir.

---

### 3.8 Püf Noktası 8 — Dikey `R` + Altta Hizalı `S` (Kontrollü Düzeltme) vs Yatay `R` + Destek Kaybı (Kontrolsüz / Sert Düşüş)

#### Grafik Gözlemi ve İki Farklı Düşüş Rejimi
Uzun süreli günlük yükseliş trendlerinde direnç (`Stabil R`) ve destek (`Stabil S`) ikilisinin birlikte oluşturduğu çok kritik bir ayrım vardır:

1. **Senaryo A — Kontrollü Düşüş / Sağlıklı Düzeltme (`Dikey R` + Altta Hizalı `S`):**
   - Güçlü bir günlük yükseliş trendinde fiyat yeni zirveler yaptıkça `Stabil R` de yukarı doğru basamaklar (`RESISTANCE_STEP_UP` / dikey `R`), arkasından `Stabil S` de yeni teyitli yüksek diplerle yukarı basamaklar veya hemen altta hizalı bir taban kurar.
   - Bu sırada fiyat üstteki dikey `R`'ye değip geri çekildiğinde, bu düşüşün **kontrollü bir düzeltme (`pullback`) olabileceği** düşünülür; alttaki `S` desteği izlenir fakat tutunma garanti değildir. Bu bölgede `▼` okunu "büyük düşüş sinyali" gibi okumak yanıltıcıdır.
2. **Senaryo B — Kontrolsüz / Sert Düşüş (`Yatay R` Tavanı + Destek Kaybı / Alt Boşluk):**
   - Yükseliş ivmesi bittiğinde `Stabil R` yukarı basamaklamayı keser ve **yataylaşır** (`FLAT_AFTER_FAVORABLE` / sabit tavan). Fiyat bu yatay direnci geçemeyip reddedildiğinde (`▼`), artık yeni tepe üretemeyen bir dağıtım tavanı oluşmuştur.
   - Hele bu yatay `R` reddinin altında `Stabil S` uzaktaysa (fiyat daha önce altı boş yükselmişse) veya fiyat alttaki `S` çizgisini de aşağı kırarsa (`üst -> alt` geçişi), yakın destek eksikliği veya destek kaybı **sert çözülme riski** hipotezini oluşturur.

#### Geçmiş Replay Kanıtları (Değiştirilmemiş Sayılarla)
Aşağıdaki ayrı kesitler hipotez için bağlam sağlar; aynı anda S/R hizası ve düşüş şiddeti birlikte sınanmadığı için ayrımı doğrulamaz:

1. **174 Hisse `F01` Ayna Ölçümü: Dikey `R` vs Yataylaşan `R` (`stabil_destek_direnc_karsilastirma_2026_11_06/toplu_bulgular.md`, `8×4s`, günlük ATR):**
   - **Direnç yukarı basamaklarken (dikey `R` proxy'si — `RESISTANCE / ADVERSE_STEP_PROXY`):**
     - `Y2026` (`n = 3.311`, `161` hisse): Aşağı tepki `%37,3` iken **yukarı devam (`+1 ATR` önce) `%37,5`**!
     - `PRE_2026` (`n = 2.750`, `164` hisse): Aşağı tepki `%29,5` iken **yukarı devam `%35,5`**!
     - Eski 100-hisse kesişimi iki dönem birlikte (`n = 3.486`, `95` hisse): Aşağı tepki `%32,5` iken **yukarı devam `%37,3`**!
     - Yani `R` dikey yukarı basamaklarken üstten gelen baskı kalıcı bir düşüş üstünlüğü **üretememekte**, trend yukarı devam etmektedir.
   - **Direnç yataylaştığında (`RESISTANCE / FLAT_AFTER_ADVERSE_PROXY`):**
     - `Y2026` (`n = 11.235`, `162` hisse): **Yukarı devam oranı `%37,5`'ten `%28,5`'e çakılır (`-9,0` puan düşüş!)** ve aşağı tepki (`%33,6`) yukarı devamın (`%28,5`) önüne geçer!
     - `PRE_2026` (`n = 7.898`): Yukarı devam `%35,5`'ten `%30,5`'e düşer, sıkışma (`hiçbiri`) `%34,7`'den `%44,0`'a çıkar.
2. **50 Hisse Model Testinde Fiyat Tarafına Göre Dikey `R` vs Yatay `R` (`RAPOR_50.md` §4 & §5):**
   - `R` yukarı basamaklarken (`Ters basamak`, Y2026): fiyat direnç altındayken (`n = 490`) aşağı `%35,9` vs **yukarı devam `%39,4`**; fiyat direnç üstündeyken (`n = 450`) aşağı `%34,2` vs **yukarı devam `%38,2`**.
   - `R` yataylaştığında (`Sonrası düz`, `n = 3.015`): **yukarı devam `%39,4`'ten `%29,5`'e (`-9,9` puan) düşer**, aşağı tepki `%32,5` ile baskın tarafa geçer!
   - Ayrıca `RAPOR_50.md` §5 (`sabit_cizgi_yollari.md`): `R` yukarı taşındığında fiyat üstteyken çizgi altına sarkan 6 olayın **4'ünde fiyat çizgi kimliği değişmeden tekrar yukarı (direncin üstüne) dönmüştür** — kontrollü düzeltmenin birebir yol izi!
3. **Alttaki `S` Tamponunun Arkadan Yetişme Mekanizması (`A01` Çizgi–Fiyat Yarışı, `24×4s`, 174 hisse Y2026):**
   - Yükseliş trendinde fiyat destekten `1–2` günlük ATR açıldığında (`n = 16.597`), alttaki `Stabil S`'nin yukarı basamaklayarak fiyata yaklaşması (`LINE_FAVORABLE_FIRST` **`%35,4`**) ile fiyatın desteğe inmesi (`PRICE_RETURN_FIRST` **`%32,6`**) dengeli yürür; fiyat `2–3,5 ATR` açıldığında (`n = 17.022`) desteğin arkadan yukarı basamaklaması **`%41,9`'a** çıkarken fiyatın eski desteğe sert dönmesi **`%16,4`'e** düşer! Yani sağlıklı günlük trendde `S` arkadan basamaklayarak düzeltmenin altına yastık koyar.
4. **Yatay `R` Reddi ve Destek Kaybında Sert Çözülme (`OK_SISTEMI` §13 & `STABIL_SORU_SETI_V2`):**
   - Yatay/sabit dirençte üretilen dolu `▼` okları (`OK_SISTEMI` §13, 176 sembol, `n = 927`; kural gereği yalnızca `fixed_resistance` yani **sabit/yatay `R`** üzerinde üretilir!) `R2 (-2 ATR önce vs +1 ATR önce)` yarışında Keşif **`%40,6 vs %32,2` (`lift +8,4`, `p = 3·10⁻⁵`)** ve Doğrulama **`%41,9 vs %31,5` (`lift +10,5`, `p = 0,00016`)** ile **2 ATR'lik sert düşüş koşusunu** kanıtlamıştır!
   - Üstelik `V2` geçiş doğrulamasında fiyatın üst bölgeden desteği kaybettiği **`üst -> alt` ailesi** (`nK = 197 / nD = 75`) `DOWN` olasılığını **`%53,3 / %58,7`'ye (`lift +9,3 / +15,2`, `p = 0,0045 / 0,0039`)**, `ust+asagi -> alt+asagi` geçişi ise **`%58,7 / %60,9`'a (`lift +14,7 / +17,4`, `p = 0,0022`)** taşımaktadır.

---

### 3.9 Ek Mekanik Püf Noktası — 4S ve Alt Zaman Dilimlerinde Ok Gücü Birim Kayması (`ATR_TF` vs `ATR_1G`) ve `18:00` Kısa Kova Etkisi

Geçmiş incelemelerde ortaya çıkan ve "zayıf görünen mumda neden ok çıktı?" sorusunu doğrudan açıklayan iki mekanik bulgu da bu tek referans dosyasında kayıt altına alınmalıdır (`STABIL_SISTEM_INCELEMESI_2026-11-08.md` §4.2, §4.4/1, §7.2):

1. **ATR Birim Kayması (`ATR4s / ATR1g = 0,52`):**
   - Stabil seviyesi **günlük** mumlardan üretilirken, `signals.py` içindeki gövde eşikleri (`≥ 0,32` / `0,35 ATR`) **grafiğin kendi zaman diliminin ATR'siyle** ölçülmektedir.
   - 40 sembollük ölçümde olay anındaki `ATR4s / ATR1g` medyanı **`0,52`** (`p10 = 0,42`, `p90 = 0,61`) bulunmuştur; yani `0,35 × 4s ATR ≈ 0,18 × günlük ATR`'dir (`1s` ve `2s`'de bu oran daha da küçülür).
   - Bu yüzden mevcut 4s `▲` oklarının **`%64,5`'i**, 100-hisse araştırmasının "güçlü mum (`≥ 0,50` günlük ATR)" eşiğinin altındadır! Oysa aynı örneklemde gövdesi gerçekten `≥ 0,50` günlük ATR olan 4s oklarda (`n = 38`) `8×4s` medyan **`+0,34 ATR`** iken, `0,25–0,50` günlük ATR bandında kalanlarda (`n = 57`) **`-0,58 ATR`** çıkmıştır.
2. **BIST `17:30 → 18:00` Yarım Saatlik Son 4S Kovası (`stabil_direnc_replay_2026_11_06`):**
   - 09:30 çapalı 4s serisinde günün son kovası (`17:30–18:00`) yalnızca **30 dakikalık** bir mumdur. Nitekim direnç `TEST` seans saati kırılımında `13:30` kovasında (`n = 881`) aşağı tepki **`%43,7`** iken `18:00` kısa kovasında (`n = 89`) **`%29,2`** (`+1 ATR` önce `%66,3`)'ye düşmektedir. Kısa kapanış kovasındaki göreli hacim ve gövde oranları tam 4 saatlik mumlarla aynı ölçekte değildir.

---

### 3.10 Desteğin altına sarkıp tekrar üstüne çıkması: kaçırılan olaylar

**Kullanıcı gözlemi:** Desteğin altına normal bir sarkma sonrası geri çıkışlarda sıkça tepki ve fiyat artışı görülüyor; bazıları sistemde görünmüyor. Bu gözlem özel sembol/tarih veya grafikte hangi mumun kaçırıldığı olmadan tek tek teşhis edilemez.

**Kodun bugün yaptığı:** `domain_engines/stabil/signals.py`, sabit destekte iki durumu zaten tanır: önceki kapanış çizgi altındayken yeni kapanışın üstte olması (`close_reclaim`) ve önceki kapanış üstte iken aynı mum fitilinin altı görüp üstte kapatması (`intrabar_sweep_reclaim`). Bu yüzden “hiç algılamıyor” demek doğru değildir; ama **her sarkmayı işaretlemiyor**. Her ikisi için sabit destek, geçerli ATR, gövde, kapanış pozisyonu, mesafe ve derinlik koşulları vardır. Dolu geri alımda hacim şartı yoktur. Dikey destek proxy’si aktifse güçlü aday bile `vertical_attempt_kind` içine aktarılıp `reclaim_kind` silinir; işaret ve güçlü geri alım alarmı da etkilenebilir. Çizgi aynı barda değişiyorsa sabit destek kapısı sağlanmaz. Ölçüm ATR biriminin ilgili hesaplamada hangi TF’den geldiği de kontrol edilmelidir. Bunlar olası nedenlerdir; örneksiz gerçek kaçırılma nedeni ve oranı bilinmez.

**Geçmiş replay — doğrudan gözlem:** [`STABIL_GERI_ALIM_VE_KART_ANALIZI.md`](STABIL_GERI_ALIM_VE_KART_ANALIZI.md) 100 hisse, 1.150 sabit-destek geri alımını inceler. `RCL-01` kapsamında 0,5–1,2 ATR sarkma ve güçlü geri alım mumu (`n=198`): ertesi 4s üstte kalma %85,9; 8×4s medyan +0,145 ATR, eşit-hisse ortalaması +0,380 ATR; +1/−1 ATR ilk %40,6/%22,3. Aynı derinlikte cılız mum (`n=180`): 8×4s medyan −0,216 ATR; ertesi mum üstte kalma %75,6. Bunlar seçili grupların betimsel sonuçlarıdır; tüm sarkmaların getirisi, nedensel etki veya canlı başarı oranı değildir. Diğer araştırma kesitindeki mevcut 50 sembollük sinyal sonuçları kaçırılan olayların tamamını ölçmez. Kaynak: [`STABIL_CANLI_SEMBOL_SISTEMATIGI.md`](STABIL_CANLI_SEMBOL_SISTEMATIGI.md).

**İleride değerlendirme:** Aynı mum fitil sarkması ile bir veya birkaç kapanış sonrası geri alımı ayrı olaylar olarak, kapanmış mum ve o anda bilinen sabit destekle ele almak; yalnız çizginin fiyata inmesini geri alım saymamak; işaret bastırma nedenini ayrıca saklamak. Otomatik `▲` veya yeni sembol kararı verilmeden kaçırılan örnekler ve nedenleri incelenmeli; kullanıcı istemedikçe yeni replay yapılmamalıdır. Blok bağlantısı ve derin iç içe filtre yoktur.

---

### 3.11 Son görüşme — dipten geri alıma mum dizisi (kullanıcı gözlemi)

**Statü: Gözlem ve fikir; ne ölçülmüş üstünlük ne de uygulama kararı.** Kullanıcı, desteğin altına sarkan fiyatın yeniden yukarı çıkışını tek büyük geri alım mumundan ibaret görmüyor. Tek büyük yeşil mum yönsüz bir ani tepki olabilir. Buna karşılık dipten itibaren düzgün biçimde ilerleyen, mumlarının çoğu yeşil olan ve desteği geri aldıktan sonra da toparlanmayı sürdürebilen bir yolun devamlılığının daha iyi olabileceğini gözlemliyor. Bu karşılaştırma geçmiş replay sonuçlarında doğrudan test edilmiş değildir.

- **Dizinin başlangıcı:** Destek altındaki en düşük noktadan desteğe doğru toparlanma; duruma göre destek üstündeki kısa bölüm de gözleme dahil edilebilir. Gerçek zamanlı gözlemde en düşük nokta ancak daha sonra anlaşılabileceğinden geçmişteki nihai dibi önceden bilmiş gibi seçmek geleceğe bakma hatasıdır. Dip adayının ne zaman bilindiği henüz tanımlanmamıştır.
- **Dizinin niteliği:** Yeşil mumların ağırlıkta olması ve fiyatın düzgün, anlamlı biçimde yükselmesi kullanıcı gözlemidir. Her mumun yeşil olması, son mumun büyük veya güçlü olması istenmiyor. Çok uzun yatayda kalma, sürüklenme veya yavaş ve düzensiz yükseliş farklı davranış olarak değerlendirilmek isteniyor; ölçülebilir sınırlar belirlenmedi. Yeşil çoğunluğu ile net fiyat ilerlemesi farklı şeylerdir: renk tek başına yolu veya getiriyi garanti etmez.
- **Destek üstünde takip:** Kullanıcı toparlanmayı destek üstünde de görmek istiyor, ancak uzun beklemek istemiyor; kısa takipte yeşil bir mumun yeterli olabileceğini söylüyor. Bu, kesin bir zorunlu mum sayısı veya doğrulanmış eşik değildir. Küçük karşı renkli mumun alanı koruyabilmesi gibi ihtimaller ayrıca gözlenebilir; kullanıcının önerisi değiştirilmeden kaydedilmiştir.
- **Temas sayısı:** Birinci, ikinci veya daha sonraki temas kendi başına otomatik olumlu/olumsuz karar değildir. Geçmiş betimsel veriler ve sınırlamalar §3.4'tedir; kullanıcı kesin bir sonuca bağlamak istemiyor.
- **Açık sorular:** Dip adayının nedensel seçimi, dizinin ne kadar süreceği, doji ve eksik mumların ele alınması, çizgi değişiminin etkisi, düzenli/sürüklenen yol ayrımı, destek üstündeki kısa takibin tanımı ve TF farkları kararlaştırılmamıştır. Yeni replay çalıştırılmamıştır; bu gözlem eski `RCL-01` rakamlarıyla aynı kesit değildir.

---

### 3.12 Kullanıcının PDF'si — genel mum ve fiyat davranışı için okuma notu

**Kaynak:** Kullanıcı tarafından eklenen `Cilt 2 - Mum Dizileri ve Fiyat Davranışları (2).pdf`, 109 PDF sayfası; metin katmanı okunmuştur. Kitap kullanıcının hazırladığı, genel teknik analiz eğitim kaynaklarından derlenmiş bir rehberdir. Yazarın belirttiği gibi **Stabil'e özel bir çalışma, replay doğrulaması, uygulama şartnamesi veya getiri garantisi değildir**. Aşağıdaki özet, kitapta anlatılan genel fikirleri aktarır; bunların evrensel geçerliliği burada bağımsız olarak doğrulanmamıştır. Şematik örneklerdeki mum sayıları ve oranlar mekanik eşik olarak alınmaz. Kitabın kendi okuyuş kontrol listesi de puanlama kuralı değildir.

| Konu ve PDF sayfaları | Genel okuma fikri | Sınır |
|---|---|---|
| Tek mum / dizi, s. 6–11 | Önceki baskı, mevcut mumda korunup geri verilen alan ve sonraki davranış bir arada okunur. Birleşik mum net özeti gösterir ama gerçek sıralamayı saklar. | Tek mum, uzun fitil veya özet görünüm tek başına geleceği belirlemez. |
| Güç ve ilerleme, s. 12–16 | Gövdeler, süre, mesafe, geri çekilme ve örtüşme hareketin ne kadar rahat ilerlediğini karşılaştırmaya yarar; aynı yönde kapanışlar süreklilik hakkında bilgi verir. | Mum rengi/sayısı tek başına yön ya da devam garantisi değildir; tüm işaretler aynı anda aranmaz. |
| Momentum ve dönüş, s. 17–29 | Eski yönün daha az ilerlemesi ile karşı yönün alan kazanması ayrıdır. İki–dört mumluk dönüşler ve çoklu itişler şekil saymaktan çok baskı değişimi açısından yorumlanır. | Yavaşlama dönüş demek değildir; dört itiş dört mum değildir ve belirli bir itiş zorunlu dönüş oluşturmaz. |
| Devam ve sıkışma, s. 30–44 | Sınırlı karşı hareket sonrası ana yönün tekrar ilerlemesi, mikro kanal ve örtüşme incelenir. Sıkışma daralma/genişleme ve başarısız ilk denemeden sonra yeniden deneme olarak okunabilir. | Sıkışma yönü önceden seçmez; küçük karşı mum veya duraklama tek başına hareketin bittiği anlamına gelmez. |
| Kırılım ve takip, s. 45–53 | Fitille aşma, seviye dışında kapanma, sonraki alanın korunması ve yeni yapı ayrı aşamalardır. | İlk dış kapanış veya ikinci kapanış garanti değildir; sonraki mumun rengi kadar alanı koruması da önemlidir. |
| Swing, ikinci deneme, s. 54–71 | Önemli ve küçük swingler ayrılır; bacaklar mesafe, süre ve geri verilen alan açısından karşılaştırılır. İkinci denemenin varlığından çok ne başardığı izlenir. | Bazı swingler ancak sonradan teyit edilir; geriye dönük doğrulama canlıda önceden biliniyor sayılmaz. İkinci deneme otomatik işlem veya ikinci destek teması için üstünlük iddiası değildir. |
| Pullback sonu ve konum, s. 72–85 | Eski yönün ilerleme kaybı, karşı tarafın alan kazanması, yerel sınırlar ve sonraki davranış ayrı bilgiler sunar. Aynı görünüm trend, seviye ve hareket alanına göre farklı yorumlanabilir. | Tek temas veya fitil dönüş değildir; yakın engel mekanik geçersizlik demek değildir. Zincirin tüm halkaları zorunlu koşul yapılmaz. |
| Hacim, çoklu TF ve genel okuma sırası, s. 86–105 | Fiyat davranışı önce, katılım ve diğer zaman dilimi yorumlayıcı ikinci katman olarak sunulur; son bölüm bir okuma sırası verir. | Hacim veya alt TF zorunlu filtre değildir. Kitabın eğitim yaklaşımı kullanıcı kararlarını, özellikle Blok'un dışarıda kalmasını ve derin filtre kurulmamasını değiştirmez. |

**Konuşmamızla ilişkisi:** Kitap genel olarak tek muma değil diziye ve takip davranışına bakma fikrine kavramsal bağlam sağlıyor; kullanıcının tarif ettiği destek altı dipten başlayan özel yeşil-mum yoğunluğu senaryosunu ölçmüyor. Kitap sonraki mumun yalnız rengine değil korunan alana da bakılmasını önerir; kullanıcının basit kısa yeşil takip tercihiyle bunu birbirinin kanıtı gibi sunmuyoruz. Daha uzun takip bilgi sağlayabilir ama gecikme yaratır; en iyi denge burada ölçülmemiştir.

**Kaynak sınırı:** Kitapta eğitim videoları kaynak gösterilir ve şekiller öğretim amaçlı şemalardır (s. 106–108). PDF'deki sayısal örnekler geçmiş replay sonucu değildir. PDF'nin tamamı metin olarak incelenmiş, şemalar ayrı görsel doğrulama yapılmamıştır; özgün PDF bu belgeye kopyalanmamıştır.

---

### 3.13 Son kararlar ve uygulama öncesi net plan — henüz kod değişikliği yok

**Kullanıcının son seçimleri:** (1) Son kullanıcı kararı: önceki kapanışı destek altında olup güçlü tek mumla üstüne çıkmaya dayalı `close_reclaim` yolu iptal edilecek; desteğin altından düzenli, çoğunluğu yeşil mumlarla toparlanıp geri çıkma ayrı aday olarak değerlendirilecek. Aynı mum içinde fitille sarkıp üstüne çıkma (`intrabar_sweep_reclaim`) iptal edilmedi. (2) Geri alımın ardından kısa takip için **sonraki kapanmış mumun yeşil olması** tercih ediliyor; uzun bekleme istenmiyor. (3) İlk aşama **net uygulama planı**; henüz üretim kodu değiştirilmeyecek ve yeni replay yapılmayacak. Kullanıcı okun anlamını önceden bir kategoriye zorlamak istemiyor. Yeşil takip, burada kazanma veya gelecekte yükselme garantisi değildir.

#### A. İki geri alım yolunu ayır

1. **Mevcut yollar:** Kullanıcı kararıyla `close_reclaim` üzerinden güçlü tek-mumlu geri alım oku iptal edilecek; `intrabar_sweep_reclaim` korunacak. Yeni çok-mumlu yol için sonraki yeşil mum takip olarak planlanır; korunan fitil yolu için yeni takip zorunluluğu kabul edilmemiştir. İptalin yalnız grafiği mi yoksa kart/alarm gibi bütün yüzeyleri mi kapsadığı netleştirilmeli; durum/lifecycle bilgisinin korunması ayrıca ele alınmalı.
2. **Yeni yol — aday fikir:** Destek altında oluşan bir dip adayından destek çizgisine doğru birkaç mumluk toparlanmayı, tek mum büyüklüğüne değil dizinin ağırlıklı yeşil oluşuna ve fiili yukarı ilerlemesine bakarak değerlendir. Ardından destek üstüne kapanış ve hemen sonraki kapanmış yeşil mum kısa takip bilgisidir. Tüm mumların yeşil olması, geri alım mumunun büyük olması veya hacim filtresi zorunlu tutulmaz.
3. **Olay sırası:** `dip adayı → destek üstüne geri alım kapanışı → sonraki mum kapanışı`. Sonraki mum kapanmadan takip sağlanmış denmez. O mum yeşil değilse seçilen yeşil takip koşulu sağlanmamıştır; olayın fiyat açısından kesin başarısız olduğu sonucuna varılmaz. Takipte destek üstünde kapanış ayrıca zorunlu mu, yoksa yalnız gözlemsel bilgi mi olacağı henüz kararlaştırılmamıştır.
4. **Grafik zamanı:** Yeni olay takip mumunda bilinebilir. İşaretin takip barına mı konacağı veya önceki geri alım barında daha sonra durum güncellenerek mi gösterileceği karar bekler; hiçbir durumda gelecekteki mum geri alım anında biliniyormuş gibi kullanılamaz. Olayın bilgisi bilinmeden geçmişe aktarılmaz; geriye dönük grafik görünümünün seçimi ayrıca netleştirilir.
5. **Çakışma:** Aynı geri alım hem eski hem yeni tanımı sağladığında iki ayrı okla grafiği doldurmamak amaçlanır; hangi yolun öncelikli olacağı ve hangi bilgilerin saklanacağı uygulamadan önce belirlenmelidir.

#### B. Belirsiz konular — seçilmiş eşik veya kanıt gibi sunulamaz

- **Dip adayı:** Geçmişin nihai en düşük noktası yerine o anda bilinen aday/kapanmış mum bilgisi kullanılmalı; adayın oluşumu, yeni dip geldikçe güncellenmesi ve zaman sınırı henüz seçilmedi.
- **Yeşil çoğunluğu:** `close > open` doğal bir tarif olabilir; doji, eşit açılış-kapanış, boşluklu mum ve oran hesabı kararlaştırılmadı. Kullanıcının çoğunluk gözlemi için kesin oran veya minimum mum sayısı belirlenmedi.
- **Düzenlilik ve ilerleme:** Net yükseliş ve uzun sürüklenme ayrımı isteniyor, fakat sayısal sınır, süre, ATR ölçeği veya karşı mum toleransı seçilmedi. Çok sayıda eşzamanlı koşul eklemek kullanıcı isteğine aykırıdır.
- **Destek kimliği:** Eski sabit desteğe göre gerçek fiyat geri alımı ile çizginin yer değiştirmesi ayrılmalı; yeni adayda desteğin değişmesi, ihlal derinliği ve toleransın nasıl yorumlanacağı henüz net değil.
- **TF / veri:** Kapalı mumlar, ilgili ATR birimleri ve 17:30→18:00 kısa kova etkisi göz önünde tutulmalı; farklı TF'lere aynı sayısal pencereyi dayatmak için kanıt yok.
- **Yeşil takip:** Takibin renginin yanında destek üstü kapanışın ayrıca şart olup olmayacağı, sinyal yeri ve olası gecikmenin sonuçları açık konulardır.

#### C. Diğer görüşmelerle uyum

- Temas sayısı tek başına güçlü/zayıf veya ok kararı değildir (§3.4); geçmişte ölçülen gruplar bu yeni dizi için başarı oranı değildir.
- Yakın ters `BOS/CHoCH`, formasyon içi karşı sınır, `S/R` koridoru ve altı/üstü boş fikirleri §3'teki kullanıcı gözlemleri/tasarım adaylarıdır. TF pencereleri ve ortak etkileri ölçülmemiştir; otomatik olarak çok katlı bir filtreye dönüştürülmez. Yapı karşı yönde yeniden kurulduğunda eski karşıt olayın baskısı sonsuza dek taşınmaz.
- Ok sonrası 1–3 barda ters BOS ile ezilme için konuşulan nedensel durum güncellemesi öneri olarak korunur; yalnız olay oluştuktan sonra uygulanabilir. `◇`'yi kaldırma grafik tercihi uygulama öncesi karardır; alternatif işaret yığılması yapılmaz.
- `OB/FVG` ile otomatik hizalama yapılmaz. Kitaplardaki göstergeler, şemalar ve rakamlar uygulama şartı veya replay sonucu sayılmaz.

#### D. Gelecekte uygulama ve kontrol sırası — henüz yapılmadı

1. Yukarıdaki açık konular kullanıcıyla netleştirilir; öneriler korunan fitil-silkeleme yolunu bozmadan küçük ve sığ tutulur.
2. Onaylı tanımdan sonra, gelecekteki mumlara bakmayan aday/durum mantığı tasarlanır; korunan fitil yolu, iptal edilen tek-mumlu yol ve yeni olayın grafik/kart yüzeyleri ile zamanlaması açıkça ayrılır.
3. Uygulamaya izin verilirse otomatik testler: aynı mum silkelemesi, birkaç mumlu geri alım, yeşil/kırmızı/doji takip, destek değişimi, yeni dip, yatay sürüklenme, aynı olayın iki yolla yakalanması, fitil yolunun korunması, iptal edilen yolun ilgili yüzeylerde davranışı ve geçmiş verinin ileri barlar eklendiğinde değişmemesi. Bu testler çalışma mantığını sınar, piyasa başarısını kanıtlamaz.
4. Yeni replay ancak kullanıcı ayrıca isterse planlanır; mevcut yöntemle adayın farklı örneklem ve dönemlerde hem yakaladıkları hem kaçırdıkları karşılaştırılır. Bu aşamada hiçbir yeni replay çalıştırılmamıştır.

---

## 4. Geçmişteki Tüm Replay Çalışmalarının Yön Farketmeksizin Bütüncül Kanıt Envanteri

Aşağıdaki tablolar, depodaki **tüm geçmiş replay çalışmalarını** yön ayrımı gözetmeksizin (`alttan üste`, `üstten alta`, `eş-kural simetri`, `MS + Formasyon`) tek bir çatı altında toplar. Hiçbir değer değiştirilmemiştir.

### 4.1 Alttan Üste (`Destek Geri Alımı`, `Temas`, `▲`, `Yükselen Basamak`) Bulguları

| Kaynak Çalışma & Evren | İncelenen Yön / Kurulum | Gerçek Örneklem (`n`) ve Değiştirilmemiş Sonuçlar | Tasarıma Doğrudan Etkisi |
|---|---|---|---|
| **`OK_SISTEMI_2026-11-08.md` §12** (`176` sembol, `1g`, keşif/doğrulama) | Sabit destek üzerinde dolu `▲` (`close_reclaim` + `intrabar_sweep`) vs destekteki ok olmayan barlar (`\|dist\| ≤ 0,50 ATR`, `n = 9.884`) | `716` ok: `R1 (±1 ATR)` lift **`+4,5 / +6,5`** (`p = 0,034 / 0,033`, Bonferroni geçmedi); **`R3 (10 bar sonra seviye üstünde kalma)`** Keşif **`%63,5 vs %49,6` (`lift +14,0`, `p = 2·10⁻⁹`)**, Doğrulama **`%58,9 vs %50,1` (`lift +8,8`, `p = 0,0053`) — GEÇTİ ✓**. | `▲` oku "hızlı ralli sinyali" değil, **"destek seviyesi tuttu / geri alındı" yapı olayıdır**. |
| **`STABIL_GERI_ALIM_VE_KART_ANALIZI.md` & `RCL-01..15`** (`100` hisse, `107.441` 4s bar, `1.150` geri alım) | Sabit `S` altından üste kapanışla geri alım (`alttan üste`) | Alttan `4.977` denemenin **`%77,1`'i (`3.836`) fitil reddi** (`med -0,102 ATR`). Makul sarkma (`0,5–1,2 ATR`) + güçlü mum (`n = 198`): ertesi 4s tutunma **`%85,9`**, `8×4s +1/-1 ATR` **`%40,6 / %22,3`** (`eqSym +0,380 ATR`), `16×4s eqSym` **`+0,413 ATR`**. Aynı yerden **cılız mumla** çıkış (`n = 180`): `16×4s med` **`-0,339 ATR`** (`-1 ATR %49,2`). Üst `%30` kapanış `+0,19` vs alt `-0,17 ATR`; `< 0,12 ATR` kıl payı kapanışta **`%34,4`** ertesi bar düşüş; `16g+` yatay `S` geri alımı **`%42,9 vs %21,4`**. | Bu kesitte güçlü ve cılız mum grupları farklıdır; bunların tümünü zorunlu filtreye çevirmek veya tekil olayı kesin tuzak saymak uygun değildir. |
| **`STABIL_CANLI_SEMBOL_SISTEMATIGI.md`** (`50` canlı sembol, `4s`, `75,9` hafta) | Canlı `evaluate_bar_behaviors` geri alım kuralları | `284` sinyal (`206` `close_reclaim`, `78` `intrabar_sweep`): ertesi 4s tutunma **`%91,5`**, `8×4s` medyan **`+0,26 ATR`** (ort. `+0,38 ATR`), `intrabar_sweep` `16×4s` ort. **`+0,84 ATR`**. | Seçilen sinyallerin betimsel sonuçlarıdır; kaçırılan geri alımların kapsamı veya nedeni bu tabloyla belirlenemez. |
| **`STB-BHV-E06` & `F02`** (`100` hisse, `4s`) | Geri alım sonrası retest bekleme vs beklememe; pasif çizgi inmesi vs aktif çıkış | Retest beklemek `8×4s` ortalamayı `+0,084 ATR` → `+0,025 ATR` düşürür. Yalnız çizgi aşağı fiyata indiğinde (`n = 475`) `16×4s med -0,059 ATR`; fiyat + çizgi birlikte lehte buluştuğunda (`n = 52`) `8×4s med` **`+0,481 ATR`**. | `▲` için zorunlu retest beklenmez; pasif çizgi inmesi geri alım sayılmaz. |
| **`stabil_ok_replay_2026_11_05`** (`174` hisse, `4s`, `555` geçerli `▲`) | 4s `▲` oklarının rejim ve bağlam performansı | Genel `UP_FIRST %49,7 / DOWN_FIRST %44,1` (`med -0,10 ATR`). `LONG_HORIZONTAL` (`n = 49`): **`%55,1 / %32,7`** (`med +0,10 ATR`); `HORIZONTAL_AFTER_DROP` (`n = 213`): **`%45,5 / %51,2`** (`med -0,30 ATR`). Yakın `OB` `%25,1` vs uzak `OB` `%25,9` zayıf. | Düşüş sonrası taze yatayda (`ters BOS` gölgesi) `▲` zarar yazar; `OB` filtrelemesi ise hiçbir fark yaratmaz. |

---

### 4.2 Üstten Alta (`Direnç Dönüşü`, `▼`, `üst -> alt` Geçişleri, `Alçalan Basamak`) Bulguları

| Kaynak Çalışma & Evren | İncelenen Yön / Kurulum | Gerçek Örneklem (`n`) ve Değiştirilmemiş Sonuçlar | Tasarıma Doğrudan Etkisi |
|---|---|---|---|
| **`OK_SISTEMI_2026-11-08.md` §13** (`176` sembol, `1g`, keşif/doğrulama) | Sabit direnç (`R`) altında dolu `▼` (`close_return_below` + `intrabar_sweep_rejection`, `927` ok) vs dirençteki ok olmayan barlar (`n = 6.477`) | **Üç yansıtmanın üçünü de Bonferroni ile geçti:**<br>• `R1 (-1/+1 ATR)` vs Kontrol B: **`%54,5 vs %46,7` (`+7,8`)** / **`%58,8 vs %49,3` (`+9,5`)** — **GEÇTİ ✓**<br>• `R2 (-2/+1 ATR)` vs Kontrol A: **`%40,6 vs %32,2` (`+8,4`)** / **`%41,9 vs %31,5` (`+10,5`)** — **GEÇTİ ✓**<br>• `R3 (10 bar direnç altı)` vs Kontrol B: **`%63,2 vs %51,3` (`+11,9`)** / **`%65,4 vs %53,1` (`+12,3`)** — **GEÇTİ ✓**. | Sabit/yatay `R` altındaki dolu `▼`, yalnızca seviye tutma değil **doğrulanmış sinyal-dereceli aşağı dönüş ve `-2 ATR` koşu olayıdır**. |
| **`STABIL_SORU_SETI_V2_2026-11-08.md`** (`119` sembol, `1g`, `n = 5.530` geçiş) | 9 durum ve 59 geçiş içinde üstten alta / aşağı yönlü doğrulama | `0` adet `OK-▲` çıkarken **5 adet `OK-▼`** iki bölmeyi de geçti:<br>1. `ust+asagi -> ust+sabit` (`n = 465/187`, `DOWN lift +6,9/+6,3`, `p = 0,0004`)<br>2. `ust+asagi -> yapisik+asagi` (`n = 226/108`, `+11,7/+3,8`, `p = 0,0005`)<br>3. `ust+asagi -> alt+asagi` (`n = 63/23`, **`+14,7/+17,4`**, `p = 0,0022`)<br>4. `ust+sabit -> yapisik+sabit` (`n = 103/50`, **`+7,4/+14,5`**, `p = 0,0087`)<br>5. `ust+yukari -> alt+yukari` (`n = 82/30`, **`+9,6/+13,2`**, `p = 0,0132`). | Sistemin doğal istatistiksel asimetrisi **üstten alta kırılma ve yatay tavan/taban çöküşü** yönündedir. |
| **`genel_okuma_2026_11_08.csv` (`A3d` & `A4`)** (`119` sembol, `1g`) | Fiyat yeri geçiş aileleri ve `OK-▼` ailesi sığ kapısı | İki bölmede geçen tek aile **`üst -> alt`**: `nK = 197` (`DOWN %53,3`, `lift +9,3`, `p = 0,0045`), `nD = 75` (`DOWN %58,7`, **`lift +15,2`**, `p = 0,0039`). `OK-▼` ailesi + tek sığ kapı (`rvol ≥ 0,8 & gövde ≥ 0,20`): **`DOWN %56,9 / %57,4`** (`lift +12,8 / +14,0`, `n = 466 / 188`, `p ≤ 0,0001`). | Tek bir sığ mum kapısı, doğru yapısal geçişin üstüne konduğunda maksimum verimi üretir; derin filtreye gerek yoktur. |
| **`stabil_direnc_replay_2026_11_06`** (`174` hisse, `4s` & `1g`) | Üstten aşağı dönüş (`RETURN_TO_SAFE_SIDE`) taşma derinliği ve sahte-seviye kontrolü | Direnç üstüne sığ taşma (`0..0,5 ATR`, `n = 140`) sonrası altına dönüşte `-1 ATR` önce **`%52,9`** vs `+1 ATR` `%44,3`; `> 1 ATR` taşma sonrası dönüşte (`n = 584`) **`%49,8 vs %44,0`** (`med -0,22 ATR`). `SHIFT_DOWN` eşleşmeli kontrol (`194` çift): gerçek `R` `%50,0` vs sahte `%39,7` (**`+10,3` puan**). | Direnç üstüne fitil/sığ taşma yapıp altına kapanan dönüşler (`▼` çekirdeği) rastgele seviyelerden anlamlı biçimde üstündür. |

---

### 4.3 Simetrik Eş-Kural (`Destek` ↔ `Direnç`) Karşılaştırma ve Yol Bulguları

| Ölçüt | `Stabil S` (Destek) Gerçek Değeri | `Stabil R` (Direnç) Gerçek Değeri | Kaynak & Mantıksal Sonuç |
|---|---|---|---|
| **Koşulsuz 4S `TEST` (`8×4s`, Y2026, 174 hisse)** | Tepki `%41,3` / **Kırılma `%51,6`** (`n = 1.616`) | Tepki `%42,1` / **Kırılma `%51,6`** (`n = 1.241`) | `stabil_destek_direnc_karsilastirma`: İki çizgi temel temas davranışında birebir aynadır (`178` eşleşik çift farkı `+1,1` puan; 50 hissede `53` çift `0,0` puan). |
| **Kırılma Sonrası `8×4s` İçinde Eski Çizgiye En Az Bir Kapanışla Dönüş** | **`%53,9`** (`825 / 1.531`) | **`%58,3`** (`781 / 1.340`) | Kırılmaların yarıdan fazlası 8 bar içinde eski çizgiyi tekrar yoklar; ancak cılız dönüş kalıcı değildir. |
| **`24×4s` Kırılma Yolu: Fiyat Eski Çizgiye Önce vs Çizgi Ters Basamak Önce** | Fiyat döner **`%63,3`** (`928/1.467`), Çizgi iner `%16,1` | Fiyat döner **`%69,4`** (`856/1.233`), Çizgi çıkar `%12,5` | `yol_bulgulari.md` (Y2026): İlk dönenlerin kalan pencerede **yeniden kırılma oranı** destekte **`%57,2`**, dirençte **`%57,0`**'dir → cılız geri alım/dönüş elenmelidir! |
| **Dikey Basamak vs Sonrası Yatay (`F01`, Y2026, 174 hisse)** | Düşen `S` (`n=2.823`): yukarı `%33,2` / aşağı `%25,6` → Yataylaşan `S` (`n=9.376`): **yukarı `%37,7`** | Yükselen `R` (`n=3.311`): aşağı `%37,3` / **yukarı devam `%37,5`** → Yataylaşan `R` (`n=11.235`): **yukarı devam `%28,5`'e düşer (`-9,0` puan)** | **Püf Noktası 8'in anahtarı:** Yükselen (dikey) `R` trendi durdurmaz (kontrollü düzeltme); yataylaşan `R` ise yukarı devamı `%37,5 → %28,5` keserek gerçek tavan kurar. |
| **`1,5–3,5 ATR` Uzaklaşmada Çizgi–Fiyat Yarışı (`A01`, `24×4s`, 174 hisse)** | `2–3,5 ATR` uzakta (`n=17.022`): `S` yukarı takip **`%41,9`**, fiyat dönüşü `%16,4` | `2–3,5 ATR` uzakta (`n=20.452`): `R` aşağı takip **`%40,4`**, fiyat dönüşü `%16,4` | Trend uzadığında gerideki çizgi `%40+` oranında basamaklayarak fiyatın arkasına hizalı tampon taşır. |

---

### 4.4 `Market Structure` (`BOS`, `CHoCH`, `PH/PL`, `WH/WL`) ve `Formasyon` Yaşam Döngüsü Bulguları

| Kaynak Çalışma | Ölçülen Yapısal Özellik | Değiştirilmemiş Gerçek Sayılar | Ok Sistemiyle Bağlantısı |
|---|---|---|---|
| **`ARASTIRMA_BULGULARI.md` Soru 5** (`704` seri, `200.028` MS olayı) | `BOS` ve `CHoCH` yön devamlılığı | Yön uyumu **`%93,2–%98,2`**, `TERS` yalnız **`%0,5–%4,0`**, `CALISTI (≥1 ATR)` **`%64,0–%77,2`** (`EXTERNAL` > `INTERNAL`). | Ters `BOS`/`CHoCH` akıntısına karşı tek mumluk `▲`/`▼` basılmamalıdır. |
| **`REPLAY_SORU_YANITLARI` S25 & S26** (`202.938` MS olayı, `57.647` BOS) | `BOS` hız profili ve yaşlanma (`SUPERSEDED`) | Hareketin **medyan `%60`'ı ilk `3` barda** gelir (`medyan tepe = 6. bar`). Eski `BOS`'ların **`%93,2–%96,4`'ü** zamanla `SUPERSEDED` olur. | Yalnız **taze / güncel** `BOS` (TF-ölçekli bar penceresi) dikkate alınır; ok sonrası **ilk `1–3` barda** ters `BOS` gelirse ok nedensel olarak ezilmiş sayılır. |
| **`ARASTIRMA_BULGULARI.md` Soru 6 & 7** (`704` seri, `273.583` rol aralığı) | `PH` / `PL` deneme dayanımı ve `WH` / `WL` süpürülme hızı | `1g EXT PH`: 1. deneme `%36,2` → `4+` deneme **`%11,1` engelleme (`%88,9` kırılım)**; `PL`: `%37,8 → %32,3`. `WH/WL` her 4 TF'de **ortanca `3,0` barda** süpürülür. | Bu MS seviyeleri Stabil çizgileriyle aynı değildir; çoklu test ve yorulma yalnız ilgili kesitin betimsel sonucudur. |
| **`FORMASYON_SONUCLARI.md` FRM-02, 04, 15, 17, 20** (`33.964` formasyon) | Formasyon genişliği, daralma, başarı ve başarısızlık şiddeti | Doğum genişliği **`0,34–0,52 ATR`**, daralma **`%76,6`**. Tamamlanma **`%76,2`** (`MFE 1,23 ATR`); `BASARISIZ_KIRILIM` (`%19,1`) ters `MAE` **`2,83 ATR`**. Yapı uyumu (`FRM-20`) **`+6,4` puan** (`%79,6 vs %73,2`). | Aktif dar formasyon içinde karşı sınıra sıkışmış oklar susturulmalı; sınırla/kırılımla hizalı oklar korunmalıdır. |
| **`KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md`** (`174` hisse × `4` TF, `25.457` aday) | Kırılım adayından teyide geçiş ve başarısız kırılım | `15.947` teyidin **`12.163`'ü 1. barda, `3.784`'ü 2. barda** gelir. Başarısız kırılımlarda `-2 ATR` yeme oranı **`%50,8–%83,3`**. Dönem değişince yukarı/aşağı üstünlüğü yer değiştirir (`4s yukarı %35,1 → %19,8`, `4s aşağı %20,6 → %41,7`). | Tek bir piyasa dönemine aşırı uyum (derin filtre) yerine her iki yönde simetrik yapısal kurallar kurulmalıdır. |

---

## 5. Kanıt Sınırları: Doğrudan Ölçülenler, Mekanik Çıkarımlar ve Henüz Birlikte Sayılmamış Kesitler

Yanlış güven veya uydurma yorum üretmemek adına bulguların kanıt derecesi üç net sınıfa ayrılmıştır:

1. **Arşivde Doğrudan Ölçülmüş Sonuçlar (kendi örneklem ve tanımlarıyla):**
   - Sabit `S` üzerinde dolu `▲` okunun **seviye tutunma** üstünlüğü (`R3`: `+14,0 / +8,8` puan, `p = 2·10⁻⁹ / 0,0053`), sabit `R` altında dolu `▼` okunun **hem yön hem `-2 ATR` koşu hem seviye** üstünlüğü (`R1`, `R2`, `R3` üçü de Bonferroni geçti).
   - `Blok` (`OB` / `FVG`) yakınlığının hem 4s `▲` oklarında (`%25,1 vs %25,9`) hem formasyon kırılımlarında (`FRM-19`: `-1,1` puan) ek filtre değeri taşımadığı.
   - Derin tek-değişkenli mum filtrelerinin senaryo-stratifiye Mantel–Haenszel testinde çöktüğü (`OR = 0,85–0,93`, `p > 0,28`), buna karşılık yapısal geçiş ailesi + tek sığ kapının doğrulandığı (`DOWN %56,9 / %57,4`, `lift +12,8 / +14,0`).
   - Dikey yükselen desteğin (`STEPPING_UP`) yataylaşmadan önce negatif beklenti (`DOWN_first %53,5`, `med -0,29 ATR`) ve kırıldığında doğrulanmış düşüş (`ust+yukari -> alt+yukari` `DOWN lift +9,6 / +13,2`) ürettiği; yataylaşınca pozitife döndüğü (`UP_first %58,2`, `med +0,11 ATR`).
   - Dikey yükselen direncin (`R` yukarı basamak) yukarı trendi durdurmadığı (`yukarı devam %37,5–%39,4`), buna karşılık yataylaşan direncin yukarı devamı sert kestiği (`%28,5–%29,5`).
   - Temas grupları için betimsel farklılıklar ölçüldü; ikinci temas otomatik onay değildir, 3+ grup tek hissede yoğunlaşır. `%48,5` ve `%60,0` 16×4s önce −1 ATR oranlarıdır, destek kırılması oranları değildir (bkz. §3.4).
   - `◇` işaretinin olayların `%87,8`'ini oluşturup hiçbir karar kuralına bağlanmadığı.

2. **Ayrı Replay Bulgularından Esinlenen, Birlikte Ölçülmemiş Hipotezler:**
   - `BOS` devamının `%60`'ının ilk `3` barda gelmesi (`S26`) + `BOS` yön uyumunun `%93–98` olması (`Soru 5`) + ilk `TEST`'lerin `%51,6` kırılması ⇒ **TF-ölçekli yakın ters `BOS` penceresinde tek mumluk okların bastırılması ve ok sonrası `1–3` barda ters `BOS` gelirse okun iptal edilmesi.**
   - Formasyon medyan genişliğinin `0,34–0,52 ATR` ve daralmanın `%76,6` olması (`FRM-02/04`) ⇒ **aktif formasyon içinde karşı sınıra (`upper_now` / `lower_now`) sıkışmış okların hareket alanının bulunmaması.**
   - Dikey `R`'de yukarı devamın `%37,5–39,4` kalması + `A01`'de `S`'nin `%35,4–41,9` arkadan basamaklaması vs yatay `R` `▼` okunun `-2 ATR` koşması + `üst -> alt` ailesinin `%53,3 / %58,7` düşmesi ⇒ **dikey `R` + altta hizalı `S`'de kontrollü düzeltme, yatay `R` + destek kaybında sert çözülme.**

3. **Geçmişte Tekil Katmanlar İzole Koşulduğu İçin Henüz Aynı Bar Üzerinde Birlikte Sayılmamış Kesitler (Sayı Uydurulmayan Noktalar):**
   - Aynı bar üzerinde eşzamanlı `(R(t) - close(t)) / ATR(t)` ve `(R(t) - S(t)) / ATR(t)` kovalarının doğrudan `▲` / `▼` başarı oranıyla çapraz tablosu (`stabil` ve `stabil_direnc` ayrı çalıştığı için geçmiş CSV'lerde tek satırda birleştirilmemiştir).
   - TF bazında (`1s`, `2s`, `4s`, `1g`) tam kaç mumluk ters `BOS` penceresinin (`ör. 1s=10, 2s=6, 4s=4, 1g=2` vs alternatifleri) hassasiyet/kayıp eğrisi.
   - `1 saatlik` ve `2 saatlik` zaman dilimlerinde Stabil oklarının doğrudan ayrı replay'i (geçmiş ok replay'leri `4s` ve `1g` üzerinde koşulmuş, MS ve formasyon ölçümleri farklı olayları kapsar; Stabil altı boş hipotezini dört TF’de doğrulamaz).

---

## 6. Sığ ve Yüksek İsabetli Hedef Mimari Özeti (Uygulama Öncesi Referans Tablosu)

Aşağıdaki tablo **uygulama kararı değil, aday fikirlerdir**; etkileri ve eşikleri doğrudan doğrulanmamıştır. Gelecekte derin filtre kurmadan ve nedensel biçimde değerlendirilmelidir.

| Kural Başlığı | `▲` (Stabil Destek Geri Alımı — *Yapı Olayı*) | `▼` (Stabil Direnç Dönüşü — *Sinyal-Dereceli Olay*) | Kapsam & Derinlik Sınırı |
|---|---|---|---|
| **1. Temel Çekirdek** | Yatay/sabit `S` üzerinde mevcut güçlü geri alım veya fitil silkelemesi (bkz. §3.10; dolu okta hacim şartı yok). | Yatay/sabit `R` altında güçlü dönüş veya üst fitil reddi (`close_return_below`, `intrabar_sweep_rejection`). | Mevcut kanıtlanmış çekirdek korunur; mikro bayrak eklenmez. |
| **2. Evrensel "Altı / Üstü Boş" Kuralı (`Tüm TF'ler`)** | `S` dikey basamaklıyorsa / altı yatay tabansız boşsa (`1s, 2s, 4s, 1g` fark etmez), pozitif `BOS` olsa bile `▲` basılmaz. | `R` dikey şelale basamaklıyorsa (üstü boşsa) veya uzun yükselişte `R` dikey yukarı basamaklarken altta yakın hizalı `S` varsa (kontrollü düzeltme rejimi) agresif düşüş `▼` sinyali basılmaz. | Tüm zaman dilimlerinde geçerli; proxy aşırı geniş tutulmaz. |
| **3. `◇` İşaretinin Kaldırılması** | Bastırılan `▲` veya zayıf temas yerine grafikte **`◇` çizilmez** (tam sessizlik). | Bastırılan `▼` veya zayıf temas yerine grafikte **`◇` çizilmez** (tam sessizlik). | `_DIKEY_UYARI_SOGUMA_BAR` yamasına gerek kalmaz; grafik sadeleşir. |
| **4. TF-Ölçekli Taze Ters `BOS` / `CHoCH` Kapısı** | Son `N_tf` mum içinde (`1s > 2s > 4s > 1g` ölçekli) taze bir **`DOWN BOS / CHoCH`** varsa ve henüz yukarı yapı onarımı gelmemişse tek mumluk `▲` bastırılır. | Son `N_tf` mum içinde taze bir **`UP BOS / CHoCH`** varsa ve henüz aşağı yapı kırılımı gelmemişse tek mumluk `▼` bastırılır. | Yalnız `CURRENT` (ezilmemiş) taze kırılım; bayat `STATE` bakılmaz. |
| **5. Formasyon İçi & İkili `(S, R)` Duvar Sıkışması** | Aktif formasyonun üst çizgisi (`upper_now`) veya aktif yatay `Stabil R` hemen tepedeyse (dar `runway_up`), iç sıkışmadaki `▲` bastırılır. | Aktif formasyonun alt çizgisi (`lower_now`) veya aktif yatay `Stabil S` hemen alttaysa (dar `runway_down`), iç sıkışmadaki `▼` bastırılır. | `Blok` (`OB` / `FVG`) **kesinlikle bakılmaz**; yalnız `Formasyon` ve karşı `Stabil` çizgisi. |
| **6. Tekrar test ve yorulma** | İkinci test otomatik onay değildir; tepki ve tutunma izlenir. Cılız/tekrarlanan temas yorulma hipotezidir. | Tekrar direnç testleri ayrı bağlamda izlenir; otomatik simetrik sonuç varsayılmaz. | Formasyon hizası ve 7–8 mum aralığı ölçülmemiş gözlemdir. |
| **7. Ok Sonrası `1–3` Mum Ters `BOS` Ezilmesi (Nedensel)** | `▲` basıldıktan sonraki `1–3` mum içinde **`DOWN BOS`** gelip seviyeyi ezerse, ok o bardan itibaren nedensel olarak `ezildi / soluk` durumuna geçer. | `▼` basıldıktan sonraki `1–3` mum içinde **`UP BOS`** gelip seviyeyi ezerse, ok o bardan itibaren nedensel olarak `ezildi / soluk` durumuna geçer. | Geçmiş bar silinmez (sıfır lookahead); yalnız ezilme barından sonra statü güncellenir. |

---

### Kaynak Replay Dosyaları Dizini (Doğrulama Bağlantıları)

- **Günlük `▲` / `▼` Tabanlı Denetim ve `◇` Seyreltme (176 ve 50 sembol):** [`OK_SISTEMI_2026-11-08.md`](OK_SISTEMI_2026-11-08.md) (§10–§14)
- **Stabil Mimari, 40-Sembol Birim Testi ve 174-Hisse Ok Özeti:** [`STABIL_SISTEM_INCELEMESI_2026-11-08.md`](STABIL_SISTEM_INCELEMESI_2026-11-08.md) (§2–§8)
- **9-Durum, 59-Geçiş, Mantel–Haenszel ve `OK-▼` Ailesi Doğrulaması (119 sembol):** [`STABIL_SORU_SETI_V2_2026-11-08.md`](STABIL_SORU_SETI_V2_2026-11-08.md) · [`genel_okuma_2026_11_08.csv`](stabil_soru_seti_v2/genel_okuma_2026_11_08.csv) · [`senaryo_dogrulama_sonuclari_2026_11_08.csv`](stabil_soru_seti_v2/senaryo_dogrulama_sonuclari_2026_11_08.csv) · [`senaryo_teshis_sonuclari_2026_11_08.csv`](stabil_soru_seti_v2/senaryo_teshis_sonuclari_2026_11_08.csv)
- **100 Hisse 48 Davranış Sorusu ve 16 Geri Alım Analizi:** [`STABIL_100_HISSE_ANALIZ_SENTEZI.md`](STABIL_100_HISSE_ANALIZ_SENTEZI.md) · [`STABIL_DAVRANIS_48_YANITLARI.md`](stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md) · [`STABIL_GERI_ALIM_VE_KART_ANALIZI.md`](STABIL_GERI_ALIM_VE_KART_ANALIZI.md) · [`STABIL_GERI_ALIM_16_SONUCLAR.json`](stabil_100_sonuclar/STABIL_GERI_ALIM_16_SONUCLAR.json)
- **50 Canlı Sembol 4S Geri Alım Doğrulaması:** [`STABIL_CANLI_SEMBOL_SISTEMATIGI.md`](STABIL_CANLI_SEMBOL_SISTEMATIGI.md)
- **174 Hisse 4S Ok Bağlam Replay'i (`OB`, `FVG`, `MS`, Rejim):** [`stabil_ok_replay_2026_11_05/RAPOR.md`](stabil_ok_replay_2026_11_05/RAPOR.md) · [`toplu_bulgular.md`](stabil_ok_replay_2026_11_05/toplu_bulgular.md)
- **174 Hisse & 50 Hisse Destek–Direnç Eş-Kural, Simetri ve Yol Replay'leri:** [`stabil_destek_direnc_karsilastirma_2026_11_06/RAPOR.md`](stabil_destek_direnc_karsilastirma_2026_11_06/RAPOR.md) · [`toplu_bulgular.md`](stabil_destek_direnc_karsilastirma_2026_11_06/toplu_bulgular.md) · [`yol_bulgulari.md`](stabil_destek_direnc_karsilastirma_2026_11_06/yol_bulgulari.md) · [`stabil_direnc_replay_2026_11_06/toplu_bulgular.md`](stabil_direnc_replay_2026_11_06/toplu_bulgular.md) · [`stabil_direnc_50_model_testi_2026_11_06/RAPOR_50.md`](stabil_direnc_50_model_testi_2026_11_06/RAPOR_50.md) · [`sabit_cizgi_yollari.md`](stabil_direnc_50_model_testi_2026_11_06/sabit_cizgi_yollari.md)
- **Market Structure, Zone ve Hacim Arşiv Replay'leri (704 / 708 seri):** [`ARASTIRMA_SONUCLARI.md`](ARASTIRMA_SONUCLARI.md) · [`ARASTIRMA_BULGULARI.md`](ARASTIRMA_BULGULARI.md) · [`REPLAY_SORU_YANITLARI_2026-10-29.md`](REPLAY_SORU_YANITLARI_2026-10-29.md)
- **Formasyon Yaşam Döngüsü ve Kırılım/Teyit Replay'leri (`33.964` formasyon & `25.457` aday):** [`FORMASYON_SONUCLARI.md`](FORMASYON_SONUCLARI.md) · [`KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md`](KIRILIM_TEYIT_REPLAY_AYRINTILI_DOSYA_2026-10-30.md) · [`TEYIT_SONRASI_HAREKET_2026-10-30.md`](TEYIT_SONRASI_HAREKET_2026-10-30.md) · [`KOSULLU_CUMLE_OLCUMU.md`](KOSULLU_CUMLE_OLCUMU.md)

### Uygulama kararı: çok mumlu toparlanma (2026-11-09)

Kullanıcı tek mumlu `close_reclaim`in grafik, kart ve alarmdan kaldırılmasını,
çok mumlu yolun sayısal tanımının seçilmesini ve hemen sonraki mumda yalnız
yeşil kapanışın yeterli olmasını onayladı. Uygulama hipotezi: aynı sabit destek
üzerinde, geri alım mumu dahil üç mumdan en az ikisi yeşil ve kapanışlar
art arda yükselir; ilk iki mumun destek altındaki en düşük dibi geri alım
mumunun dibinden yüksek değildir ve geri alım kapanışı bu dipten en az 0,5 ATR
yukarıdadır. İlk sonraki kapalı mum yeşilse olay o mumda kaydedilir; bu mumun
destek üstünde kapanması aranmaz. Destek değişirse aday düşer. Bu eşikler
uygulama seçimi olup replay ile ölçülmüş performans iddiası değildir.

### İlk bağlam uygulaması: kapsam ve sınırlamalar

Taze dış BOS/CHoCH için başlangıç pencereleri 1s=10, 2s=6, 4s=4,
1g=2 bardır; bunlar ölçülmüş optimumlar değil uygulama hipotezleridir.
Yalnız zaman damgası hedef mumla eşleşen, kapanışta onaylı olaylar okunur;
en son ters yapıyı sonraki aynı yönlü yapı onarabilir. Ok sonrası ilk üç
barda ters BOS gelirse grafik o oku o andan itibaren bastırılmış olarak
kaydeder; gönderilmiş 4s alarmın durumu da uygun yapı verisi varsa güncellenir.
Geçmişte gönderilmiş Telegram bildirimi geri alınmaz veya değiştirilmez. Veri eksikse ters olay
varmış gibi davranılmaz. Grafik koridorunda karşı Stabil çizgisi veya yalnız
şimdiki formasyon sınırı 0,5 ATR içinde ve hareket yönündeyse ok bastırılır.
Bu mesafe de test edilmemiş bir hipotezdir; geçmişe bugünkü formasyon
geometrisi taşınmaz. Blok verisi kullanılmaz. Koridor ve aynı mumdaki aktif formasyon sınırı bağımsız 4s alarmında da,
yalnız mevcut ve zaman hizalı kaynaklar varsa değerlendirilir. `/stabil` komutunda aynı anlık ve zaman hizalı yapı önbelleği varsa ters
yapı bağlamı uygulanır; güncel mum için eşleşen formasyon ve doğrulanabilen
direncin karşı sınırı da değerlendirilir. Geçmiş bir oka bugünkü formasyon
taşınmaz. Eksik kaynaklar otomatik olarak engel sayılmaz.


**Altı/üstü boş sınırı:** Mevcut dikey/kademe proxy'si tüm desteklenen TF'lerde
korunur; geometrik bir hava boşluğu veya yatay tabansızlık ayrıca ölçülmedi.
Bu nedenle proxy ile gerçek görsel boşluk eşdeğer kabul edilmez ve evrensel
performans iddiası yapılmaz.
