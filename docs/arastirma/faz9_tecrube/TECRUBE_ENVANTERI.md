# Tecrübe Envanteri — replay'lerin ölçtüğü GENEL dersler (tek tek sahne değil)

> **KAYNAK GEÇERLİLİĞİ (2026-11-12, FAZ9-C denetimi — tarih sınırlı):**
> **§A–§I satırlarının TAMAMI** sızıntılı tetikle (G5 gelecek-okuması)
> ölçülmüş FAZ5–FAZ9-A hatlarının ürünüdür: **sayılar karar tabanı olarak
> geçersizdir**, yalnız deney-öncesi sezgisel referans olarak okunabilir.
> **§J ve sonrası** audit'li (as-of) hatlardandır ve geçerlidir.
> Tek geçerli sayı kaynağı: `FAZ9_PLAN_VE_SONUCLAR.md` §8/§11/§12.


**Tarih:** 2026-11-11 · **Durum:** Tam envanter (kullanıcı görevi: *"replay'lerde
ölçtüklerimizi tespit et, tam liste hazırla, verileri iyice topla"*)
**Amaç:** Domain'lerin "öğreneceği tecrübe hazinesi" — her satır **genel bir
ders**dir (binlerce gözlemden), tek vaka anekdotu değildir. Entegrasyon sütunu,
cümlenin hangi katmanda (G1–G5 / TYR / hedef / stop / cümle sicili) yaşanacağını
gösterir.

**Okuma kuralları (hepsi zorunlu):**
1. **n<30 sayılmaz; n<300 "nadir", yorum yok** (ampirik_referans.NADIR_ESIK).
2. **Tek satır = tek taban**; iki yüzde aynı satıra yazılmaz.
3. **"Arşivde şuydu"** deriz; kâr/tavsiye/garanti değil (kalibrasyon yok).
4. **Tek rejim penceresi** (May2025–Eki2026, BIST likit ~177): yön asimetrisi
   rejimde dönebilir.
5. Aleyhte ölçü de tecrübedir — **nasıl sayılmayacağını** gösterir (§I).

Kaynak dosyalar `docs/arastirma/` altındadır; satır sonunda kısaltmayla yazılıdır
(AR=ARASTIRMA_SONUCLARI · AB=ARASTIRMA_BULGULARI · AMP=AMPIRIK_REFERANS ·
TM=TAHMIN_KATMANI · OK=OK_SISTEMI · S2=STABIL_SORU_SETI_V2 ·
SEN=STABIL_OK_BAGLAM…SENTEZI · FRM=FORMASYON_SONUCLARI ·
KT=KIRILIM_TEYIT_REPLAY… · SS=STOP_SERMAYE_REPLAY · GZ=golge faz raporları).

---

## A) BLOKLAR / ZONE (OB–FVG) — G5'in tecrübesi

| # | Genel ders | Ölçüm | n | Kaynak | Entegrasyon |
|---|---|---|---|---|---|
| A1 | **OB tekrar denenir; FVG tek denemeliktir** | OB tek deneme %59–60, 3+ deneme %12,9 (max20 epizot); FVG tek deneme %71–78, 3+ ≈%0,007 (4 adet); FVG %23 hiç temas almaz, OB %6,7 | OB17.048 / FVG55.145 zone | AR §1 | G5 cümlesi: "FVG'de soru 'temas aldı mı', OB'de 'kaç deneme'" |
| A2 | **Zone bariyer değil, zamanlama aracıdır** | Dokunuşta ≥1A tepki **%65,0–66,5** (ters %11,2–14,8) AMA zone'ların **~%90'ı** eninde sonunda geçilir (OB geçilme %85,4–93,6) | 240.484 dokunuş / 187.046 zone | AR §2 | hedef G5: zone'ları kalıcı destek/direnç sayma; hedef=zone değil |
| A3 | **Destek kenarı dirençten daha sert tepki verir (büyüklükte, sıklıkta değil)** | 1d OB alt kenar 2,187A vs üst kenar 1,660A (fark +0,53A); CALISTI iki kenarda yakın | 90.485 temas (1h OB) | AR §3 | hedef/stop: alt kenar teması daha değerli |
| A4 | **Yüksek zone tepkisi anlık ve kalıcı; alçak zone yavaş ve geri verir** | ≥2A: decay 1,248 · CALISTI %71,0; <0,5A: decay 2,418 · tepe sonradan gelişir (oran 3,31) | 6.285 (1d FVG) — ≥2A kovası n=162 **nadir** | AR §4 | hedef ufku: yüksek zone→kısa hedef, alçak→sabır ya da yok |
| A5 | **Pratik tepki eşiği1 ATR'dir** | Temasların %59'u ≥1A, %39'u ≥2A tepki (TF'ler üst üste) | 187.046 zone | AR §3 | cümle: "eşik1,0 kat" |
| A6 | **Dokunuş anında yüksek hacim tepkiyi ZAYIFLATIR (hacim teyit değil, ihlal işareti)** | rvol Q4: %61,0–61,3 vs Q1: %66,6–70,1 (fark ~9p); uzanım 2,272→1,868A | Q4 6.740 / Q1 11.928 | AR §8 · AMP#7 | G5/G4: "hacim teyit eder" filtresi **ters** çalışır |
| A7 | **UFUK: FVG tam dolum %40 (ömür5,7 mum); OB 1g iptal %82,8 (ömür32,5 mum)** | — | 55.145 / 17.048 | TM#13/14 · AB | TYR ufuk satırı (yön değil, süre) |
| A8 | *(negatif)* Zone3+ temas ayrımı yok: 1,94 vs2,02A, GA üst üste | — | — | TM#7 | satır üretilmez |
| A9 | *(negatif)* Zone içi/dışı farkı 1,1p — eşik hiçbir zaman geçmez | %75,9 vs %77,0 | — | AMP (kaldırıldı) | kart satırı yok |

