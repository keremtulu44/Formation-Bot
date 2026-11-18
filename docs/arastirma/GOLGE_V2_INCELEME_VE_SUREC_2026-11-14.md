# Gölge v2 — İnceleme, Düzeltmeler ve İşlem-İçi Süreç Ölçümü (2026-11-14)

> **Durum:** inceleme + ölçüm · **Kapsam:** yalnız gölge/araştırma (`senaryo_v2/`, `research/golge_v2*.py`).
> Canlı ürün (`bot/`, `patterns/`, `grafik/`, `notifier/`, `domain_engines/`, `data/` …) ve v1 `senaryo/` değişmedi.
> **Sayıların kaynağı:** `sonuclar/golge_v2/` altındaki üretilmiş dosyalar; her bölümde dosya adı yazılıdır.
> Ana koşunun kod özeti `df187d7e9732`. Buradaki hiçbir sonuç canlı kural ya da yatırım önerisi değildir.

## 1. Kısa sonuç

1. **Körlük giderildi; ama görmek tek başına beklentiyi artırmadı.** Yarış artık işlem açıkken her kapanışta
   Stabil, Market Structure, formasyon, OB/FVG ve hacim durumunu yeniden okuyor, tezin durumunu izliyor ve
   kaydediyor. Bu gözlemlere dayanan önceden sabitlenmiş 20 yönetim kuralından **hiçbiri kabul çıtasını geçmedi**.
2. **En tutarlı aday:** kapanış tez seviyesinin ters tarafında → sonraki açılışta çık. D7'de işlem başına
   +0,018 R; üç kümede ve iki dönemde pozitif. Ancak en kötü güven aralığı sıfırı içeriyor ve doğrulama
   döneminde yalnız 29 işlemi etkiliyor. Kural değil, ileriye dönük gölge defterde izlenecek aday.
3. **"Aleyhte" görünen gözlemlerin çoğundan sonra işlemde kalmak hâlâ kazandırıyor.** İlk ters kapanışta, karşı
   OB/FVG reddinde, karşı Stabil reddinde ya da ters hacim baskısında çıkmak beklentiyi artırmıyor: D7'de dördünün
   de nokta tahmini negatif; karşı blok reddinde çıkış geniş kümede (D1) ayırt edilebilir biçimde zararlı.
4. **İnceleme 12 sorun buldu, hepsi düzeltildi** (§2). En büyük ikisi: düzeltilmemiş bölünme/bedelli kopuklukları
   (697 olay; tek işlemde −72 R'ye varan yapay sonuçlar) ve Mod 2'de R paydası (+71 R'ye varan yapay sonuçlar).
5. **Başlık sayısı düştü, karar aynı kaldı ama kırılgan.** D7 net +0,1234 → **+0,1147 R** (648 → 637 işlem).
   Kabul kapısı yine `GECTI_4H_1D_CEKIRDEK`; fakat D6 alt sınırı zaman kümelerinde sıfırın altına iniyor, keşif
   dönemi kararı teyit etmiyor ve doğrulamadaki fazlalık short tarafından geliyor (§4).
6. **Bir konu açık kaldı.** Market Structure motoru bazı sembollerde bayat durumu "geçerli" diye bildiriyor (§8).
   Motor canlı ürün kodu olduğu için dokunulmadı; gölge tarafında yalnız etiketlendi. D7'de etkilenen olay yok.
7. **Kayıpların anatomisi çıkarıldı** (§6). D7'de 637 işlemin 323'ü kâr, 314'ü zarar etti; zarar edenlerin %89'u stop oldu.
   Stopların %73'ünde uyarı sayılacak bir kapanış yoktu, %53'ü endeks ters giderken geldi. Toplam net +73,1 R'nin
   +67,4 R'si en iyi 5 haftadan geliyor.
8. **Endeks rejimi filtresi doğrudan stopları elemiyor** (§6.7). Girişte bilinen 7 endeks rejimi tanımı × 4 filtre = 28
   varyantın hiçbiri üç kümenin hiçbirinde kabul çıtasını geçmedi. D7'de stoptan önce 0,5 ATR'yi bile görmeyen 151 işlemin
   oranı endeks işleme karşıyken %23,0, aynı yöndeyken %24,1. "Endeks düşüşteyken long açma" bu 151 stopun 10–20'sini
   eliyor, karşılığında 24–46 kârlı işlemi de götürüyor; toplam etkisi +0,6 ile −13,3 R arasında.
9. **Kâr görüp dönen işlemleri önceden ayıran bir domain gözlemi yok** (§6.8). D7'de 129 işlem en az 0,5 ATR, bunların
   58'i en az 1 ATR gördükten sonra stop oldu. Tepe mumu %39,5'inde bilinen bir karşı engele takılmıştı; ama 0,5 ATR
   mumunda engele takılmak hedefe gidenlerde de aynı sıklıkta görülüyor ve sonradan stop oranını değiştirmiyor (takılanda
   %30,9, takılmayanda %31,7). Dönüşe en çok eşlik eden şey işlem sürerken endeksin tersine dönmesi (%61,2). 0,5 / 1 ATR
   görüldüğü kapanışta bilinen 24 gözlemin hiçbirine göre çıkmak kabul çıtasını geçmedi.
10. **Sistem aleyhte gözleme tepki vermiyor; verseydi de tek bir gözlem dışında kazanmazdı** (§6.9). Baz sistem işlem açıkken
    gördüğünü kaydeder; stop, hedef ve süre dışında bir şey yapmaz. Kâr gördükten sonra engele takılma, tez seviyesinin içine
    kapanış, formasyon bozulması, ters süpürme, ters hacim ve endeks tetiklerine iki tepki (sonraki açılışta çık, stopu
    girişe çek) eşleşmiş replay ile ölçüldü: 48 varyanttan D7 ve D6'da geçen yok. D7'de engele takılınca çıkmak stop olacak
    65 işlemde +76,6 R kazandırıyor, hedefe gidecek 86 işlemde −87,5 R kaybettiriyor. Tutarlı tek artı tez seviyesinin içine
    kapanışta (+4,4 R); o da madde 2'deki adayın kendisidir.

## 2. Bulunan sorunlar ve düzeltmeler

Sayılar düzeltme öncesi (commit `9ba3d19`) ve sonrası tam koşuların olay bazında karşılaştırmasıdır.

| # | Sorun | Ölçülen etki | Düzeltme |
|---:|---|---|---|
| 1 | **İşlem-içi körlük.** Yarış dolumdan sonra yalnız OHLC'yi iki donmuş fiyata (stop, hedef) karşılaştırıyordu. `BarDurum` her bar için domain durumunu taşıdığı hâlde işlem sırasında okunmuyor, kaydedilmiyordu. | Tek işlem-içi sinyal (1–3 bar ters dış BOS) D7'nin 648 işleminde 0 kez tetiklenmişti. | `senaryo_v2/surec.py` (gözcü, tez durumu, politika kancası) + `yaris.py::surecli_yaris` (§5). |
| 2 | **Düzeltilmemiş kurumsal işlem kopuklukları.** Arşiv fiyatları düzeltilmemiş; bölünme/bedelli sonrası açılış boşluğu gerçek hareket gibi işleniyordu. | 697 olay, 27 sembol. En uç örnek `FENER:1h:1484` tek işlemde −72,07 R. Karantinadaki olayların toplam brüt sonucu −70,23 R. | Veri karantinası: açılışı önceki kapanıştan %11,5'ten fazla kopan barı işlem penceresinde (13 bar) ya da son 60 barlık bağlamında taşıyan olay, sonuca bakılmadan ölçüm dışı. CSV'ler bütün satırları etiketiyle taşır. |
| 3 | **Tez iptali aynı bardaki hedefi eziyordu.** Kapanışta verilen `TEZ_IPTAL_BOS`, aynı barda daha önce dolmuş bar içi hedefin önüne geçiyordu. | Mod 0'da 15 ayrı işlem (1,5 ATR hedefte 5, 2,0 ATR hedefte 2, yapısal hedefte 12); hepsi ikincil sınıf (C katmanı), 1h/2h/4h. D1/D6/D7'de 0. | Bar içi sıra tek yerde tanımlı: boşluk stopu → stop → hedef → kapanış kararları. |
| 4 | **Mod 2 R paydası.** Boşlukla limitten iyi fiyata dolan emirde payda gerçek `\|giriş − stop\|` idi. | Dolan işlemlerde en büyük R 70,99 → 5,71. Birincil + kapılar açık 148 dolan işlemin ortalaması −0,1825 → −0,2516 R (R'si değişen 10 işlem). | Payda planlanan risk (`limit − stop`); masraf R'si de aynı paydaya bölünür. |
| 5 | **Mod 2 dolum barı stopunun ofseti** olay barından sayılıyordu; 3-stop freni yanlış barı kullanıyordu. | 664 işlemde çıkış ofseti, 16 olayda fren etiketi değişti (frende 46 → 56). | Ofset dolumdan itibaren sayılır. |
| 6 | **Mod 2 tez iptali penceresi** olay barından sayılıyordu; geç dolan emirde tez iptali hiç çalışmıyor, dolum barının kapanışı değerlendirilmiyordu. | 24 işlemin çıkışı `TEZ_IPTAL_BOS` oldu; kapanış-modu kolonları 393 satırda değişti. | Pencere dolumdan sayılır; dolum barının kapanışı işleme dahildir. |
| 7 | **Mod 2 bekleyen limit** ters dış kırılımla iptal edilmiyordu. | 8 emir (6'sı zaten dolmamıştı; 2'si dolup hedefe gitmişti). | `LIMIT_IPTAL_BOS`. |
| 8 | **Önbellek anahtarı yalnız sembol adıydı.** Kod ya da `--tfs` değişince eski sonuç sessizce geri geliyordu; satır sırası tamamlanma sırasına bağlıydı. | — | Anahtar = sembol + TF listesi + kod özeti + veri özeti; atomik yazım; satırlar evren sırasında. Bağımsız önbellekli iki tam koşu aynı CSV içeriğini üretti. |
| 9 | **Domain motoru hata veren seri ölçüme sızabiliyordu** (kapılar varsayılan değerle doluyordu). | Bu arşivde 0 seri. | Fail-closed: seri ölçüme alınmaz, raporda sayılır. |
| 10 | **Güven aralığı yalnız sembol kümeliydi**; aynı gün birlikte hareket eden hisseleri bağımsız sayıyordu. | D6 doğrulama alt sınırı sembol kümesinde +0,013, hafta kümesinde −0,051 (§4). | Rapor §8: sembol / gün / hafta / ay kümeleri; `karar_zaman_kumesi` ve `karar_kesif_teyidi` alanları. Kapı kuralının kendisi değiştirilmedi. |
| 11 | **Üç D7 alt ölçüm betiği** çalışma dizinine bağlı yol kullanıyordu; ara önbellekleri git'e girebiliyordu. | — | Yollar depo köküne göre; `sonuclar/golge_v2/*/parca/` git dışı. |
| 12 | **`import senaryo_v2`** formasyon paketini yüklüyordu. | — | Süreç adları tembel dışa açılır. |

Kontrol edilip **etkisiz** bulunanlar:

- **MTF ölçümünde "4s durum" tazeliği.** `mtf_yonetim.mtf_signal`, kalıcı bir durum olan 4s yapısal yönüne de
  aynı-gün tazeliği uyguluyor; yani her sabah ilk 4s mumu kapanana kadar o durumu görmüyor. `four_state_kalici`
  seçeneği eklendi ve sekiz temel 4s-durum kolu bununla bir kez yeniden koşuldu: 601 işlemin hepsinde sonuç kalıcı
  olmayan eşiyle birebir aynı. Yani o kolların sessizliği tazelik kuralından kaynaklanmıyor (olası neden: 4s dış
  yönü ufuk içinde nadiren ters dönüyor; ayrıca ölçülmedi). `mtf_olcum` raporunun sonucu değişmiyor; sonuç özdeş
  olduğu için kalıcı kollar betiğin varyant listesine eklenmedi.
- **Market Structure bayatlığı** (§8).

## 3. Başlık sayıları: önce / sonra

`4h + 1d`, 2,0 ATR hedef, 30 bps masraf düşülmüş R, sembol kümeli %95 GA. Kaynak: `ozet_rapor.json`.

| Katman | Dönem | Önce N | Önce Net15 R | Önce GA | Sonra N | Sonra Net15 R | Sonra GA |
|---|---|---:|---:|---|---:|---:|---|
| D0_Tum_Olaylar | tumu | 13708 | -0,0596 | [-0,0849; -0,0324] | 13477 | -0,0605 | [-0,0865; -0,0331] |
| D1_Birincil_KirilimAdayi | tumu | 4289 | +0,0090 | [-0,0357; +0,0541] | 4233 | +0,0100 | [-0,0333; +0,0535] |
| D6_A_Cekirdek_Veya_Arti | tumu | 1140 | +0,0693 | [-0,0097; +0,1403] | 1124 | +0,0611 | [-0,0202; +0,1297] |
| D6_A_Cekirdek_Veya_Arti | kesif | 750 | +0,0295 | [-0,0513; +0,1105] | 738 | +0,0210 | [-0,0726; +0,1078] |
| D6_A_Cekirdek_Veya_Arti | dogrulama | 390 | +0,1460 | [+0,0173; +0,2759] | 386 | +0,1378 | [+0,0126; +0,2745] |
| D7_A_Arti_UyumluBOS | tumu | 648 | +0,1234 | [+0,0214; +0,2196] | 637 | +0,1147 | [+0,0102; +0,2161] |
| D7_A_Arti_UyumluBOS | kesif | 422 | +0,0632 | [-0,0495; +0,1741] | 414 | +0,0543 | [-0,0605; +0,1685] |
| D7_A_Arti_UyumluBOS | dogrulama | 226 | +0,2358 | [+0,0623; +0,4043] | 223 | +0,2269 | [+0,0547; +0,3943] |

`4h + 1d` merdivenindeki değişimin tamamı karantinadan gelir; motor düzeltmeleri (§2 #3) bu katmanlarda hiçbir
işlemi değiştirmedi. Karantina D7'den 11 işlem çıkardı ve bunlar net kazananlardı (toplam +6,89 R); yani
karantina başlık sayısını yükseltmedi, düşürdü.

## 4. Kabul kararı ne kadar sağlam?

Kapı kuralı değiştirilmedi: D6 ve D7'nin doğrulama dönemi, sembol kümeli alt sınırı sıfırın üstündeyse geçer.
Karar yine `GECTI_4H_1D_CEKIRDEK`. Aşağıdaki dört sınama aynı kararın ne kadar dar bir zeminde durduğunu gösterir.

**a) Küme tanımı.** Aynı ortalama, dört küme tanımıyla. Kaynak: `ozet_rapor.json → karar_saglamlik`, rapor §8.

| Katman | Dönem | N | Net15 R | Sembol | Gün | Hafta | Ay | Hepsinde > 0 |
|---|---|---:|---:|---|---|---|---|---|
| D6_A_Cekirdek_Veya_Arti | kesif | 738 | +0,0210 | [-0,0688; +0,1054] (k=171) | [-0,0896; +0,1415] (k=239) | [-0,0923; +0,1363] (k=64) | [-0,1109; +0,1409] (k=16) | hayır |
| D6_A_Cekirdek_Veya_Arti | dogrulama | 386 | +0,1378 | [+0,0126; +0,2709] (k=155) | [-0,0211; +0,2836] (k=114) | [-0,0507; +0,3131] (k=29) | [-0,0257; +0,2446] (k=7) | hayır |
| D7_A_Arti_UyumluBOS | kesif | 414 | +0,0543 | [-0,0616; +0,1690] (k=149) | [-0,0937; +0,2045] (k=191) | [-0,0884; +0,2065] (k=62) | [-0,1040; +0,1892] (k=16) | hayır |
| D7_A_Arti_UyumluBOS | dogrulama | 223 | +0,2269 | [+0,0560; +0,3943] (k=124) | [+0,0427; +0,4111] (k=96) | [+0,0652; +0,3724] (k=29) | [+0,1378; +0,3192] (k=7) | evet |

D7 doğrulama dört kümede de pozitif. D6 doğrulama yalnız sembol kümesinde pozitif. İki katman da keşif döneminde
sıfırdan ayırt edilemiyor. Ay kümesinde küme sayısı azdır (7–16); o sütun gösterge niteliğindedir.

Sembol sütunu §3'teki aralıktan üçüncü ondalıkta ayrılabilir (D7 doğrulama alt sınırı: +0,0547 ve +0,0560).
İkisi de sembol kümeli bootstrap'tir; merdiven tablosu 800, bu tablo 1.000 yeniden örneklemeyle hesaplanır.
Kapı kararı merdiven tablosundaki aralığı kullanır.

**b) Yön × dönem.** Kaynak: `ozet_rapor.json → kesit_kalite_yon`, rapor §4.

| Katman | Yön | Keşif N | Keşif Net15 R | Keşif GA | Doğrulama N | Doğrulama Net15 R | Doğrulama GA |
|---|---|---:|---:|---|---:|---:|---|
| A_ARTI | long | 248 | +0,1418 | [-0,0150; +0,3086] | 99 | +0,1436 | [-0,1206; +0,3877] |
| A_ARTI | short | 166 | -0,0764 | [-0,2653; +0,1210] | 124 | +0,2935 | [+0,0503; +0,5388] |
| A_CEKIRDEK | long | 203 | +0,0534 | [-0,0949; +0,2272] | 91 | -0,1030 | [-0,3214; +0,1022] |
| A_CEKIRDEK | short | 121 | -0,1474 | [-0,3342; +0,0555] | 72 | +0,1662 | [-0,1177; +0,4511] |

Doğrulama dönemindeki fazlalık short tarafından geliyor; aynı short tarafı keşifte negatifti. Bu, kapının
ölçtüğü şeyin bir kısmının dönemin yönü olduğunu düşündürür. A_ARTI long iki dönemde de yaklaşık +0,14 R; ama
aralığı iki dönemde de sıfırı içeriyor. Short sonuçları açığa satışın mümkün olduğunu varsayar; erişim ve
ödünç maliyeti modellenmedi.

**c) Karantina penceresi.** Geri-bakış uzunluğu bir yargıdır. Kaynak: `karantina_duyarlilik/RAPOR.md`.

| Seçenek | D7 N | D7 Net15 R | D7 doğrulama GA alt | D6 N | D6 Net15 R | D6 doğrulama GA alt |
|---|---:|---:|---:|---:|---:|---:|
| `karantinasiz` | 648 | +0,1234 | +0,0673 | 1140 | +0,0693 | +0,0205 |
| `geri_0` | 645 | +0,1195 | +0,0635 | 1133 | +0,0653 | +0,0171 |
| `geri_60` (varsayılan) | 637 | +0,1147 | +0,0560 | 1124 | +0,0611 | +0,0126 |
| `geri_120` | 633 | +0,1143 | +0,0451 | 1111 | +0,0602 | +0,0072 |
| `geri_sinirsiz` | 601 | +0,1127 | +0,0259 | 1043 | +0,0678 | +0,0015 |
| `sembol_disi` | 578 | +0,1145 | +0,0460 | 993 | +0,0684 | +0,0089 |

`geri_sinirsiz`: bir seride ilk kopukluktan sonraki bütün olaylar çıkar. `sembol_disi`: herhangi bir serisinde
kopukluk olan 29 sembol tümüyle çıkar. D7 ortalaması her seçenekte 0,113–0,123 arasında. D6'nın doğrulama alt
sınırı her seçenekte pozitif kalıyor ama +0,0015'e kadar iniyor.

**d) Market Structure bayatlığı.** §8. D7'de 0, D6'da 13 olay etkileniyor; D6 doğrulama alt sınırı
+0,0126 → +0,0116.

