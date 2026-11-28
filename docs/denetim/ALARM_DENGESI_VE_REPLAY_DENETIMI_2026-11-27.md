# Alarm dengesi, filtre etkisi ve replay güvenilirliği

> **Devam çalışması:** [Nedensel alarm kapsamı: seçilenler, bastırılanlar ve gecikme](NEDENSEL_ALARM_KAPSAMASI_2026-11-27.md). Aşağıdaki eski sayımlar retrospektif proxy olarak korunur; adet azalması kalite artışı değildir. Onarılmış aday akışının yeni kohortlarını bu tablolara karıştırmayın.

**Tarih:** 27 Kasım 2026. **Aşama:** mevcut sistemi teşhis; yeni canlı filtre seçimi değil.
**İstek:** daha dengeli, daha net alarmlar; önce mevcut eksikler ve eklenen filtrelerin günlük ortalamaya etkisi.
**İncelenen:** mevcut çalışma ağacı; daha önceki mum/AI/teslim düzeltmeleri korunmuştur. Bu incelemede canlı alarm kodu, eşikler, motorlar, Telegram hedefleri değiştirilmedi. Commit/push/deploy yok.

## 1. Yönetici sonucu

1. **P6 çok güçlü bir hacim filtresi.** Eski pilotu bugünkü araştırma koduyla tekrar ürettim: aynı 22 seans, 50 sembol, dört native TF üzerinde P0 + 6 bar cooldown **97,09**, P6 + aynı cooldown **35,68 potansiyel olay/seans**; **%63,25 azalma**. Bu bütün botun veya senin DM'inin beklenen günlük bildirimi değildir.
2. **Az alarm = daha kaliteli alarm sonucu çıkmıyor.** Yönlü kaliteyi doğrulaması beklenen domain replay'inde önemli yön ve nedensellik kusurları bulundu. Bu yüzden eski %67–69 “isabet” oranlarını yeni filtre kararı için geçerli kanıt saymıyorum.
3. **P6 dengeli/yön bağımsız bir filtre değil.** Koşu, olay yönüne göre değil fiyatın pozitif 6 bar değişimine göre hesaplanıyor. “Genişleme” adı verilen oran da son 10 barın, onları içeren son 50 bara oranı; normal veride 1'i geçemez. Bu pilotta P6 esas olarak “fiyat zaten yukarı koşmuş mu?” seçimi yapıyor.
4. **Üç alarm yolunu tek filtre sanmamak gerekiyor.** Ana formasyon, Stabil 4s geri alım ve yeni domain farklı kapı/state/cooldown kullanıyor. P6 yalnız yeni domain yolunda; geometri ve devamlılık ayarları bütün yolları ortak biçimde yönetmiyor.
5. **15 → 3–5 düşüşü filtrelerle büyüklük olarak uyumlu olabilir; nedeni kanıtlanmış değil.** Hangi alarm yolu/hedef/dönem karşılaştırıldığı ve o dönem çalışan env/state bilinmeden kesin atıf yapamayız. Arşiv yeni dönemin tamamını da kapsamıyor.

**Önerim:** İlk iş filtre eklemek veya P4'e geçmek değil; domain replay'i kapanış-anı snapshot'larıyla güvenilir hâle getirmek ve üç alarm yolunu aynı olay/teslim defterinde ölçmek. Sonra netliği ilk bariyer sırası, ters hareket ve kapanışta korunan hareketle değerlendirmek.

## 2. Neyi gerçekten çalıştırdım?

### 2.1 Yeni arşiv koşusu

