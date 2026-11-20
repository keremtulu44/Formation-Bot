# ALARM YÖNÜ — ölçüm ne diyorsa o

> **Durum:** Öneri (kural değişikliği YOK) · **Tarih:** 2026-11-19
> **Dayanak:** [`DOMAIN_ALARM_REPLAY.md`](DOMAIN_ALARM_REPLAY.md) (704 seri, 334.191 tetik + 162.810 taban) ·
> [`REPLAY_ANA_DERLEMESI.md`](REPLAY_ANA_DERLEMESI.md) §5.7/§5.8 · R19/R21/R22
> **Ne yapar:** mevcut alarm tasarımının neden "tetiklendiği için" hissi verdiğini
> ölçümle açıklar ve **alternatif bir yön** önerir.
> **Ne yapmaz:** canlı kodu değiştirmez; eşik/kural önermez, **çerçeve** önerir.
>
> ⚠️ **GÜNCELLEME (aynı gün):** Bu dosyadaki 4 katmanlı öneri, yarı evren
> politika koşusuyla **kısmen düzeltildi**. Ölçüm: kanal katmanı (Katman 0)
> isabet kazandırmıyor; **bağlam filtresi** kazandırıyor. Düzeltilmiş sonuçlar
> ve 3 seçenek: [`ALARM_POLITIKA_SONUCLARI.md`](ALARM_POLITIKA_SONUCLARI.md).
> Özellikle §5 ("Üç seçenek") ve §2 (P4/P6 satırları) buradaki §3'ün yerine geçer.

---

## 1 · Tek cümlelik teşhis

> **Alarm bir "olay bildiricisi" olarak çalışıyor; ölçüm ise onu bir "nadirlik
> dedektörü" olarak çalıştırmamız gerektiğini söylüyor.**

Sebep tek bir sayıda: **taban oranı %64,1.** Yani rastgele bir barda, hiçbir alarm
olmadan, 12 bar içinde ≥1 ATR hareket görme olasılığı **%64**. Alarmlı barlarda bu
**%66,5**. Fark **+2,4 pp**. Bu, "alarm işe yarıyor" demek için çok az; "alarm
gürültünün üstüne %2,4 pp biniyor" demek için yeterli.

Kullanıcının şikâyeti ("değerli olduğu için değil, tetiklendiği için geliyor")
bu sayıyla birebir örtüşüyor.

---

## 2 · Ölçümün söylediği 6 şey

| # | Bulgu | Sayı | Ne demek |
|---|---|---|---|
| 1 | **Kapsam ≠ değer** | tetiklerin **%56'sı OB** (+1,7 pp), **%2,5'i HACIM** (+7,3 pp) | En çok konuşan kanal en az bilgi taşıyor |
| 2 | **Kombinasyon seyreltiyor** | HACIM tek başına **%71,6**; HACIM+OB **%67,9**; FORMASYON+HACIM+OB **%65,9** | "Daha çok kanal ateşledi" **daha kötü** sonuç. Mevcut sistem tam tersini varsayıyor |
| 3 | **Belirsizlik azalmıyor** | tetik %30,5 iki yöne de ≥1 ATR · taban %30,4 | Alarm "iki yönlü oynaklık" diyor; yön söylemiyor |
| 4 | **Tekrar bilgi taşımıyor** | tetiklerin **%65,3'ü** cooldown ile susturuluyor; sonuç farksız (%66,1 vs %67,4) | Kartların üçte ikisi aynı bilginin tekrarı |
| 5 | **BOS zararlı** | tetiklediğinde aleyhte ≥1 ATR **%73,5**, iki yöne de **%36,2** (taban %30,4) | Tek başına alarm olarak gürültü ekliyor, bilgi değil |
| 6 | **Nadirlik değerli** | en iyi segment **HACIM × yukarı koşu %74,7** (n=4.075, z=+13,9) | Bir alarm ne kadar **az** ve ne kadar **bağlamlıysa** o kadar iyi |

**6. maddenin kanıtı daha net:** HACIM kanalı 334.191 tetiğin **%2,5'i**; buna
rağmen tabandan en büyük farkı (+7,3 pp) o üretiyor. OB tetiklerin %56'sı ve farkı
+1,7 pp. **Nadirlik ile değer arasında ters oran var.**

