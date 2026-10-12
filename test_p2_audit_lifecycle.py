# --- FAZ 2 FİNAL AUDİT: YAŞAM DÖNGÜSÜ REGRESSİYON TESTLERİ -------------
#
# Bu dosya P2.6 öncesi yapılan "Formation history tamamlandı mı?" auditinin
# ölçümlerini regression testine döker. Amaç: audit sırasında doğrulanan
# davranışın ileride sessizce bozulmasını engellemek.
#
# KAPSAM (yalnızca history/persistence gözlemi — matematik DEĞİŞMEZ):
#   1. Tek formation'ın 7 aşamasının HEPSİ aynı `stable_id` taşıyor.
#   2. Zincir sonunda history kaydında 8 kısımın tamamı var.
#   3. P2.0'da "henüz persist edilmeyen" (INCELENMELI) işaretlenmiş 48 alanın
#      tamamı gerçekten diske yazılıyor.
#   4. Kırılım doğrulama anında dondurulan `break_confirmation_strength`
#      gerçekten history'ye ulaşıyor (auditte neredeyse "kayıp" sanıldı).
#   5. TRANSIENT alanlar history'ye sızmıyor; şema dışı alan yok.
#   6. Motor seviyesindeki `invalid_reason` BİLİNÇLİ olarak history'de değil
#      (kontrat dışıdır — kayıp değil, bilinçli sınır).
#
# Buradaki hiçbir test formation matematiğini değiştirmez; yalnızca mevcut
# motorun ürettiği history'yi okur ve kontratı doğrular.

from datetime import datetime

import pandas as pd

import karne as K
from state import formation_history as fh
from state import formation_schema as schema
from state import outcome_link as ol

from test_breakout_retest_terminal import (  # noqa: F401  (ortam fixture)
    _kirilim_retest_zinciri,
    _retest_senaryosu,
    _turler,
    ortam,
    _STOCK,
    _TF,
)
from test_formation_history import _kanalli_pennant

# ---------------------------------------------------------------------
# 7 aşama — Requirement 2'nin "ana testi": her aşamada stable_id kaydedilir.
# ---------------------------------------------------------------------
_ASAMALAR = ("dogum", "geometri", "olay", "kirilim", "retest", "terminal", "outcome")

# Karne kırılım kaydı için outcome ölçülebilir sabit seri (hedefe ulaşır).
# NOT: damga `localize` ile üretilmeli — sabit ofsetli ("+03:00") bir Timestamp
# `date_range(tz="Europe/Istanbul")` içinde pandas tarafından reddedilir.
_OUTCOME_BAR = K.ISTANBUL_TZ.localize(datetime(2026, 10, 1, 10, 30))


def _outcome_serisi():
    """Hedefe ulaşan (DURUM_HEDEF) sabit ileri seri — 12 bar."""
    kap = [100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0,
           103.5, 104.0, 104.0, 104.0, 104.0]
    return pd.DataFrame({
        "open": [c - 0.02 for c in kap], "high": [c * 1.002 for c in kap],
        "low": [c * 0.998 for c in kap], "close": kap, "volume": [1] * 12},
        index=pd.date_range(_OUTCOME_BAR, periods=12, freq="h",
                            tz="Europe/Istanbul"))


def _outcome_bagla(sid):
    """Verilen stable_id için Karne kırılım kaydı yazıp outcome'ı bağlar."""
    bar = _OUTCOME_BAR
    defter = K.KarneDefteri()
    defter.kirilim_kaydet(_STOCK, _TF, "Boğa Flaması", "KIRILIM_TEYITLI", 1,
                          100.0, 2.0, 80.0, bar, stable_id=sid)
    return ol.bagla(defter, _STOCK, _TF, sid, saglayici=lambda s, t: _outcome_serisi())


def _asama_sidleri(rec):
    """Bir history kaydından aşama -> {stable_id,...} haritası çıkarır."""
    cikar = {a: set() for a in _ASAMALAR}

    # 1) doğum
    cikar["dogum"].add(rec.get("stable_id"))
    cikar["dogum"].add((rec.get("dogum") or {}).get("stable_id"))

    snapshots = rec.get("snapshotlar") or []
    for snap in snapshots:
        tur = snap.get("tur")
        if tur in ("geometri", "kirilim", "retest", "terminal"):
            cikar[tur].add(snap.get("stable_id"))

    # 3) yaşam döngüsü olayları
    for olay in rec.get("olaylar") or []:
        cikar["olay"].add(olay.get("stable_id"))

    # 7) outcome — kaydın kendi stable_id'i üzerinden bağlanır
    if rec.get("sonuc"):
        cikar["outcome"].add(rec.get("stable_id"))

    return {a: {s for s in v if s} for a, v in cikar.items()}


# =====================================================================
# 1) ANA TEST: 7 aşama tek stable_id
# =====================================================================