## B) MARKET STRUCTURE — G3'ün tecrübesi

| # | Genel ders | Ölçüm | n | Kaynak | Entegrasyon |
|---|---|---|---|---|---|
| B1 | **BOS/CHoCH yönle tepki %97–98 uyumlu ve ~%70'i gerçekten devam eder** — MS, OB/FVG'den daha güvenilir yön teyidi | EXTERNAL BOS: CALISTI %71,0 · ort devam 2,500A · TERS %0,9 | 3.387 (4h) | AR §5 | G3 cümlesi: "kırılımın %75'i sürdü" (yukarı,1651) |
| B2 | **Yukarı kırılımlar aşağıdan güvenilir (~8p)** | 4h EXT BOS UP %75,0/2,827A vs DOWN %67,3/2,189A; INTERNAL UP %72,2 vs DOWN %64,6 | 3.387 + 6.505 | AR §5 · TM#1 (tek Bonferroni geçen yön iddiası: +9,5p) | TYR lehte/aleyhte sayacı |
| B3 | **INTERNAL olay daha sık ama biraz daha zayıf** — sıklık×güven içi değerli kılar | EXT %71,0 vs INT %68,2 (4h BOS) | 6.505 INT | AR §5 | G3: kapsam etiketi |
| B4 | **Çok test edilen korunan TEPE çöker; korunan DİP tutar** | PH 1d EXT engelleme: 1 deneme %36 → 4+ deneme **%8**; PL %37,5 → %33,3 | 1.176 (PH4+) | AR §6 | hedef/stop: tepe hedef olmaktan çıkar, kırılım beklentisi olur |
| B5 | **Zayıf seviyeler (WH/WL) medyan3 barda süpürülür** — hedef ufku 3–6 bar,20 değil | ziyaret %70–81, süpürme %59–70; ortanca ulaşım3 bar (tüm TF) | 24.527 swing (4h) | AR §7 | hedef/zaman: WL/WH hedefi H≠10 bağlar |
| B6 | **Kırılım yönü–rol uyumu sonucu iyileştirir** | uyumlu %79,6 vs uyumsuz %73,2 (+6,4p) | 31.960 | FRM-20 · AMP#3 | cümle: "rol uyumlu %80 (15.724)" — ama puan eşiği5'i **geçmez** (nötr, TM#10) |
| B7 | **WH/WL INTERNAL'da daha gürültülü, WL WH'den daha çabuk süpürülür** | INT %77–81 vs EXT %65–71; WL +3–5p | — | AR §7 | G3 yaş/süpürme kuralı |

## C) STABIL — G1'in tecrübesi

