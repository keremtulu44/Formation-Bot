# FORMASYON TARAFI — "şu olursa şu olur" kuralları neden kurulamıyor

> **Durum:** Ölçüm · **Tarih:** 2026-11-19 · **Canlıya etkisi: YOK**
> **Veri:** 352 seri, 177.723 tetik + 86.496 taban (`var/replay/da_pol`)
> **Yeni replay koşulmadı** — diskteki satırlar yeniden kesildi.

---

## 1 · Önce senin tespitin doğru mu?

> "formasyonda retest kırılım vs olunca bildiriyor, bunlar da genelde olan olmuş oluyor"

**Doğru. Ve sebebi şu ölçüde:**

| | oran |
|---|---:|
| Kırılım/retest tetiğinden sonra 12 barda **1 ATR'lik tepki bitmiş** | **%60,6** |
| Tepki **hiç 12 barı doldurmadan** (ilk 3 barda) bitmiş | %19,3 |
| Tepkinin **medyan tamamlanma barı** | **19. bar** |

Yani alarm "kırılım oldu" dediğinde, hareketin **yarısından fazlası zaten
geride**. Senin gördüğün tam olarak bu: **olay, olayı bildiren mesajdan önce
oluyor.** Bu bir his değil, ölçü.

---

## 2 · Asıl soru: formasyon tarafında "şu olursa şu olur" var mı?