---

## 3 · Önerilen yön: 4 katman, tek kural

Bugünkü sistem: *"kanallardan biri ateşlerse kart bas"*.
Önerilen: *"ateşleyen kanal sayısı değil, **nadirlik + bağlam** karar verir."*

| Katman | Ne zaman | Ne gönderilir | Neden |
|---|---|---|---|
| **0 · Sessiz** | yalnız OB / FVG / BOS tetikledi | **hiçbir şey** (günlük özete satır) | Bunlar tetiklerin %70'i; farkları +1,7/+2,8/−2,0 pp. Tek tek kart değmez |
| **1 · Özet satırı** | formasyon state değişimi + zone dokunuşu | günlük **tek** mesajda sembol · state · ATR uzaklık | R21'in dersi: aynı uyarının tekrarı; tek mesajda toplanınca değerli |
| **2 · Kart** | **HACIM ≥5×** veya **HACIM + FORMASYON** birlikte | bugünkü kart (kısaltılmış) | En güçlü kanal + en güçlü kombinasyon (%73,2) |
| **3 · Çizim** | Katman 2 **ve** tetik 09:00–10:00 veya 17:00 seansında | grafik (aşağıdaki tasarım) | Saat segmentleri %75–77; günde en fazla 1–2 tane |

**Tek kural:** Bir alarmın değeri, **kaç kanalın ateşlediğiyle değil**, o kanalın
taban farkıyla ve nadirliğiyle ölçülür.
> **Düzeltme:** Politika koşusu bunun **yalnız yarısını** doğruladı. Kanal farkı
> gerçek ama küçük; onu elemek isabet kazandırmıyor. Kazandıran şey **bağlam**. Bu, bugünkü "çok kanal = güçlü sinyal"
varsayımının **ölçümle çürütülmesidir** (2. madde).

**Ne zaman uygulanmaz:** Bu bir *önerme*dir. Katman 0'ı uygulamak, bugün giden
kartların ~%70'ini keser; bu kullanıcı kararıdır, ölçüm kararı değil.

---

## 4 · Grafik nasıl daha anlamlı olur — 5 tasarım kuralı

Sorunuzun ikinci yarısı: *"daha net grafikler nasıl çıkarırız?"* Ölçümün doğrudan
söylediği 5 kural:

### Kural 1 — **Yön oku çizme, aralık konisi çiz.**
Ölçüm: tetiklerin %30,5'i 12 barda **iki yöne de** ≥1 ATR görüyor; medyan tepe
3,19 ATR **her iki yönde de** (MFE≈MAE). Yani ok, ölçümün yalan söylediği tek şey.
Yerine: tetikten sonraki 12 bar için **beklenen aralık konisi** (medyan 3,2 ATR
üst/alt). Grafik "şuraya gidecek" değil, **"bu kadar oynayabilir, iki yöne de"** der.
R21 zaten söylüyor: 1.315 okun **%89'u ▼ aynı uyarının tekrarı**, %79 şüpheli.

### Kural 2 — **Tekrar sayısını çiz, seviyeyi değil.**
Ölçüm: Stabil **2. temas +0,32 ATR**, **3.–4. temas −0,67 ATR**; OB tekrar
denenir, FVG **tek kullanımlık** (%0,0 üçüncü temas). Grafikte bölgeye
"**1. / 2. / 3. temas**" etiketi konur; 3+ ise bölge **griye** düşer, "tükendi"
yazar. FVG dolarsa **çizgi silinir** — bugün ikinci kez çizilmesi ölçümle çelişir.

### Kural 3 — **Bağlamı ölçü olarak yaz, sıfat olarak değil.**
Ölçüm: en değerli tetiklerde **6 bar koşu yukarı** (+10,6 pp), **sıkışma** ve
**ATR yüzdeliği** gibi bağlamlar ayrıştırıcı. Kart/grafik "güçlü sinyal" demek
yerine üç ölçü basmalı: `sıkışma 0,34 · koşu +1,8 ATR · ATR yüzdelik %82`.
Bunlar zaten hesaplanıyor (`bagl_*` sütunları) — sadece **karta yazılmıyor**.