| # | Genel ders | Ölçüm | n | Kaynak | Entegrasyon |
|---|---|---|---|---|---|
| C1 | **Koşulsuz test yarı yarıya: tepki %41,3 / kırılma %51,6** → ONAY olmadan "destek tuttu" denemez | destek TEST n=1.616; direnç aynası n=1.241 (aynı %51,6) | 1.616/1.241 | SEN · BRIFING §3.1 | G1 cümlesi: "onaysız testte kırılma %51,6" |
| C2 | **Onaylı tutunma koşulsuzdan ~+14p güçlü** — ▲ "seviye tuttu" iddiası doğrulandı | R3-B: %63,5 vs %49,6 (+14,0, p2e-9) keşif · %58,9 vs %50,1 (+8,8, p0,0053) doğrulama ✓ | 480/236 (ok) · 9.884 kontrol | OK §12 | G1: ▲ = "seviye geri alındı/tuttu" **değil** ralli (R1/R2 geçmedi) |
| C3 | **Dikey tırmanışta çizginin altı boştur; ilk düzleşmede beklenti olumsuz** | STEPPING_UP → ilk düzleşme DOWN_first %53,5, med −0,29A; 4s düzleşme −0,363A; yataylaşınca UP_first %58,2, med +0,11A | 4.205 + 2.660 + 4.248 | SEN · S2 | U1 kuralı / G1: dikey rejimde ▲ bastırılır (kodda,0 vaka ihlal) |
| C4 | **Ayna: sert düşüşte üstü boş dikey direnç — eren dönüşler tepki sıçramasına yakalanır** | STEPPING_DOWN / REBASED_LOWER | — | SEN | G1 direnç cümlesi |
| C5 | **Doğrulanan5 geçişin hepsi "üstten alta"** | ustuasagi→altasagi +14,7/+17,4 · ustsabit→yapisik +7,4/+14,5 · ustyukari→altyukari +9,6/+13,2 … | 5.530 geçiş (119 sembol) | S2 | G1+G4: asimetri = üstten alta kırılım (0 OK-▲,5 OK-▼) |
| C6 | **Sığ kapı yeter; derin filtre çöker** | OK-▼ ailesi + rvol≥0,8 & gövde≥0,20 → DOWN %56,9/%57,4 (+12,8/+14,0) ✓✓; derin mum filtreleri MH OR0,85–0,93, p>0,28 | 466/188 | SEN A5/A3d | TYR mimarisi: **tek sığ kapı + doğru yapısal geçiş** (kırmızı çizgi5 doğrulandı) |
| C7 | **Yatay sabit dirençte dolu ▼, sert düşüş koşusu kanıtlar** | −2A önce %40,6/41,9 vs +2A önce %32,2/31,5 (+8,4/+10,5 ✓) | 927 (176 sembol) | OK §13 · SEN | direnç cümlesi: "üst boş → −2A koşu" |
| C8 | **Ok gürültüsü: okların %89'u aynı ▼ yapı uyarısının tekrarı** | 1.315 ok → U1▼1.176, gerçek▲139 (%11); denetim: şüpheli %79 | 50 sembol | OK §2 | seyreltme:20bar (§10); cümle sicili için tekrar sayacı |
| C9 | **Ok eşikleri kodda canlı** (K1 close_reclaim, K2 sweep, M1 taban kopuşu, M2 basamak momentum, U1 dikey bastırma) — **hacim şartı kaldırıldı** (§9) | hepsi eşik+3bar soğuma | — | OK §1, §9 | G1 kural seti (bozulmaz kural: dikeyken altı boşsa ▲ yok) |

## D) FORMASYON — G2'nin tecrübesi

