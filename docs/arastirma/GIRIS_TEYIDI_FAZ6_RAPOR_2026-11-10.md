# Faz 6 — Giriş Teyidi Raporu (holdout koşusu)

**Tarih:** 2026-11-10 · **Karar:** GATE **GEÇMEDİ** (6/7; K2 −2,24 ≤ +5,0) ·
**Başlık:** teyit kapısı çalışır, ölçülebilir katkı var, ama K2'yi onarmıyor.

Kurallar koşudan önce tescilli: `docs/tasarim/FAZ6_GIRIS_TEYIDI_KURALLARI_2026-11-10.md`
(V1 + Revize1 T1505) · modül `senaryo/giris_teyidi.py` ·8 test (87 yeşil).

---

## 1. Koşu künyesi (temizlik)

| | |
|---|---|
| Evren | **holdout120 sembol** (ilk30 kalibrasyon dışı — sızıntı yok) ×4 TF =480 seri |
| Kod | `arena/aa25d787-formation-bot` · `cd50efe` + çıktı commiti `60835ff` |
| Hata | **0** · süre2.811 sn (~47 dk) · defter746.495 kayıt (bozuk0) |
| Plan | **990** (teyit_red2069 → tutunma **%32,4**) |
| Sonuç | hedef299 · stop351 · zaman340 · yok0 (stop payı %35,5) |
| Çıktılar | `ozet_faz6_holdout.json`, `olcum_faz6/`, `inceleme_faz6_holdout.json`, `kapi_karari.json` |

## 2. Kapı ölçümü (K1–K6 · koşumdan önceki eşikler)

| Kapı | Eşik | Faz5 (eski tam koşu) | **Faz6 holdout** | Durum |
|---|---|---|---|---|
| K1 doğrulama n | ≥50 |566 | **224** | ✓ |
| **K2 UYGUN−kör (puan)** | ≥**+5,0** | **+0,67** | **−2,24** | **✗ (tek kırmızı)** |
| K3 doğrulama bek (ATR) | >0 | +0,1107 | **+0,1204** | ✓ **(yükseldi)** |
| K4 G1 kapalı plan % | ≤5 | 0 | **0** | ✓ |
| K5 RET sonrası ihlal | =0 |0 | **0** | ✓ |
| K6a keşif bek (ATR) | >0 | +0,3595 | **+0,346** | ✓ (hafif düşük) |
| K6b doğrulama bek (ATR) | >0 | +0,1107 | **+0,1204** | ✓ **(yükseldi)** |

**Yorum:** teyidi geçen paketin **doğrulama ve keşif beklentisi yükseldi**
(K3 +%8,7). K2 ise **negatife döndü** — ölçüm, "UYGUN paketi kör akışa
karşı" sorusunu soruyor; teyit bu soruya dokunmuyor, sürükleyen **hüküm
(verdict) tarafı** (BOS/CHOCH reddi + RET-G1 + erken/sonrası — §7).

## 3. Giriş kvadrantı — eski tam koşu vs Faz6 holdout

| Giriş yeri | Eski (n2.771) | **Faz6 (n990)** | Δ | stop oranı |
|---|---|---|---|---|
| **iyi zamanlama** | %50,1 | **%53,7** (532) | **+3,6 p** | %5,4 (29/532) |
| **erken girdi-düştü** | %30,5 | **%36,1** (357) | **+5,6 p ✗** | %83,7 (299/357) |
| geç girdi-dibi kaçırdı | %12,2 | **%6,4** (63) | −5,8 p | **%0** |
| **yüksekten girdi-düştü** | %7,2 | **%3,8** (38) | **−3,4 p ✓** | %60,5 (23/38) |

- **990 stopun322'si (%81) hâlâ erken+yüksekten** (önce %90 → **8,8 p iyileşti**;
  erken299 + yüksekten23).
- **Çıkış kvadrantı:** ortada596 · dipte208 · tepede186 → **erken-satış
  patolojisi sürüyor** (geç-kal yerine sat: dipte satılan208 işlem).
- Stop kalitesi: doğrulandı333 / toparlandı18 → toplam351 stopun **%94,9'ı
  gerçekten doğrulanmış** (kalite yüksek; sorun giriş yeri).

**Dürüst okuma:** teyit kapısı yüksekten-girişi **yarıya indirdi** ve iyi
payını yükseltti; ancak **erken giriş payı arttı** (%30,5→36,1). Sebep
kalibrasyonda da görüldü: erken ile iyi giriş **giriş-öncesi neredeyse aynı**
(§7) — giriş-öncesi devamlılık kuralları erken'i ayıramaz; kapı yalnızca
yanlış-kalitede (yüksekten/zayıf bek) süzüyor.

## 4. Kaçan tetikler (kapı analizi, bağımsız yarış)