**Okuma.** D7'nin doğrulama sonucu sınadığım her tanımda ayakta. D6 kapıyı kıl payı geçiyor ve zaman
kümelerinde geçmiyor. Keşif dönemi iki katmanı da teyit etmiyor; iki dönem arasındaki fark büyük ölçüde yönsel.
Bu yüzden karar "geçti" olarak kalsa da canlıya taşımak için değil, ileriye dönük gölge defteri sürdürmek için
bir gerekçe olarak okunmalı.

## 5. İşlem-içi süreç

### 5.1 Ne eklendi

- **Gözcü** (`SurecGozcusu`): işlem bir barın kapanışına sağ ulaştıysa o kapanışta nedensel bir gözlem üretir —
  açık R, çıkışa kadar MFE/MAE, domain etiketleri, tez durumu. Yalnız o barın ve bir önceki kapanışın durumunu
  okur. Gözcü sonucu değiştirmez (gözcülü ve gözcüsüz yarışın eşitliği testle sabit).
- **Tez durumu:** `BEKLIYOR → TEYITLI → SINANIYOR → BOZULDU`. Tez seviyesinin ters tarafında iki ardışık kapanış,
  formasyonun başarısız kırılıma düşmesi ya da ters dış yapı kırılımı tezi bozar; bozulma kalıcıdır.
- **Etiketler:** formasyon yaşam döngüsü (`FRM_*`), tez seviyesi (`SEVIYE_ICI`, `SEVIYE_GERI_ALINDI`), karşı Stabil
  çizgisi (`SR_KARSI_*`), OB/FVG (`BLOK_*`), hacim (`VP_*`), fiyat yolu (`FIYAT_*`), iç ve dış yapı olayları
  (`MS_*`), sistemin işlem sırasında ürettiği yeni adaylar (`ADAY_*`).
- **Politika kancası** (`SurecPolitikasi`): gözleme göre çıkış, stop taşıma ya da hedefi sürme. Varsayılan politika
  yoktur; her biri opt-in'dir ve eşleşmiş replay ile ölçülür.
- **Kayıt:** ana CSV'lerde `surec_*` kolonları (gözlem sayısı, çıkışa kadar MFE/MAE, tez yolu, etiket izi).
- **Nedensellik:** 2026-04-01'de kesilen seri ile tam seri, penceresi kesimden önce biten her işlemde aynı yarış
  sonucunu ve aynı süreç kaydını üretir (`test_golge_v2_kesme.py`, 4 seri × 3 mod).

### 5.2 İşlem açıkken ne görülüyor

D7, 637 işlem. Kaynak: `RAPOR_GOLGE_V2.md` §9. Bu bölüm betimleyicidir; kural değeri ölçmez.

- İşlem başına ortalama 4,04 kapanış gözleniyor.
- **87 işlem (%13,7) ilk barda, bar içinde kapanıyor.** Bunlarda işlemin kendi zaman diliminde görülecek tek bir
  kapanış bile yok; bar kapanışına dayanan hiçbir süreç kuralı onlara dokunamaz.
- Stop olan 280 işlemin %39,3'ü stoptan önce +0,5 R, %16,1'i +1 R görmüştü.
- Çıkıştan önceki son tez durumu: `TEYITLI` 406 işlem, net +0,41 R, stop oranı %31. `SINANIYOR` 62 işlem, −1,06 R,
  %94. `BOZULDU` 26 işlem, −0,96 R, %85. Bu ilişki sonuç-koşulludur: stopa giden işlem zaten tez seviyesinin
  içinden geçer. Kural değerini §5.3–5.4 ölçer.

### 5.3 Etiket görüldükten sonra işlemde kalmak ne getiriyor?

