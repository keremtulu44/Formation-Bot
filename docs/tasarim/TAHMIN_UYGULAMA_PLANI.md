# Beklenti katmanı — uygulama planı (2026-10-21)

> **Durum:** Plan. **Kod değişmedi.** Onaylanınca §6 sırasıyla yazılacak.
> **Bu turda düzeltilen:** hükmün sonundaki `zayıf` kaldırıldı.

---

## 0 · "Zayıf" neden yanlıştı, yerine ne geliyor

`BEKLENTİ: devam · zayıf` üç şeyi aynı anda iddia ediyordu: yön (devam),
gücü (zayıf), ve güvenilirliği (belirsiz). Kartın geri kalanı sayıyla
konuşurken son satır sıfata düşüyordu — **ölçülebilir olmayan bir kelime.**

Yeni sözleşme: **hüküm tek kelime, gücü sayı söyler.**

```
◇ beklenti: kararsız
◇ 1 lehte · 1 aleyhte
```

`zayıf`, `güçlü`, `muhtemel`, `yüksek ihtimal` → kartta **yasak** (test ile korunur).
Hükmün alabileceği **4 değer** var, beşincisi yok:

| Hüküm | Anlamı |
|---|---|
| `devam` | en az 2 ölçüm lehte, aleyhte yok |
| `tek kanıt` | 1 ölçüm lehte, aleyhte yok |
| `kararsız` | en az 1 lehte + en az 1 aleyhte |
| `yön kanıtı yok` | lehte ölçüm yok (aleyhte olsa da bu hüküm) |

---

## 1 · Eşik: "zayıf/güçlü" sıfatının yerini alan tek kural

Sıfat uydurmak yerine **her ölçümün kendi yayılımının yarısı** eşik alınır.
Etki bu eşiğin altındaysa **nötr** sayılır ve hükme girmez — "%4 fark var ama
kanıtlanmadı" gibi cümleler böylece kendiliğinden eleniyor.

| Ölçüm | Taban | Eşik | Gerekçe (yayılım) |
|---|---|---|---|
| MS devam | dokunuş tabanı **%65,5** | **±5,0 puan** | 32 hücre %57,5–77,5 → yayılım 20, yarısı 10; muhafazakâr 5 |
| Hacim (RVOL) çeyreği | aynı taban | **±4,0 puan** | Q1–Q4 farkı 9,2 (2h) · 9,1 (4h) |
| Bölge yüksekliği | aynı taban | **±3,0 puan** | kova yayılımı %64,3–71,0 |
| Rol uyumu | aynı taban | **±5,0 puan** | uyumlu/uyumsuz farkı 6,6 |
| Zone içi/dışı | aynı taban | **±2,0 puan** | fark 1,1 → **hiçbir zaman geçmez** |

Son satır önemli: `zone içi %75,9` vs `zone dışı %77,0` farkı **1,1 puan**.
Eşiği geçmediği için bu ölçüm hükme **hiç girmez** — "zone içinde olmak kötü"
gibi bir cümle kurulamaz. Eski tasarımda bu satır kartta duruyordu; artık nötr.

**Ek kural:** `n < 300` olan hücre hükme girmez (gürültü). Ör. 1d DIS CHOCH ↑ n308
sınırda kalır, kullanılırsa "sınırda" olarak işaretlenir.

---

## 2 · Kuru çalıştırma — gerçek tablo değerleriyle 5 senaryo

Kod yazmadan, mevcut `ampirik_referans` sabitleriyle hükmü hesapladım:

| Senaryo | Ölçümler (puan) | Hüküm | Kart satırı |
|---|---|---|---|
| **A** SISE 4s ↑ dış BOS | MS %75,0 (**+9,5**), hacim Q1 %70,1 (+4,6), bölge 1,4 kat %67,8 (+2,3), rol %79,7 (+4,7) | **devam** | `◇ beklenti: devam` / `◇ 2 lehte` |
| **B** THYAO 4s ↓ dış BOS | MS %67,3 (+1,8), hacim Q4 %61,0 (**−4,5**), bölge 1,1 kat (+2,3), rol (+4,7) | **yön kanıtı yok** | `◇ beklenti: yön kanıtı yok` / `◇ 1 aleyhte` |
| **C** GARAN 1s, MS yok | rol %79,7 (+4,7) | **yön kanıtı yok** | `◇ beklenti: yön kanıtı yok` |
| **D** AKBNK 1g ↑ dış BOS | MS %77,5 (**+12,0**), hacim Q1 %63,9 (−1,6), bölge 0,3 kat (−1,2) | **tek kanıt** | `◇ beklenti: tek kanıt` / `◇ 1 lehte` |
| **E** ASELS 1g ↑ dış BOS | MS %77,5 (+12,0), hacim (−1,6), rol (+4,7) | **tek kanıt** | `◇ beklenti: tek kanıt` / `◇ 1 lehte` |

**Beklenmedik ama doğru sonuç:** senin örnek senaryon (B) `devam` değil,
**`yön kanıtı yok`** çıkıyor. Çünkü 4h dış BOS ↓ %67,3 — dokunuş tabanı %65,5'ten
yalnızca 1,8 puan yüksek. Bu fark gürültü. Kart "devam" demek yerine susuyor.

**Neden bu iyi:** eski tasarım burada `devam · zayıf` diyordu — yani hem
kanıtlanmamış bir yön iddiası hem de ölçülmemiş bir sıfat. Yeni tasarım
"kanıtım yok" diyor. Bu, ürünün en dürüst cümlesi.

**Hangi alarmda `devam` çıkar?** 32 MS hücresinden yalnız 11'i eşiği geçiyor
ve bunların **10'u yukarı yönlü**:

| Hücre | % | puan | n |
|---|---|---|---|
| 1d dış BOS ↑ | 77,5 | +12,0 | 873 |
| 1d iç BOS ↑ | 76,1 | +10,6 | 1569 |
| 4h dış BOS ↑ | 75,0 | +9,5 | 1651 |
| 1d dış CHOCH ↑ | 72,7 | +7,2 | 308 |
| 4h dış CHOCH ↓ | 70,9 | +5,4 | 650 |

Dikkat: `4h dış CHOCH ↓` de eşiği geçiyor. Yani "aşağı yön hep zayıf" **doğru
değil** — ayrım kapsam (dış) ve tip (CHOCH) ile değişiyor. Kart bunu tek tek
gösterecek, genel kural uydurmayacak.

---

## 3 · Kartta nasıl durur (3 satır tavanı)

Sıra sabit: **hüküm → sayaç → ufuk**. Üçüncü satır yoksa kart kısalır.

```
◇ beklenti: devam
◇ 2 lehte
◇ tepe 2,8 · ters 1,9 kat
```

Çelişkide:

```
◇ beklenti: kararsız
◇ 1 lehte · 1 aleyhte
◇ tipik ömür 90 mum
```

Hüküm `yön kanıtı yok` ise sayaç satırı yalnız aleyhte varsa basılır; **ufuk ve
büyüklük yine basılır** (onlar yön iddiası taşımıyor).

Ölçülen genişlikler: `◇ beklenti: yön kanıtı yok` **203,5 px** · `◇ 1 lehte · 1 aleyhte`
**163 px** · `◇ tipik ömür 90 mum` **168,5 px** · `◇ devam ederse tipik 2,5 kat`
**232 px** — hepsi 262,8 px bütçesinin altında.

**Büyüklük satırı (`tepe/tip ters`)** — kaynak: `ort_devam_h12` + `ort_ters_h12`.
İkisi de 12 mumluk **tepe** ölçüsüdür, kapanış değildir. Kural: `net = lehe − ters`;
`net < 0,30 ATR` ise satır **basılmaz**. 32 MS hücresinde bu eşiği 15 hücre geçiyor
ve geçenlerin 15'i de ↑ kırılım; ↓ kırılımların 16'sında net ortalaması **−0,05**.
Ayrıntı: `TAHMIN_KATMANI.md` Ek A.