| # | Genel ders | Ölçüm | n | Kaynak | Entegrasyon |
|---|---|---|---|---|---|
| D1 | **Formasyonların %76,2'si tamamlanır; %19,1'i başarısız kırılım; %4,7 geçersiz** | — | 32.321 | FRM-15 · AMP#1 | G2 ana cümlesi: "benzer 32.321 · %76'sı sürdü" |
| D2 | **Tamamlanan formasyon medyan11 bar sürer, teyitten sonra ~1,23A gider** | MFE med 1,23A (ÇGA 0,61–2,14) | 24.618 | FRM-16 | hedef/ufuk: formasyon hedefi kısa-orta |
| D3 | **Başarısız kırılım sert geri döner** | MAE med **2,83A** (ÇGA 2,00–4,00) | 6.186 | FRM-17 | stop: gürültü toleransı2,8A — erken stop zararı değil |
| D4 | **Olgunluk: medyan daralma %76,6** | geometri fazı medyan1 bar (apekse yakın doğum) | 33.964 | FRM-04 · BRIFING §3.1 | G2: "daralma %60'ken" bildiri eşiği |
| D5 | **Doz-yanıt: sınıra yakınlık kırılımı getirir** | min mesafe 0–0,5A → kırılım %95,6 · ≥2A → %17,6 | 32.551 / 17 (≥2A nadir) | FRM-06 | G2: "sınıra yakın" iddiası ölçülü |
| D6 | **Retest yaygın değil: %34,9, medyan1 barda gelir; retest hacmi düşükse +4,6p** | — | 28.624 (geri çekilme) | FRM-12/14 · AMP#4 | G2 retest cümlesi |
| D7 | **Kırılım anında zone varlığı formasyona YARDIM ETMEZ (hafif olumsuz)** | zone var %75,9 vs yok %77,0 (−1,1p); OB var −1,4p ✓ | 32.137 | FRM-19 | çapraz cümle: "bölge olmasa daha iyi" — kırılım-punktında OB beklentisi kırılır |
| D8 | **Kırılım-rol uyumu sıklığı %53,5 (şans eşiğinde) ama sonucu +6,4p** | uyum oranı %53,5 (tanımlayıcı) | 33.964 | FRM-08 + FRM-20 | ayrımı yaz: "sık" ≠ "önemli" |
| D9 | **Tip dağılımı + genişlik**: Alçalan Üçgen %28,8… medyan genişlik 0,34–0,52A; n<50 tipler yalnız sayı | — | 33.964 | FRM-02 | G2 tip cümlesi |
| D10 | **Öncül şart değil**: doğum öncesi20 bar getirisi medyan −0,04A | — | 33.964 | FRM-01 | G2: öncül hareket iddiası yok |

## E) GİRİŞ MEKANİZMASI & PLAN GEOMETRİSİ (Fazlar)

| # | Genel ders | Ölçüm | n | Kaynak | Entegrasyon |
|---|---|---|---|---|---|
| E1 | **Kırılım teyidi ucuza yakalanır: %76,3 ilk barda** (toplam %100 iki barda) | yol içi medyan +0,21A | 15.947 teyit | KT · SEN · BRIFING §5 | G5 giriş: "teyidin %76'sı ilk barda" |
| E2 | **Teyit alamamak felaket değil ama erken sinyal de değil** | teyit alamama: %0,4 ilk iki kapanışta +2A; %20,0 on mumda | 3.577 | KT | G3: "bekle" maliyeti ölçülü |
| E3 | **Aşağı teyitler yukarıdan güçlü** | 4s aşağı yol %49,3 (n377) vs yukarı %25,8 (n426) | 25.133 sonuç | KT | G3 yön dili |
| E4 | **Zemin teyidi (Faz6) çalışır ama tek başına kapı onarmaz** | teyit_red2.069 →990 plan, tutunma %32,4; yüksekten girişi yarıya indirdi; K2 +0,67/−2,24 → **6/7 GEÇMEDİ** | 990 | GZ Faz6 | teyit = giriş katmanı, hüküm (TYR) sürükleyici |
| E5 | **Baz geometri doğrulandı: stop1,0 / hedef1,5 /10bar** | beklenti **+0,090A**; durdurma %42,8 · hedef %34,6 · yok %22,7; keşif+0,0918 ↔ doğrulama+0,0870 | 15.808 | SS §2 | plan varsayılanı (Faz0) |
| E6 | **Maliyet şart:**0,10A tur-başı maliyette baz hücre −0,010A'ya düşer | ideal0,5/2,0 sıralaması maliyetle tersine döner | 15.808 | SS §2 | Faz2 maliyet modeli zorunlu |
| E7 | **Risk üst üste serilerde:** serilerin %60,7'si ≥3, %16,2'si ≥5; maks10 | streak kuralının beklentiye maliyeti −%1,7 | 15.808 | SS §2 · §6.3 | sermaye katmanı (günde2 stop tetiklenmedi) |
| E8 | **Durdurulanların %73–82'si geniş stopla bile kazanca dönmez** →1,0A stop korunur | p90 MAE (hedefe varanlar)1,48A | 8.326 (Faz0) | BRIFING §5 | stop yeri tartışması kapanmış |
| E9 | **H=15/20 zaman stopu RED** (uzatma işe yaramadı) | Faz7 K2 −4,46 (Faz6 −2,24 → Faz8 **+5,03 GEÇTİ**) | 990/990 | GZ Faz7/8 | zaman kapısı kapalı |
| E10 | **FAZ8 ana50 final:**412 plan, PF2,12, net+175,5A, kâr %55,8, kapı7/7 ✓ | K2 +5,03 (marj +0,03 — taze26 doğrulama adayı) | 412 | GZ Faz8 · ANA50_DETAY | kapı sonucu; K2 = UYGUN paketi vs kör baz |
| E11 | **Çıkış profili:** hedef %100 kârlı (+233A) · zaman %65 (+73A) · stop %0 (−131A) | kâr omuzu1–2A (111 işlem); zarar omuzu0,5–1A (90) | 412 | ANA50_DETAY | hedef/zaman ayrımı cümleleri |
| E12 | **Domain izin formatı KAZANCI AYRIŞTIRMAZ** | stop'ların %83'ü ↔ hedeflerin %82'si aynı kaynak kümesi (stabil/blok/formasyon); zemin412/412 ACTIVE | 412 | ZARAR_TESHISI §3–4 | **ders:** ayrım izinlerde değil giriş zamanlamasında |
| E13 | **Erken giriş her şeyi açıklamaz ama teşhisi taşır** | erken_girdi133 →112 stop (%84), küme net −99A; iyi_zamanlama233 →9 stop, **+257A** | 412 | ZARAR_TESHISI §2 | teşhis; ama ön-gözlem filtreleri kesilemez (I1) |
| E14 | **Tepeden yaklaşan (990 plan) ham bırakılan +2215,8A** — trailing/tampon/H20 RED; **ana50 öncelikli** | — | 990 | TEPEDEN_KLASIK | evren kararı |
| E15 | **Evren dersi:**70 sorunun3 kaynağı: kronik düşük likidite7, erken %39, doğrulama −0,07 | ana50:39 kârlı/11 zararlı sembol | 990+70 | DIGER70_TEŞHIS | G0 evren kapısı: ciro-top50 |