| Kapı | n | bek (ATR) | giriş kvadrantı |
|---|---|---|---|
| BEKLE · olgunluk yok (>1 ATR) |3.405 | +0,349 | iyi1569 · erken966 · geç550 · yüksekten320 |
| **Faz6 giriş teyidi** | **2.255** | **+0,314** | iyi1117 · erken615 · geç323 · yüksekten200 |
| BEKLE · taze karşıt MS |579 | +0,237 | iyi292 · erken210 |
| 20-bar boşluk |199 | −0,031 | iyi91 · erken86 |
| RET · G1 kapandı |142 | +0,358 | geç59 · yüksekten42 |

Teyitle kesilen2.255 adayın bağımsız beklentisi **+0,314** — tutulan990
planın K3+K6 ortalamasına (+0,12…+0,35) yakın; yani kapı artık **yanlış
tarafı kesmiyor** (V1'de kesilenler bek+0,35 ile tutulandan iyiydi — Revize1
püf noktası, belge §Revize1).

## 5. Kalibrasyon → Revize1 (özet; tam tablo belgede)

- **V1** ("zemin close3 + yeni dip yok + mom3≤0,5"): erken/stop'ı
  **oynatmadı** (stop %36,7→35,4, erken %33,2→32,2) — "yeni dip yok"
  **yıkanma dipini** kesiyordu (test edilmemiş düşüşleri bırakıyordu).
- **T1505 seçildi** (test15 bar · low≤zemin+0,5 ATR · close≥zemin ·
  pencere dibinden dönüş): offline **retention %41,9 · bek +0,365 ·
  yüksekten %7,6→4,6 · iyi +7 p**.
- **Gerçek etkileşim** retention'ı %32,4'e çekti (boşluk/zincir etkileşimi;
  offline bağımsız yarış bunu göremiyor). Mutlak hacim990 plan/yıl —
  **aç kalma riski yok** (kullanıcının30-40 işlem korkusunun çok üstü), ama
  **%40 zemin karşılanmadı** → belgeye not düşüldü.

## 6. K2 neden hâlâ kırmızı (ve ne yapmalı)

K2, **hüküm tarafının** hâlâ kör akışın gerisinde olduğunu söylüyor
(+0,67 → −2,24; eşik +5,0). Teyit (giriş-öncesi devamlılık) ile onarılamaz —
önceki analizin "erken ≈ iyi" bulgusu bunu zaten zorunlu kılıyordu.
Kalan kaldıraçlar (Faz6'da dokunulmadı, sıradaki adaylar):

1. **Erken-satış/stop tarafı (P2):** erken giriş önden ayırt edilemiyor ama
   **erken anlaşılıp erken çıkış** yapılabilir (dönüşsüz düşüşte stop
   öncesi çıkış) —990 planın351 stopunun %85'i bu iki grupta.
2. **Hedef patolojisi cap** (P1): >10 ATR hedefler (n=113) K2/K6
   beklentiyi şişiyor/bozuyor olabilir — K2'nin koşullu hedef tanımını
   etkiler.
3. **Verdict tarafı (BOS/CHOCH veto):** RET/BEKLE'de kaldı; UYGUN'a
   giren taze karşıt-uyarıların payı ölçüldü (kapı analizinde).

## 7. Tekrarlanabilirlik (2. replay) — SONUÇ

Aynı komut, aynı holdout → `sonuclar/golge_zincir_koşu2` (17:53 bitti,
2.696 sn, **0 hata**). Karşılaştırma:

| ölçüt | koşu1 | koşu2 | |
|---|---|---|---|
| hukum (BEKLE/UYGUN/RET) |338.291 /270.551 /158.414 | **aynı** | ✓ |
| tetik / plan / teyit_red |200.964 /990 /2.069 | **aynı** | ✓ |
| sonuç (hedef/stop/zaman) |299 /351 /340 | **aynı** | ✓ |
| defter SHA-256 (ilk16) | `9ba8d7effb84255f` | **`9ba8d7effb84255f`** | ✓ **byte-birebir** |
| süre |2.811 sn |2.696 sn | (yalnız duvar saati) |

**Replay birebir deterministik** — iki bağımsız çalışma746.495 kaydın
tamamında byte-aynı çıktı ürettı. Ölçüm zinciri (olcum→kapi→inceleme)
aynı deftere1 kez uygulandı; tekrar gerekmedi (sha eşitliği kanıt).

## 8. Reprodüksiyon

```bash
# holdout listesi (ilk30 hariç120) — /tmp/holdout_semboller.txt
python3 research/golge_zincir.py --semboller $(cat /tmp/holdout_semboller.txt) --cikti sonuclar/golge_zincir
python3 research/golge_olcum.py --defter sonuclar/golge_zincir/golge_defter.jsonl --cikti <çık>
python3 research/golge_kapi.py --olcum <çık>/olcum_ozet.json
python3 research/golge_inceleme.py --defter sonuclar/golge_zincir/golge_defter.jsonl --cikti <çık>/inceleme_ozet.json
python3 -m pytest test_senaryo_giris_teyidi.py -q   #8 test
```
