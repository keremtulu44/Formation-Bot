# Tahmin katmanı — "1 · 2 · 3" şablonu (2026-10-21 · tasarım)

> **Durum:** Tasarım önizlemesi. **Kod değişmedi.**
> **Kısa cevap:** Evet yapılabilir — ama **yön tahmini** olarak değil, **ölçülmüş
> beklenti** olarak. Aradaki fark bu belgenin tamamı.

---

## 1 · Neden "yukarı/aşağı gider" diyemiyoruz

Üç ölçüm bunu kapatıyor:

| Ölçüm | Sonuç | Anlamı |
|---|---|---|
| MFE vs MAE (11 hücre) | ikisi de ≈ **2,0 ATR** | hareket var, **yön yok** |
| NET %95 GA | 11 hücrenin **10'unda sıfırı içeriyor** | yön avantajı istatistiksel olarak gösterilemedi |
| Tek istisna | FRM 2h NET 0,1835 [0,0262, 0,3475] | tek hücre; geçerli-n payı **%49,7** |

Yani "kırılım aşağı oldu → aşağı devam eder" cümlesi, elimizdeki veriyle
**kanıtlanmış bir cümle değil**. Ama şu üçü kanıtlı:

1. **Ne kadar oynayacağı** (≈2 ATR) — güçlü kanıt
2. **Ne kadar süreceği** (OB ~90 mum, FVG ~5 mum) — orta kanıt
3. **Hangi koşulda devam eğiliminin arttığı** (MS, zone yüksekliği, hacim) — orta kanıt

Bu yüzden tahmin katmanı **yön vaadi vermez**; "bu kurulum geçmişte nasıl bitti"
der ve **çelişkiyi** gösterir.

---

## 2 · Şablon

Üç blok, sabit sıra, her biri **tek soruya** cevap:

```
1 · NE OLDU        → sistem ne dedi (kanıt: canlı veri)
2 · GEÇMİŞTE NASIL  → bu kuruluma en yakın ölçüm (kanıt: kayıt sayısı + oran)
3 · BURADA FARKLI   → canlı sapma: güçlendiren / zayıflatan
    ↓
   BEKLENTİ        → devam · zayıf · kararsız · kanıt yok
```

Kural: **3. blok boşsa beklenti yazılmaz.** Sapma yoksa "sıradan bir kurulum"
demektir; sıradan kurulumda taban oran tek başına konuşur.

---

## 3 · Üç ayrı iddia — karıştırılmaması gereken şey

Tahmin tek cümle değil; **üç ayrı iddia**. Her birinin kanıtı farklı güçte:

| İddia | Ölçüm | n | Güç |
|---|---|---|---|
| **Yön** | MS dış BOS devam %71,0 (↑ %75,0 / ↓ %67,3) | 3387 | **B** — NET 0 olduğu için "kâr" değil "yapı devamı" |
| **Süre** | OB 1h medyan ömür 90 mum · FVG tam dolum %40 | 59130 | **A** — tek ölçüm, geniş n |
| **Büyüklük** | tepki ≈ 2,4 ATR (MS devam) · dokunuş ≥1 ATR %65 | 240484 | **A** — en sağlam |

**A** = kartta basılır · **B** = basılır, "kanıt sınırlı" tonunda · **C** = basılmaz.

---

## 4 · Karar tablosu (uygulanacak kurallar)

Her satır ölçülmüş bir ilişki; hiçbiri sezgi değil.

| # | Koşul (canlı) | Ölçüm | Etki | Güç |
|---|---|---|---|---|
| 1 | MS **dış** BOS, kırılım yönü ↑ | %75,0 devam · 2,827 ATR | **+ güçlü** | B |
| 2 | MS **dış** BOS, ↓ | %67,3 · 2,189 ATR | + zayıf | B |
| 3 | MS **iç** BOS | %68,2 (6505) | + zayıf | B |
| 4 | MS yok / ölçülmedi | — | **yön iddiası yok** | — |
| 5 | Önündeki zone ≥2 ATR | CALISTI %71,0 · decay 1,248 | + kısa ufuk | A |
| 6 | Önündeki zone <0,5 ATR | %64,3 · decay 2,418 | − hareket geç gelir | A |
| 7 | Zone **3+ temas** | tepki 1,94 ATR (GA üst üste) | − hafif, **kanıt zayıf** | C→yazılmaz |
| 8 | Zone **1. temas** | 2,02 ATR | nötr | B |
| 9 | RVOL **Q4** (yüksek) | CALISTI %61,0 vs %70,1 | **− 9 puan** | A |
| 10 | RVOL **Q1** (düşük) | %70,1 | **+ 9 puan** | A |
| 11 | FVG'de "kaçıncı temas" | 3+ temas yalnız **4 adet** | **satır yok** | — |
| 12 | FVG tam dolum riski | %40,3 · superseded %16,6 | erken bitme uyarısı | A |
| 13 | OB 1d iptal | %82,8 | erken bitme uyarısı | A |
| 14 | Zone geçilme (her durumda) | %85,4–93,6 | **bariyer sayılmaz** | A |

