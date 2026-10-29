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
| **[KOLON_SOZLUGU.md](KOLON_SOZLUGU.md)** | **Ortak dil:** her kolonun anlamı, birimi, `n` birimi, sınıf değerleri, formasyon tablosu taslağı | Sorgu yazmadan / tablo okumadan önce |
| **[FORMASYON_SONUCLARI.md](FORMASYON_SONUCLARI.md)** | **Formasyon cevapları:** FRM-01…20 kartları (n + taban + GA) | Formasyon sorularının cevabı |
| **[AMPIRIK_REFERANS.md](AMPIRIK_REFERANS.md)** | **Canlıya bağlanan ölçüm:** hangi sayı kartta hangi koşulda basılıyor (`ampirik_referans.py`) | Ölçümü metne çevirirken |
| **[KOSULLU_CUMLE_OLCUMU.md](KOSULLU_CUMLE_OLCUMU.md)** | **Ölçüldü, yazılmadı:** "giderse tamamlanır" cümlesinin çapraz tablosu (yakınlık + aşım kovaları), karar ve gerekçe | Koşullu cümle önerilmeden önce |
| **[REPLAY_OZET_2026-10-21.md](REPLAY_OZET_2026-10-21.md)** | **Son replay'in okunur özeti:** tek ekran + tek tabloda MFE/MAE/NET + örneklem payı | Hızlı karar / paylaşım için |
| **[KOVA_FAZI_OLCUMU_2026-10-23.md](KOVA_FAZI_OLCUMU_2026-10-23.md)** | **Kova fazı ölçümü:** kayan pencerenin 2s/4s fazlarını saatten saate döndürmesinin motor kararına ve bildirim tekrarlarına etkisi; ölçüldü ve sabit-çapa düzeltmesi uygulandı (§9) | Resample/tekrar bildirimi konuşmadan önce |
| **[DZ_REPLAY_SONUCLARI_2026-10-28.md](DZ_REPLAY_SONUCLARI_2026-10-28.md)** | **DZ replay hattı:** 177 sembol × 4 TF = 708 seri, 0 hata — OB/FVG nedensel replay sonuçları + `dz_*` CSV/Supabase eşleme (`scripts/backfill/dz_yukleme.py`) | Zone kapsamı/doğruluğu doğrularken |
| **[REPLAY_SORU_SETI_2026-10-29.md](REPLAY_SORU_SETI_2026-10-29.md)** | **S01–S32 soru seti:** kod karşılığı + cevap sözleşmesi §0–§7 (eşik: <5 RED / 5–12 kart metni / ≥12 kural) + açık uç sicili §8 | Soru sözleşmesini okumak için |
| **[REPLAY_SORU_YANITLARI_2026-10-29.md](REPLAY_SORU_YANITLARI_2026-10-29.md)** | **S01–S32 cevapları** (`research/soru_cevaplama.py`, 708 seri 0 hata): 19 canlıya / 1 kart metni / 7 RED / 1 karar yok / 4 gözlem | "Bu kural neye göre, kaç puanla?" diye |
| [AI_SORU_URETICI_PROMPT.md](AI_SORU_URETICI_PROMPT.md) | Dış AI'a verilecek soru-üretici prompt (tek parça; kolon/ölçek/eşik sözlüğü gömülü) | Yeni soru seti üretilirken |
| [AI_SONUC_YORUM_TALIMATI.md](AI_SONUC_YORUM_TALIMATI.md) | Dış AI'a verilecek sonuç-yorumu paketi: yalnız yorum (yeni ölçüm/soru istemez, sayı uydurmaz) | Replay sonuçları yorumlatılırken |
| [SORU_KOVA_BASELINE_2026-10-29.json](SORU_KOVA_BASELINE_2026-10-29.json) | Yayın kapısının §6 kova bazeline (`research/soru_kapisi.py`; saparsa yayın durur) | Kapı sonucu değiştiğinde |
| [ARASTIRMA_RAPORU_DUZMETIN.txt](ARASTIRMA_RAPORU_DUZMETIN.txt) | Aynı sonuçların düz metin dışa aktarımı (paylaşım için) | Telegram/forum aktarımı |
| [arastirma_ms_hatali_seriler.txt](arastirma_ms_hatali_seriler.txt) | MS motorunun patladığı **35 serinin** listesi | Kayıt (düzeltildi 2026-10-28) — aşağıya bak |