- `research.domain_alarm_replay --aktif-evren --son-bar 480`: **50 sembol × 4 TF = 200/200 seri; 0 hata; 252 sn**.
- Kaynak: `backfill_data/` içindeki **native 1h/2h/4h/1d** dosyaları. Bu koşuda 2h/4h yeniden örneklenmedi.
- Her serinin son en fazla 480 mumu: TF'ler aynı takvim süresini kapsamaz. Önceki mumlar motor ve cooldown hazırlığı için korunur; bu, tam arşivden başlatılmış bir motor koşusuna eşdeğer değildir.
- Ortak değerlendirme: **19 Ekim–18 Kasım 2026, 22 İstanbul seansı**. Son/kısmi gün dışarıda. Sıfır olaylı günler paydada tutulur; olay tarihinden gün uydurulmaz.
- Kapsam: repo varsayılan aktif evreninin 50/57 sembolü. Arşiv dışında BRENT, USDTRY, XAGUSD, XAUUSD, XBANK, XU50, XUSIN. Üretim evreni/env doğrulanmış değildir.
- 43.596 ölçüm satırı, kontroller dahil **37.165 tekil olay**. Değerlendirme penceresinde kontroller hariç **6.462 tekil tetik**; bunların 121'i iki ayrı yön ölçüm satırına açılmıştır. Aynı sembol/TF/bar tek olay sayıldı.
- Politika **cooldown'dan önce**, cooldown **pencere öncesi geçmişi kaybetmeden** uygulanır. Sonucu tamamlanmamış olay sıklığa girer, kaliteye başarısız diye yazılmaz.

**Kritik sınır:** Bu yeni koşu eski hesabı yeniden üretir; aşağıdaki nedensellik testinden geçmeyen eski domain tetik rekonstrüksiyonunu kendiliğinden düzeltmez. Sayılar **retrospektif proxy/filtre duyarlılığı**dır; doğrulanmış nedensel canlı simülasyon veya Telegram teslimi değildir.

### 2.2 Kayıtlı sonuçların yeniden okunması

- `ALARM_POLITIKA_P0_P6_2026-11-20.md`: 2.136/785 olay sayıları yeni koşuda aynı çıktı.
- `sonuclar/bes_alarm_pilotu/OLAYLAR.csv.gz` ve `genis/ADAYLAR.csv.gz`: ham satırlardan grup/payda ve ilk ±1 ATR sayımları yeniden yapıldı; ilgili kayıtlı raporla uyumlu. Bu **yeni replay/ileri test değildir**.
- Eski `sonuclar/kirilim_replay/manifest.json`: kayıtlı **348 kaynak dosyası hash'inin hiçbiri mevcut arşiv baytlarıyla aynı değil**; en son aday 19 Ekim. Hash farkı bütün fiyatların değiştiğini kanıtlamaz, fakat aynı girdi iddiasını engeller. `research/kirilim_denetim.frame_for` ayrıca 2h/4h'yi 1h'den türetiyor. Bu sonuçları bugünkü native alarm akışının günlük tahmini diye taşımadım.

## 3. Filtreler günlük sayıyı ne kadar etkiliyor?

**Birim: tekil sembol × TF × bar potansiyel olayı / ortak seans. Teslim edilmiş mesaj değil.**

| Senaryo | 22 seansta olay | Ortalama/seans | Medyan/seans | P0 + 6 bara göre |
|---|---:|---:|---:|---:|
| Hiç politika yok, cooldown yok | 6.462 | 293,73 | 297,5 | karşılaştırma tabanı değil |
| **P0 + 6 bar cooldown** | **2.136** | **97,09** | **99,5** | taban |
| P1: yalnız tek BOS'u sustur + 6 bar | 2.061 | 93,68 | 95,5 | −%3,51 |
| P2: yalnız hacim ≥5× + 6 bar | 47 | 2,14 | 1,0 | −%97,80 |
| P3: zayıf kanallar tek başına sessiz + 6 bar | 1.415 | 64,32 | 65,0 | −%33,75 |
| **P6: mevcut bağlam + 6 bar** | **785** | **35,68** | **31,0** | **−%63,25** |
| P4: katman + bağlam; yüksek hacim istisnası + 6 bar | 500 | 22,73 | 19,0 | −%76,59 |
| P5: P3 + seçili saatler + 6 bar | 711 | 32,32 | 29,0 | −%66,71 |
| P7: P6 veya yüksek hacim + 6 bar | 811 | 36,86 | 31,5 | −%62,03 |