D7. `İleri R` = nihai brüt R − etiketin ilk görüldüğü kapanıştaki açık R. `Aynı yaşta koşulsuz` = aynı kapanış
sayısında açık olan bütün işlemlerin ileri getirisi. Aralıklar sembol/gün/hafta/ay kümelerinin en kötüsü.
Kaynak: `surec_olcum/RAPOR.md`.

| Etiket | N | O anda açık R | Kalmanın ileri R'si | En kötü GA | Keşif (n) | Doğrulama (n) | Aynı yaşta koşulsuz | Fark | Fark en kötü GA | Bilgi |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|
| `SEVIYE_ICI` | 102 | -0,668 | -0,126 | [-0,293; +0,044] | -0,162 (73) | -0,034 (29) | +0,086 | -0,212 | [-0,377; -0,041] | KOTU |
| `TEZ=SINANIYOR` | 112 | -0,625 | -0,142 | [-0,314; +0,038] | -0,209 (80) | +0,024 (32) | +0,084 | -0,226 | [-0,394; -0,046] | KOTU |
| `FRM_RETEST` | 57 | -0,592 | -0,172 | [-0,412; +0,150] | -0,244 (43) | +0,052 (14) | +0,060 | -0,231 | [-0,473; +0,088] | — |
| `FIYAT_ZARARDA` | 341 | -0,263 | +0,074 | [-0,072; +0,220] | +0,051 (225) | +0,119 (116) | +0,121 | -0,046 | [-0,191; +0,100] | — |
| `FIYAT_TERS_KAPANIS` | 432 | -0,023 | +0,066 | [-0,082; +0,197] | +0,043 (285) | +0,110 (147) | +0,103 | -0,037 | [-0,178; +0,090] | — |
| `SR_KARSI_RED` | 104 | -0,200 | +0,047 | [-0,218; +0,280] | +0,053 (67) | +0,036 (37) | +0,086 | -0,039 | [-0,308; +0,193] | — |
| `VP_TERS_BASKI` | 123 | -0,152 | +0,076 | [-0,078; +0,217] | +0,048 (77) | +0,122 (46) | +0,080 | -0,004 | [-0,160; +0,141] | — |
| `BLOK_DUVAR` | 182 | +0,263 | +0,109 | [-0,066; +0,283] | +0,065 (123) | +0,199 (59) | +0,120 | -0,012 | [-0,186; +0,162] | — |
| `FRM_TEYITSIZ` | 51 | -0,069 | +0,324 | [+0,029; +0,593] | +0,439 (33) | +0,113 (18) | +0,031 | +0,293 | [-0,002; +0,562] | — |

- **Tez seviyesinin kaybı gerçek bilgi taşıyor.** Kapanış tez seviyesinin ters tarafına geçtikten sonra kalan yol,
  aynı yaştaki sıradan bir işlemin kalan yolundan ayırt edilebilir biçimde kötü (fark −0,21 R, aralık sıfırı
  dışlıyor). Aynı gözlemin iki adı olan `SEVIYE_ICI` ve `TEZ=SINANIYOR` tek bulgudur, iki değil.
- **Ama kalmanın kendisi ayırt edilebilir biçimde zarar değil** (−0,13 R, aralık sıfırı içeriyor) ve etki
  keşif döneminde yoğun (−0,16; doğrulamada −0,03, n=29).
- Zararda kapanış, ters kapanış, karşı Stabil reddi, ters hacim baskısı ve karşı blok reddinden sonra kalmanın
  beklentisi **pozitif**. Bu etiketler "aleyhte" görünür ama çıkış gerekçesi değildir.
- `FRM_TEYITSIZ` (kırılım teyit alamadı) sezgiye ters biçimde iyi görünüyor; n=51 ve doğrulama hücresi 18 olduğu
  için bulgu sayılmaz, not edildi.

### 5.4 Eşleşmiş replay: kural olarak uygulansaydı

Aynı işlemler, aynı giriş ve ilk stop; yalnız yönetim kuralı farklı. `Fark` kümedeki bütün işlemler üzerinden
işlem başına net R farkıdır. Çıkış kurallarında esas uygulama sinyalden sonraki barın açılışıdır.
Kaynak: `surec_olcum/RAPOR.md`, `surec_olcum/ozet.json`.

**D7 (637 işlem; baz +0,1147 R)**

| Varyant | Etkilenen | İyileşen / kötüleşen | Fark R/işlem | En kötü GA | Keşif (etkilenen) | Doğrulama (etkilenen) | Karar |
|---|---:|---:|---:|---|---:|---:|---|
| Tez seviyesi içine kapanış → sonraki açılışta çık | 101 | 83 / 11 | +0,0181 | [-0,0117; +0,0409] | +0,0222 (72) | +0,0104 (29) | ZAYIF_ARTI |
| Formasyon retest ediliyor → sonraki açılışta çık | 57 | 47 / 7 | +0,0130 | [-0,0124; +0,0372] | +0,0187 (43) | +0,0023 (14) | ZAYIF_ARTI |
| Tez bozuldu → sonraki açılışta çık | 26 | 20 / 4 | +0,0055 | [-0,0048; +0,0146] | +0,0071 (18) | +0,0025 (8) | SAYILMAZ (n<30) |
| İlk ters kapanış → sonraki açılışta çık | 432 | 229 / 191 | -0,0389 | [-0,1180; +0,0421] | -0,0247 (285) | -0,0653 (147) | GECMEDI |
| Karşı OB/FVG bandında ret → çık | 180 | 76 / 104 | -0,0295 | [-0,0757; +0,0154] | -0,0217 (121) | -0,0438 (59) | GECMEDI |
| Karşı Stabil çizgisinde ret → çık | 101 | 59 / 38 | -0,0074 | [-0,0473; +0,0259] | -0,0086 (66) | -0,0051 (35) | GECMEDI |
| Ters hacim baskısı → çık | 114 | 58 / 51 | -0,0128 | [-0,0413; +0,0131] | -0,0099 (72) | -0,0182 (42) | GECMEDI |
| Sistemin kendi karşı yön adayı → çık | 44 | 28 / 16 | -0,0007 | [-0,0294; +0,0235] | +0,0044 (28) | -0,0103 (16) | GECMEDI |
| +1 R görülünce stop başa baş | 82 | 48 / 34 | -0,0115 | [-0,0551; +0,0343] | -0,0049 (58) | -0,0237 (24) | GECMEDI |
| +1 R görülünce stop +0,25 R | 96 | 52 / 44 | -0,0140 | [-0,0704; +0,0443] | -0,0007 (65) | -0,0386 (31) | GECMEDI |
| +1,5 R görülünce stop +0,5 R | 38 | 20 / 18 | +0,0001 | [-0,0330; +0,0320] | -0,0007 (26) | +0,0014 (12) | GECMEDI |
| Hedefte çıkma; +1,0 ATR kilit, ufka taşı | 262 | 84 / 178 | +0,0029 | [-0,1094; +0,1424] | -0,0639 (162) | +0,1269 (100) | GECMEDI |
| Hedefte çıkma; +1,0 ATR kilit + 1,5 ATR iz | 262 | 92 / 170 | +0,0219 | [-0,0722; +0,1304] | -0,0245 (162) | +0,1082 (100) | GECMEDI |
| Hedefte çıkma; +1,5 ATR kilit + 1,0 ATR iz | 262 | 84 / 178 | +0,0238 | [-0,0413; +0,0955] | +0,0039 (162) | +0,0607 (100) | ZAYIF_ARTI |

Ters yapı kırılımında çıkış D7'de hiçbir işlemi etkilemedi (0 işlem); ölçülemez.

**Üç kümede aynı kurallar**

| Varyant | D7 fark | D6 fark (1124) | D6 en kötü GA | D1 fark (4233) | D1 en kötü GA |
|---|---:|---:|---|---:|---|
| Tez seviyesi içine kapanış → sonraki açılışta çık | +0,0181 | +0,0144 | [-0,0064; +0,0326] | +0,0033 | [-0,0109; +0,0165] |
| Tez bozuldu → sonraki açılışta çık | +0,0055 | +0,0009 | [-0,0095; +0,0104] | +0,0049 | [-0,0003; +0,0096] |
| İlk ters kapanış → çık | -0,0389 | -0,0239 | [-0,1013; +0,0569] | -0,0286 | [-0,0688; +0,0148] |
| Karşı OB/FVG bandında ret → çık | -0,0295 | -0,0364 | [-0,0774; +0,0080] | -0,0305 | [-0,0603; -0,0004] |
| +1 R görülünce stop başa baş | -0,0115 | -0,0039 | [-0,0343; +0,0293] | -0,0051 | [-0,0226; +0,0125] |
| Hedefte çıkma; +1,0 ATR kilit + 1,5 ATR iz | +0,0219 | +0,0625 | [-0,0093; +0,1450] | +0,0201 | [-0,0250; +0,0714] |
| Hedefte çıkma; +1,5 ATR kilit + 1,0 ATR iz | +0,0238 | +0,0482 | [-0,0071; +0,1073] | +0,0148 | [-0,0195; +0,0489] |

Üç küme iç içedir (D7 ⊂ D6 ⊂ D1); aynı yönde çıkmaları üç bağımsız doğrulama değildir.

### 5.5 Okuma

- **Hiçbir kural `GECTI` ya da `UMUT_VAR` olmadı.** Kabul kuralı: fark iki dönemde de pozitif, iki dönemde de en
  az 30 işlem etkileniyor ve en kötü alt sınır sıfırın üstünde.
- **Tez seviyesinin kaybında çıkmak** tutarlı ama küçük: D7'de etkilediği 101 işlemin 83'ünü iyileştiriyor,
  toplam +11,5 R. İşlem başına +0,018 R, bazın (+0,115 R) yaklaşık altıda biri. Aralık sıfırı içeriyor.
- **Karşı blok reddinde çıkmak zararlı:** D1'de −0,031 R/işlem ve en kötü üst sınır bile sıfırın altında. Önceki
  `iptal_olcum` çalışmasının "duvar iptali beklentiyi artırmadı" sonucunu temiz kümede ve uygulanabilir çıkış
  fiyatıyla doğruluyor.
- **Kâr koruma (stop taşıma)** üç eşikte de sıfır ya da negatif; `mtf_olcum` çalışmasındaki sonuçla aynı yönde.
- **Hedefte çıkmayıp iz sürmek** D6'da +0,05–0,06 R/işlem ve sembol kümeli aralığı pozitif ([+0,010; +0,116]);
  zaman kümelerinde aralık sıfırı içeriyor, D7'de keşif döneminde iki izli varyanttan biri negatif. Etkilenen
  işlemlerin çoğu kötüleşiyor (D6, 1,5 ATR izli varyant: 269 kötüleşen, 178 iyileşen), kazanç az sayıda büyük
  işlemden geliyor. İzlemeye değer, kural değil.
- **İç yapıyı izleyen stop** bu ufukta hiç devreye girmedi: 1.435 hedef görmüş işlemin hepsinde yalnız kilitli
  varyantla birebir aynı sonuç. Korunan iç seviye, en yaklaştığı anda bile kilidin medyan 3,4 ATR altında
  (40 sembollük bir kerelik keşif örneği; betiği depoda değil).
- **İlk barda ölen %13,7** bar kapanışına dayalı hiçbir kuralla görülemez. Bunun için alt zaman dilimi akışı
  gerekir; `mtf_olcum` o yolu denedi ve test ettiği kurallar da beklentiyi artırmadı.

### 5.6 Sınırlar

- 20 varyant × 3 küme ve küme başına onlarca etiket sınandı; çoklu karşılaştırma düzeltmesi yok.
- Varyant listesi ve kabul kuralı tam koşudan önce sabitlendi. Tam koşudan sonra iki değişiklik yapıldı;
  ikisi de hiçbir kararı değiştirmedi: (1) dönem hücresine de `n ≥ 30` şartı — yalnız sıkılaştırır;
  (2) yapı izi politikasında fiyatın ters tarafındaki bayat seviyenin yok sayılması — hata düzeltmesi, 8 işlemi
  etkiliyordu. `Bilgi` sütunu da tam koşudan sonra eklendi; önceden hesaplanan `Fark` aralığını bayrağa çevirir.