def test_yasam_dongusu_yedi_asama_tek_sid(ortam):
    """Gerçek motorla sürülen tek formation: 7 aşamanın HEPSİ aynı stable_id.

    `len(unique(sid)) == 1` olmalı. Herhangi bir aşamada SID kaybolur veya
    değişirse bu test başarısız olur — Requirement 2'nin doğrudan testi.
    """
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar and durumlar[-1] == "FORMASYON_TAMAMLANDI", (
        "senaryo terminal'e ulaşmadı: %s" % durumlar)

    defter = fh.yukle(_STOCK, _TF)
    kayitlar = fh.kayitlar(defter)
    assert len(kayitlar) == 1, "tek formation bekleniyordu: %d kayıt" % len(kayitlar)
    rec = kayitlar[0]
    sid = rec["stable_id"]

    # Outcome bağla (Karne kırılım kaydı + mevcut sinyal_sonucu).
    ozet = _outcome_bagla(sid)
    assert ozet is not None, "outcome bağlanamadı"
    assert ozet["durum"] == K.DURUM_HEDEF

    rec = fh.kayit_getir(fh.yukle(_STOCK, _TF), sid)
    assert rec is not None and rec.get("sonuc"), "outcome history'ye yazılmadı"

    sidler = _asama_sidleri(rec)

    # Her aşama GERÇEKTEN bir SID taşıyor mu?
    bos = [a for a, v in sidler.items() if not v]
    assert not bos, "şu aşamalarda stable_id yok: %r" % bos

    tum = set()
    for asama, v in sidler.items():
        tum |= v
        assert v == {sid}, "aşama %r yabancı SID taşıyor: %r" % (asama, sorted(v))

    assert len(tum) == 1, "SID süreksiz: %r" % sorted(tum)


# =====================================================================
# 2) History bütünlüğü: 8 kısım
# =====================================================================

def test_yasam_dongusu_butun_kisimlar_historyde(ortam):
    """Zincir sonunda kayıt: kimlik, doğum, geometri, olaylar, kırılım,
    retest, terminal, outcome kısımlarının TAMAMINI içerir."""
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar[-1] == "FORMASYON_TAMAMLANDI"

    rec = fh.kayitlar(fh.yukle(_STOCK, _TF))[0]
    sid = rec["stable_id"]
    _outcome_bagla(sid)
    rec = fh.kayit_getir(fh.yukle(_STOCK, _TF), sid)

    kisimlar = {
        "kimlik": rec.get("stable_id"),
        "dogum": (rec.get("dogum") or {}).get("alanlar"),
        "geometri": [s for s in rec.get("snapshotlar", []) if s.get("tur") == "geometri"],
        "olaylar": rec.get("olaylar"),
        "kirilim": [s for s in rec.get("snapshotlar", []) if s.get("tur") == "kirilim"],
        "retest": [s for s in rec.get("snapshotlar", []) if s.get("tur") == "retest"],
        "terminal": rec.get("terminal_state"),
        "outcome": rec.get("sonuc"),
    }
    eksik = [k for k, v in kisimlar.items() if not v]
    assert not eksik, "history'de eksik kısımlar: %r" % eksik

    # Geometri snapshot'ları anlamlı geçişlerle sınırlı (per-bar dump değil).
    turlar = _turler(rec)
    assert turlar.get("kirilim", 0) >= 2, "freeze + teyit beklenir: %r" % turlar
    assert turlar.get("terminal") == 1, "tek terminal snapshot: %r" % turlar
    assert len(rec["olaylar"]) <= fh.MAX_OLAY
    assert len(rec["snapshotlar"]) <= fh.MAX_SNAPSHOT


# =====================================================================
# 3) Kontrat kapsamı: INCELENMELI alanlar gerçekten persist ediliyor
# =====================================================================

def test_incelenmeli_alanlar_gercekten_historyde(ortam):
    """P2.0'da 'henüz persist edilmeyen' diye işaretlenmiş alanların tamamı
    artık diske yazılıyor. Eksik kalan varsa kontrat bozulmuş demektir."""
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar[-1] == "FORMASYON_TAMAMLANDI"

    rec = fh.kayitlar(fh.yukle(_STOCK, _TF))[0]
    persist_edilen = set()
    persist_edilen |= set((rec.get("dogum") or {}).get("alanlar") or {})
    for snap in rec.get("snapshotlar") or []:
        persist_edilen |= set(snap.get("alanlar") or {})

    incelenmeli = set(schema.INCELENMELI)
    assert incelenmeli, "INCELENMELI boş — liste bozulmuş"
    kapsanmayan = incelenmeli - persist_edilen
    assert not kapsanmayan, (
        "INCELENMELI olarak işaretli ama history'ye yazılmayan alanlar: %r"
        % sorted(kapsanmayan))