P1/P2/P3/P5/P7 araştırma alternatifleridir; canlı politika seçicisi yalnız P0/P6/P4 kabul eder. Buradaki alternatifler devreye alınmadı.

### 3.1 P6 ve cooldown'un etkisini ayırma

Aynı ham 6.462 olay üzerinde, **P6 önce**:

```
6.462 ham olay
  └─ P6: 4.808 elenir (%74,40); 1.654 kalır (75,18/seans)
       └─ 6 bar cooldown: 869 daha elenir (%52,54 kalan üzerinden)
            └─ 785 kalır (35,68/seans)
```

P0 altında yalnız cooldown: 6.462 → 2.136 (**−%66,95**). İki koruma birlikte filtresiz/cooldown'suz tabana göre **−%87,85**. P6'nın **zaten cooldown'lu** P0'a marjinal etkisi ise **−%63,25**. Bu yüzdeler toplanmaz; kapılar etkileşir ve hangi olayın cooldown başlattığı değişir.

| P6 yanında cooldown | Olay | Ort./seans | Mevcut P6+6'ya göre |
|---|---:|---:|---:|
| Yok | 1.654 | 75,18 | +%110,70 |
| 3 bar | 1.034 | 47,00 | +%31,72 |
| **6 bar — mevcut varsayılan** | **785** | **35,68** | taban |
| 12 bar | 627 | 28,50 | −%20,13 |

**Bunlar önerilen yeni cooldown değerleri değil**, mevcut sessizliğin hangi katmandan geldiğini gösteren karşılaştırmadır. 6 barın takvim süresi TF'ye göre çok değişir: günlükte altı işlem barı, saatlikte altı saatlik işlem barı; bütün TF'lerde “4 saat” değildir.

### 3.2 Günler arasında dağılım

- P6 medyan **31**, p90 **69,1**, tepe **89** olay/seans. Ortalama tek başına kullanıcı deneyimini anlatmıyor.
- Aynı evrende 22 Ekim P0 **93**, P6 **3**; 23 Ekim P0 **69**, P6 **5**. Bunlar **retrospektif domain adaylarıdır**, senin o gün aldığın mesajlar değil. Ancak “azaldıysa mutlaka veri bozuldu” sonucunun yanlış olabileceğini gösterir.
- İlk 11 seansta P0/P6 **92,73/30,27**, sonraki 11'de **101,45/41,09**. Bu dönem eskiden politika seçiminde kullanıldığı için bu bölme kör holdout değil, yalnız zamansal duyarlılık kontrolüdür.
- P6 olay dağılımı: 1h **348**, 2h **226**, 4h **159**, günlük **52**. Dört ayrı TF sonucu tek günlük sinyal sayısı gibi sunulmamalı.
- Ek bir filtre bazı günlerde sayıyı artırabilir: daha erken olayı susturunca sonraki olay cooldown'a takılmayabilir. Günlük farkları mekanik olarak birbirinden çıkarıp bağımsız filtre katkısı saymak hatalıdır.

### 3.3 Aynı olayın ikinci kartı ve simetri deneyi

- `YENI_DOMAIN_ALARM_IMMEDIATE_TEKRAR=0` için yalnız replay'in taşıdığı formasyon state'leriyle yapılan **proxy**: P6 **785 → 763**, **35,68 → 34,68/seans** (−%2,80). Diğer BOS/OB/FVG/hacim gerekçeleri korunur. Canlı `notification_state`, kalite ve gerçekten ana karta teslim bilgisi replay'de yok; bu tam bir çapraz-yol tekilleştirme ölçümü değildir.
- Araştırma hipotezi: koşuyu yalnız `>=+1` yerine `abs(koşu)>=1` kabul etmek **1.549 / 70,41 olay/seans** üretir. Bu “daha iyi alarm” kanıtı değildir; simetri eklemek neredeyse iki kat hacim getiriyor. **Canlıya eklenmedi.** Yönlü/risk alarmlarını birbirine karıştırmadan yeniden ölçülmeli.