- Bar içi sıra bilinmez: stop ile hedef aynı barda ise stop sayılır.
- Keşif ve doğrulama aynı arşivin iki dilimidir ve baz beklenti aralarında belirgin oynar (§4b).

## 6. Sonuç anatomisi: kim kazandı, kim kaybetti, nasıl kaybetti

Ana rapor "ortalama kaç R" sorusunu yanıtlar; bu bölüm aynı işlemleri tek tek açar. Yarış yeniden koşulmadı: sonuçlar ana
CSV'den okundu, yol fiyat arşivinden çözüldü ve arşivden yürütülen yol 4.233 işlemin hepsinde CSV'deki çıkış nedeni,
çıkış mumu ve MFE ile aynı çıktı; stop sonrası alanlar da CSV'nin ufuk kapanışı ve saf yol MFE'siyle sınandı. Sayılar D7
içindir (637 işlem); D6 ve D1'de oranlar birbirine çok yakındır (§6.6).
Kaynak: `sonuclar/golge_v2/sonuc_anatomisi/RAPOR.md` (15 başlık × 3 küme), `ozet.json`, `islemler.csv.gz`.
Aynı işlemler üzerinde üç izleme sorusu ayrı betiklerle ölçüldü: girişte bilinen endeks rejimi (§6.7), kâr görüp dönen
işlemlerin domain dökümü (§6.8) ve o gözlemlere tepki verilseydi ne olacağı (§6.9); kaynakları o alt bölümlerde yazılıdır.