## F) HACİM — güvenilirlik ve koşullu kullanımdaki tecrübesi

| # | Genel ders | Ölçüm | n | Kaynak | Entegrasyon |
|---|---|---|---|---|---|
| F1 | **Sıfır hacim sistemli ve99,4'ü09:30 açılış müzayedesidir — çıkarılmaz** | 1s:59.604/558.724 sıfır; yalnız166'u09:30 dışı | 558.724 | KT · AR(arsiv notu) | `volume_usable` bayrağı; hilesiz okuma |
| F2 | **Dokunuş anında yüksek rvol ZAYIFLATır (A6 ile aynı ders)** | Q4 %61,0 vs Q1 %70,1 | 18.668 | AR §8 | G5 cümlesi: "hacim yüksek: %61 tepki verdi" |
| F3 | **Doğru bağlamda hacim yardımcı: retest hacmi düşükse +4,6p; OK-▼ sığ kapısı rvol≥0,8 ✓✓** | +14,0 lift doğrulama | 28.624 / 466 | FRM-14 · SEN | asla genelleme: **koşullu** kullan |
| F4 | **Hacim temelli asla kesinleştirilmez; golge zincirde hiç kullanılmıyor** (412/412 "hacim doğrulanmadı") | XU100/XU30'da hacim yok | 412 | BRIFING §10 · GZ | BOŞLUK J4: VP izin katmanında değil |
| F5 | *(ölçüm sınırları)* hacim endekslerinde KULLANILAMAZ; ortalamayı bozar | ayrı gösterilir | — | AR §8 | veri sözlüğü |

## G) VERİ / YAPISAL TUZAKLAR (yanlış ölçümü engelleyen dersler)

| # | Genel ders | Kaynak |
|---|---|---|
| G1 | **OB motoru dolan zone'u listesinden siler** — snapshot'tan ölçüm yasak (138 vs18 zone,7,7× eksik) | AR (tuzağ1) |
| G2 | **structural_role mutate olur** — final snapshot'ta2 PH/0 PL görünür; PH/PL soruları yalnız bar-bar rol izlemesiyle cevaplanır (273.583 aralık) | AR (tuzağ2) |
| G3 | **MS motoru canlıda sessiz çöküyor** (eski: %5,0 seri, sessiz degrade) — görünür uyarı kuralı doğdu | AR · denetim |
| G4 | **Sansür + TUM_ZONE:** sağdan sansür %0,3–14,6; kenar ölçümü temasların ~%77'si (TUM_ZONE %21–23 "OLCULEMEDI") | AR |
| G5 | **Tek rejim penceresi + likit177 sembol** — BREP harici; asimetri rejimde döner | AR · AMP §6 |
| G6 | **Bozuk OHLC/%30+ sıçrama karantinası +80 bar ısınma** ölçüm hijyeni | KT |

