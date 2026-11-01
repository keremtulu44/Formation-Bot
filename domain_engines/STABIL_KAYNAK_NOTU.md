# Stabil native kaynak ve entegrasyon durumu

**Kayıt:** 2026-11-01 · [Ana rehber](../docs/arastirma/STABIL_REHBERI.md).

## Kurtarılan özgün dosya

[05_stabil.txt](05_stabil.txt) yükleme alanındaki `stabil_domain_clean.txt`
dosyasından **baytları değiştirilmeden** kopyalandı.

- Boyut: **75.710 bayt**, 1.637 satır.
- SHA256: `649896d2ba5860e7c1637e8e7aaae79f8b4574d6de331de7eb53e93f163e6a5e`.
- Bu hash önceki oturum kaydıyla eşleşiyor; bu turda gerçekten doğrulandı.
- İçerik: iki Python çekirdeği ve üç sözleşme; Python 3.11+ StrEnum/dataclass/pandas.
- Matematik, eşikler veya sözleşme metni bu belgeleme turunda değiştirilmedi.

## Kaynağın sağladığı bağımsız roller

| Bileşen | Native çıktılar |
|---|---|
| `stabil_trend_engine.py` | WeeklyTrendSnapshot, DailyTrendSnapshot, H4TrendSnapshot, H4EvidenceStatus |
| `stabil_support_lifecycle.py` | DailySupportObservation, lifecycle snapshot, destek olayları, seviye/floor ve mesafe/süreler |

Dosya adları TXT içindeki bileşenlerdir; şu checkout'ta runtime paketlerinin
mevcut olduğunu göstermez. **`domain_engines/stabil/` entegrasyonu bulunamadı.**
Kaynağı kaydetmek botun registry/runner/scan yüzeyine motor eklemez.

## Kurtarılacak entegrasyon sözleşmesi

- Tam native trend/destek export'ları bağımsız korunmalı; daha az veri taşıyan
  grafik projeksiyonu native sonuçların yerine geçmemeli.
- Derin W/D/H4 girdi ve rol bazında hazır/veri-hatası ayrımı.
- Günlük destek trend warm-up'ından bağımsız olabilir.
- BIST kapanış takvimi yabancı piyasalara uygulanmamalı; yabancı rol için
  sertifikalı gerçek kapanış gerekir. Açılış etiketi bilinirlik anı değildir.
- Öğrenme/replay izole olmalı, canlı latest registry'den okumamalı.
- Performans observer'ı yalnız mevcut snapshot'ı kaydeder; hesap/durum
  geçişini değiştirmez. Kaynak eşitliği yalnız tam observer eklerini
  normalize etmeli; bağımsız prefix eşitliği ayrıca test edilmelidir.
- Native kaynakta olmayan birleşik MAIN/health/risk çıktısı veya Pine skorları
  varmış gibi üretilmemeli.

[Grafik/kart kapsamı ve eksik dosyalar](../docs/arastirma/STABIL_DOSYA_ENVANTERI.md) ·
[Replay yöntemleri](../docs/arastirma/STABIL_REPLAY_HATLARI.md).