"Mum" işlemin kendi zaman dilimindeki mumdur (4s işlemde 4 saatlik, günlükte günlük). Mum çözünürlüğünde stop mumunun içindeki
sıra bilinmez; "stoptan önce görülen kâr" stop mumunu saymaz ve alt sınırdır. Saatlik arşiv stop mumunun içini açar: 4s
işlemlerde birebir (4s mumlar 1s'ten türer); günlük işlemlerde yaklaşık, saatlik arşivin olmadığı tarihlerde yok. D7'nin 280 stopundan
254 tanesi saat çözünürlüğünde çözüldü.

### 6.1 Genel tablo

| | İşlem | Pay | Ortalama net R | Toplam net R |
|---|---:|---:|---:|---:|
| Kâr eden | 323 | %50,7 | +1,27 | +409,0 |
| Zarar eden | 314 | %49,3 | −1,07 | −335,9 |
| Tümü | 637 | | +0,115 | +73,1 |

| Nasıl kapandı | İşlem | Pay | Ortalama net R |
|---|---:|---:|---:|
| Hedefe ulaştı | 262 | %41,1 | +1,43 |
| Stop oldu | 255 | %40,0 | −1,13 |
| Açılış boşluğuyla stop oldu | 25 | %3,9 | −1,44 |
| Süre doldu: ne stop ne hedef (61 kârda, 34 zararda) | 95 | %14,9 | +0,24 |

- Ortalama kazanç ortalama kaybın 1,18 katı. Bu oranla sıfır beklenti için kâr eden işlem oranının %45,8 olması gerekir;
  gerçekleşen %50,7. Beklentinin tamamı bu yaklaşık 5 puanlık farktan geliyor.
- **Masraf brüt kazancın yarısını götürüyor:** brüt +147,2 R, masraf 74,1 R (%50,4), net +73,1 R.
  İşlem başına masraf 0,116 R. D6'da bu pay %64,5, D1'de %92,9.

### 6.2 Zarar edenler nasıl kaybetti

Her zarar eden işlem tek satırdadır. Boşlukla stop olan işlem, öncesinde ne görmüş olursa olsun kendi satırındadır.

| Kayıp yolu | İşlem | Zarar edenlerin payı | Toplam net R |
|---|---:|---:|---:|
| Stop olmadı; süre doldu, zararda kapandı | 34 | %10,8 | −11,7 |
| Açılış boşluğu stopu atladı | 25 | %8,0 | −35,9 |
| Girişten sonraki ilk mumda stop | 47 | %15,0 | −54,1 |
| 2+ mum yaşadı, +0,25 R'yi hiç görmedi | 58 | %18,5 | −65,0 |
| +0,25–0,5 R gördü, döndü | 51 | %16,2 | −56,4 |
| +0,5–1 R gördü, geri verdi | 60 | %19,1 | −67,9 |
| +1 R ve üstünü gördü, geri verdi | 39 | %12,4 | −44,9 |
| **Toplam** | **314** | **%100** | **−335,9** |

Kabaca üçe bölünüyor: 105 işlem (%33,4) +0,25 R'yi bile görmeden stop oldu; 99 işlem (%31,5) en az +0,5 R
gördükten sonra geri verdi; kalan 110 işlem (%35,0) az kâr görüp döndü, boşlukla stop oldu ya da süresi doldu.

### 6.3 Stop olanların yolu

Stop olan işlem 280; zarar edenlerin %89,2 kadarı.

| Stoptan önce en az | Mum çözünürlüğü (280 stop) | Saat çözünürlüğü (254 stop) |
|---|---:|---:|
| +0,25 R | 162 (%57,9) | 161 (%63,4) |
| +0,5 R | 110 (%39,3) | 111 (%43,7) |
| +1 R | 45 (%16,1) | 46 (%18,1) |
| +1,5 R | 18 (%6,4) | 16 (%6,3) |

- **Ne zaman:** 1. mumda 48 (%17,1), 2–3. mumda 108 (%38,6), 4–6. mumda 82 (%29,3),
  7–10. mumda 42 (%15,0).
- **İlk mumda stop (48 işlem; stopların %17,1 kadarı):** bunların 35 tanesinde stop 1 ATR ya da daha yakındı. Stopu 1 ATR ya da
  daha yakın olan işlemlerde ilk mumda stop oranı %18,2, daha geniş stoplularda %2,9. Saat çözünürlüğünde çözülen 40 işlemden
  31 tanesi (%77,5) stoptan önce +0,25 R'yi bile görmedi; yani bunlar "önce çıktı sonra düştü" değil, doğrudan stop.
- **Boşlukla stop (25 işlem; stopların %8,9 kadarı):** hepsi günün ilk mumunda, yani gece boşluğu. Ortalama brüt −1,33 R,
  en kötü −2,91 R; stop fiyatı yerine açılıştan dolmanın ek kaybı toplam 8,2 R.
- **En az +0,5 R görüp stop olanlar (110 işlem):** en iyi andan stopa medyan 2 mum; 66 tanesinde bir ya da iki mum. 58 stop
  hedef yolunun en az yarısını, 23 stop en az dörtte üçünü görmüştü.
- **Stopların %73,2 kadarında uyarı kapanışı yoktu.** 48 işlem ilk mumda stop oldu; 157 işlemde son kapanış hâlâ tez
  seviyesinin doğru tarafındaydı ve tek mum hem seviyeyi hem 0,5 ATR tamponu geçti. Yalnız 75 (%26,8) stopta
  son kapanış seviyenin ters tarafındaydı. Stop mumu başlarken fiyat stopa medyan 0,81 ATR uzaktaydı;
  stopların %66,8 kadarında 1 ATR ya da daha yakın. Sıradan büyüklükte tek bir ters mum yetiyor.
- **Stoptan sonra:** 41 (%14,6) işlem ufuk içinde özgün hedefe ulaştı; 42 (%15,0) hedefe varmadı ama
  ufuk sonunda girişin kâr tarafındaydı; 64 (%22,9) giriş ile stop arasında, 129 (%46,1) stopun da ötesinde bitti.
- Stop ile hedefin aynı mumda görüldüğü, sıra bilinmediği için stop sayılan işlem yalnız 2. Saatlik veride önce hedefin
  görüldüğü stop yok.

### 6.4 Stop olmadan kapananlar ve zora girip kurtaranlar

- Süresi dolan 95 işlemden 61 tanesi kârda (ortalama +0,56 R), 34 tanesi zararda (ortalama −0,35 R) kapandı.
  Zararda kapananların 17 tanesi yol boyunca en az +0,5 R görmüştü; 3 tanesi brütte artıdaydı, masraf zarara çevirdi.
- Aleyhte 0,5 R gören 392 işlemden 280 tanesi (%71,4) stop oldu, 83 tanesi (%21,2) kârla kapandı. Aleyhte 0,75 R
  gören 323 işlemde kârla kapanan 32 (%9,9).
- Hedefe ulaşan 262 işlemden 39 tanesi ilk mumda ulaştı; 54 tanesi (%20,6) hedeften önce en az 0,5 R aleyhte kalmıştı.

### 6.5 Zarar neyle birlikte geliyor

**Piyasa.** İşlem açıkken `XU100`'ün işlemin yönüne göre hareketi (giriş anında bilinmez):

| İşlem süresince endeks | İşlem | Stop | Hedef | Net R | En kötü GA |
|---|---:|---:|---:|---:|---|
| %2'den fazla ters | 86 | %72,1 | %12,8 | −0,55 | [−0,80; −0,30] |
| %0,5–2 ters | 127 | %66,9 | %24,4 | −0,47 | [−0,68; −0,23] |
| yatay (±%0,5) | 156 | %45,5 | %42,9 | +0,06 | [−0,16; +0,27] |
| %0,5–2 lehte | 143 | %27,3 | %51,7 | +0,46 | [+0,24; +0,69] |
| %2'den fazla lehte | 115 | %15,7 | %65,2 | +0,91 | [+0,67; +1,18] |

Stop olanların %53,5 kadarında endeks en az %0,5 ters gitti; hedefe ulaşanlarda bu oran %16,3, endeksin lehte gittiği pay %57,8.
Endeks yatayken beklenti sıfıra yakın (+0,06 R). Girişten ÖNCEKİ 5 mumda endeksin yönü ise ayırt etmiyor: dört kovada stop oranı
%43,3–%45,8 arasında. Sonuçla en güçlü birlikte hareket eden büyüklük bu; ama giriş anında bilinmiyor.

**Haftalar.** 90 haftadan 51 tanesi artıda, 39 tanesi ekside. En iyi 5 hafta +67,4 R üretti; onlar olmadan toplam net +5,7 R
(hepsiyle +73,1 R). D6'da en iyi 5 hafta çıkarılınca toplam −21,8 R'ye düşüyor. 35 haftada bütün işlemler aynı yöndeydi.

**Stop mesafesi.** Hedef sabit 2,0 ATR olduğu için dar stopta hedef R olarak uzak, geniş stopta yakındır.

| Stop mesafesi | İşlem | Stop | İlk mumda stop | Kâr eden | Ort. hedef R | Net R | En kötü GA |
|---|---:|---:|---:|---:|---:|---:|---|
| ≤ 0,8 ATR | 112 | %63,4 | %21,4 | %35,7 | 2,89 | +0,09 | [−0,26; +0,46] |
| 0,8–1,0 ATR | 80 | %61,3 | %13,8 | %37,5 | 2,24 | +0,01 | [−0,35; +0,38] |
| 1,0–1,3 ATR | 133 | %47,4 | %6,8 | %52,6 | 1,74 | +0,19 | [−0,05; +0,46] |
| 1,3–1,7 ATR | 126 | %41,3 | %2,4 | %54,8 | 1,35 | +0,14 | [−0,15; +0,42] |
| 1,7–2,2 ATR | 90 | %33,3 | %1,1 | %55,6 | 1,04 | +0,03 | [−0,17; +0,22] |
| > 2,2 ATR | 96 | %15,6 | %0,0 | %66,7 | 0,72 | +0,18 | [+0,03; +0,31] |

Stop mesafesi stop SAYISINI belirliyor (dar stopta %62,5, genişte %36,0) ama beklentiyi aynı ölçüde belirlemiyor: dar stoplu
işlemler +0,06 R, geniş stoplular +0,14 R ve aralıklar örtüşüyor. En geniş kova (> 2,2 ATR) üç kümede de aralığı sıfırın
üstünde kalan tek kovadır (D7 +0,18, D6 +0,17, D1 +0,13 R); çok sayıda kesitten biri olduğu için bulgu değil, adaydır.

**Dönem ve yön.** Keşif dönemindeki short işlemler ayrışıyor: stop %54,8, hedef %26,5, net −0,08 R. Diğer üç
hücrede stop oranı %39,9–%40,4.

**Ayırt etmeyenler.** Giriş saati, formasyon tipi ve aynı gün aynı yönde açılan işlem sayısı kümeler arasında tutarlı bir fark
vermiyor; tabloları kaynak raporda.

### 6.6 Üç kümede aynı oranlar

| Oran | D7 | D6 | D1 |
|---|---:|---:|---:|
| İşlem | 637 | 1.124 | 4.233 |
| Kâr eden | %50,7 | %48,5 | %42,9 |
| Stop olan | %44,0 | %44,8 | %51,0 |
| Stopların: ilk mumda | %17,1 | %13,9 | %20,5 |
| Stopların: açılış boşluğuyla | %8,9 | %7,1 | %7,4 |
| Stopların: önce en az +0,5 R gördü | %39,3 | %38,7 | %37,8 |
| Stopların: uyarı kapanışı yoktu | %73,2 | %73,0 | %71,9 |
| Stopların: sonra hedefe gitti | %14,6 | %12,1 | %13,4 |
| Stopların: endeks en az %0,5 ters | %53,5 | %56,4 | %54,6 |
| Masrafın brüt içindeki payı | %50,4 | %64,5 | %92,9 |

Stopların iç dağılımı üç kümede neredeyse aynı. Kümeler stop oranında, kâr eden işlem oranında ve masrafın payında ayrışıyor.

### 6.7 Endeks rejimi filtresi: "endeks düşüşteyken long açma" doğrudan stopları eler mi?

§6.5 işlem SÜRERKEN endeksin yönünün sonuçla en güçlü birlikte hareket eden büyüklük olduğunu, girişten önceki 5 mumun ise
ayırmadığını gösterdi. Burada daha uzun vadeli bir soru soruldu: girişte bilinen endeks rejimi, **doğrudan stop** olan
(stoptan önce 0,5 ATR'yi bile görmeyen) işlemleri ayırıyor mu? D7'de böyle 151 işlem var (işlemlerin %23,7 kadarı).

Ölçümden önce 7 rejim tanımı ve 4 filtre sabitlendi; 28 varyant üç kümede sınandı. Rejim yalnız giriş mumunun kapanışından
ÖNCE kapanmış günlük `XU100` kapanışlarından hesaplanır. Kabul merdiveni §5.4'tekiyle aynıdır (iki dönemde de pozitif, dönem
başına en az 30 işlem ve en kötü zaman kümeli aralığın alt sınırı sıfırın üstünde). "Etki", elenen işlemlerin net R'sinin
ters işaretlisidir.
Kaynak: `sonuclar/golge_v2/endeks_filtresi/RAPOR.md`, `ozet.json`, `islemler.csv.gz`.

- Rejim tanımları: endeksin son 10 / 20 / 60 günlük getirisi ekside; endeks 20 / 50 günlük ortalamasının altında; ortalamanın
  altında ve ortalama düşüyor; endeksin günlük dış piyasa yapısı ayı.
- Filtreler: düşüşte long yok; yükselişte short yok; rejime karşı işlem yok; düşüşte hiç işlem yok.

**D7, yön × 20 günlük endeks getirisi:**

| Yön / endeks | İşlem | Stop | Doğrudan stop | Net R | Keşif (n) | Doğrulama (n) |
|---|---:|---:|---:|---:|---:|---:|
| long / endeks düşüşte | 76 | %42,1 | %25,0 | +0,029 | +0,068 (39) | −0,013 (37) |
| long / endeks yükselişte | 271 | %39,5 | %21,8 | +0,174 | +0,156 (209) | +0,237 (62) |
| short / endeks düşüşte | 144 | %56,2 | %28,5 | −0,073 | −0,441 (72) | +0,295 (72) |
| short / endeks yükselişte | 146 | %41,1 | %21,9 | +0,234 | +0,203 (94) | +0,292 (52) |
| *bütün D7* | 637 | %44,0 | %23,7 | +0,115 | +0,054 (414) | +0,227 (223) |

**D7, "endeks düşüşteyken long açma" kuralı, altı tanımla:**

| Düşüş tanımı | Elenen long | Elenenlerin net R'si | Elenen doğrudan stop (/151) | Elenen kârlı işlem | Toplam etki | En kötü GA (R/işlem) | Karar |
|---|---:|---:|---:|---:|---:|---|---|
| son 10 gün ekside | 92 | −0,007 | 19 | 46 | +0,6 R | [−0,052; +0,043] | GECMEDI |
| son 20 gün ekside | 76 | +0,029 | 19 | 39 | −2,2 R | [−0,044; +0,032] | GECMEDI |
| son 60 gün ekside | 51 | +0,016 | 10 | 24 | −0,8 R | [−0,047; +0,037] | GECMEDI |
| 20 günlük ortalamanın altında | 85 | +0,003 | 20 | 44 | −0,3 R | [−0,045; +0,038] | GECMEDI |
| 50 günlük ortalamanın altında | 80 | +0,152 | 17 | 45 | −12,2 R | [−0,068; +0,025] | GECMEDI |
| ortalamanın altında ve ortalama düşüyor | 57 | +0,233 | 12 | 33 | −13,3 R | [−0,059; +0,013] | GECMEDI |

Yedinci tanım (endeksin günlük dış yapısı ayı) arşivde yalnız 1 düşüş dönemi buluyor ve D7'de 1 long eliyor; kanıt taşımıyor.

- **28 varyanttan hiçbiri üç kümenin hiçbirinde kabul çıtasını geçmedi.** D7: GECMEDI 24, SAYILMAZ_N<30 2, ZARARLI 2; D6:
  GECMEDI 26, SAYILMAZ_N<30 1, ZAYIF_ARTI 1; D1: GECMEDI 21, ZAYIF_ARTI 7.
- **Doğrudan stop oranı rejime göre değişmiyor.** Endeks işleme karşıyken %23,0, işlemle aynı yöndeyken %24,1 (taban %23,7).
  "Düşüşte long açma" kuralının elediği longlarda doğrudan stop oranı %19,6–%25,0; yani kural doğrudan stopları değil,
  sıradan bir long kesitini eliyor: 151 doğrudan stopun 10–20 tanesi gidiyor, karşılığında 24–46 kârlı işlem de gidiyor.
- **Düşüşte açılan longlar D7'de zarar etmiyor.** Altı tanımda elenenlerin ortalaması −0,007 ile +0,233 R arasında; kuralın
  toplam etkisi +0,6 ile −13,3 R arasında.
- **"Düşüşte hiç işlem açma"** (20 günlük tanım) 220 işlem eliyor, toplam +8,3 R; ama keşifte +0,0703, doğrulamada −0,0931
  R/işlem: işaret dönüyor. Nedeni tablodaki short / endeks düşüşte hücresi: keşifte zarar ediyor, doğrulamada kâr ediyor.
- **Geniş kümede (D1) "düşüşte long açma" rakam olarak artıda ama dönemler arasında tutmuyor.** 10 günlük tanımla 941 long
  elenir, toplam +74,7 R (işlem başına +0,0177 R, en kötü aralık [−0,0188; +0,0562]); keşifte −0,0216, doğrulamada +0,0885
  R/işlem. Elenen longlar keşifte kârlı, doğrulamada zararlıydı.
- **Tek tutarlı iz betimleyici bir hücrede.** Endeks son 60 günde işlemin tersine %5'ten fazla gitmişse: D7 125 işlem −0,116
  R [−0,395; +0,153]; D6 233 işlem −0,132 R [−0,348; +0,074]; D1 1375 işlem −0,112 R [−0,275; +0,029]. D7 ve D6'da zayıflık
  short tarafında (endeks 60 günde %5'ten fazla YÜKSELMİŞKEN açılan shortlar: D7 103 işlem −0,173 R, keşif −0,166 / doğrulama
  −0,186); endeks %5'ten fazla DÜŞMÜŞKEN açılan longlar az ve ekside değil (D7 22 işlem +0,154 R). Bu kova ön-kayıtlı bir
  filtre değil, aralıklar sıfırı içeriyor: kural değil, gölge defterde izlenecek aday.
- **Bağımsız gözlem az.** Arşiv 499 endeks günü; 20 günlük tanımla yalnız 25 ayrı düşüş dönemi var. İşlem sayısı yüksek
  görünse de bir rejim filtresinin kanıtı dönem sayısıyla sınırlıdır.
- **Duyarlılık.** Girişle aynı anda kapanan endeks günü de sayılırsa 10 karar etiketi değişiyor; geçen varyant sayısı yine 0.

### 6.8 Kâr görüp dönenler: 0,5 / 1 ATR gördükten sonra stop olan işlemlerde domainler ne gösteriyordu?

D7'nin 280 stopundan 151 tanesi stoptan önce 0,5 ATR'yi hiç görmedi; **129 tanesi en az 0,5 ATR, bunların 58 tanesi en az 1
ATR gördükten sonra döndü** (hedef 2 ATR). Bu bölüm o işlemleri Stabil, Market Structure, formasyon, OB/FVG, hacim ve endeks
açısından açar. Sonuçlar ana CSV'den okundu, yalnız domain serileri yeniden kuruldu. Eşik ve tepe, çıkış mumundan ÖNCEKİ
mumlardan okunur (stop mumunun içi bilinmez; sayılar alt sınırdır). Engel her zaman ilgili mumdan önceki kapanışta bilinen
seviyedir. Ölçü ATR'dir; §6.3'teki "en az +0,5 R görüp stop olan 110 işlem" aynı sorunun R cinsinden sayımıdır.
Kaynak: `sonuclar/golge_v2/kar_gorup_donen/RAPOR.md` (8 başlık × 3 küme), `ozet.json`, `islemler.csv.gz`.

Üç okuma vardır ve güçleri farklıdır: *tepeden stopa* yalnız stop olanlara geriye dönük bakar (ne görüldüğünü anlatır, neden
olduğunu kanıtlamaz); *eşikten sonra* aynı olayı eşiği gören bütün işlemlerde arar (kontrol); *eşik anı* eşiğin ilk görüldüğü
mumun kapanışında bilinenlere bakar ve tek adil karşılaştırmadır, çünkü o an sonuç bilinmez ve aynı eşiği görüp hedefe
gidenler kontrol grubudur.

**Eşiği görüp o mumun kapanışında hâlâ açık olan işlemlerin akıbeti (D7).** Eşiği ilk kez çıkış mumunda gören işlemler
(örneğin tek mumda hedefe giden) burada yoktur:

| Eşik | İşlem | Stop oldu | Hedefe gitti | Süre doldu, kârda | Süre doldu, zararda | Grubun net R'si |
|---|---:|---:|---:|---:|---:|---:|
| 0,5 ATR | 411 | 129 (%31,4) | 194 (%47,2) | 60 (%14,6) | 28 (%6,8) | +0,402 |
| 1 ATR | 293 | 58 (%19,8) | 163 (%55,6) | 53 (%18,1) | 19 (%6,5) | +0,706 |

**Tepeden stopa ne görüldü (D7; bir işlemde birden çoğu olabilir).** "Kontrol": aynı tür olay eşiği gören bütün işlemlerde
eşikten sonra görülünce stop oranı / görülmeyince stop oranı. İki oran yakınsa o gözlem dönüşü açıklamaz.

| Gözlem | 0,5 ATR görüp stop (129) | Kontrol | 1 ATR görüp stop (58) | Kontrol |
|---|---:|---:|---:|---:|
| Tepe mumu bilinen bir karşı engele değdi, kapanışla aşamadı | 51 (%39,5) | %30,1 / %32,8 | 25 (%43,1) | %20,0 / %19,6 |
| Tepe bir engelin 0,25 ATR dibinde kaldı (değmedi) | 6 (%4,7) | — | 2 (%3,4) | — |
| Tepeden stopa endeks işlemin tersine en az %0,5 gitti | 79 (%61,2) | %54,0 / %19,6 | 40 (%69,0) | %40,2 / %9,5 |
| Hissenin kendi yapısı bozuldu (tez seviyesinin içine kapanış, formasyon bozulması, ters BOS/CHoCH) | 51 (%39,5) | %61,6 / %23,4 | 19 (%32,8) | %61,3 / %14,9 |
| Ters hacim baskısı ya da tepede yüksek çaba – zayıf sonuç | 36 (%27,9) | %34,4 / %30,5 | 16 (%27,6) | %23,7 / %18,8 |
| Stop bir açılış boşluğuyla geldi | 13 (%10,1) | — | 7 (%12,1) | — |
| Hiçbiri görülmedi | 12 (%9,3) | — | 5 (%8,6) | — |

- **Takıldığı engel hangi domain?** 129 işlemde tepe mumu: Market Structure seviyesi 37 (%28,7), OB/FVG bandı 27 (%20,9),
  Stabil karşı seviyesi 6 (%4,7) (örtüşür). OB/FVG'nin 13 tanesinde fiyat banda dışarıdan gelip takıldı, 14 tanesinde önceki
  kapanışta zaten bandın içindeydi.
- **Market Structure.** Tepe ile stop arasında ters dış ya da iç BOS/CHoCH görülen işlem 0; yapı kırılımı stoptan önce
  gelmiyor (stop mumunun kendisinde 3). Motorun ters süpürme / sahte kırılım olayı tepe mumunda 10 (%7,8), tepe ile stop
  arasında 35 (%27,1) işlemde var.
- **Formasyon ve tez seviyesi.** Tepe ile stop arasında tez seviyesinin içine kapanış 47 (%36,4), formasyon bozulması (retest
  / teyitsiz / başarısız / karşı kırılım) 40 (%31,0).
- **Hacim.** Tepe ile stop arasında ters hacim baskısı 33 (%25,6); tepede "yüksek çaba – zayıf sonuç" sınıfı yalnız 3
  işlemde.
- **Dönüşün büyüklüğü ve hızı.** Tepeden stopa medyan 2,32 ATR geri çekilme; 87 (%67,4) işlemde 2 ATR'den fazla. Tepeden
  stopa medyan 2 mum; 68 işlemde bir ya da iki mum. Stoptan önceki son kapanışta 45 (%34,9) işlem hâlâ kârdaydı. Tepe mumu 86
  (%66,7) işlemde aralığının en az yarısını geri verip kapattı.
- **1 ATR görüp dönen 58 işlemde** tablo aynı: endeks %69,0, engel %43,1; geri çekilme medyan 2,68 ATR ve 54 (%93,1) işlemde
  2 ATR'den fazla.

**Eşik anı: 0,5 ATR'nin ilk görüldüğü mumun kapanışında bilinenler.** "Stop": gözlem varken / yokken sonradan stop olma
oranı. "Çıkılsaydı": o kapanışta karar verip sonraki açılışta çıkmanın kümenin işlem başına net R'sine etkisi (masraf aynı;
kabul merdiveni §5.4'teki gibi).

| O kapanışta görülen | D7'de görüldüğü işlem | D7 stop: varken / yokken | D7 karar | D1 stop: varken / yokken | D1 karar | D7'de çıkılsaydı (R/işlem) | En kötü GA | Karar |
|---|---:|---:|---|---:|---|---:|---|---|
| Bilinen bir karşı engele değdi, kapanışla aşamadı | 162 | %30,9 / %31,7 | AYIRMIYOR | %34,4 / %32,2 | ZAYIF | −0,0199 | [−0,0651; +0,0252] | GECMEDI |
| … karşı Stabil seviyesi | 13 | %38,5 / %31,2 | SAYILMAZ_N<30 | %42,7 / %32,7 | AYIRIYOR | −0,0011 | [−0,0154; +0,0114] | SAYILMAZ_N<30 |
| … karşı Market Structure seviyesi | 90 | %40,0 / %29,0 | ZAYIF | %38,1 / %31,3 | AYIRIYOR | +0,0119 | [−0,0280; +0,0480] | ZAYIF_ARTI |
| … karşı OB/FVG bandı | 107 | %25,2 / %33,6 | ZAYIF | %33,0 / %33,9 | AYIRMIYOR | −0,0281 | [−0,0634; +0,0077] | GECMEDI |
| Bir karşı engeli kapanışla aştı | 60 | %21,7 / %33,0 | ZAYIF | %21,4 / %35,4 | AYIRIYOR | −0,0126 | [−0,0594; +0,0267] | GECMEDI |
| Kapanışın önünde en çok 0,5 ATR'de engel var | 158 | %33,5 / %30,0 | AYIRMIYOR | %31,7 / %36,0 | AYIRIYOR | −0,0061 | [−0,0523; +0,0441] | GECMEDI |
| Market Structure ters süpürme / sahte kırılım † | 24 | %29,2 / %31,5 | SAYILMAZ_N<30 | %44,0 / %32,3 | AYIRIYOR | +0,0008 | [−0,0127; +0,0143] | SAYILMAZ_N<30 |
| Formasyon girişten sonra aleyhte duruma geçti (retest ediliyor / teyitsiz / başarısız) † | 22 | %22,7 / %31,9 | SAYILMAZ_N<30 | %24,7 / %34,1 | AYIRIYOR | −0,0053 | [−0,0193; +0,0084] | SAYILMAZ_N<30 |
| Kapanış tez seviyesinin ters tarafında | 8 | %87,5 / %30,3 | SAYILMAZ_N<30 | %85,3 / %32,1 | AYIRIYOR | +0,0017 | [−0,0048; +0,0069] | SAYILMAZ_N<30 |
| Hacim baskısı işlemin tersine | 11 | %27,3 / %31,5 | SAYILMAZ_N<30 | %52,4 / %32,8 | AYIRIYOR | −0,0013 | [−0,0115; +0,0085] | SAYILMAZ_N<30 |
| Göreli hacim 0,75'in altında | 44 | %36,4 / %30,7 | AYIRMIYOR | %34,1 / %34,1 | AYIRMIYOR | −0,0112 | [−0,0400; +0,0198] | GECMEDI |
| Girişten beri endeks en az %0,5 ters | 67 | %35,8 / %30,6 | ZAYIF | %38,7 / %32,6 | ZAYIF | −0,0088 | [−0,0379; +0,0207] | GECMEDI |
| Girişte 20 günlük endeks rejimi karşı | 144 | %28,5 / %33,0 | ZAYIF | %33,4 / %33,6 | AYIRMIYOR | −0,0231 | [−0,0701; +0,0234] | GECMEDI |
| 0,5 ATR'yi mum içinde gördü, altında kapattı | 215 | %42,3 / %19,4 | AYIRIYOR | %42,7 / %23,3 | AYIRIYOR | −0,0375 | [−0,0943; +0,0195] | GECMEDI |
| Mum aralığının en az yarısını geri verdi | 128 | %46,1 / %24,7 | AYIRIYOR | %46,8 / %26,9 | AYIRIYOR | −0,0077 | [−0,0489; +0,0314] | GECMEDI |
| Stop uzaklığı en çok 1 ATR | 106 | %42,5 / %27,5 | AYIRIYOR | %41,1 / %28,3 | AYIRIYOR | −0,0224 | [−0,0783; +0,0356] | GECMEDI |

Liste 24 gözlemdir; tamamı ve 1 ATR eşiği kaynak raporda. 20 gözlem ölçümden önce sabitlendi; † işaretli olanlar (kaynak raporda 4
tane) ve "çıkılsaydı" sütunu ilk koşudan sonra domain kapsamını tamamlamak için eklendi. Çoklu karşılaştırma düzeltmesi yoktur.

- **Bilinen bir engele takılmak dönüşü öngörmüyor.** 0,5 ATR mumu bir karşı engele değip aşamadıysa sonradan stop oranı
  %30,9, değmediyse %31,7. Seviyeler sık: eşik mumlarının %39,4 kadarı zaten bir engele değiyor; dönen işlemlerin tepe
  mumunda görülen %39,5 oranı bu tabanla aynı.
- **Domainler arasında fark var ama D7'de sayı yetmiyor.** Market Structure seviyesinde ret D7'de %40,0 / %29,0, Stabil
  seviyesinde ret D1'de %42,7 / %32,7 (D7'de yalnız 13 işlem). OB/FVG bandında ret ters yönde: D7 %25,2 / %33,6, D1 %33,0 /
  %33,9; karşı bant bu örneklemde duvar gibi davranmıyor (§5.4'te bu rette çıkmanın D7'de −0,030 R/işlem vermesi ve D1'de
  ayırt edilebilir biçimde zararlı çıkmasıyla tutarlı). Engeli kapanışla aşmak koruyucu: D1 %21,4 / %35,4.
