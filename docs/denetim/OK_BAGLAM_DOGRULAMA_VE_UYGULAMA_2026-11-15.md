# Ok bağlam profili — doğrulama ve uygulama (2026-11-15)

Kullanıcı onayı: "kontrol et, iyice doğrula, buna göre düzeltelim."

## Profil (yalnız yukarı ▲; dirence uygulanmadı — tür replay'i yok)
- **güçlü:** `upward_rebase_momentum` VEYA (`multi_bar_recovery` + rejim
  `BREACHED_FIXED_SUPPORT`)
- **zayıf:** rejim `HORIZONTAL_AFTER_DROP` + geri alım/süpürme oku
- Kaynak: `stabil_ok_replay_2026_11_05/events.csv.gz` (555 geçerli ok;
  kayıttaki `close_reclaim`, üretimdeki `multi_bar_recovery` karşılığıdır)

## Doğrulama (aynı kayıt üzerinde, tanım değiştirilmeden)
| Kontrol | güçlü | zayıf |
|---|---|---|
| Tümü (n=186 / 192) | %57,5 yönde · %16,1 zayıf · med +0,23 | %44,8 · %30,7 · −0,34 |
| İlk yarı (n=100/102) | %57,0 · %15,0 | %46,1 · %27,5 |
| İkinci yarı (n=86/90) | %58,1 · %17,4 | %43,3 · %34,4 |
| Üst üste binmeyen (n=162/180) | %57,4 · %16,0 | %45,0 · %30,0 |

Sembol kümeli bootstrap (2000): yön farkı medyan **+12,7pp**, %95 GA
**[+1,6, +24,1]**; zayıf farkı medyan **+14,6pp**, GA **[+5,5, +23,8]**.
İki aralık da sıfırı dışarıda bırakır ama yön aralığının alt sınırı sıfıra
yakındır → etki "büyük kesin" değil, "ölçülü ve tutarlı" diye okunmalı.
Bileşenler ayrı ayrı da aynı yönde (rebase %58,7; geri alım+kırık-sabit
%56,8; düşüş-yatay rejimi tek başına %45,5).

Sınırlar: aynı arşivden türetildi (dış örnek değil), çoklu karşılaştırma
düzeltmesi yok, olaylar tarih korelasyonunu paylaşır. Bu yüzden uygulama
**filtre değil görsel sınıftır**.

## Uygulama
- `grafik/tarama.py`: davranıştan bar bazında `rejimler` + `baglam`
  ({bar: guclu/zayif}) snapshot'a yazılır.
- `grafik/render.py`: güçlü ok **beyaz halka**, zayıf ok **soluklaştırılır**
  (zemin rengi yarı saydam örtü; ok silinmez). Sayaçlar
  `meta["cizgiler"]["stabil"]["baglam_guclu_isaret"/"baglam_zayif_isaret"]`.
- Ok üretimi, bastırma, alarm ve kart mantığı **değişmedi**.
- Önceki "MS uyumu/FVG engeli halkası" denemesi kullanıcı isteğiyle
  geri alınmıştı (b39b133); bu uygulama onun yerine geçmez — farklı,
  doğrulanmış tanıma dayanır.

## İzleme
Canlıda halkalı/soluk ok dağılımı ve ileri tarihli performansı ayrıca
ölçülmeden sınıf tanımı genişletilmeyecek; direnç tarafı kendi replay'i
koşulmadan aynı sınıfı almayacak.
