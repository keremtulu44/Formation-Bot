"""Batch 8 / C2 (8.3) — Panel raporu: canlı durum artık PARAMETRE olarak alınır.

`main.py` içindeki `_panel_raporu` global durumu (LiveState, `_scan_job_active`,
`last_run_stats`, `ACTIVE_STOCKS`) okuyordu; bu yüzden metin üretimi main
döngüsünden bağımsız test edilemiyordu. Bu modülde aynı çıktı, dışarıdan verilen
bağlamla üretilir (davranış birebir aynı):

    durum             -> LiveState.status() çıktısı (dict)
    formations        -> LiveState.formations() listesi
    aktif_hisseler    -> tarama evreni (main'deki ACTIVE_STOCKS)
    tarama_suruyor    -> analiz işi sürüyor mu (main'de `_scan_job_active`)
    last_run_stats    -> son tarama kapsamı (processed/requested)
    kapsam_notu / bos_analiz_mesaji -> main'in durum metinleri

main.py'deki `_panel_raporu` bu fonksiyonu çağıran ince bir adaptördür.
"""

from datetime import datetime

from config import ISTANBUL_TZ
from telegram_commands import kirp

from reporting.format import (
    PANEL_IPUCU, PANEL_MESAJ_SINIRI, PANEL_TIMEFRAMES,
    filtrele_formasyonlar, gecen_sure, panel_durum_sayilari, panel_filtre_coz, panel_hucre,
    panel_kalite, panel_kritik_listesi, panel_sigdir, veri_durumu_satiri,
)