## 4. Mevcut kodun filtre haritası

| Katman / yol | Mevcut kapı | Günlük etkiyi bu koşudan söyleyebilir miyiz? |
|---|---|---|
| Veri | Kapanmış bar, yeterli seri, canlı taramada seans bazlı güncellik, sağlayıcı kurtarma | Hayır; geçmiş API kesintisi/retry/gerçek tarama takvimi yok. Güvenlik kapısı korunmalı. |
| Ana formasyon | Anlık: `KIRILIM_TEYITLI`, `RETEST_BASARILI`, `KIRILIM_GECERSIZLESTI`; sıkışma özete | Domain P6 tablosu bunu ölçmez. |
| Ana formasyon kalite | 1h 80, 2h 78, 4h 75, günlük 70; iptal olayı istisnası | Hayır; bu replay'de gerçek kapanış anı effective-quality ve teslim aday defteri yok. Eski raw-quality'yi vekil kullanıp kesin günlük sayı üretmedim. |
| Devamlılık | DM/public alt sınır varsayılan **0**, yani bu musluk kapalı | Repo varsayılanıyla ilave eleme yok; üretim env'inin kanıtı değil. Eski puanlama raporunun kendi geri çekme notu da var. |
| Ana yol tekrar/kota | Kimlik/state mührü, 4 saat cooldown, MTF aile/yön/olay birleştirme 4 saat, DM/public ayrı | Olay ve teslim state'i olmadan günlük katkı ayrı hesaplanamaz. Günlük 120/saatlik 20 varsayılan tavanı; basitçe bu sayıya kırpmak doğru simülasyon olmaz. |
| İptal/geri alma | TF bazında 3/2/2/2 kapanış + 0,3 ATR derinlik; önceki teyit teslimi gerekir | Daha az yanlış iptal amaçlar; P6 tablosunun içinde değil. |
| **Yeni domain** | Yerel varsayılan şalter **kapalı**; açılırsa Stabil `dist_atr>=−3`, tazelik 390 dk, kanal tetikleri, P6 ve 6 bar | P6/cooldown **proxy** ölçüldü. Destek hard kapısı, canlı tazelik, kalite/kanal eşliği ve gerçek dispatch bütünü yeniden kurulmadı. Üretimde şalter açık mı doğrulanmadı. |
| Stabil 4s geri alım | Şalter varsayılan açık; yalnız sweep/multi-bar-recovery; kapalı günlük/4s bilgi, karşıt yapı ve yakın sınır kapıları, 6 bar cooldown | Bu çalışma domain rekonstrüksiyonundan bunun günlük etkisini türetmez. Güncel türlerle, bu kapıları ayrı kaydeden replay gerekir. |
| Kart süzgeci / görsel halkalar | `TELEGRAM_KART_SUZGEC`, bağlam güçlü/zayıf halkaları | **Sunum değişikliğidir; doğrudan alarm elemez.** Grafikte okun solmasıyla push sayısını karıştırmamak gerekir. |
| AI | Geçerli taze veride yorum; hata/eksikte düz teknik kart | AI düz karta düşüşünün aday elemesi olmaması tasarım gereği. AI hazırlık satırı da teslim makbuzu değildir. |

Yeni domain/Stabil yardımcı kuyrukları, ana formasyonun bütün public kalite/devamlılık filtrelerini otomatik olarak ortak kullanmıyor. Bu yüzden bir ayarı değiştirip üç yolun aynı oranda azalmasını beklememek gerekir.

## 5. Somut eksikler ve sorunlar

### A — Kritik: replay geçmişi gelecekten etkileniyor