- **D7'de 24 gözlemden ayıran 3 tanesi mumun kendi biçimi ve stop mesafesi:** eşiği görüp altında kapatmak (%42,3 / %19,4),
  uzun fitil (%46,1 / %24,7), dar stop (%42,5 / %27,5). 1 ATR eşiğinde ayıran tek gözlem uzun fitil.
- **Ayıran gözlemde çıkmak yine de kazandırmıyor.** İki eşik × 24 gözlem × üç kümede kabul merdivenini geçen çıkış kuralı: D7
  0, D6 0, D1 0. D7'de 0,5 ATR'yi gören her işlemden sonraki açılışta çıkmak −0,0637 R/işlem; uzun fitilde çıkmak −0,0077,
  eşik altı kapanışta çıkmak −0,0375 R/işlem. Bu gözlemler stop olasılığını yükseltiyor ama çıkış fiyatı zaten geri verilmiş
  oluyor ve aynı gözlemi görüp hedefe giden işlemlerin kârı kesiliyor (0,5 ATR görenlerin %47,2 kadarı hedefe gidiyor).
- **Dönüşle birlikte gelen iki şey işlem sürerken ortaya çıkıyor.** Eşikten sonra endeks en az %0,5 ters giderse stop oranı
  %54,0, gitmezse %19,6; hissenin kendi yapısı bozulursa %61,6, bozulmazsa %23,4. İlki §6.5'teki piyasa bulgusunun aynısıdır
  ve önceden bilinmez; ikincisi büyük ölçüde stopa giden yolun kendisidir (tez seviyesinin içine kapanışta stop oranı %88,7)
  ve çıkış kuralı olarak §5.4'te sınandı, geçmedi.
- **Ters süpürme adayı sonradan sınandı, geçmedi.** Market Structure motorunun ters süpürme / sahte kırılım olayı eşikten
  sonra görüldüğünde stop oranı %45,6, görülmediğinde %28,0; ama eşik mumunun kendisinde yalnız 24 işlemde var ve orada
  ayırmıyor. "Eşikten sonra" tablosu uzun yaşayan işlemi cezalandırdığı için bu fark kanıt değildir; §5.4'teki 20 varyantın
  arasında da yoktu. §6.9'da tepki olarak ölçüldü: D7'de çık −3,8 R, stopu girişe çek +0,6 R; ikisinde de keşif artı,
  doğrulama eksi.
- **Üç kümede aynı tablo.** Görüp dönenlerde endeksin tersine dönmesi D7 %61,2, D6 %59,1, D1 %59,1; hiçbir gözlemin eşlik
  etmediği dönüş D7 %9,3, D6 %8,7, D1 %6,3.

