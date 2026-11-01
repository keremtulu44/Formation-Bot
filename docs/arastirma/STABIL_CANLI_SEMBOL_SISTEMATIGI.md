# Canlı Deploy Sembolleri (`config.BIST_50`) Üzerinde Stabil Güçlü Geri Alım Sistematiği Doğrulaması

Bu rapor, canlı ortamda taranan `config.BIST_50` evreni üzerinde, üretimde çalışan tek merkezli değerlendiricinin (`domain_engines/stabil/signals.py::evaluate_bar_behaviors`) **nedensel (causal) 4S geçmiş testi** sonuçlarını özetler.

---

## 1. Test Kapsamı ve Canlı Evren Uyumu

- **Canlı tarama evreni (`config.BIST_50`):** Toplam 57 sembol (`48` BIST hissesi + `5` BIST endeksi + `4` makro sembol). Makro sembollerde (`USDTRY`, `EURTRY`, `GRAMALTIN`, `ONSALTIN`) alarm kapalı olduğu için canlı bildirim evreni **53 semboldür**.
- **Arşivde test edilen canlı semboller:** `48` BIST hissesinin **tamamı** + `XU100` ve `XU30` dahil **50 sembol** (`2025-05-07 .. 2026-10-19`, **75,9 hafta**).
- **Sıfır sapma ilkesi:** Geçmiş testte ayrı bir araştırma formülü değil, bizzat canlı kart, grafik `▲` işareti, `/stabil` komutu ve 4S alarm hattını besleyen `evaluate_bar_behaviors` fonksiyonu çalıştırılmıştır.

---

## 2. Birleşik Güçlü Sinyal Kuralları (Yapmacık Skor Yok, Saf Mum Davranışı)

Sinyal yalnızca günlük Stabil destek çizgisi **sabitken** (o barda aşağı kademe indirmiyorken) iki gerçek fiyat davranışından biri oluştuğunda tetiklenir:

1. **Kapanışla Güçlü Geri Alım (`close_reclaim`):**
   - Önceki 4S kapanışı desteğin altındayken, yeni kapanan 4S mumu desteğin net üstüne geçer.
   - Önceki sarkma derin bir çöküş değildir (`<= 1,5 ATR` makul silkeleme bandı).
   - Mumun gövdesi güçlüdür (`>= 0,32 ATR`), kapanış mumun üst bölgesindedir (`>= %65`) ve hacim son 20 mum ortalamasının üstündedir (veya gövde çok güçlüdür `>= 0,45 ATR`).
2. **Fitille Silkeleme Sonrası Güçlü Dönüş (`intrabar_sweep_reclaim`):**
   - Önceki kapanış destek üstündeyken, fiyat seans içinde desteğin altına anlamlı sarkar (`-0,08` ile `-1,20 ATR` arası fitil).
   - Aynı 4S mumu güçlü yeşil gövdeyle (`>= 0,35 ATR`) ve üst bölgede (`>= %68`) kapanarak desteği korur ve hacim/gövde teyidi verir.

**Gönderim disiplini:**
- Sembol başına **6 adet 4S mum (~3 işlem günü)** bekleme süresi (`cooldown`).
- Aynı 4S taramasında **3'ten fazla sembol** tetiklenirse (sert piyasa dönüşü anları): en güçlü **2 tekil kart** + kalanlar için **1 toplu dönüş özeti** gönderilir (böylece tek seansta bildirim yağmuru oluşmaz).

---

## 3. Canlı Semboller Üzerindeki Geçmiş Test Sonuçları (75,9 Hafta)

| Ölçüt | Birleşik Sistem (`50` Sembol) | Kapanışla Geri Alım (`close_reclaim`) | Fitille Silkeleme (`intrabar_sweep`) | Yalnız `48` Hisse |
| :--- | :---: | :---: | :---: | :---: |
| **Toplam Sinyal Sayısı** | **284** | 206 | 78 | 274 |
| **Tetiklenen Sembol Sayısı** | **50 / 50** | 50 / 50 | 37 / 50 | 48 / 48 |
| **Haftalık Ham Sinyal (50 sembol)** | **3,74 / hafta** | 2,72 / hafta | 1,03 / hafta | 3,61 / hafta |
| **53 Canlı Sembolde Haftalık Mesaj (Toplu özet kuralı sonrası)** | **~3,35 mesaj / hafta** | — | — | — |
| **Sonraki 4S Mumda Destek Üstü Kalıcılık** | **%91,5** | %91,3 | %92,3 | %91,2 |
| **2 İşlem Günü Sonra Ortanca / Ortalama Fark (`8×4S`)** | **+0,26 / +0,38 ATR** | +0,24 / +0,41 ATR | +0,31 / +0,30 ATR | +0,27 / +0,37 ATR |
| **4 İşlem Günü Sonra Ortalama Fark (`16×4S`)** | **+0,37 ATR** | +0,22 ATR | **+0,84 ATR** | **+0,42 ATR** |

### Öne Çıkan Bulgular
- **Tam hedef ritim:** Toplu piyasa dönüş kuralıyla birlikte canlıdaki 53 sembol genelinde ortalama **haftada ~3,3–3,4 mesaj** üretir; ne sessiz kalır ne de gürültü yapar.
- **Homojen dağılım:** 76 haftalık dönemde tek bir hisseye yığılma yoktur; 50 sembolün tamamı en az bir kez sinyal üretmiş, en hareketli hisseler (`ALARK`, `ASELS`, `HEKTS`) 1,5 yılda toplam 10 sinyal (~2 ayda 1 sinyal) üretmiştir.
- **Yüksek tutunma kalitesi:** Sinyal mumundan hemen sonraki 4S mumda desteğin üstünde kalma oranı **%91,5**'tir.