Kural aramak için doğru ölçü şu: **"önce hedefe mi varıyor, stopu mu yiyor?"**
(12 bar içinde +2 ATR, −1 ATR'den önce — ve aleyhte 1 ATR hiç görülmemiş.)

| hedef : stop | taban | tetikler | en iyi koşul | başabaş | sonuç |
|---|---:|---:|---:|---:|---|
| 1 : 1 | %33,7 | %35,8 | %35,6 | %50,0 | **ZARAR** |
| 1,5 : 1 | %29,9 | %32,5 | %33,0 | %40,0 | **ZARAR** |
| 2 : 1 | %24,9 | %27,7 | %29,0 | %33,3 | **ZARAR** |
| 3 : 1 | %15,5 | %17,9 | %19,6 | %25,0 | **ZARAR** |

**Hiçbir hedef/stop oranında başabaş yakalanmıyor.** En iyi koşul (%29,0),
gereken %33,3'ün altında. 40 bar ufkunda da aynı: 2:1'de taban %31,1, en iyi
koşul %33,3, başabaş %33,3 — **tam sınırda, kâr yok.**

> **Hüküm:** Bu veride "OB şu olursa şu olur" diye **kâr üreten** bir koşul yok.
> Sadece "oynaklık biraz daha yüksek" diyen koşullar var. Fark 1–4 pp.

---

## 3 · Peki ne var? — 3 tane gerçek, kullanılabilir şey

Kâr üretmiyor ama **yanlış alarmı azaltıyor** ve **beklentiyi doğru kuruyor**:

### (a) Tek gerçek öncü: **koşu hızı** — +6 pp
Tetikten önceki 6 barda **≥2 ATR koşmuşsa** hareket olasılığı %69,6 (taban %63,7).
Diğer tüm koşullar ≤ +2,6 pp. Yani "hacim patladı", "sıkışma genişledi" gibi
şeyler değil, **fiyatın kendisi koşuyorsa** sonrası daha hareketli.

Ama aynı koşul, "önce +2 ATR" ölçüsünde **kayboluyor** (+1,0 pp). Yani koşu,
*oynaklığı* artırıyor, *kazanma şansını* artırmıyor.

### (b) En iyi kombinasyon: **hacim canlı (≥1,3×) + OB bölgesi** → %29,0 (n=14.180)
Taban %24,9. Fark +4,1 pp. Tek başına en iyi koşul. Ama %33,3 başabaşın altında.

### (c) Ters yönde kullanılabilir: **sıkışma genişliyor + hacim patlaması**
| koşul | oran |
|---|---:|
| sıkışma ≥1 + rvol ≥2 | %23,2 |
| sıkışma ≥1 + HACIM kanalı | %23,1 |
| **taban** | **%24,9** |

Yani **"sıkışma genişliyor" alarmı, tabandan daha kötü.** Alarm olarak
kullanılmaması gereken tek formasyon durumu bu. (Bugün canlıda tam tersi
varsayılıyor: sıkışma güçleniyor → önemli.)

---

## 4 · Formasyonu "daha dengeli" tutmak ne demek — 4 kural

Senin istediğin denge şu 4 şeyle ölçülür. Hepsi bugün **tek yönlü**:

| denge ekseni | bugün | ölçümün söylediği |
|---|---|---|
| **Zamanlama** | tetiklenince bildir (geç) | tepkinin %60'ı ilk 12 barda bitiyor → **tetikten önce** ölç (koşu, sıkışma, uzaklık) |
| **Yön** | "kırılım" → tek yön ima | devam %34 altında; hedef/stop tüm oranlarda zararda → **iki yön** |
| **State** | 14 state'in hepsi "olay" gibi sunuluyor | en iyi/kötü state arası **0,27 ATR** — state'ler neredeyse aynı |
| **Sayı** | her state için kart | state ayırt etmiyorsa **state'e kart basmak gereksiz** |

**Somut sonuç:** 14 formasyon state'inin 12 barda tepki oranı **%56,5–%68,6**
arasında. Aralık **12 pp**, ve bu aralık 3.000+ örneklemle bile **tesadüf
olabilir** (84 segment denendi → Bonferroni eşiği |z|>3,2). Yani:

> **Formasyon state'i alarm üretmek için yeterli bir ayrıştırıcı değil.**
> `RETEST_BEKLENIYOR` (%68,6) ile `SIKISMA_GUCLENIYOR` (%65,3) arasında
> 3,3 pp var — aynı sembolde art arda gelen iki mesajın **farklı şey
> söylediğini iddia etmek** bu sayıyla savunulamaz.

---

## 5 · O zaman formasyon tarafında ne yapmalı — net cevap

**Kâr kuralı aramayı bırak.** Veri onu desteklemiyor; 4 hedef/stop oranının
4'ü de zararda. Bulunursa da büyük ihtimalle aşırı uydurma olur.

**Onun yerine 3 şey yap:**

1. **Birimi değiştir.** Kart "kırılım oldu" yerine **"12 bar medyan aralık
   4,7 ATR (taban aynı)"** desin. Bu bilgi **doğru** (ölçüldü) ve **kullanılabilir**:
   stop/hedef koyarken 4,7 ATR'lik oynaklığı hesaba katarsın. Bugünkü kart bunu
   söylemiyor.
2. **Geç kalmayı kabul et ve söyle.** Kartın ilk satırı **"hareketin %60'ı
   geçti"** olsun. Bu, kullanıcıyı yanlış beklemekten korur — ki senin şikâyetin
   tam buydu.
3. **Kart sayısını state'e göre değil, nadirliğe göre belirle.** State'ler
   ayrışmıyor (0,27 ATR); nadirlik ayrışıyor (en iyi koşul n=14.180, tüm
   tetikler n=177.723).

---

## 6 · Dürüst sınırlar

- **Kâr ölçüsü basit:** hedef/stop eşit zaman penceresinde, komisyonsuz, kayma
  yok. Gerçek işlem maliyeti eklense oranlar **daha da kötüleşir**.
- **"Önce vardı" ölçümü 12 ve 40 bar**: aynı barda hem hedefin hem stopun
  görüldüğü durumlar **stop sayıldı** (kötümser). Gerçek sıra bilinmiyor —
  bu, sonuçları **iyimser** gösteriyor olabilir.
- **`bagl_uzaklik_atr` sütunu bu koşuda boş** — "fiyat seviyeye ne kadar uzak"
  kırılımı yapılamadı. Oysa R37'nin `dist_atr < 0` bulgusu (çöküş tarafı +1,5
  puan) bu sütuna dayanıyordu. **Tekrar ölçülmesi gereken tek şey bu.**
- **Kâr kuralı yok** demek, "hiçbir koşulda yok" demek değil: **bu ölçü
  setinde ve bu 352 seride** yok.
