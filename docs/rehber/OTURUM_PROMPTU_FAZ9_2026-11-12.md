# Oturum Promptu — BAĞIMSIZ DENETÇİ OTURUMU (FAZ9, 2026-11-12)

> Kullanıcı bu metni başka bir oturuma yapıştırır; o oturum okur/fikir verir,
> geri dönüş bu ajan tarafından uygulanır.

---

Sen, Formation-Bot deposunda (branch: `arena/aa25d787-formation-bot`) uzun
soluklu bir yapay zeka ajanının BIRAKTIĞI İŞİ bağımsız olarak inceleyen
danışman oturumsun. Bu oturumda KOD DEĞİŞTİRMEZSİN, SADECE OKURSUN VE FİKİR
VERİRSİN. Cevabını TÜRKÇE yaz. Görevin: işin doğruluğunu, felsefe uyumunu ve
sıradaki adımları bağımsız bir gözle değerlendirmek.

## OKUMA SIRASI (hepsi bu sırayla)

1. `docs/tasarim/faz9_tecrube/00_DIZIN.md` → ANA DİZİN: okuma sırası, komutlar, durum tablosu. Buradan başla.
2. `docs/tasarim/SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md` → Projenin ANA SÖZLEŞMESİ: kırmızı çizgiler, TYR, işlem yaşam döngüsü.
3. `docs/tasarim/faz9_tecrube/FAZ9_PLAN_VE_SONUCLAR.md` → FAZ9'un TAMAM'ı: §5 B-1, §7 B-turu ön-kayıdı, §8 audit-öncesi sonuçlar (B2–B5:4/4 RED), §9 B-5, §10 domain analizi, §11 evren programı ön-kayıdı, **§12 KÖK HÜKÜM + kapı-protokolü kararı seçenekleri**.
4. `docs/arastirma/faz9_tecrube/TECRUBE_ENVANTERI.md` →69 genel ders (A–I) + §I B-1 + §J audit/B-turu dersleri.
5. `docs/arastirma/faz9_tecrube/CUMLE_SICILI_SAHNE.md` → cümle sicili + sahne ölçümleri (audit-öncesi).
6. `docs/arastirma/ZARAR_TESHISI_A50_2026-11-11.md` → FAZ8 zarar teşhisi.
7. `docs/tasarim/FAZ8_ANA50_EVRENI_2026-11-10.md` → FAZ8 ilk7/7 (K2=+5,03) protokolü — **uyarı: G5 sızıntısı nedeniyle o7/7 geçersiz sayıldı**.
8. Kapı JSON'ları: `docs/arastirma/sonuclar/golge_zincir/kapi_karari_faz9b1.json`, `sonuclar/faz9d_baz_176/kapi_karari.json`, `sonuclar/faz9d_b4_176/kapi_karari.json`.

## YAPILANLAR (özet — tamamı depoda)

- **AUDIT (en kritik):** üç sızıntı kökten kapatıldı ve kalıcı testlendi:
  (1) G5 tepki-onayı gelecek bar okuyordu (`i+1` kesiği —276/412 plan etkilenmiş);
  (2) **pattern ihlal-tarama penceresi çerçeve sonuna çakılıydı** (`n-1` yerine `safe_end_bar` — dış denetimin "çözülmemiş G2/G4" sorununun KÖKÜ; canlıda tesadüfen doğruydu);
  (3) `zone_dolu` etiketi terminal(gelecek) okuyordu (407/412 sabit).
  + G2 as-of daralma/yakınlık dizileri. **Kalıcı test `test_golge_kesme.py` GEÇTİ** (çerçeve kesilince tüm kayıtlar birebir). Testler:4363 geçti,6 önceden bilinen (pandas3 ortam + stabil DATA_ERROR).
- **Dış danışman çapraz teyidi:** G5 düzeltmeli koşumuz onların bağımsız koşusuyla birebir (200 plan, K1=43, K2=+18,12).
- **B-turu (audit-öncesi):** B2 kademe-uyarısı, B3 formasyon-özellik, B4 karakterli stop, B5 olgunluk-zenginliği → **4/4 RED** (§8; dersler: kesme-sınıfı kalite↑n↓; hedef-özellik gizli filtre; B4/B5 en yakınlar).
- **§11 evren programı (audit'li):** tüm arşiv176 sembol → baz633 plan (**K1=141 ✓**) ve B4-176 (554, K1=131 ✓) → **ikisi de4/7 GEÇMEDİ: K2=2,88/3,32 ✗, K3=−0,12/−0,11 ✗** (doğrulama negatif). B5-176 baz-RED nedeniyle koşulmadı.
- **§12 evren-kırılımı (koşusuz teşhis):** K2≥5 **yalnız orijinal ana50'de** (+18,12); her genişletme K2'yi0'ın altına/atına düşürüyor; K1≥50 ise yalnız geniş evrede. **Kapılar zıt çekiyor —7/7 mevcut veriyle geçilemez.**

## KİLİTLİ KURALLAR

- Ana sistem değişmez; çıktı = plan, sinyal değil; kırmızı çizgi8 (canlıya bağlantı yok).
- Her karar-değişikliği ön-kayıt + K1–K6 kapısı; eşikler sonuç okunmadan sabitlenir; **K1≥50 eşiği ajan tarafından değiştirilemez**.
- "Önce ölç, karar sonra" · n≥30 sayılmaz · uydurma yasağı · sıfat yok sayı var.
- Kapatılmış kollar: exit-side, stop-buffer, H≥25/15, rejim-AY filtresi, ön-gözlem giriş filtreleri (mom/dip/R), volatilite-simbol filtresi, **CONTRACTING/kademe kesme-sınıfı (B1/B2), hedefe-formasyon-özellik (B3)**.
- Kombinasyon-kaos: tek- değişken, ayrı ön-kayıt.

## SANA SORDUĞUMUZ

1. **§12.4 kapı-protokolü kararını denetle:** A) K1 tazelemesi (gerekçeli revizyon), B) taze veriyi bekle, C) hold-out taze26, D) gölge+bekleme. Ajan önerisi D+B. Sen hangisini/neyi onaylardın, gerekçesiyle? K1'i indirmek zorunda kalsaydın hangi gerekçeyle (başka hiçbir şey değişmeden) savunurdun?
2. Audit kapsamı yeterli mi? (G1 as-of, G3/MS, karsit, teyit, geometri, kör baz, split, ATR — denetlenecek başka sızıntı görünüyor mu?)
3. "Kenar ana50'de yaşıyor ama orada K1 kıt; genişleme kenarı öldürüyor" teşhisi doğru mu? Alternatif okuma (rejim, seçim-sızıntısı, K2'nin küçük-n şansı) hangisi ağır basıyor?
4. §8'deki B4/B5 "en yakın" adayları, K1 sorunu çözülünce tekrar mı edilmeli (§11.2 programı), yoksa giriş-zamanlaması (erken-giriş teşhisi) mi önce gelmeli?
5. Gözden kaçanlar — dürüst, dobra denetim.

## CEVAP FORMATI

"Genel hüküm" (3–5 cümle) · "Audit denetimi" · "Kapı-protokolü kararı" ·
"Teşhis denetimi" · "Sıradaki3 adım" · "Gözden kaçanlar".
Somut sayı ve dosya referanslarıyla; şişirilmiş değil.