Test: aynı serinin son 480 mumu için gözlemleri çıkar; ayrıca yalnız ilk 360 mumuyla tekrar çıkar. **İlk 360 mumdaki** geçmiş tetik/kanal/yönler aynı olmalı.

| Seri | Tam koşudan geçmiş olay | Yalnız prefix'te olay | Tetik/kanal/yön farklı bar |
|---|---:|---:|---:|
| THYAO 1h | 106 | 112 | 7 |
| THYAO 2h | 115 | 118 | 6 |
| THYAO 4h | 115 | 118 | 5 |
| THYAO günlük | 129 | 135 | 9 |
| ASELS 1h | 108 | 114 | 6 |
| ASELS 2h | 137 | 142 | 8 |
| ASELS 4h | 128 | 133 | 8 |
| ASELS günlük | 93 | 93 | 2 |

**8/8 seride, toplam 51 farklı bar.** Bu oran bütün evrenin hata oranı değildir; iki sembollük açık bir sözleşme ihlalidir. Örneğin THYAO 1h 26/27/124/125. bardaki BOS, kısa koşuda var, daha uzun koşuda geçmişten siliniyor.

Kodda tetik üretimi geçmiş BOS/CHoCH için **son ledger'ın** `validity/relevance` alanlarını kullanıyor; geçmişteki geçerli olay sonradan `FAILED/HISTORICAL` olunca geçmiş tetik de kaybolabiliyor. FVG reaksiyon rekonstrüksiyonu da terminal `native_full_fill` alanını okuyor. Bütün 51 farkı tek sebebe atamıyorum; kanıt, prefix değişmezliğinin bozulmasıdır.

**Etkisi:** mevcut tablonun aritmetiği tekrar üretilebilir ama gerçek zamanlı karar sırası doğrulanmış değildir. Filtreyi optimize etmek için kullanılmamalı. Daha önceki 300-seri bağlam formülü paritesi, tetik üretiminin bu zamansal paritesini sınamıyordu.

### B — Kritik: domain replay yönü güvenilir değil

- `sembol_timeframe_tetikleri`: BOS/CHoCH varlığında `yon = 1 if son_bos else 0`. Negatif BOS'u da **+1** etiketliyor. Sentetik DOWN BOS ile yeniden üretildi.
- `_yon_tahmini`, fiyatın içinde kaldığı bölgeyi seçerken bölgenin o barda doğmuş/aktif olmasını doğrulamıyor. 2. bardaki yön, **20. barda doğacak** bir BULLISH bölge eklenince 0 → +1 oluyor.
- Yön 0 olan olay yukarı/aşağı iki ölçüm satırına ayrılırken özgün “yön bilinmiyor” bayrağı kayboluyor. Eski politika hesabı bu satırlardan birini cooldown sıralamasında seçiyor; bu tek başına güvenilir yön tahmini değildir.

**Sonuç:** Eski %67–69 yönlü uzanım, “güçlü hareket yakalama” ve bunlardan türeyen politika üstünlüğü sayıları yeniden doğrulanmalı. Bu denetim yeni çıktıda yönlü başarı yayınlamıyor.

### C — Yüksek: P6'nın anlamı ve yön dengesi

- İç içe pencereler nedeniyle `range10/range50 <= 1`. `>=1` gerçek anlamda önceki döneme göre genişleme değil, kısa pencerenin uzun pencerenin tüm aralığını kapsamasıdır; dört ondalığa yuvarlama çok yakın değerleri de 1 yapabilir.
- 6.462 tetikte oran **26 kez tam 1**, **0 kez >1**, eksik **0**. Pozitif koşu **1.639**, negatif koşu **2.064** kez eşiği geçmiş.
- P6'nın geçtiği 1.654 olayın 1.639'unda zaten pozitif koşu var; oran dalı yalnız **15 ek olay** getiriyor. Bu dönemde filtre neredeyse tamamen pozitif koşu filtresi.
- Düşüş/risk kartlarını da sunan domain kanalında negatif olayları aynı pozitif koşuya bağlamak ürünün yön dengesini bozabilir. Kasıtlı yalnız-long tercihse açıkça adlandırılmalı; iki yönlü seçim isteniyorsa olay yönü korunarak ayrı denenmeli.