### Kural 4 — **Hacmi "teyit" diye etiketleme.**
Ölçüm: OB'de Q1 %66,9 → Q4 **%61,4** (ters); ama alarm tarafında HACIM **+7,3 pp**.
Doğru cümle: "hacim **dikkat** çekiyor", "hacim **teyit etti**" değil. Kart
metninde "onaylandı/teyit" kelimesi ölçümle **çelişir**.

### Kural 5 — **Grafiği nadir tut.**
Ölçüm: günde 37 kartlık hacimde grafik değersizleşiyor; cooldown %65'i zaten
kesiyor. Öneri: **günde en fazla 1–2 grafik**, yalnız Katman 3. Grafik az
olduğunda "geldi" demek bilgi taşır; her saat geldiğinde taşımaz.

---

## 5 · Bu yönün test edilebilir olması (önemli)

Öneri, "bence daha iyi olur" değil; **ölçülebilir** olacak şekilde yazıldı. Aynı
replay hattıyla 4 soru cevaplanabilir:

| Soru | Nasıl ölçülür | Bugünkü cevap |
|---|---|---|
| Katman 0'ı kapatsam ne kaybederim? | yalnız-OB/FVG/BOS satırlarının taban farkı | +1,7 / +2,8 / −2,0 pp — **kayıp yok** |
| Katman 2'ye geçsem kaç kart/gün? | HACIM ≥5× sayısı / gün | 8.213 tetik / ~365 gün / 176 sembol ≈ **0,13/sembol/gün** |
| Kombinasyon gerçekten seyreltiyor mu? | kanal kombinasyon tablosu (§2) | Evet: HACIM 71,6 → HACIM+OB 67,9 |
| Konili grafik "yanlış yön" hissini azaltır mı? | kullanıcıya A/B: ok vs koni | **ölçülmedi** — tek eksik bu |

Son satır dürüst olmak için var: **kullanıcı algısı ölçülmedi.** Ölçüm "ok
yanıltıcı" diyor ama "koni daha iyi hissettiriyor"u **kanıtlamıyor**. Bunun için
10–15 kartlık bir A/B gerekir.

---

## 6 · Karar tablosuna eklenmesi gerekenler

`REPLAY_ANA_DERLEMESI.md` §7.5'e girmesi önerilen satırlar:

| Karar | Dayanak | Neden |
|---|---|---|
| **Yapılabilir:** Kanal değerine göre katman (0/1/2/3) | R37 | HACIM +7,3 · OB +1,7 · BOS −2,0 |
| **Yapılabilir:** BOS'u tek başına alarm saymamak | R37 | aleyhte %73,5, iki yöne de %36,2 |
| **Yapılabilir:** Cooldown'u korumak (hatta artırmak) | R37 | %65,3 tekrar, kayıp yok |
| **Güvenilemez:** "Çok kanal ateşledi = güçlü sinyal" | R37 §2 | HACIM+OB (67,9) < HACIM (71,6) |
| **Güvenilemez:** Yön oku | R21, R37 | okların %89'u tekrar; tetiklerin %30,5'i iki yönlü |
| **Ölçülmedi:** Koni grafiğin algısı | — | A/B testi gerekir |

---

## 7 · Özet — ne düşünüyorum

1. **Evet, bir yön belirledik.** Ama "hangi eşiği değiştirelim" değil: **alarmın
   ne olduğunu** değiştirmek gerekiyor. Bugün *olay bildiricisi*, ölçüm
   *nadirlik dedektörü* istiyor.
2. **En büyük tek kazanç grafikte değil, elemelerde:** katman 0'ı kapatmak
   kartların ~%70'ini keser ve ölçülen kayıp **+1,7 pp**'nin altında.
3. **En büyük tek risk yanlış yön hissi:** ok çizmek. Ölçüm iki yönlü oynaklık
   diyor; ok tek yön söylüyor. Konili aralık, ölçümün söylediğini çizen tek şey.
4. **Sıradaki adım (öneri):** Katman 2 kartını ve konili grafiği **tek sembolde**
   prototiple, 10–15 kartlık A/B yap. Kod tarafı: `bot/domain_alarm_service.py`
   (katman seçimi) + `grafik/` (koni çizimi). Canlıya dokunmadan.
