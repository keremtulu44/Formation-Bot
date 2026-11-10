# Faz 7 — Zaman Stopu (H) Testi — Koşudan Önce Tescil

**Tarih:** 2026-11-10 · **Durum:** tescilli (Faz6 holdout koşusundan SONRA,
kapı A/B'si olarak) · **Kural değişikliği YOK** — yalnız çıkış penceresi H.

## 1. Gerekçe (kanıt, çevrimdışı — holdout990 plan üzerinde)

Faz6 mikro-kapı taraması (hepsi ölçüldü ve REDDEDİLDİ):

| aday | pnl/plan (baz +0,2950) | karar |
|---|---|---|
| P1 hedef cap >10 ATR | −0,003 (cap10) / −0,006 (cap6) | **red** (etkisiz/negatif) |
| P2-E1 tez kırılımı çıkışı (close < zemin) | **−0,022** | **red** — stop zeminden yalnız **0,10 ATR** uzakta (STOP_TAMPON_ATR), "erken çıkış alanı" fiilen yok |
| E2 dip erken-çıkışı (0,75/1,00/1,25 ATR) | −0,048 / −0,025 / −0,013 | **red** |
| E3/E4 ilk-bar/4.bar çıkışları | −0,03…−0,10 | **red** |
| E5 trailing (0,75/1,00) | −0,057 / −0,044 | **red** |
| E6 giriş geciktirme (higher-low onayı, K bar) | kalite + ama hacim990→172 (%17) | **red** — aşırı-filtre (yılda ~170 plan → kullanıcı yasağı) |
| **H=15 (zaman stopu)** | **+0,0085** | **aday** |
| **H=20 (zaman stopu)** | **+0,0290 (+%10)** | **aday — asıl** |
| 1d çıkarma | −0,0003 (etkisiz) | red (1d tek başına +0,2960 — sürükleyici değil) |

H=20 mekaniği: hedef erişimi299→384 (+85), zaman çıkışı340→153,
stop351→452 (geç kalan bazı planlar stopa gidiyor ama net kazanç +).
**Erken giriş payını çözmez** (çözüm girişte bulunamadı — §9) — ödül
toplamını artırır.

## 2. Test

- **Komut:** `--zaman-stopu 20` (aynı holdout120 sembol — Eşleştirilmiş
  A/B: plan POPÜLASYONU H'den bağımsızdır (girişte karar), yalnız
  çözünme değişir → Faz6 koşusuyla birebir aynı990 plan beklenir,
  yalnız sonuç dağılımı/K3/K6 değişir).
- **Beklenti (offline'dan):** sonuç ≈ hedef384 / stop452 / zaman153;
  K3/K6 yönü ↑ (pnl/plan +0,295→+0,324). Sapma olursa raporlanır.
- Kapılar K1–K6 EŞİKLERİ DEĞİŞMEZ. K2 beklentisi: değişmeyebilir
  (K2 çözünmeye duyarlı — ölçülüp raporlanır).
- Doğrulama sonrası: H=20 kabul/karar raporu (`FAZ7` ek'i).

## 3. Riskler

- Zaman10→20 bar = pozisyon süresi2× (maliyet modeli işlem-başı düz
  (cost0 ölçüm) — H değişimi işlem sayısını değiştirmez; K3 maliyet0
  varsayımı altında etkisizdir).
- Aynı holdout tekrar kullanılıyor (eşleştirilmiş A/B — kapı seçimi
  değil, çıkış parametresi tayini; deklare edildi).
- Erken stop payı artabilir (geç stoplar); asıl ölçüt K3/K6 ve
  pnl/plan yönüdür.

---

## Ek A — Koşu öncesi derin tarama (aynı gün,990 holdout plan)

**H doygunluk eğrisi (pnl/plan):**
| H |10 |15 | **20** | **25** |30 |40 |
|---|---|---|---|---|---|---|
| | +0,2950 | +0,3035 | **+0,3240** | **+0,3292 (tepe)** | +0,3249 | +0,3197 |

Eğri20–25 platosu,30+ düşüş (geç stoplar birikiyor: stop452→512).
**Bu faz H=20 ile tescilli** (Ek'teki15/20 adaylığı); H=25 plato tepe
notu — SONRAKİ iterasyon adayı (ayrı tescil gerekir).

**H=10 → H=20 grup kırılımı (kim kazanıyor?):**
| grup | H10 | H20 | değişim |
|---|---|---|---|
| iyi (n532) | +1.001 (hedef256) | **+1.080 (hedef331)** | ✓ asıl kazanç burada; ama stop29→92 (geri-dönüş vuruşu) |
| erken (n357) | −0,755 | −0,774 | ≈ aynı/kötü — H erken'i kurtarmıyor (beklendiği gibi) |
| geç (n63) | +1.250 (stop0) | +1.021 (stop11) | ✗ kötüleşiyor (uzun pencere geç'i vuruyor) |
| yüksekten (n38) | −1,312 | −1,103 | ✓ hafif iyileşme |

**Sonuç:** H=20'nin artı toplamı **iyi grubun hedef erişiminden** geliyor;
erken zararı sabit kalıyor. Yani bu bir "ödül büyütme" kaldıracı —
erken-giriş çözümü değil (§9 ile tutarlı).

**Kombinasyon taraması (H=20 + çıkış kuralı):** dip1,25/1,50 → +0,3105/+0,3056;
trail1,00/1,25 → +0,2555/+0,2903 — **hepsi H=20 tek başına (+0,3240)
altında → EXIT TARAFI KAPANDI** (tek başına da kombinasyon da hep negatif).

**Popülasyon notu:** gap=20 bar = H=20 olduğundan açık-plan bastırması
gap ile çakışır → plan POPÜLASYONUNUN990 ile birebir aynı olması beklenir
(aynı bar sırası: önce çözünme, sonra tetik); sapma raporlanır.
