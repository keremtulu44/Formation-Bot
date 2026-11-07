# Direnç replay — yerel doğrulama

- Düzeltilmiş tam koşu: **174/174 hisse**, sıfır sembol hatası; 175.050 adet
  4s olay satırı ve 17.161 terslenmiş native günlük yaşam-döngüsü olayı.
- İlgili araştırma ve Stabil testleri: **60 geçti** (Python 3.11.2); bu, tüm
  repo veya hedef Python 3.12 altında yeni bir tam regresyon çalışması değildir.
  Yeni direnç araştırması test dosyasında 17 test bulunur. Ruff yeni Python
  dosyalarında temizdir.
- `python -m research.stabil_resistance_verify`: 349 arşiv hash'i, 19
  koşu-kaynağı hash'i ve iki olay çıktısının hash'i; olayların tarihlerinde
  köken ≤ teyit ≤ kullanılabilirlik ≤ 4s açılışı; benzersiz olay anahtarları;
  geçerli/eksik ufuk ve aynı-bar durumları; 374 eşleşmenin grup/mesafe/tekrar
  koşulları; tüm satırlarda gap–gerçek temas ayrımı doğrulandı.
- Sabit tohumla seçilen **24 gerçek olayda** günlük prefix tekrar çalıştırılarak
  seviye/tavan/kimlik ve durum karşılaştırıldı; saatlik arşivden üretilmiş
  4s fiyatlar ve sonraki 8 barın ilk ±1 ATR ve kapanış sonucu ayrıca yeniden
  hesaplandı. Bu örneklem tüm satırların bağımsız ikinci replay'i değildir;
  native çekirdek aynıdır.
- Manifestin `source_sha256` alanı tam replay esnasındaki kaynak hash'lerini
  korur. Sonradan yalnızca rapor bağlantıları ve kanıt PNG'lerinin depo
  kuralına uygun `docs/gorseller/` konumu değiştirildi; eski/yeni hash'leri
  `post_replay_presentation_changes` içinde, yeni doğrulayıcının hash'i de
  `post_replay_verification_sha256` içinde kayıtlıdır. Olay dosyaları ve
  sayısal toplama algoritması bu düzenlemede değiştirilmedi.
- Görsel dikey/yatay eşlemesi, veri sağlayıcının kurumsal işlem düzeltmeleri,
  gerçekten gerçekleşebilir giriş/çıkış ve canlı teslimat ayrı doğrulama ister.
