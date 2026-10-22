# Ampirik Referans — ölçümü canlı metne bağlayan katman

> **Durum:** Yürürlükte · **Tarih:** 2026-10-22 · **Kod:** `ampirik_referans.py`
> **Test:** `test_ampirik_referans.py` (45 kontrol)
> **Kaynak tablolar:** [ARASTIRMA_BULGULARI.md](ARASTIRMA_BULGULARI.md) ·
> [FORMASYON_SONUCLARI.md](FORMASYON_SONUCLARI.md)

## 1. Neden var

Alarm kartı ve `/tara` çıktısı yalnız **"şu an ne oldu"** bilgisini taşıyordu:
kırılan seviye, kapanış, kalite, temas sayısı. Oysa `docs/arastirma/` altında
**aynı kurulumun arşivde nasıl sonuçlandığı** ölçülü durumda — bu sayılar
kartta hiç görünmüyordu (metin "sade" kalıyordu), yalnız 2621 satırlık rapor
dosyalarında duruyordu.

Bu katman ölçümü **olayın kendi özelliklerine koşullu** tek satıra çevirir:
her alarmda tekrarlanan sabit bir dipnot değil, o an ayırt edici olan sayı.

```
▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla

▲ direnç · boşluk 4s 41,90 +%5,8
· kalite 81/100 — güç 100
· bant 94 mum (30 Eylül'den)

◈ 4s yapı dış ve iç yukarı

◇ 32321 formasyon · %76 tuttu   ← formasyon sonucu (FRM-15)
◇ tutunca ~1,05 TL · %2,6       ← aynı ölçüm, TL ve % olarak
◇ rol uyumlu %80 · 15724        ← yön–rol uyumu (FRM-20)
· geçmiş davranış, kazanç değil

katılım 4s hacim 0,45 kat
```

## 2. Sözleşme

1. **Uydurma yok.** Her sayı rapor tablosundan elle alınmıştır; kaynağı
   `KAYNAK_TABLOLARI` sözlüğünde satır adıyla yazılıdır. Tabloda olmayan kesit
   (ör. 1h FVG zone referansı, 15m TF) için satır **üretilmez**.
2. **`n` satırda görünür.** Ölçüm tabanı olmadan oran basılmaz.
3. **Betimleme, tavsiye değil.** Çıktı "beklenen getiri" değil "arşivde bu
   kurulumda şu davranış gözlendi" cümlesidir. `al/sat/hedef/stop/kâr/zarar/
   tavsiye/garanti` kelimeleri testle yasaklanmıştır.
4. **Tek kaynak.** Sayı yalnız `ampirik_referans.py`'de durur; biçimleyici
   (kart, `/tara`) sayı hesaplamaz, gelen satırı basar.
5. **Sessizlik yeğdir.** Koşul sağlanmıyorsa satır dönmez. Kartı doldurmak için
   ilgisiz ölçüm basılmaz.
6. **Satır bütçesi.** Her satır ≤ 283 px (`telegram_measure`); testte
   `_kart_esik_px()` ile doğrulanır. Uzun ifade kısaltılır, satır bölünmez
   (bölünme girintili devam satırı üretir ve kart düzenini bozar).
7. **Varsayılan kapalı.** `domain_bolumleri(olcum=True)` verilmedikçe hiçbir
   yüzey değişmez; mevcut çağıranların metni bayt bayt aynı kalır.

## 3. Hangi ölçüm, hangi koşulda, hangi satır

Öncelik sırası `ONCELIK` sözlüğünde. KRİTİK: satırlar önce **aileye** göre
süzülür (`AILE_OLCU`), sonra aile içinde önceliğe göre sıralanır. Kart en çok
**3** satır basar (DM); public bültende **2**. Boş aile (`""`) süzgeci kapatır.

| # | Ölçüm | Koşul (canlı veri) | Kart satırı | n | Kaynak |
|---|---|---|---|---|---|
| 0 | MS devamı | alarm TF'de teyitli+güncel BOS/CHoCH | `◇ 1651 kırılımın %75'i sürdü` | kova n | Soru 5 |
| 1 | Formasyon sonucu | her formasyon alarmı (taban satır) | `◇ 32321 formasyon · %76 tuttu` | 32321 | FRM-15 |
| 2 | Tutan hareket | ATR + kırılım fiyatı varsa | `◇ tutunca ~1,05 TL · %2,6` | 24618 | FRM-16 |
| 3 | Yön–rol uyumu | kırılım yönü + en yakın PH/PL | `◇ rol uyumlu %80 · 15724` | 15724 / 13573 | FRM-20 |
| 4 | Geri çekilme | yalnız `retest_seen=False` | `◇ geri çekilme %35 · 28624` | 28624 | FRM-12 |
| 5 | Dokunuş tepkisi | fiyat bir OB/FVG temasında | `◇ 240484 temasta %65 tepki` | 240484 | Soru 2 |
| 6 | Zone yüksekliği | ATR + alarm TF zone geometrisi | `◇ bölge 1,0 kat · %68 (858)` | kova n | Soru 4 |
| 7 | Hacim çeyreği | rvol alt/üst uçta (≈Q1 / ≈Q4) | `◇ hacim yüksekken %61 sürdü` | kova n | Hacim tablosu |

