# Okları anlamlandırma + destek/direnç dışı domainler — 2026-11-15

Kaynak: kayıtlı ok replay'i (`stabil_ok_replay_2026_11_05/events.csv.gz`,
555 geçerli ▲, 8 bar) + S01–S32 zone/MS/hacim replay'i
(`REPLAY_SORU_YANITLARI_2026-10-29.md`). Koşu:
`python scripts/stabil_ok_kalite_analizi.py`

## 1. Ok tek başına değil, bağlamıyla anlamlı — ölçüde durum

| Bağlam (domain) | Ölçüm | Yorum |
|---|---|---|
| Ok türü (Stabil) | rebase %17,3 zayıf / %58,7 yönde; süpürme %29,6 | En güçlü ayrım — kademe yapıldı |
| Mesafe (Stabil geometri) | çizgiye 0,1–0,5 ATR: %20,1 zayıf / %53,0; >1 ATR: %27,1 | Yakın ama temas etmemiş ok daha iyi |
| MS durumu tek başına | bearish %26,4 ≈ bullish %24,3 zayıf | **Ayrım yok** — filtre olmaz |
| MS × tür | geri alım + boğa MS: %65,2 yönde (n=23) | Küçük n; görsel işaret olabilir |
| Yakın FVG (zone) | süpürme %36,4, geri alım %30,8 zayıf (yokken %28,6/%21,8); rebase etkilenmiyor | Tür seçici engel |
| Yakın OB (zone) | %25,1'e karşı %25,9 | **Fark yok** — OB yakınlığı ok işareti olmamalı |
| Hacim kovası | düşük %25,3 ≈ yüksek %24,6 | **Ayrım yok** (S12 ile uyumlu: tek ölçüt rvol) |
| Stabil 4s davranışı | `RECOVERY_FAILED` %10,9 zayıf / %63,0 yönde (n=46); `SELLING_WEAKENING` %44,3 yönde, medyan −0,39 | İlginç ama n küçük + adlandırma paradoksu; önce doğrulama |
| Seans saati | 13:30 barları belirgin iyi, 17:30 kötü | Karıştırıcı olabilir (bar boyu/hacim tabanı); saat filtresi kurulmaz |

## 2. Uygulanan: ok bağlam halkaları (grafik, sinyal kararı değişmez)

Tarama katmanında (ATR + MS olayları + zone kutuları oradayken) hesaplanır,
renderer yalnız çizer:

- **Beyaz halka** = yapı uyumu: ok öncesi pencerede aynı yönlü teyitli
  BOS/CHoCH (MS domaini). `yapi_uyumlu_barlar`
- **Kırmızı halka** = yakın engel: ok yönünde ≤1 ATR karşı **FVG** (OB
  bilinçli dışarıda — ölçüde farkı yok). `engel_yakin_barlar`
- İki tarafta da (destek ▲ / direnç ▼) aynı dil; sayaçlar
  `meta["cizgiler"][...]["yapi_uyumlu_isaret"/"engel_yakin_isaret"]`.

Halka filtre değildir: replay gözlemsel ve alt grup n'leri küçük; ok
üretilmeye/bastırılmaya devam eder, kullanıcı bağlamı görür.

## 3. Destek/direnç dışındaki domainler için öneriler (replay sıralı)

1. **Market Structure (BOS/CHoCH):** Zaten ok sonrası ters BOS'ta iptal
   (gri ok) + taze ters yapıda bastırma var. Ek: ok **öncesi** uyum halkası
   (uygulandı). MS durumunu tek başına kartta "boğa/ayı" diye sunmak
   replay'de desteksiz — sunulmamalı.
2. **FVG:** Ok bağlamında tek işe yarayan zone sinyali. Öneri: kartta
   "önünde yakın FVG var" cümlesi yalnız geri alım/süpürme türlerinde
   (rebase'de ölçülmüş etki yok). Grafik halkası uygulandı; kart cümlesi
   `kart_yorum` kapısından (≥12 puan kuralı) geçmeden eklenmemeli.
3. **Order Block:** Yakınlık ok kalitesini ayırmıyor; S10'da efor-sonuç
   uçurumu OB'de güçlü (+34,3pp) ama o zone'un kendi davranışı, ok
   bağlamı değil. Öneri: OB, ok halkasına girmez; kartta yalnız bölge
   bilgisi olarak kalır (mevcut davranış).
4. **Hacim katılımı (VP):** Ok anı hacim kovası ayrım yapmıyor; S12 kararı
   gereği tek ölçüt rvol. Öneri: oka hacim rozeti eklenmez (mevcut ⚡ rozeti
   yeter). `SELLING_WEAKENING` hali ayrıca izlenmeye değer (medyan −0,39)
   ama önce 1s/2s + saat düzeltmeli replay.
5. **Formasyon:** Karşı sınır koridoru zaten oku bastırıyor (0,5 ATR).
   Öneri: bastırılan ok grafikte hiç görünmediği için kullanıcı "neden ok
   yok"u göremiyor — bastırma nedeni meta'da var; karta tek satır gerekçe
   (mevcut `baglam_bastirilan`) genişletilebilir.
6. **Günlük (1g) Stabil bağlamı:** `DAILY_RAW_STRUCTURE_BROKEN` %62,2
   yönde (n=45) — günlük yapı kırıkken 4s okları daha iyi davranmış.
   Hipotez olarak not edildi; çoklu karşılaştırma düzeltmesi olmadan
   kurala dönüşmez.

## 4. Sıradaki ölçüm işleri (uygulamadan önce)
- Direnç oklarının tür bazlı replay'i (▼ sayıları hâlâ yok).
- `RECOVERY_FAILED` + mesafe bandı birleşik tablosu (n büyütme: 1g oklar).
- Saat karıştırıcısı: aynı-saat normalize hacimle 13:30/17:30 farkı tekrar.
- Halka etiketlerinin canlıda dağılımı: kaç ok halka alıyor, halkalı/
  halkasız ayrımı ileri tarihli (out-of-sample) dönemde korunuyor mu.