### 6.9 Tepki ölçümü: sistem bu gözlemlere tepki verseydi ne olurdu?

§6.8'in "tepeden stopa" tablosu doğal bir itiraz doğurur: engele takılma, tez seviyesinin içine kapanış, formasyon bozulması,
ters süpürme ve ters hacim işlem açıkken görülüyor; sistem neden tepki vermiyor? Tespit doğrudur: baz sistem bu gözlemleri
kaydeder ama işlem açıkken stop, hedef ve süre dışında hiçbir şey yapmaz (ilk mumlardaki ters dış kırılımda tez iptali vardır
ama D7'de hiç devreye girmedi). Bu bölüm tepki verilseydi ne olacağını eşleşmiş replay ile ölçer (§5.4 ile aynı motor, aynı
işlemler, aynı giriş / ilk stop / hedef / masraf, aynı kabul merdiveni).

İşlem çıkışa kadar en az 0,5 ATR (ya da 1 ATR) gördükten sonra — aynı kapanış dahil — tetik ilk kez yandığında tek bir tepki
verilir: **sonraki açılışta çık** ya da **stopu girişe çek**. 2 eşik × 12 tetik × 2 tepki = 48 varyant, üç küme. Tetikler
§6.8 tablosunun satırlarıdır ve o tablo görüldükten sonra yazılmıştır: ölçüm ön-kayıtlı değildir. Baz sonuçlar ana rapor ve
`surec_olcum` ile 4.233 işlemin hepsinde aynıdır; "0,5 ATR görülünce çık" satırı §6.8'in mumlardan hesaplanan karşı-olgusuyla
işlem işlem aynı sonucu verir.
Kaynak: `sonuclar/golge_v2/tepki_olcum/RAPOR.md` (4 tablo × 3 küme), `ozet.json`, `islemler.csv.gz`.

**D7, 0,5 ATR gördükten sonra** (411 işlem bu eşiği çıkıştan önce gördü; 129 tanesi stop oldu). "§6.8'de": aynı gözlemin §6.8
tablosunda 129 stop içinde sayıldığı işlem. "Stop olacaklarda / hedefe gideceklerde": tepkinin sonucunu değiştirdiği
işlemlerin baz sonucuna göre sayısı ve o gruptaki toplam etkisi.

| Tetik | §6.8'de | Tetiklenen | Çık: stop olacaklarda | Çık: hedefe gideceklerde | Çık: fark R/işlem (toplam) | Karar | Girişe çek: fark R/işlem (toplam) | Karar |
|---|---:|---:|---:|---:|---:|---|---:|---|
| Koşulsuz: 0,5 ATR görülür görülmez | — | 411 | 129: +160,9 R | 194: −197,1 R | −0,0637 (−40,6 R) | GECMEDI | −0,0600 (−38,2 R) | GECMEDI |
| Mum bilinen bir karşı engele takıldı | 51 | 216 | 65: +76,6 R | 86: −87,5 R | −0,0239 (−15,2 R) | GECMEDI | −0,0130 (−8,3 R) | GECMEDI |
| … karşı Stabil seviyesi | 6 | 31 | 7: +7,0 R | 11: −11,7 R | −0,0078 (−5,0 R) | GECMEDI | −0,0019 (−1,2 R) | SAYILMAZ_N<30 |
| … karşı Market Structure seviyesi | 37 | 150 | 49: +54,5 R | 57: −59,4 R | −0,0088 (−5,6 R) | GECMEDI | −0,0069 (−4,4 R) | GECMEDI |
| … karşı OB/FVG bandı | 27 | 146 | 36: +45,9 R | 62: −55,9 R | −0,0199 (−12,7 R) | GECMEDI | −0,0086 (−5,5 R) | GECMEDI |
| Kapanış tez seviyesinin içine döndü | 47 | 53 | 47: +15,1 R | 2: −5,0 R | +0,0069 (+4,4 R) | ZAYIF_ARTI | +0,0069 (+4,4 R) | ZAYIF_ARTI |
| Formasyon bozuldu | 40 | 75 | 43: +21,8 R | 16: −20,6 R | −0,0075 (−4,8 R) | GECMEDI | −0,0075 (−4,8 R) | GECMEDI |
| Market Structure ters süpürme | 35 | 79 | 36: +18,1 R | 16: −18,1 R | −0,0059 (−3,8 R) | GECMEDI | +0,0009 (+0,6 R) | GECMEDI |
| Ters hacim baskısı | 36 | 96 | 33: +19,3 R | 20: −22,7 R | −0,0195 (−12,4 R) | GECMEDI | −0,0080 (−5,1 R) | GECMEDI |
| Girişten beri endeks en az %0,5 ters | — | 150 | 58: +48,1 R | 46: −48,5 R | −0,0169 (−10,8 R) | GECMEDI | −0,0103 (−6,5 R) | GECMEDI |
| Domain gözlemlerinden herhangi biri | — | 274 | 93: +91,9 R | 101: −104,1 R | −0,0331 (−21,1 R) | GECMEDI | −0,0226 (−14,4 R) | GECMEDI |
| İki farklı tür domain gözlemi birikti | — | 140 | 63: +35,9 R | 27: −33,7 R | −0,0128 (−8,2 R) | GECMEDI | +0,0017 (+1,1 R) | GECMEDI |

- **48 varyanttan D7 ve D6'da geçen yok; D1'de 2.** D7: GECMEDI 36, SAYILMAZ_N<30 7, ZAYIF_ARTI 5; D6: GECMEDI 42, ZAYIF_ARTI
  6; D1: GECMEDI 38, UMUT_VAR 2, ZARARLI 4, ZAYIF_ARTI 4.
- **Tablo geriye bakar, tepki ileriye.** §6.8 tablosu tepe mumundan sayar; tepe ancak işlem bittikten sonra bilinir. Tetik,
  eşik görüldükten sonraki her kapanışta aranır ve tablodaki işlemlerin hepsini kapsar: tepe mumu engele takılan 51 stopun
  hepsinde yanar, ayrıca 14 stopta daha (toplam 65). Ama aynı tetik hedefe gidecek 86 işlemde de yanar. Tek fark hacim
  satırındadır: tablodaki 36 işlemin 3 tanesi yalnız tepe mumundaki "yüksek çaba – zayıf sonuç" gözlemidir; tetik ters hacim
  baskısıdır (33).
- **Engele tepki vermek kazananı kesiyor.** Tetiklenen 216 işlemin 65 tanesi (%30,1) stop olacaktı, 86 tanesi (%39,8) hedefe
  gidecekti; eşiği gören bütün işlemlerde bu oranlar %31,4 ve %47,2. Çıkmak stop olacaklarda +76,6 R kazandırıyor, hedefe
  gideceklerde −87,5 R kaybettiriyor. Stabil, Market Structure ve OB/FVG ayrı ayrı da eksi. Geniş kümede (D1) "engele
  takılınca çık" −150,9 R ile ZARARLI.
- **Daha seçici gözlemler de yetmiyor, çünkü geç geliyor.** Formasyon bozulmasının tetiklendiği 75 işlemin 43 tanesi stop
  olacaktı, yalnız 16 tanesi hedefe gidecekti; ama görüldüğünde fiyat yolun bir kısmını geri vermiş oluyor: kurtarılan stop
  başına +0,51 R, kesilen kazanan başına −1,29 R. Formasyon, süpürme, hacim, endeks, "herhangi biri" ve "iki farklı tür"
  tetiklerinin iki tepkiyle on iki varyantı D7'de −21,1 ile +1,1 R arasında; hepsi GECMEDI. §6.8'de aday diye not edilen ters
  süpürme de bunların içinde: çık −3,8 R, girişe çek +0,6 R; keşifte artı, doğrulamada eksi.
- **Koşulsuz kâr koruma da tutmuyor.** 0,5 ATR görülür görülmez çıkmak D7'de −40,6 R, stopu girişe çekmek −38,2 R (D1'de
  −200,4 ve −157,3 R; ikisi de ZARARLI). Stopu girişe çekmek stop olacak 129 işlemin hepsini kurtarıyor (+113,9 R) ama girişe
  değip sonra hedefe gidecek 84 işlemi kesiyor (−129,1 R).
- **Tek tutarlı tetik: kapanışın tez seviyesinin içine dönmesi.** D7'de tetiklenen 53 işlemin 47 tanesi stop olacaktı, yalnız
  2 tanesi hedefe gidecekti; tepki 43 işlemi iyileştirip 5 işlemi kötüleştiriyor. Etki D7 +4,4 R (+0,0069 R/işlem,
  ZAYIF_ARTI); D6 +7,5 R (+0,0067 R/işlem, ZAYIF_ARTI); D1 +26,0 R (+0,0061 R/işlem, ZAYIF_ARTI). Üç kümede ve iki dönemde
  artı; D1'de 1 ATR eşiğinde UMUT_VAR (+23,9 R; en kötü aralık [+0,0005; +0,0105]). Kazanç küçük, çünkü kapanış seviyenin
  içine döndüğünde fiyat stopa zaten yakındır: kurtarılan stop başına +0,32 R.
- **Bu yeni bir bulgu değil, §5.4'teki adayın teyidi.** Aynı kural kâr şartı olmadan §5.4'te ölçülmüştü: D7 +11,5 R (101
  işlem), D1 +14,2 R (862 işlem). Kâr şartıyla D7 +4,4 R, D1 +26,0 R: şartın katkısı kümeler arasında aynı yönde değil. Kural
  değil, ileriye dönük gölge defterde izlenecek aday olmayı sürdürüyor.
- **D7'deki öbür üç artı satır geniş kümelerde tutmuyor.** 1 ATR'den sonra stopu girişe çekmek D7'de OB/FVG bandına takılınca
  +6,5 R, iki farklı tür birikince +4,1 R, endeks ters gidince +1,8 R veriyor (üçü de ZAYIF_ARTI; sonucu değişen 38–53
  işlem). Aynı varyantlar D6'da +5,9 / +2,7 / −3,1 R, D1'de −9,3 / −7,6 / −0,6 R ve hepsi GECMEDI.
- **Stabil seviyesi yalnız geniş kümede artı.** 1 ATR'den sonra karşı Stabil seviyesine takılınca çıkmak D1'de +33,0 R (220
  işlem, ZAYIF_ARTI; en kötü aralık [−0,0011; +0,0168]); ama D7'de −4,5 R (18 işlem) ve D6'da −4,9 R (48 işlem). Artı D6
  dışındaki işlemlerden geliyor; çekirdek kümelerde yön ters. Aday değil, not.
- **Kısmi çıkış işareti değiştirmez.** Masraf pozisyonla orantılı olduğundan pozisyonun yarısını kapatmanın farkı ve güven
  aralığı tam çıkışınkinin tam yarısıdır; eksi olan tepki artıya dönmez.
- **"Görüldü" ile "tepki verilmeliydi" aynı şey değil.** Bir gözlem ancak hedefe gidecek işlemlerde nadiren yanıyorsa ve
  fiyat henüz geri verilmemişken görülüyorsa tepkiye değer. Bu örneklemde ilk koşulu yalnız tez seviyesinin içine kapanış
  sağlıyor; o da ikinci koşulu sağlamadığı için küçük kalıyor.

### 6.10 Okuma

- **Stop çoğunlukla aniden geliyor.** Stopların %73'ünde stoptan önce uyarı sayılacak bir kapanış yok; kapanışa bakan bir
  çıkış kuralı ancak kalan 75 stopa dokunabilir. §5.4'te en iyi adayın (tez seviyesi içine kapanışta çık) küçük kalması
  bununla tutarlı.