### Aile ayrımı (2026-10-22 kararı)

Aynı kartta **iki farklı yüzde** görmek okumayı bozuyordu: "%76 kırılım tuttu"
(formasyonun sonucu) ile "%75 devam etti" (MS olayının devamı) ayrı soruların
cevabıdır; yan yana gelince hangisinin neyin ölçüsü olduğu anlaşılmıyordu.
Bu yüzden her alarm yalnız kendi ailesini basar:

| Aile | Basılan ölçüm | Tipik satır |
|---|---|---|
| `FRM` | `uyum` · `retest` · `temel` · `hareket` | `◇ 32321 formasyon · %76 tuttu` |
| `MS` | `ms` | `◇ 1651 kırılımın %75'i sürdü` |
| `ZONE` | `zone` · `yukseklik` · `rvol` | `◇ 240484 temasta %65 tepki` |
| `""` (boş) | kısıtsız — eski davranış (geri dönüş yolu) | — |

### Beklenti hükmü (`TELEGRAM_KART_TAHMIN`, varsayılan KAPALI)

Ölçüm satırlarının **önüne** tek kelimelik bir hüküm eklenebilir:
`devam` · `tek kanıt` · `kararsız` · `yön kanıtı yok`. Hüküm bir yön tahmini
DEĞİLDİR: NET %95 GA 11 hücrenin 10'unda sıfırı içerdiği için "yukarı gider"
cümlesinin kanıtı yok. Hüküm yalnız "ölçümler aynı yöne mi bakıyor" sorusunu
cevaplar.

| Ölçüm | Taban | Eşik (puan) | Gerekçe (yayılım) |
|---|---|---|---|
| MS devamı | %65,5 | ±5,0 | 32 hücre %57,5–77,5 → yayılım 20, yarısı 10; muhafazakâr 5 |
| Hacim (rvol) | %65,5 | ±4,0 | Q1–Q4 farkı 9,2 (2h) · 9,1 (4h) |
| Bölge yüksekliği | %65,5 | ±3,0 | kova yayılımı %64,3–71,0 |
| Rol uyumu | %75,0 | ±5,0 | uyumlu/uyumsuz farkı 6,6 → eşiği GEÇMEZ (nötr) |
| Zone içi/dışı | %65,5 | ±2,0 | fark 1,1 → hiçbir zaman geçmez |

Kurallar:

* `n < 300` hücre hükme **girmez** (gürültü) — bölge ≥2 kat kovası (n=162) bu
  yüzden tek başına hüküm üretmez.
* Rol uyumu tabanı formasyon ailesinindir (%75,0), dokunuş tabanı (%65,5)
  değil: aksi hâlde 79,7 − 65,5 = +14,2 ile yapay "güçlü lehte" çıkardı.
* Hüküm satırı + sayaç satırı ölçüm slotlarını yer; kart 3 satırı aşmaz
  (hüküm varsa en çok 1 ölçüm satırı kalır).
* **Yön kanıtı yoksa satır basılmaz** (boş satır yerine yokluk).
* Sıfat yok: gücü `◇ 2 ölçüm lehte · 1 aleyhte` sayacı söyler; `kararsız`
  durumunda aleyhte olanın **adı** yazılır.
* Varsayılan kapalı: `TELEGRAM_KART_TAHMIN=1` ile açılır (bir hafta izleme
  şartı — tasarım `TAHMIN_UYGULAMA_PLANI.md` §8).

### Nadir kademesi — `n < 300`

Tabanı 300'ün altında olan kesitte **oran basılmaz**: `◇ nadir (162) · yorum yok`.
Gerekçe: 162 gözlemde %71 ile %60 arasındaki fark GA95 içinde kalır (±7 puan);
kart onu "sonuç" gibi okutuyordu. Kullanıcı kararı (2026-10-22): *"nadir senaryo
yorum yapmak doğru olmaz yazılsın"*. Eşik tek yerde: `ampirik_referans.NADIR_ESIK`.

### Sade dil sözleşmesi (2026-10-22)

Kullanıcı: *"herkesin anlayabileceği format… teknik bilen biri bile
anlayamayabilir"*. Ölçüm satırında kısaltma yaşamaz:

| Önce | Sonra | Neden |
|---|---|---|
| `n1651` | `1651` | `n` etiketi tabanı gizemliyordu; düz sayı okunur |
| `BOS ↑dış devam %75` | `kırılımın %75'i sürdü` | kısaltma + ok; kesit adı düz Türkçe |
| `CHoCH` | `dönüşün` | tip bilgisi korunur, kısaltma kalkar |
| `retest oranı %35` | `geri çekilme %35` | jargon → günlük sözcük |
| `1,2 ATR` | `~1,05 TL · %2,6` | ATR bilmeden okunur (ATR varsa) |
| `bölge 1,4 ATR` | `bölge 1,4 kat` | "normalin katı" ifadesi |
| `yüksek RVOL` | `hacim yüksekken` | RVOL kısaltması kartta yok |
| `tamamlandı %76` | `%76 tuttu` | motorun `FORMASYON_TAMAMLANDI` hâli "hedefe ulaştı" DEĞİL, "kırılım teyit aldı ve bandın içine dönmedi" demek |
| `bar` | `mum` | aynı şey, herkesin bildiği sözcük |
| `FVG` / `OB` | `boşluk` / `blok` | kart yüzeyinde kısaltma yok |
| `◇ BOS …` benzeri sıfat | ölçü | `tipik`, `zayıf`, `güçlü`, `muhtemel` yasak (testli) |

Testler: `test_ampirik_referans.py::test_sade_dilde_kisaltma_yok`,
`::test_sade_dilde_sifat_yok`, `::test_tuttu_ifadesi_motorun_terminal_durumunu_dogru_anlatir`,
`test_kart_metin.py::test_kart_jargon_tasimaz`.

### Kaldırılan satır: `zone içi/dışı %76 / %77`

Eski satır iki grup arasındaki **1,1 puanlık** farkı basıyordu; kendi kanıt
eşiği (`KANIT_ESIKLERI["zone"]` = ±2 puan) hiçbir zaman geçmiyor, yani satır
kart yerini boşa harcıyordu. Yerine ölçülmüş dokunuş tepkisi geçti
(`◇ 240484 temasta %65 tepki`; aralık %65,0–66,5 → **alt uç** yazılır).

### Bilinçli yaklaşımlar (gizlenmiyor)

- **RVOL çeyreği yaklaşıktır.** Arşivde çeyrekler gözlem dağılımından kesildi;
  canlı `rvol` değeri çeyrek **ortalamasına en yakın** kovaya atanır. Kesin
  sınır canlı tarafta yeniden üretilemediği için `≈` yaklaşımı kullanılır ve
  yalnız ayrışan uçlar (Q1/Q4) basılır.
- **Zone yüksekliği kova tablosu 1d FVG ölçümüdür** (n=6285). Satır "tüm
  ailelerde geçerli" iddiası taşımaz; orta kovalarda nitelik etiketi yerine
  ölçülen yükseklik yazılır (`◇ bölge 1,0 kat · %68 (858)`).
- **Geri çekilme gördüyse satır basılmaz.** FRM-13 sonucu geri çekilme
  **derinliğine** bağlıdır; derinlik kartta ölçülmediği için sabit oran
  yanıltıcı olurdu.
- **MS tablosunda yön yoksa** kapsam×tip satırına düşülür (n daha büyük).

## 4. Raporlardan farkı

| | `docs/arastirma/*.md` | karttaki `◇` satırı |
|---|---|---|
| Amaç | soruyu kanıtlamak | olayı bağlama oturtmak |
| Kapsam | 704 seri, tüm kesitler | tek olay, tek kesit |
| Güvenlik | GA, çoklu test notları | n + "arşiv" ifadesi |
| Karar | kural önerisi | kural değil, referans |

Satır bir **iddia** değil **bağlam**dır: "%80 tamamlandı" cümlesi bu olayın
%80 kazanacağı anlamına gelmez; aynı tanımla ölçülen 15.724 olayın %79,7'sinin
tamamlandığını söyler. Maliyet, kayma, pozisyon ve çıkış kuralı yoktur.

## 5. Yeni bir ölçüm nasıl eklenir

1. Sayıyı `docs/arastirma/` tablosundan al; satır adını `KAYNAK_TABLOLARI`'na yaz.
2. `ampirik_referans.py` içinde tabloyu ekle (n + oran birlikte).
3. `_<ad>_satiri()` fonksiyonunu yaz: koşul yoksa `None` döndür.
4. `olcum_satirlari()` aday listesine ve `ONCELIK`'e ekle.
5. `test_ampirik_referans.py`'ye üç test ekle: **değer**, **koşulsuzluk**,
   **genişlik**. `n < 50` olan kesitler için satır yazılmaz.
6. Bu tabloya satır ekle.

## 6. Sınırlar

- Tek rejim penceresi (intraday 2025-05 → 2026-10); rejim değişiminde özellikle
  yön asimetrisi dönebilir. Satırlar bu yüzden "arşivde" ifadesiyle yazılır.
- Motor parametreleri değiştirilmedi (canlı "Dengeli" profili).
- Ölçümler 12 bar / ATR penceresindedir; 12 adet 1h bar ile 12 adet 1d bar aynı
  takvim süresi değildir.
- Kart satırı bir **olasılık** sunmaz: kalibrasyon, GA ve çoklu test düzeltmesi
  bu katmanın kapsamı dışındadır (raporlarda durur).
