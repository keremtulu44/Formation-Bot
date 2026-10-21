# Araştırma — arşiv ölçümü (OB/FVG/MS/PH-PL/WH-WL/Hacim)

> **Durum:** Yürürlükte · **Ölçüm tarihi:** Ekim 2026 · **Veri:** `backfill_data/` 365 günlük gerçek arşiv
> **Taban:** 176 sembol × 4 zaman dilimi = **704 seri**, **994.142 gözlem satırı**

Bu klasör, botun **canlı karar kurallarını değiştirmeden** motor çıktısının piyasada ne
yaptığını ölçen hattın çıktısıdır. Repodaki tek "yeni bilgi" üreten belge grubudur; kod
tartışmalarında sayı gerektiğinde buraya bakılır.

## Nereden okunur

| Dosya | Ne | Nasıl okunur |
|---|---|---|
| **[ARASTIRMA_SONUCLARI.md](ARASTIRMA_SONUCLARI.md)** | **Ana belge:** soru bazında cevap + yorum | Buradan başla |
| [ARASTIRMA_BULGULARI.md](ARASTIRMA_BULGULARI.md) | Ham tablo eki (üretici script buraya yazar) | Sonucu doğrulamak için |
| [ARASTIRMA_HATTI.md](ARASTIRMA_HATTI.md) | Yöntem, modüller, anti-lookahead sözleşmesi | Ölçüme güvenmeden önce |
| **[YASAM_TABLOSU.md](YASAM_TABLOSU.md)** | **Soru sicili:** OB/FVG/formasyon için yaşam tablosu, kilitli sorular, cevap formatı | Yeni ölçüm yapmadan önce |
| [ARASTIRMA_RAPORU_DUZMETIN.txt](ARASTIRMA_RAPORU_DUZMETIN.txt) | Aynı sonuçların düz metin dışa aktarımı (paylaşım için) | Telegram/forum aktarımı |
| [arastirma_ms_hatali_seriler.txt](arastirma_ms_hatali_seriler.txt) | MS motorunun patladığı **35 serinin** listesi | Açık bulgu — aşağıya bak |

## Kilit bulgular (tek paragrafta)

Zone'lar **bariyer değil, zamanlama aracıdır**: dokunuş anında ~%65 beklenen yönde ≥1 ATR
tepki var (ortalama ~2,0 ATR), ama zone'ların ~%90'ı eninde sonunda geçiliyor. OB tekrar
tekrar denenir (%24'ü iki+ epizot), FVG pratikte tek denemeliktir (%23'ü hiç temas almaz).
Destek tarafı tepkiyi daha büyük üretir (1d'de +0,53 ATR). BOS/CHOCH **zone'dan daha
güvenilir** bir yön teyidi: %97–98 yön uyumu, ~%70 devam; yukarı kırılımlar aşağıdan ~%8 puan
daha iyi. Çok test edilen korunan tepe çöker (4+ denemede engelleme %36 → %8) ama korunan
dip tutar (%37,5 → %33,3). **Sezginin tersine**, dokunuş anında yüksek hacim (Q4) her intraday
TF'de en zayıf tepkiyi verir (%60–61 vs %70); hacim burada teyit değil, tükenme işaretidir.

## ⚠️ Açık bulgu: canlı botta sessiz MS çökmesi

704 serinin **35'inde (%5,0)** MS motoru
`ValueError: confirmed break references must still be active` ile düşüyor
(1h'de 20, 2h'de 6, 4h'de 4, 1d'de 5 seri — AEFES, FROTO, EBEBK, CWENE, ALGYO…).

Canlı botta `_execute_domain` bu hatayı yuttuğu için bot **çökmüyor**; o sembolün MS
domaini **sessizce boş kalıyor** — BOS/CHOCH sinyali hiç üretilmiyor ve kullanıcıya uyarı
gitmiyor. 1h'de 20 sembol, botun her gün bu semboller için yapısal kırılım üretmemesi
demektir. Hata ölçüm hattına özgü değil: canlı runner'ın kullandığı `engine.replay(frame)`
yolu birebir aynı hatayı veriyor (AEFES/ALFAS/ALGYO üzerinde doğrulandı).

**Önerilen ilk adım** (kök neden ayrı iş): `_execute_domain` hata yakaladığında Telegram'a
"MS domain devre dışı" uyarısı düşürmek — sessiz boşluk yerine görünür degrade.
Ayrıntı: [ARASTIRMA_SONUCLARI.md](ARASTIRMA_SONUCLARI.md) §"Canlı botta bulunan sessiz MS çökmesi".

## Yeniden üretim

```bash
python scripts/backfill/arastirma_kosu.py --limit 3      # pilot
python scripts/backfill/arastirma_kosu.py                # tam koşu (~60 dk, 704 iş)
python scripts/backfill/arastirma_kosu.py --agrega       # yalnız raporu yeniden üret
```

Ham çıktı `arastirma_cikti/*.jsonl` (git'e girmez); rapor
`docs/arastirma/ARASTIRMA_BULGULARI.md` (bu klasör) olarak yazılır.

## Sınırlar (özet — tamamı SONUCLARI §Sınırlar)

- Tek 365 günlük rejim; rejim değişiminde özellikle yön asimetrisi dönebilir.
- Havuz BIST likit ~177 hisse; küçük hisseler temsil edilmiyor. `BRENT` havuz dışı.
- Bu bir **istatistiksel ölçüm**, işlem stratejisi backtest'i değil: maliyet, kayma,
  pozisyon boyutu ve çıkış kuralı modellenmedi. "%65 CALISTI" kârlılık değil, ≥1 ATR'lik
  yönlü uzanım sıklığıdır.
- Motor parametreleri değiştirilmedi; ölçüm canlı "Dengeli" profiliyle alındı.