---

## 5 · Çelişki kuralı — "kararsız" da bir cevaptır

| Destek | Çelişki | Hüküm |
|---|---|---|
| ≥2 | 0 | `devam` |
| ≥1 | 1 | `devam · zayıf` |
| herhangi | **≥2** | `kararsız` — çelişen ölçümler **adıyla** yazılır |
| MS yok | — | `yön kanıtı yok` (sayı basılmaz) |

**Neden puan yok:** ölçümler bağımsız değil (aynı mumlardan türüyor). 0–100 puan
üç kez aynı kanıtı sayıp sahte güven üretir. Bu yüzden **sayaç**: kaç destek,
kaç çelişki — ve çelişkinin adı.

---

## 6 · Örnek 1 — senin verdiğin senaryo

> "Kırılım teyitli, önünde blok var, aşağı yönde kırılım, BOS olmuş."

```
1 · NE OLDU
▼ THYAO 4s AŞAĞI TEYİTLİ
Alçalan Üçgen — kapanışla
🕒 21 Ekim 13:30→17:30 mumu
· kapanış 288,50 · sınır 289,75
▼ aşağıda blok 284,00 — %1,6
◈ yön aşağı · dış kırılım (BOS)

2 · GEÇMİŞTE NASIL BİTTİ
◇ geçmişte %67 devam (3387)
◇ %10 devam etmedi · %1 ters
◇ devam ederse tipik 2,2 kat

3 · BURADA FARKLI
◇ 3. temas → tepki 1,94 kat
◇ hacim 2,8 kat → %61'e düşer

BEKLENTİ: devam · zayıf
```