## H) ENTEGRE EDİLMEMİŞ / ÖLÇÜLMEMİŞ — sıradaki işin listesi

| # | Boşluk | Durum | Sıradaki adım (sözleşmeye göre) |
|---|---|---|---|
| H1 | **Sahne-bileşimi**: "dikey-direnç-testi", "onaysız-zemin-testi" gibi **çok-kişili sahneler → sonuç dağılımı** | Yok — her ders tek-idдia | Az sayıda ön-kayıtlı sahne, tek tek ölç (FAZ8 usulü) |
| H2 | **Cümle sicili (B4)**: her bildiri tipinin kendi geçmişi (tuttu mu, kaçıncı barda) | Sözleşmede var, kod yok | Basamak0–1 (defter zenginleştirme → rapor) |
| H3 | **Diyalog döngüsü**: takip_et → abone → fiyat → katmanı yeniden konuşturma | Sözleşmede §3, kod yok | En zor parça — en sona |
| H4 | **Hacim izin katmanı (VP)** | Motor var, izin yok (bilinçli) | Önce audit (F1) sonra ölç |
| H5 | **Formasyon üst sınırı hedefe dahil değil** | Yazılı bilinmeyen | Hedef geometrisi fazı (kapı ile) |
| H6 | **Karakterli stop** (yatay zemin vs dikey basamak) | Tasarım §5, kod tek formül | Karakter sınıfları + ölçüm |
| H7 | **TYR'ye zenginlik girişi** (kosul/seviye/görev TYR'e akıyor mu?) | Akmıyor → lehte sayacı | Basamak0: aktif bildiriler plana işlensin |
| H8 | **Rejim/genişlik** (evren-genişlik) | Açık kaldı (ay-filtresi overfit kapandı) | Genişlik ≠ ay filtresi; ayrı faz |

## I) ÇALIŞMAYAN / YASAKLANAN — tekrar denenmesin

| # | Ders | Kanıt |
|---|---|---|
| I1 | **Ön-gözlem giriş filtreleri** (mom10<−1, dip<0,5, R>5,5, stop<0,9, kombolar) — elenenlerin kendisi **pozitif** | ZARAR_TESHISI §10: mom10 elenen +46,4A, dip elenen +95,1A |
| I2 | **H=15/20 zaman stopu** | Faz7 K2 −4,46 RED |
| I3 | **Exit-side / stop-buffer / K2-by-H kolları** | kapalı (kullanıcı kararı) |
| I4 | **Rejim-AY filtresi** | overfit kapandı |
| I5 | **Derin mum filtreleri** | Mantel–Haenszel OR0,85–0,93, p>0,28 |
| I6 | **"Hacim teyit eder" filtresi** | ters (F2) |
| I7 | **▲ = hızlı ralli iddiası** | R1/R2 geçmedi; doğrulanmış tek iddia R3 "seviye tuttu" |
| I8 | **Zone3+ temas / zone içi-dışı satırları** | fark yok / eşik geçmez |
| I9 | **Dikeylik proxy'si fazla geniş** (838 eski aday bastırıldı) — tanım fiyat–çizgi boşluğuyla hizalanmalı | SEN (bileşik düzeltme) |
| I10 | **"%57-58 doğruluk düşük" yanılgısı** — hedef metrik kâr kapısı: PF ve beklenti geçti, tek sayı doygunluk yok | FAZ8 · TM §5 (tek sayı sunulmaz) |

---

*Kullanım sırası:* (1) domain cümlesi yazılacaksa bu envanterden satır + n + kaynak
alınır (uydurma yasağı); (2) yeni ölçüm varsa satır buraya eklenir; (3) §H
boşlukları faz planı olur — **hepsi önce ölç, sonra kapı, sonra hüküm.*

## I. (FAZ9 eki) B-1 — CONTRACTING filtresi: **RED** (2026-11-11)