def panel_raporu(arguman: str, durum, formations, aktif_hisseler, tarama_suruyor: bool = False,
                 last_run_stats=None, tamamlandi: bool = False, kapsam_notu: str = "",
                 bos_analiz_mesaji: str = "", simdi=None) -> str:
    """48 hisse x 4 TF slot paneli: sayılar + puana göre top 12 aday. Filtre destekler.

    Filtre: `/panel 1h` · `/panel THYAO` · `/panel 1h THYAO` · `/panel kirilim`
    """
    now = simdi or datetime.now(ISTANBUL_TZ)
    st = durum or {}
    kolonlar, hisse_tokenlari = panel_filtre_coz(arguman, aktif_hisseler)
    satir_hisseler = list(aktif_hisseler)
    if hisse_tokenlari:
        satir_hisseler = [s for s in aktif_hisseler
                          if any(t in s.lower() for t in hisse_tokenlari)]
        if not satir_hisseler:
            return (f"🔍 '{arguman.strip()}' filtresine uyan hisse yok "
                    f"({len(aktif_hisseler)} hisse evreni).")
    filtreli = filtrele_formasyonlar(formations, arguman)

    # Slot haritası: (HISSE, tf) -> kayıt. LiveState hisse|TF başına tek kayıt tutar,
    # bu yüzden 48x4 = 192 slotun üzerine çıkılamaz (sayılar bu yüzden anlamlı).
    slot = {}
    for f in filtreli:
        tf = str(f.get("timeframe", "")).lower()
        hisse = str(f.get("stock", "")).upper()
        if hisse and tf in kolonlar:
            slot[(hisse, tf)] = f
    toplam_slot = len(satir_hisseler) * len(kolonlar)

    # --- başlık + sayılar (her modda tam görünür) ---
    filtresiz = not arguman.strip()
    kapsam = (f"{len(aktif_hisseler)} hisse x {len(PANEL_TIMEFRAMES)} TF" if filtresiz
              else f"{len(satir_hisseler)}/{len(aktif_hisseler)} hisse · "
                   f"{len(kolonlar)}/{len(PANEL_TIMEFRAMES)} TF")
    satirlar = [f"📋 PANEL — {kapsam} — {now.strftime('%d.%m.%Y %H:%M')}"]
    if not filtresiz:
        satirlar.append(f"Filtre: {arguman.strip()}")
    durum = st.get("son_tarama_durumu", "yok")
    tarama = f"Son başarılı tarama: {gecen_sure(st.get('son_tarama_bitis'))} · durum {durum}"
    if st.get("tarama_suruyor") or (tarama_suruyor and not tamamlandi):
        tarama = "Analiz sürüyor"
    if durum == "basarisiz":
        kapsam_is = (f"{(last_run_stats or {}).get('processed', st.get('son_is_hisse_basarili', 0))}/"
                     f"{(last_run_stats or {}).get('requested', st.get('son_is_hisse_istek', len(aktif_hisseler)))}")
        tarama += f" · son deneme başarısız ({kapsam_is} hisse hesaplandı)"
    elif durum == "tamamlandi":
        tarama += (f" · hesaplanan {st.get('son_tarama_hissesi', '—')}/"
                   f"{st.get('son_tarama_beklenen_hisse') or len(aktif_hisseler)} hisse")
    satirlar.append(f"{tarama} · dolu slot {len(slot)}/{toplam_slot}")
    veri_zamani = st.get("son_tarama_veri_zamani")
    if veri_zamani:
        satirlar.append(veri_durumu_satiri(
            veri_zamani, st.get("son_tarama_taze_veri"),
            st.get("son_tarama_beklenen_hisse"), st.get("son_tarama_fetch_hatasi"),
            st.get("son_tarama_en_eski_veri_yasi_dk"),
        ))
    if kapsam_notu:
        satirlar.append(kapsam_notu)
    if st.get("snapshot_yuklendi"):
        satirlar.append("♻️ Önceki kayıt gösteriliyor; güncel analiz için /panel çalıştırılıyor.")
    satirlar.append("")
    satirlar.append("📊 SAYILAR")
    tf_parcalari = []
    for tf in kolonlar:
        kayitlar = [slot[(h, tf)] for h in satir_hisseler if (h, tf) in slot]
        if kayitlar:
            ort = sum(panel_kalite(k) for k in kayitlar) / len(kayitlar)
            tf_parcalari.append(f"{tf} {len(kayitlar)}/{len(satir_hisseler)} ort q{ort:.0f}")
        else:
            tf_parcalari.append(f"{tf} 0/{len(satir_hisseler)}")
    satirlar.append(" · ".join(tf_parcalari))
    satirlar.append(panel_durum_sayilari(filtreli))
    # Eşik altı adaylar: liste ve sayaçlarda görünürler ama alarm ÜRETMEZLER.
    # (Eskiden yalnız debug log'da düşüyorlardı; kullanıcı "kaç tanesi
    # gösterilmiyor?" sorusunu hiçbir yerden göremiyordu.)
    esik_alti = 0
    for f in filtreli:
        esik = f.get("min_quality")
        if esik is None:
            continue
        try:
            if panel_kalite(f) < float(esik):
                esik_alti += 1
        except (TypeError, ValueError):
            continue
    if esik_alti:
        satirlar.append(f"⚠️ {esik_alti} aday alarm eşiğinin altında (listelenir, push üretmez)")
    if st.get("son_tarama_durumu") == "basarisiz":
        satirlar.append("⚠️ Son tarama eksik/başarısız; bu panel boşluğu sinyal yokluğu değildir.")
    elif not formations:
        satirlar.append(bos_analiz_mesaji)
    sabit_kuyruk = [""] + panel_kritik_listesi(filtreli) + ["", PANEL_IPUCU]

    # --- slot tablosu: önce tam (boş slotlar '—'), sığmazsa kompakt ---
    grid_tam = [f"{h} " + " · ".join(panel_hucre(slot.get((h, tf)), tf) for tf in kolonlar)
                for h in satir_hisseler]
    if not slot:
        # Hiç dolu slot yok (taze kurulum ya da filtre hiçbir şeye uymadı): 48 satır
        # '—' yazmak yerine tek satırda söyle; sayılar ve top 12 zaten durumu anlatıyor.
        grid_tam = [f"— tüm slotlar boş ({len(satir_hisseler)} hisse x {len(kolonlar)} TF)"]
    metin = "\n".join(satirlar + [""] + ["🗂 SLOTLAR (" + " · ".join(kolonlar) + ")"] +
                      grid_tam + sabit_kuyruk)
    if len(metin) > PANEL_MESAJ_SINIRI:
        # Kompakt: boş slotlar yazılmaz, hiç slotu dolmayan hisseler tek satırda toplanır.
        grid_kisa, bos = [], []
        for h in satir_hisseler:
            dolu = [panel_hucre(slot[(h, tf)], tf) for tf in kolonlar if (h, tf) in slot]
            if dolu:
                grid_kisa.append(f"{h} " + " · ".join(dolu))
            else:
                bos.append(h)
        if bos:
            grid_kisa.append(f"boş ({len(bos)}): " + " ".join(bos))
        govde = satirlar + [""] + ["🗂 SLOTLAR (kompakt)"] + grid_kisa + sabit_kuyruk
        metin = "\n".join(govde)
        if len(metin) > PANEL_MESAJ_SINIRI:
            # Aşırı kalabalık gün: grid kırpılır, sayılar ve TOP 12 korunur.
            sabit = satirlar + [""] + ["🗂 SLOTLAR (kompakt)"]
            butce = PANEL_MESAJ_SINIRI - sum(len(s) + 1 for s in sabit + sabit_kuyruk)
            metin = "\n".join(sabit + panel_sigdir(grid_kisa, max(butce, 0)) + sabit_kuyruk)
    # Son güvenlik: desen adları çok uzun olsa bile Telegram'ın 4096 sınırını aşma.
    return kirp(metin, PANEL_MESAJ_SINIRI + 200)