### D — Yüksek: canlı kartta karışık yön tek yöne indirgeniyor

`_yon_isareti`, gerekçelerde hem ↑ hem ↓ varsa önce ↑ gördüğü için **▲** döndürüyor. `BOS ↑ + OB ↓` ile yeniden üretildi. Bu iki gerekçe aynı yönde teyit değildir; karta “karışık/çatışmalı” durumu gerekir. Çelişkiyi otomatik kapıya çevirmeden önce sayısı ve sonuçları ölçülmeli.

### E — Orta: sıralama kalitesi ölçülmüş değil

Domain `rank_score` gerekçe adedi + hacim bonusu + destek altı/risk + BOS bonusu. Çok gerekçeyi daha iyi alarm saymak replay'in kendi kanal sonuçlarıyla desteklenmiyor. Özellikle `VERI_SUPHE` hacim kademesini kaldırmıyor; uç hacim yine öncelik bonusu alabiliyor. “Veri güvenilirliği”, “risk olayı”, “yönlü fırsat” aynı puanda karışıyor.

### F — Orta: sessizlik, özetleme ve kopya aynı şey değil

- Domain 6 bar cooldown sembol/TF düzeyinde; yeni yön veya farklı gerekçe için ayrı slot yok. Gürültüyü azaltır ama yeni bilgi de sessizleşebilir. Cooldown'u kaldırmak yerine **anlamlı durum değişimini** araştırmak gerekir.
- Ana formasyon ile domain'in aynı olayı ikinci kez bildirmesi varsayılan olarak açık; mevcut proxy'de kapatmak yalnız ~1 olay/seans azaltıyor. “Bütün azalma kopya temizliğinden” açıklaması desteklenmiyor.
- Burst sınırı aşılınca üst iki tekil kart + kalanları özetleyen sayfalar kullanılıyor. **Özet satırı, olay, mesaj ve albüm farklı sayılardır.** 35,68 olayı 35,68 telefona düşen bildirim saymak yanlış.

## 6. Kayıtlı replay, daha net alarm için ne söylüyor?

### Desteklenen şey: iddiayı doğru ölçmek

Yeni domain proxy'sinde 12 mumda herhangi yöne ≥1 ATR görülmesi P0 **%99,16**, P6 **%99,73**. İki yöne de ≥1 ATR P0 **%28,70**, P6 **%29,90**. Yön seçimi ters çevrilse bile bu ölçüler değişmez; fakat tetik popülasyonunun yukarıdaki nedensellik sınırı devam eder. Bunlar **yön başarısı, ilk bariyer sırası veya getiri değildir**. “Hareket oldu” metriği bu ufukta neredeyse herkeste gerçekleşiyor; net alarmı ayırt etmiyor.

### Ek filtre eklemeyi desteklemeyen kayıtlı bulgular

Erişilebilir ham aday kayıtları yeniden sayıldı; bunlar farklı dönem/evrenlerdeki eski ölçümlerdir, yeni domain tablosuyla birleştirilmez. Geniş geri alış temel grubunun 4.112/2.050 sayımı `genis/KURALLAR.csv` kayıtlı özetinden alınmıştır; daraltılmış `ADAYLAR.csv.gz` bu temel grubun tüm ham satırlarını taşımadığı için o payda bu tur hamdan yeniden üretilmedi:

| Fikir | Adayın ilk +1 ATR oranı | Karşılaştırma / sınır | Karar |
|---|---:|---|---|
| Teyit + Stabil üstü + açık karşıt bölge mesafesi | 348/694 = %50,1 | Yalnız aynı destek koşulu korunarak yakın karşıt bölge grubu önceki raporda 221/434 = %50,9; genel aday dışı 294/572 = %51,4 | Yakın OB/FVG'yi yeni evrensel hard filtre yapmak desteklenmiyor. Mevcut Stabil 0,5 ATR sınırıyla da aynı kural değil. |
| Pozitif eğim + yakın BOS + üst TF hacmi | 159/321 = %49,5 | Pozitif eğim başlangıçları 574/1.166 = %49,2 | İlave “teyit” katmanı tek başına netlik getirmemiş. |
| Dipten ≥%80 temiz yeşil yol ile geri alış | 13/19 = %68,4 | Çok nadir; genel geri alış 2.050/4.112 = %49,9. 19 temiz yolun hepsi 3–5 mum; zaman kümelenmesi var. | İlginç gölge araştırma; bağımsız alarm veya kesin kalite iddiası için yetersiz. |

15 Kasım ok bağlam çalışmasındaki güçlü/zayıf ayrımı da kendi belgesinde **görsel sınıf**, alarm filtresi değil. Eski `close_reclaim` ile güncel `multi_bar_recovery` tanımları birebir doğrulanmadan eski oranları bugünkü sinyalin karnesi saymak doğru olmaz.

## 7. Dengeli ve net alarm için önerdiğim sıra

### Öncelik 1 — Ölçüm tabanını düzelt

1. Her kapalı barda tetik snapshot'ını o anda dondur: event yönü, aktif zone kimliği/kalan sınırı, formasyon kimliği/state/kalite, Stabil destek/mesafe, veri kaynağı.
2. Gelecekteki event validity/zone dolumu geçmiş snapshot'ını değiştirmesin. Negatif BOS negatif kalsın; bilinmeyen yön ayrı alan olarak korunsun.
3. Aynı karar motorunu replay ve canlıda ortak kullan. Prefix testleri yalnız fiyat/bağlam formülünde değil **tetik + politika + cooldown kararında** çalışsın.
4. Üç yolu ve iki hedefi ayrı defterle: `aday → veri kapısı → olay/kalite → politika → tekilleştirme → kuyruk kabulü → metin/albüm teslimi`. Bir olayda bütün ret nedenleri ve sıralı ilk ret saklansın. Önceki `/akis` faydalı başlangıçtır; tam günlük/hedef bazlı defterin yerine geçmez.

### Öncelik 2 — Alarmın iddiasını ayrıştır

- **Teyitli olay:** kapanışta ne değişti, hangi seviye, ne olursa geçersiz? Ana alarm bunu taşısın.
- **Bağlam gözlemi:** OB içinde olmak, FVG teması veya hacim artışı tek başına “yön kesin” demesin. İkinci aynı-olay kartı yerine ilk kartın gerekçesi/özet adayı olarak karşılaştırılsın.
- **Risk/çatışma:** karşıt yapı veya teyit iptali “fırsat puanı” ile aynı sıralamada değerlendirilmesin. Karışık yön açıkça yazılsın.
- Kısa kart korunmalı: olay + izlenecek bölge + geçersizlik; ayrıntı komut/grafikte. AI, deterministik olmayan ek teyit kapısı değil, bu olguları açıklayan katman olarak kalsın.

### Öncelik 3 — Kalite ve yükü birlikte seç

- Önceden sabitlenmiş birkaç politika; sınırsız eşik taraması yok. Mevcut P6 referans olarak dursun, P4'e sırf daha az diye geçilmesin.
- Başarı: aynı ATR/ufukta **önce lehte mi önce aleyhte mi**, aynı mumda çift bariyer belirsiz, süre sonu ve eksik ufuk ayrı; kapanışta korunmuş hareket + MAE de gösterilsin. İşlem maliyeti modellenmeden getiri iddiası yok.
- Yük: olay/seans, hedef başına mesaj, medyan/p90/tepe, sıfır-alarm günü, TF/sembol/dönem dağılımı ve kaçırılan anlamlı olay.
- İleride kullanılacak arşivle kronolojik purge'lü bölme, sembol/gün kümeli belirsizlik ve sonra gerçek ileri gölge izleme. Bu 22 seans yeni kör doğrulama sayılmasın.
- **Şimdiki karar:** güvenlik kapıları korunur; yeni hard filtre/gevşetme yapılmaz. Önce replay sözleşmesi, sonra politika tercihi.