**Ufuk satırı kaynağı** (bu tablo `ampirik_referans`'ta henüz yok, eklenecek):

| Aile | TF | ort. ömür (mum) | n |
|---|---|---|---|
| OB | 1s | 89,8 | 59130 |
| OB | 4s | 47,1 | 22916 |
| OB | 1g | 32,5 | 13549 |
| FVG | 2s | 5,7 | 27910 |
| FVG | 4s | 5,2 | 18594 |
| FVG | 1g | 5,4 | 8641 |

Kaynak: `ARASTIRMA_BULGULARI.md` Soru 2 (`ort_omur_bar` sütunu). Bu tablo
kartta `◇ tipik ömür 5 mum` olarak çıkar — FVG'nin "tek kullanımlık" olması
artık ölçüyle görünür.

---

## 4 · Kod planı — dosya dosya

| # | Dosya | Değişiklik | ~satır |
|---|---|---|---|
| 1 | `ampirik_referans.py` | `ZONE_OMUR` tablosu · `KANIT_ESIKLERI` · `Kanit` dataclass · `beklenti(k)` · `beklenti_satirlari(k, azami=3)` | +140 |
| 2 | `ampirik_referans.py` | `Kurulum`'a `aile: str \| None` alanı (yükseklik tablosu 1d FVG, ömür tablosu aile×TF — ikisi de aile istiyor) | +1 |
| 3 | `notification_context.py` | `olcum_bolumu(...)` → `aile=` geçir; `domain_bolumleri`'ne `beklenti: bool = False` | +15 |
| 4 | `notifier.py` | sade kartta `olcum[:2]` → `olcum[:3]`, beklenti satırları önce | +6 |
| 5 | `main.py` | `/tara` çıktısında tam 1-2-3 bloğu (hüküm + tüm lehte/aleyhte + ufuk + büyüklük) | +25 |
| 6 | `config.py` | `TELEGRAM_KART_BEKLENTI` (varsayılan **kapalı**) | +4 |

**İmza:**

```python
def beklenti(k: Kurulum) -> dict:
    """Kurulumun yön beklentisi — sıfat yok, sayaç var.

    Dönüş: {"hukum": "devam"|"tek_kanit"|"kararsiz"|"kanit_yok",
            "lehte": [{"ad","deger","puan","n","kaynak"}],
            "aleyhte": [...],
            "notr": [...],
            "ufuk": {"mum": 90, "n": 59130, "aile": "OB", "tf": "1h"} | None,
            "buyukluk_atr": 2.5 | None}
    """
```

**Tasarım kuralı:** `beklenti()` **hiçbir yeni sayı uydurmaz.** Bütün değerler
`MS_YON`, `RVOL_KOVALARI`, `YUKSEKLIK_KOVALARI`, `FRM_UYUM` tablolarından gelir;
yalnız `ZONE_OMUR` yeni tablo olarak eklenir (yukarıdaki 6 satır, kaynağı belli).

---

## 5 · Test planı (yazılacak testler)

| Test | Neyi korur |
|---|---|
| `test_hukum_kumesi_kapali` | Dönen hüküm yalnız 4 değerden biri; başka değer üretilemez |
| `test_sifat_yasak` | Kart/`/tara` çıktısında `zayıf`, `güçlü`, `muhtemel`, `ihtimal`, `bekleniyor` geçemez |
| `test_zayif_arti_devam_yok` | `devam · zayıf` gibi iki kelimeli hüküm üretilemez (regresyon) |
| `test_esik_alti_notr` | `%67,3` (4h dış BOS ↓) → nötr; hüküm `kanit_yok` |
| `test_esik_ustu_lehte` | `%75,0` (4h dış BOS ↑) + hacim Q1 → `devam` |
| `test_celiski_kararsiz` | 1 lehte + 1 aleyhte → `kararsiz` ve sayaç `1 lehte · 1 aleyhte` |
| `test_zone_ici_hic_girmez` | zone içi/dışı farkı 1,1 → hiçbir hükümde görünmez |
| `test_n300_alti_girmez` | n<300 hücre hükme girmez |
| `test_ufuk_tablosu_kaynakli` | Ömür satırı yalnız `ZONE_OMUR`'da olan (aile, TF) için basılır |
| `test_tepe_ters_cifti` | Büyüklük satırı ya iki tarafı da yazar ya hiç basılmaz; tek başına sayı çıkmaz |
| `test_buyukluk_net_esigi` | `net < 0,30` → satır yok (4h dış BOS ↓ regresyonu) |
| `test_tepe_kelimesi_zorunlu` | Büyüklük satırında `devam`/`tipik` değil `tepe` geçer |
| `test_kart_3_satir_tavan` | Beklenti en fazla 3 satır, kart toplamı ≤ 20 |
| `test_metin_butcesi` | Her satır `telegram_measure.genislik()` ≤ 262 px |
| `test_kanit_yoksa_yon_yok` | Lehte ölçüm yoksa hiçbir satırda `%` oranı ile yön iması olmaz |
| `test_geri_donus_anahtari` | `TELEGRAM_KART_BEKLENTI=0` → eski metin bayt bayt aynı |

---

## 6 · Uygulama sırası

| Adım | İş | Çıktı | Süre |
|---|---|---|---|
| 1 | `ZONE_OMUR` + `KANIT_ESIKLERI` + `Kanit` | veri katmanı, testlerle | ~1 saat |
| 2 | `beklenti()` + 4 hüküm | saf fonksiyon, 12 test | ~2 saat |
| 3 | `beklenti_satirlari()` + px denetimi | kart metni | ~1 saat |
| 4 | `Kurulum.aile` + `notification_context` geçişi | bağlama | ~1 saat |
| 5 | `notifier` kart sırası (3 satır) | canlı kart | ~1 saat |
| 6 | `/tara` tam 1-2-3 | komut çıktısı | ~1 saat |
| 7 | tam paket + `git diff --check` | regresyon | ~30 dk |

Toplam: **~7,5 saat**, tek oturumda bitiyor. Her adım kendi testiyle kapanır;
2. adımdan sonra fonksiyon tek başına doğrulanabilir (kart olmadan).

---

## 7 · Risk ve geri alma

| Risk | Karşılık |
|---|---|
| Kullanıcı `yön kanıtı yok`'u "bozuk" sanır | `/durum` ve `/olcum`'da açıklama: "kanıt yok = ölçüm eşiği geçmedi, veri eksik değil" |
| Sayaç satırı kartı şişirir | 3 satır tavanı + px testi; taşarsa sayaç satırı düşer, hüküm kalır |
| Yeni ömür tablosu yanlış eşleşir | `aile` + `tf` anahtarı zorunlu; eksikse satır yok |
| Rejim değişir, eşikler kayar | `OLCUM_SURUMU` tek yerde; tablo güncellenince tüm çıktı döner |

**Geri alma:** `TELEGRAM_KART_BEKLENTI=0` (varsayılan) → hiçbir şey değişmez.
Açıldıktan sonra sorun çıkarsa tek satırlık env ile eski karta dönülür.

---

## 8 · Onayına ihtiyacım olan 3 şey

1. **Hüküm kelimeleri:** `devam` / `tek kanıt` / `kararsız` / `yön kanıtı yok`.
   `tek kanıt` yerine `sınırlı kanıt` mı olsun? (`tek kanıt` daha kısa, 163 px)
2. **Sayaç satırı:** `◇ 1 lehte · 1 aleyhte` (163 px) mi, `◇ 1 ölçüm lehte · 1 aleyhte`
   (216 px) mi? İkincisi daha açık ama kartta yer yiyor.
3. **Varsayılan kapalı mı açık mı?** Önerim: **kapalı** yaz, sen DM'de açıp 1 hafta
   izle, sonra public'e aç.

---

## 9 · Bu planın söylemediği şey

- Bu katman **kâr tahmini değil**; `%75` = "1651 olayın %75'i devam etti".
- Yön iddiası yalnız ölçüm eşiği geçtiğinde kurulur; çoğu alarmda kurulmaz.
- Hedef fiyat, stop, pozisyon, kaldıraç: yok.
- 12 bar / ATR penceresi sabit; farklı ufuk ölçülmedi.
- Tek rejim penceresi (2025-05 → 2026-10); rejim değişirse sayılar döner.