**Türkçe okunuşu:** Yapı aşağı yönde ve dış kırılım var — geçmişte bu kurulumun
%67'si devam etmiş, %10'u devam etmemiş, %1'i ters dönmüş. Devam ettiğinde
tipik hareket normalin 2,2 katı. Ama iki şey bunu zayıflatıyor: blok zaten 3 kez
test edilmiş (tepki ortalaması 1,94'e iniyor) ve hacim normalin 2,8 katı —
yüksek hacimde devam oranı %70'ten %61'e düşüyor.

**Kritik cümle:** "devam eder" değil, "**geçmişte %67 devam etmiş; burada iki ölçüm
bunu zayıflatıyor**". Aradaki fark, tavsiye ile ölçüm arasındaki fark.

---

## 7 · Örnek 2 — "çok temas = sıkışık" iddiasının ölçülmüş hâli

Senin ikinci cümlen: *"OB'ye göre birçok temasla geçilmiş, o bölgede biraz
sıkışık, aşağı yönün gelmesi ya da kırılımın erken bitmesi."*

Bu cümlenin **iki parçası var; biri veriyle uyuşmuyor, biri uyuşuyor.**

**(a) "Çok temas = sıkışık bölge" — veri bunu desteklemiyor:**

| Ölçüm | Sonuç |
|---|---|
| Zone'ların geçilme oranı | **%85,4–93,6** (temas sayısından bağımsız olarak yüksek) |
| 3+ temaslı OB zone oranı | %12,9 (17048 zone) — **azınlık**, kural değil |
| Temas arttıkça tepki | 2,02 → 1,94 ATR (**%4 düşüş**) |
| Bu farkın GA'sı | **üst üste biniyor** → kanıtlanmadı |

Yani "çok temaslı bölge sıkışıktır, aşağı gelir" cümlesi kartta **basılmaz**.
Basılabilecek hâli: *"blok 3. kez test ediliyor — tepki ortalaması 1,94'e inmiş,
ama fark istatistiksel olarak kanıtlanmadı."*

**(b) "Kırılım erken bitebilir" — bu ölçülü ve doğru:**

| Aile | Erken bitme göstergesi | n |
|---|---|---|
| FVG 2h | tam dolum **%40,3** · yerine yeni yapı **%16,6** · aktif kalan **%0,3** | 27910 |
| OB 1d | iptal **%82,8** · boşlukla atlama **%2,9** · aktif **%14,6** | 13549 |

Bu, kartın en değerli uyarısı olabilir: **"bu yapı tipik olarak 5 mum içinde
tükenir; kırılımın ilk 2-3 mumu kritik."**

---

## 8 · Kartta nasıl görünür — 3 satır, bütçe aynı

Beklenti bloğu, mevcut 3 `◇` satırının **ikisini yer**, böylece kart 20 satırda kalır:

```
◇ bölge normalin 1,4 katı
◇ beklenti: devam · zayıf
◇ geçmişte %67 devam (3387)
```

veya çelişkili durumda:

```
◇ beklenti: kararsız
◇ çelişki: hacim 2,8 kat
```

Yön kanıtı yoksa **hiç basılmaz** (boş satır yerine yokluk):

```
◇ bölge normalin 1,4 katı
◇ kırılım sürdü %75 · 1651 kayıt
◇ direnç→destek %80 · 15724
```

`/tara` çıktısında tam hâli (1-2-3 + okunuş) görünür.

---

## 9 · Neyi **yapmayacağız** (bu katmanın sınırı)

| Yapılmayacak | Neden |
|---|---|
| "yukarı gider / aşağı gelir" | NET ≈ 0, yön avantajı kanıtsız |
| "hedef 45,20" | ölçülmüş bir hedef yok; MFE dağılımı 2,0–2,4 ATR ama yön yok |
| 0–100 güven puanı | ölçümler bağımsız değil, puan sahte kesinlik üretir |
| "sıkışık bölge" yorumu | ölçüm desteklemiyor (§7a) |
| temas sayısı (FVG'de) | 3+ temas yalnız 4 adet |
| 50 kayıttan az kesit | örneklem yetersiz |
| formasyon bayrak/flama genellemesi | n < 50 |

---

## 10 · Uygulama sırası

| Adım | İş | Nerede |
|---|---|---|
| 1 | `beklenti()` fonksiyonu: 14 kural → destek/çelişki listesi → hüküm | `ampirik_referans.py` |
| 2 | Kuralların sabitleri tek dosyada, her biri **kaynak + n** ile | `ampirik_referans.py` |
| 3 | Kart satırları (3 satır, mevcut `◇` slotlarına) | `notifier.py` |
| 4 | `/tara` tam çıktısı (1-2-3 + okunuş) | `main.py` |
| 5 | Testler: her kural için sınır durumu, çelişki sayacı, "kanıt yok" hâli | `test_ampirik_referans.py` |
| 6 | Geri dönüş anahtarı: `TELEGRAM_KART_TAHMIN=kapali` | `config.py` |

**Adım 1'in imzası (öneri):**

```python
beklenti(olay, ms, zone, hacim) -> {
    "hukum": "devam" | "zayif" | "kararsiz" | "kanit_yok",
    "destek": [{"ad": "dış BOS ↑", "oran": 75.0, "n": 3387}],
    "celiski": [{"ad": "hacim Q4", "etki": -9.0, "n": 11928}],
    "ufuk": "kisa" | "orta" | "uzun",
    "buyukluk_atr": 2.4,
}
```

Kart bu sözlükten **en fazla 3 satır** basar; `/tara` hepsini basar.

---

## 11 · Dürüst uyarı

Bu katman eklendiğinde kullanıcıların **en çok yanlış anlayacağı** şey şu olacak:
`◇ geçmişte %71 devam (3387)` satırını "bu alarm %71 kazanç" diye okumak.

Bu yüzden her beklenti hükmünün yanında **sabit bir dipnot** durmalı:
`· geçmiş davranış, kazanç değil` (249 px · tek satır, kart altında).

Ve hüküm kelimesi `beklenti` olmalı — `tahmin`, `sinyal`, `fırsat` değil.
"Tahmin" kelimesi vaat gibi okunur; "beklenti" ölçüm gibi okunur.