## Ölçümün canlı metne bağlandığı yer

Kart ve `/tara` çıktısı artık yalnız "şu an ne oldu" değil, aynı kurulumun
arşivdeki karşılığını da basıyor (`◇` satırları). Hangi ölçümün hangi koşulda
yazıldığı, `n` gösterimi ve yaklaşımlar: [AMPIRIK_REFERANS.md](AMPIRIK_REFERANS.md).
Katman varsayılan kapalıdır; açan yüzey açıkça `olcum=True` verir.

## Kilit bulgular (tek paragrafta)

Zone'lar **bariyer değil, zamanlama aracıdır**: dokunuş anında ~%65 beklenen yönde ≥1 ATR
tepki var (ortalama ~2,0 ATR), ama zone'ların ~%90'ı eninde sonunda geçiliyor. OB tekrar
tekrar denenir (%24'ü iki+ epizot), FVG pratikte tek denemeliktir (%23'ü hiç temas almaz).
Destek tarafı tepkiyi daha büyük üretir (1d'de +0,53 ATR). BOS/CHOCH **zone'dan daha
güvenilir** bir yön teyidi: %97–98 yön uyumu, ~%70 devam; yukarı kırılımlar aşağıdan ~%8 puan
daha iyi. Çok test edilen korunan tepe çöker (4+ denemede engelleme %36 → %8) ama korunan
dip tutar (%37,5 → %33,3). **Sezginin tersine**, dokunuş anında yüksek hacim (Q4) her intraday
TF'de en zayıf tepkiyi verir (%60–61 vs %70); hacim burada teyit değil, tükenme işaretidir.

## ⚠️ ~~Açık bulgu: canlı botta sessiz MS çökmesi~~ → 2026-10-28'DE DÜZELTİLDİ

> **Güncelleme (2026-10-28):** Kök neden (kilitli geçici referansın aday fork'unda
> kaybolması) düzeltildi; 35 hatalı serinin tamamı hatasız tamamlanıyor.
> Ayrıntı + doğrulama: [denetim/MS_KILITLI_REFERANS_DUZELTME_2026-10-28.md](../denetim/MS_KILITLI_REFERANS_DUZELTME_2026-10-28.md).
> Görünür degrade (`/durum` MS arıza satırı) zaten koddaydı (`bot/commands._ms_hata_satiri`).
> Aşağıdaki metin ölçüm anındaki (Ekim 2026) tarihli kayıttır:

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
*(2026-10-28: degrade `/durum` MS arıza satırıyla zaten vardı; kök neden ayrıca
düzeltildi — bu "ilk adım" maddesi kapanmıştır.)*

## Yeniden üretim

```bash
python scripts/backfill/arastirma_kosu.py --limit 3      # pilot
python scripts/backfill/arastirma_kosu.py                # tam koşu (~60 dk, 704 iş)
python scripts/backfill/arastirma_kosu.py --agrega       # yalnız raporu yeniden üret
```

Ham çıktı `arastirma_cikti/*.jsonl` (git'e girmez); rapor
`docs/arastirma/ARASTIRMA_BULGULARI.md` (bu klasör) olarak yazılır.

Aynı JSONL tabanından replay soru hattı (S01–S32):

```bash
python run_directional_zone_replay.py                    # DZ replay: 708 seri → dz_* CSV
python research/soru_cevaplama.py                        # S01–S32 → REPLAY_SORU_YANITLARI_*.md + soru_seti_sonuclari.json
python -m research.soru_kapisi                           # yayın kapısı (çıkış 0 = açık; --kova-yaz ile baseline üretimi)
python scripts/ornek_kartlar.py                          # 9 örnek kartlık galeri
```

## Sınırlar (özet — tamamı SONUCLARI §Sınırlar)

- Tek 365 günlük rejim; rejim değişiminde özellikle yön asimetrisi dönebilir.
- Havuz BIST likit ~177 hisse; küçük hisseler temsil edilmiyor. `BRENT` havuz dışı.
- Bu bir **istatistiksel ölçüm**, işlem stratejisi backtest'i değil: maliyet, kayma,
  pozisyon boyutu ve çıkış kuralı modellenmedi. "%65 CALISTI" kârlılık değil, ≥1 ATR'lik
  yönlü uzanım sıklığıdır.
- Motor parametreleri değiştirilmedi; ölçüm canlı "Dengeli" profiliyle alındı.