- **"Önce kâr gördü" tek başına koruma gerekçesi değil.** Stopların %39'u önce en az +0,5 R gördü; ama hedefe ulaşan
  işlemlerin %21'i de hedeften önce 0,5 R aleyhte kaldı. Stopu yaklaştıran bir kural iki grubu ayıramıyor: +1 R'de stopu
  başa başa çekmek 82 işlemi etkiledi, 48'ini iyileştirip 34'ünü kötüleştirdi ve net −0,012 R/işlem verdi (§5.4).
  Kârın görüldüğü kapanışta bilinen domain gözlemlerinin çoğu iki grubu ayırmıyor; ayıranlarda (uzun fitil, eşik altı
  kapanış, dar stop) çıkmak da kazandırmıyor (§6.8). Kârdan sonra görülen aleyhte gözleme tepki vermek de, tez seviyesinin
  içine kapanış dışında, kazandırmıyor: gözlem ya hedefe gidecek işlemlerde de yanıyor ya da fiyat geri verildikten sonra
  geliyor (§6.9).
- **Stop yerinde mi?** Stop olanların %46'sı ufuk sonunda stopun da ötesindeydi, %15'i stoptan sonra hedefe gitti. Stopu
  genişletmenin ya da yeniden girişin değeri burada ölçülmedi; bu sayılar yalnız tavanı gösterir.
- **Sonuç piyasanın sonraki yönüne bağlı.** Endeks işlem süresince yatay kaldığında beklenti sıfıra yakın; kazanç endeksin
  lehte gittiği, kayıp ters gittiği işlemlerden geliyor. Girişten önceki endeks yönü bunu öngörmüyor; 10–60 günlük rejim
  tanımları da öngörmüyor ve "endeks düşüşteyken long açma" doğrudan stopları elemiyor (§6.7). Haftalık yığılma
  (en iyi 5 hafta olmadan +5,7 R) aynı şeyi söylüyor ve §4'teki "karar zaman kümelerinde kırılgan" sonucunun işlem
  düzeyindeki karşılığıdır.
- **Masraf dar stopta ağır.** Stop mesafesi 0,8 ATR ve altında olan işlemlerde masraf işlem başına 0,21 R; 2,2 ATR'den geniş
  olanlarda 0,05 R.

### 6.11 Sınırlar

- Bu bölüm betimleyicidir: olanı sayar, bir kuralın değerini ölçmez. Kural değeri eşleşmiş replay ile ölçülür (§5.4).
- Mum çözünürlüğünde stop mumunun içi bilinmez. Saat çözünürlüğü D7'nin 280 stopundan 254'ünde var; stop saatinin kendi içi
  yine bilinmez.
- Piyasa tablosu işlem bittikten sonra bilinen bir büyüklüğe bakar. Hissenin endeksle birlikte hareket etmesi beklenen bir
  şeydir; tablo neden kanıtlamaz, sonucun neyle birlikte geldiğini gösterir.
- Giriş koşulu tabloları ilişki gösterir. Çok sayıda kesit sınandı, çoklu karşılaştırma düzeltmesi yok; kümeler iç içedir.
- §6.7'de bağımsız gözlem işlem değil rejim dönemidir (20 günlük tanımda 25 düşüş dönemi); arşiv iki yıldır (499 endeks
  günü). "Geçmedi" sonucu bu arşiv için geçerlidir; filtrenin hiçbir koşulda işe yaramayacağını göstermez.
- §6.8'in "tepeden stopa" ve "eşikten sonra" tabloları sonuca koşulludur ve kural değeri taşımaz; kural değeri eşik anı
  tablosunun "çıkılsaydı" sütunu ile §6.9'daki tepki ölçümüdür. İkisi de sonraki açılışta tam çıkışı, §6.9 ayrıca stopu
  girişe çekmeyi ölçer; sabit oranlı kısmi çıkışın etkisi tam çıkışın aynı oranıdır. Stopu tetik mumunun ötesine taşıma ve
  yeniden giriş ölçülmedi (kâr şartı olmadan stop taşıma §5.4'te).
- §6.9 ön-kayıtlı değildir: tetikler §6.8 tablosu görüldükten sonra, o tablonun satırlarından yazıldı; 48 varyant × 3 küme
  sınandı, çoklu karşılaştırma düzeltmesi yok. Tetikler aynı örneklemde stoplarda sık görüldükleri için seçildiğinden
  yanlılık tepkinin lehinedir; `GECMEDI` sonuçları bu yüzden zayıflamaz, artı çıkan satırlar ise ancak aday sayılır.

## 7. Önceki üç D7 alt ölçümü

`iptal_olcum`, `mtf_olcum` ve `donus_anatomisi` karantinadan önceki 648 işlemlik D7 kümesinde yapıldı; raporları o
kümeyi anlatır. Betikler bilerek aynı kümeyi okumaya devam ediyor.

- `iptal_olcum` ve `donus_anatomisi` yeni motorla yeniden koşuldu ve taahhütlü çıktıları yeniden üretti (sayısal
  fark en fazla 1e-13; `donus_anatomisi`'nde satır sırası tamamlanma sırasına bağlı).
- `mtf_olcum` 601 işlemlik aynı kümeyi ve aynı sonuçları üretti. Betiğin çıktısı taahhütlü dosyadan iki küçük
  noktada ayrılıyor: dışlanan 47 olayın 43'ünün etiketi (`incomplete_hourly_horizon` → `missing_hourly_session`)
  ve bir işlemde çıkış bar indeksi (net ve neden aynı). Aynı fark bu çalışmadan önceki betikle (commit `9ba3d19`)
  de çıkıyor; yani bu çalışmadan kaynaklanmıyor. Taahhütlü dosyalar olduğu gibi bırakıldı.
- Karantina sonrası kümede, uygulanabilir çıkış fiyatıyla güncel işlem-içi ölçüm bu belgenin §5'idir.
- `donus_anatomisi`'nin sorduğu "kâr görüp dönen işlemler" sorusunun karantina sonrası kümedeki güncel sayımı §6.3'te, domain
  dökümü §6.8'de, tepki ölçümü §6.9'dadır.

## 8. Açık konu: Market Structure motorunda bayat durum

Market Structure motoru bir korunan seviyeyi "geçerli" diye bildirirken fiyat o seviyenin çok ötesinde kapanmış
olabiliyor. Ardışık taban/tavan barlarında ya da kopukluk sonrasında swing oluşmayınca kırılım olayı üretilemiyor
ve durum yüzlerce bar öyle kalabiliyor. Örnek: `BEGYO` günlükte fiyat Mayıs 2025'teki ardışık taban günlerinde
korunan dibin (15,28) altına indi; motor kırılımı kaydetmedi ve on üç ay sonra, fiyat 4,16 iken, iç yapı hâlâ
"yükseliş, korunan dip 15,28" diyor.

- Motor canlı ürün kodudur (`domain_engines/market_structure/`); **dokunulmadı**.
- Gölge v2'ye etkisi ölçüldü. Olay barında dış yapının korunan seviyesi kapanışın 1 ATR'den fazla gerisindeyse olay
  `ms_dis_bayat` etiketi alır (ölçümden çıkarılmaz). Temiz kümede 780 olay, 46 sembol. `4h + 1d` katmanlarında:
  D1'de 58, D6'da 13, **D7'de 0** olay. D7 taze ve uyumlu bir dış BOS istediği için takılı motor D7 olayı
  üretmiyor. Kaynak: `RAPOR_GOLGE_V2.md` §7b.
- Bir kerelik keşif taramasında (betiği depoda değil) `KRGYO` 4s serisinde barların %96'sında, `HATEK` 4s'de %90'ında,
  `PEKGY` 4s'de %85'inde dış korunan seviye fiyatın 1 ATR'den fazla gerisindeydi. `HATEK`'te veri kopukluğu yok.
- Canlı kartlar aynı motorun durumunu gösteriyorsa bu sembollerde aynı bayatlık görülebilir; doğrulanmadı.

## 9. Yeniden üretim

```bash
python -m research.golge_v2 --evren evren176 --workers 2            # ~18 dk; ana CSV'ler + RAPOR_GOLGE_V2.md
python -m research.golge_v2_karantina_duyarlilik                    # ~30 sn; karantina_duyarlilik/
python -m research.golge_v2_surec_olcum --workers 2                 # ~4 dk; surec_olcum/
python -m research.golge_v2_sonuc_anatomisi --workers 2             # ~15 sn; sonuc_anatomisi/
python -m research.golge_v2_endeks_filtresi --workers 2             # ~35 sn; endeks_filtresi/
python -m research.golge_v2_kar_gorup_donen --workers 2             # ~4 dk; kar_gorup_donen/
python -m research.golge_v2_tepki_olcum --workers 2                 # ~5 dk; tepki_olcum/
python -m pytest test_golge_v2_surec.py test_golge_v2_kesme.py test_golge_v2_birim.py \
    test_golge_v2_iptal_olcum.py test_golge_v2_mtf_yonetim.py test_golge_v2_sonuc_anatomisi.py \
    test_golge_v2_endeks_filtresi.py test_golge_v2_kar_gorup_donen.py test_golge_v2_tepki_olcum.py -q
```

Süreler 2 çekirdekli makinede ölçüldü. `--cache-dir` verilirse sembol sonuçları önbelleğe alınır; anahtar kod ve
veri özetini içerdiği için kod değişince kendiliğinden düşer.

| Dosya | İçerik |
|---|---|
| `senaryo_v2/surec.py` | Gözcü, tez durumu, etiket sözlüğü, politikalar |
| `senaryo_v2/yaris.py` | `surecli_yaris` (bar içi zaman sırası tek yerde), Mod 2 düzeltmeleri |
| `senaryo_v2/adaptor.py`, `modeller.py` | Kopukluk tespiti, karantina aralıkları, süreç alanları, `ms_dis_bayat` |
| `senaryo_v2/rapor.py` | Zaman kümeli güven aralıkları, süreç özeti |
| `research/golge_v2.py` | Ana koşucu: karantina, fail-closed, önbellek anahtarı, rapor §7–§9 |
| `research/golge_v2_surec_olcum.py` | İleri beklenti tablosu + 20 varyantlı eşleşmiş replay |
| `research/golge_v2_karantina_duyarlilik.py` | Karantina penceresine duyarlılık |
| `research/golge_v2_sonuc_anatomisi.py` | Kâr/zarar dökümü, kayıp yolları, stop öncesi ve sonrası, piyasa ve giriş koşulu kesitleri |
| `research/golge_v2_endeks_filtresi.py` | Girişte bilinen endeks rejimi: 7 tanım × 4 filtre, doğrudan stop ayrımı, kademeli tablo, duyarlılık |
| `research/golge_v2_kar_gorup_donen.py` | 0,5 / 1 ATR görüp stop olanların domain dökümü: tepeden stopa, eşikten sonra, eşik anı, çıkış karşı-olgusu |
| `research/golge_v2_tepki_olcum.py` | Kâr gördükten sonra aleyhte gözleme tepki: 2 eşik × 12 tetik × 2 tepki, eşleşmiş replay |
| `test_golge_v2_surec.py` | Süreç, politika, Mod 2, karantina ve rapor yardımcıları testleri |
| `test_golge_v2_sonuc_anatomisi.py` | Yol yürüyücünün motorla eşitliği, sınıflandırıcılar, özetin iç tutarlılığı |
| `test_golge_v2_endeks_filtresi.py` | Rejimin nedenselliği, stop grupları, filtreler, kabul merdiveni, çıktının iç tutarlılığı |
| `test_golge_v2_kar_gorup_donen.py` | Engel okuması, eşik mumu, birincil gözlem, fark aralığı, çıkış karşı-olgusu, çıktının iç tutarlılığı |
| `test_golge_v2_tepki_olcum.py` | Tetikler ve nedensellik, tepki politikası, özet; çıktının ana rapor, `surec_olcum` ve `kar_gorup_donen` ile işlem işlem eşitliği |