# =====================================================================
# 4) Kırılım alanları: doğrulama anında dolu
# =====================================================================

def test_breakout_alanlari_dogrulanma_aninda_dolu(ortam):
    """`break_confirmation_strength` kırılım teyit anında history'ye ulaşır.

    Audit sırasında neredeyse "kayıp" olarak rapor edilecekti: dondurma
    (KIRILIM_DENEMESI) anında değer None'dır çünkü teyit henüz olmamıştır.
    Teyit (KIRILIM_TEYITLI) anında alan gerçekten dolu olmalıdır.
    """
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar[-1] == "FORMASYON_TAMAMLANDI"

    rec = fh.kayitlar(fh.yukle(_STOCK, _TF))[0]
    kir = [s for s in rec.get("snapshotlar", []) if s.get("tur") == "kirilim"]
    stateler = {s.get("state") for s in kir}
    assert stateler, "kırılım snapshot'ı yok"

    teyit = [s for s in kir if s.get("state") == "KIRILIM_TEYITLI"]
    assert teyit, "kırılım teyit snapshot'ı yok: %r" % sorted(stateler)
    alanlar = teyit[-1].get("alanlar") or {}
    assert "break_confirmation_strength" in schema.BREAKOUT_FIELDS
    assert alanlar.get("break_confirmation_strength") is not None, (
        "teyit anında break_confirmation_strength boş — freeze geri alınmış?")

    # Dondurma anında None olması DOĞRUDUR (teyit henüz yok).
    deneme = [s for s in kir if s.get("state") == "KIRILIM_DENEMESI"]
    if deneme:
        assert (deneme[0].get("alanlar") or {}).get(
            "break_confirmation_strength") is None, (
            "dondurma anında teyit gücü dolu olmamalı")


# =====================================================================
# 5) Şema disiplini: TRANSIENT sızıntısı yok, şema dışı alan yok
# =====================================================================

def test_transient_sizintisi_ve_sema_disi_alan_yok(ortam):
    """History'ye yazılan alanların hiçbiri TRANSIENT değil; hiçbiri şema
    dışı değil. Bu, "transient field yanlışlıkla persist ediliyor mu?"
    sorusunun ölçümüdür."""
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar[-1] == "FORMASYON_TAMAMLANDI"

    rec = fh.kayitlar(fh.yukle(_STOCK, _TF))[0]
    persist_edilen = set()
    persist_edilen |= set((rec.get("dogum") or {}).get("alanlar") or {})
    for snap in rec.get("snapshotlar") or []:
        persist_edilen |= set(snap.get("alanlar") or {})

    assert persist_edilen, "hiç alan persist edilmemiş"
    sizinti = persist_edilen & set(schema.TRANSIENT_FIELDS)
    assert not sizinti, "TRANSIENT alanlar history'ye sızmış: %r" % sorted(sizinti)
    disi = persist_edilen - set(schema.ALL_FIELDS)
    assert not disi, "şemada tanımlı olmayan alanlar yazılmış: %r" % sorted(disi)


# =====================================================================
# 6) Bilinçli sınır: motor seviyesi `invalid_reason` kontrat dışıdır
# =====================================================================

def test_motor_seviyesi_invalid_reason_bilincli_olarak_historyde_degil(ortam):
    """`ArgentEngine.invalid_reason` kontratın (85 alan) dışındadır ve
    history'ye YAZILMAZ.

    Bu BİLİNÇLİ bir sınırdır, kayıp değildir: alan motor içinde her bar
    yeniden hesaplanan bir teşhis metnidir ve `PatternCandidate`'ın parçası
    değildir. Eğer ileride terminal nedeni de persist edilmek istenirse
    bu test güncellenmeli (audit raporunda "MINOR FOLLOW-UP" olarak not
    edilmiştir). Testin amacı: alanın sessizce ve kontrolsüz sızmasını
    önlemek.
    """
    mgr, durumlar = _kirilim_retest_zinciri(_retest_senaryosu())
    assert durumlar[-1] == "FORMASYON_TAMAMLANDI"

    rec = fh.kayitlar(fh.yukle(_STOCK, _TF))[0]
    persist_edilen = set()
    persist_edilen |= set((rec.get("dogum") or {}).get("alanlar") or {})
    for snap in rec.get("snapshotlar") or []:
        persist_edilen |= set(snap.get("alanlar") or {})

    assert "invalid_reason" not in persist_edilen, (
        "invalid_reason beklenmedik şekilde history'ye girmiş — kontrat dışı "
        "alanın bilinçli sınırını taşıyor; audit raporunu güncelleyin")

    # Terminal nedeni olarak `terminal_state` zaten persist ediliyor.
    assert rec.get("terminal_state") == "FORMASYON_TAMAMLANDI"