## 8. Senin günlük 15 → 3–5 soruna doğrudan cevap

P6'nın etkisi küçük değil: bu örneklemde cooldown sabitken yaklaşık **üçte iki azalma** var. Yalnız matematiksel bir senaryoda, aynı yol/evren/koşullarda 15 × 0,3675 ≈ **5,5** eder. **Bu senin geçmişindeki 15'in P0 domain sayısı olduğunu veya bugünkü düşüşün sebebini kanıtlamaz.** Formasyon ve Stabil toplamıysa bu çarpan uygulanamaz.

Mevcut veriden söyleyebildiğim: hem piyasa/rejim hem filtreler büyük günlük fark üretebilir. Söyleyemediğim: “kesin haberlerden”, “kesin veri kesintisinden” veya “kesin P6'dan”. Kesin ayırım için aynı kanal/hedefin karşılaştırılabilir tam gün kayıtları ve o günkü etkin konfigürasyon gerekli.

## 9. Çıktılar, tekrar koşusu ve testler

- [Özet + manifest + kaynak hash'leri](../arastirma/sonuclar/alarm_filter_audit_2026_11_27/summary.json)
- [22 seansın günlük politika sayıları](../arastirma/sonuclar/alarm_filter_audit_2026_11_27/daily.csv)
- [Prefix/yön/karışık-kart kanıtları ve kayıtlı replay kontrolleri](../arastirma/sonuclar/alarm_filter_audit_2026_11_27/replay_contracts.json)
- Yeni çevrimdışı araç: `research/alarm_filter_audit.py`; sözleşme probu: `scripts/diagnostics/alarm_replay_contract_audit.py`.

```bash
# Aynı çıktıyı karıştırmamak için ilk replay'e YENİ/BOŞ dizin ver.
STOCK_UNIVERSE='' .venv/bin/python -m research.domain_alarm_replay \
  --aktif-evren --son-bar 480 --rapor-atla --cikti var/alarm_audit_YENI
STOCK_UNIVERSE='' .venv/bin/python -m research.alarm_filter_audit \
  --input var/alarm_audit_YENI --output var/alarm_audit_ozet
.venv/bin/python -m scripts.diagnostics.alarm_replay_contract_audit \
  --output var/alarm_audit_ozet/replay_contracts.json
```

Ara ölçüm JSONL'leri `var/` altında Git dışındadır; küçük özetler/sayım kanıtı depoda tutulur. Testler çift yönün tek olay sayılmasını, bozuk çiftlerin reddini, sıfır gün paydasını, eksik sonucun başarısız sayılmamasını, pencere öncesi cooldown'u, politika sırasını ve JSONL/CLI round-trip'i kapsar.

**Doğrulama:** hedefli araştırma testleri **78 geçti**. Alarm/politika/replay/servis/tekrar/routing/grafik teslim ve patch yüzeyi geniş seçimi **1.522 geçti — 188,21 sn** (tamamlanma test logunda doğrulandı). Bu seçimler örtüşür; toplanmaz. Son kontrolde repo geneli Ruff, `git diff --check`, yeni dosyaların derlemesi ve `pip check` temiz; çıktı JSON'ları, rapor bağlantıları ve manifest kod hash'leri doğrulandı. Bu tur bütün proje testleri baştan çalıştırılmadı. Yerel Python 3.11; deploy 3.12 farkı sürüyor. Canlı API/messaging/AI çağrısı veya Supabase yazımı yapılmadı.