- **Kural:** "zemin dinamiği CONTRACTING ise giriş açılmasın" (n188, +0,330A/işlem).
- **Sonuç:** kapı **6/7 GEÇMEDİ** (K1=47<50) — kalite arttı (K2+8,59 · K30,5795 ·
  PF2,46 · kârlı%58,5) ama doğrulama nüfusu90→47 düştü ve toplam net −62,1A.
- **Ders:** zayıf-grup-filtresi kaliteyi yükseltir, nüfusu ve toplam kârı kırar;
  **uyarı-mekanizması (B-1b/B-2) filtre-denemeden önce denenmeli.**
- Kayıt: `FAZ9_TECRUBE_ENTEGRE §6` + `kapi_karari_faz9b1.json`.

---

## J. (FAZ9 eki) B-turu + AUDIT — dersler (2026-11-11)

- **AUDIT (en büyük ders):** üç bağımsız sızıntı kapatıldı — (1) G5 tepki
  penceresi gelecek bar okuyordu (`i+1` kesiği,276/412 plan etkilenmişti),
  (2) **violation tarama penceresi çerçeve sonuna çakılıydı** (`n-1` yerine
  `safe_end_bar` — canlıda tesadüfen doğru, uzun replay'de erken barlar
  yanlıştı; dış denetimin çözülmemiş G2/G4 sorununun KÖKÜ), (3) zone_dolu
  terminal(gelecek) etiketi (407/412 sabit). **Kalıcı test:** `test_golge_kesme.py`
  — çerçeve kesilince tüm kayıtlar birebir (GEÇTİ).
- **Audit-öncesi B2–B5:4/4 RED** (FAZ9 §8): kesme-sınıfı (B2) kalite↑ n↓;
  hedef-özellik (B3) gizli filtre; karakterli-stop (B4) en yakın2; olgunluk-
  zenginliği (B5) en yakın (kârlı% −0,6pp) ve tek n-büyüten kol.
- **K1=43 yapısal yetmezlik:** küçük evren (ana50) kapıdan geçmeyi imkânsız
  kıldı → **evren=176 kararı** (FAZ9 §11, sıralama belirsizliği de kalktı).
- **K2 tek-işleme bağlı** (std hata≈7,4 puan) — bu nüfusta K2 tek başına
  ayırt edici değil; dörtlü şart gerekli.
- **Giriş zamanlaması hâlâ baskın kâr kaynağı** (erken-giriş teşhisi §5):
  hedef/stop kolları ikincil; kaldıraç girişte aranmalı (sahne/cümle ile).

## K. (FAZ9 eki) Ok-plan olay-dışıklığı — giriş-zamanlaması ilk denemesi (2026-11-12)

§13 ön-kayıdı (K1/K2▲ · girişten önce5 bar · baz176 planları633):
**HÜKÜM YOK.** `ok_var=1` =0/633 (4h-birim koşusu) ve1/633 (TF-doğru
koşu; doğrulama n=0).168 sembolde toplam160 K1/K2 (0,95/sembol);
planlara-en-yakın-ok >100 bar olan314/633. **Ders:** K1/K2 oku
(çizgi≤1,80 ATR) ile formasyon plan girişi **mekanik olarak ayrık olaylar**
—5-bar pencere bile değil,20-bar pencere bile n≥100 tavanı≈13'e takılır.
Yumuşak skor uygulanmadı (Q2-iii, ön-kayıt gereği). Tek istisna YKBNK4h
(hedef,+1,60A) — kanıt değil. Giriş-zamanlaması sıradaki denemesi farklı
özellikle (mesafe_atr/teyit yaşı) veya U1▼ hazard'ıyla ayrı ön-kayıtla.
Çıktı: `docs/arastirma/sonuclar/golge_zincir/ok_plan_zamanlama/`.

**Eki §14 (U1▼ tehlike):** aynı pencerede `u1_var=1` = **13/633**
(keşif9/doğrulama4; yön karışık) → n≥100 imkânsız, **HÜKÜM YOK**.
Ders: onay-kutusu K1/K2 ve tehlike-kutusu U1 **ikisi de** plan
girişiyle olay-dışık — ok-tabanlı özellikler plan ayrıştırması için
kapandı; kalan garantili kaynak **per-plan sürekli özellikler**
(mesafe_atr, teyit yaşı). Çıktı: `.../u1_plan_tehlike/`.
