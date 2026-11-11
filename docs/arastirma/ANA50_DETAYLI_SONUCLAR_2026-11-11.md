# Ana50 — Detaylı Sonuçlar (klasik H=10 replay'i, çevrimdışı tam döküm)

**Kaynak:** holdout120 defteri `plan_sonuc.csv` × ciro-top50 evreni ·
n=412 plan · FAZ8 replay'i `sonuclar/golge_zincir_faz8ana50/` doğrular.

## 1. Ana özet

| | ANA50 |
|---|---|
| İşlem | **412** |
| Kâr eden | **230 → %55,8** |
| Zarar eden |175 → %42,5 (7 başa baş) |
| **Net toplam** | **+175,5 ATR** |
| **Ortalama** | **+0,426 ATR ≈ +%0,84 / işlem** |
| Kazanan ort | +1,446 ATR ≈ **+%3,12** |
| Kaybeden ort | −0,898 ATR ≈ **−%2,12** |
| Kazanç/kayıp oranı |1,61 kazanan / kaybeden |

## 2. İşlem listeleri

**En iyi5:** DAPGM/1h **+12,5A** · BTCIM/1h +5,9 · PAPIL/4h +4,9 ·
SKBNK/1h +4,4 · SKBNK/1d +4,2
**En kötü5:** EFOR/1h −1,8 · EFOR/2h −1,8 · FENER/1h −1,8 · HEDEF/4h −1,8 ·
KONTR/4h −1,9 (hepsi −2 ATR altında — derin zarar yok, sınırlı)

## 3. Çıkış türüne göre

| çıkış | n | ort pnl | toplam | çıkış sonrası20-bar tepe koşusu (bırakılan) |
|---|---|---|---|---|
| hedef |137 | **+1,702** | +233,2 | ort +3,55 ATR (hedef sonrası devam) |
| zaman |143 | +0,511 | +73,0 | ort +1,72 ATR |
| stop |132 | −0,991 | −130,8 | ort +1,92 ATR (stop sonrası toparlanma!) |

## 4. Giriş yeri (kvadrant)

| giriş | n | toplam pnl |
|---|---|---|
| iyi zamanlama | **233** | **+257 ATR** |
| erken-düştü |133 | −99 ATR |
| geç-dip-kaçırdı |28 | +42 ATR |
| yüksekten-düştü |18 | −24 ATR |

→ Ana50'de erken oranı **%32** (tüm120: %36); erken zararı −99 ATR
(tüm120'de −269) — çekirdek evren erken'i de daha az üretiyor.

## 5. Dönem / rejim

- **Keşif:** n322 → +0,4311/plan · **Doğrulama: n90 → +0,4073/plan**
  (ikisi neredeyse eşit — çekirdek evrende dönem düşüşü YOK; tüm120'de
  keşif0,346 ↔ doğrulama0,120 idi)
- **Max üst üste kayıp serisi:9**
- En kötü aylar: **2026-10 (−0,58)** · 2025-01 (−0,22) · 2026-09 (−0,15)
- En iyi aylar: **2026-08 (+1,15)** · 2026-04 (+1,07) · 2025-06 (+0,86)

## 6. Tepeden bırakılan (klasik lens — ayrı rapor: TEPEDEN_KLASIK)

- Ana50 toplam **+984,9 ATR** (ort +2,39/plan) çıkış sonrası20-bar tepe koşusu
- Kazananlarda MFE gerçekleşmesi **%45** (10-bar tepe fırsatının yarısı
  hedef/R kilidine takılıyor)

## 7. Sınırlamalar

- Çevrimdışı döküm (H10 defter CSV'si + arşiv); FAZ8 replay birebir
  doğrulamalı (plan n412 bekleniyor).
- Ciro sıralaması arşiv-ortalama (inceleme) — üretim kuralı FAZ8 §2.
- Yüzdeler ATR-tabanlı, maliyet0 (K3 ölçüm varsayımı).
