# -*- coding: utf-8 -*-
"""Faz 4 — sermaye kuralları testleri (streak, gün durdurma, tavan)."""

from senaryo.kurallar import gun_durdur_uygula, streak_uygula, tavan_uygula


def _kayit(sym, tf, bar, sonuc, t_gun="2026-06-01", saat="10:00"):
    return {
        "plan_id": f"{sym}-{tf}-{bar}", "sembol": sym, "tf": tf,
        "bar_index": bar, "sonuc": sonuc,
        "t": f"{t_gun}T{saat}:00+03:00", "pnl_atr": -1.0 if sonuc == "stop" else 1.5,
        "H": 10,
    }


# --- streak ----------------------------------------------------------------
def test_streak_uc_stoptan_sonrakini_atlar():
    kayitlar = [_kayit("A", "4h", i, "stop") for i in (10, 30, 50)]
    kayitlar += [_kayit("A", "4h", 70, "hedef")]
    out, ozet = streak_uygula(kayitlar)
    assert [r["kural"] for r in out] == ["kural_yok", "kural_yok", "kural_yok",
                                         "streak_atla"]
    assert ozet["atlanan"] == 1


def test_streak_atlama_sayaci_sifirlar():
    # 3 stop → 1 atla (sayaç sıfır) → sonrası tekrar sayılır
    kayitlar = [_kayit("A", "4h", i, "stop") for i in (10, 30, 50)]
    kayitlar += [_kayit("A", "4h", 70, "hedef")]      # atlandı, sayaç 0
    kayitlar += [_kayit("A", "4h", 90, "stop")]       # 1
    out, _ = streak_uygula(kayitlar)
    assert out[4]["kural"] == "kural_yok"   # 5. kayıt (atlamadan sonra)


def test_streak_seriler_birbirinden_bagimsiz():
    kayitlar = [_kayit("A", "4h", i, "stop") for i in (10, 30, 50)]
    kayitlar += [_kayit("B", "4h", 10, "stop")]       # B'nin ilki
    out, _ = streak_uygula(kayitlar)
    assert out[3]["kural"] == "kural_yok"             # B serisi etkilenmedi


def test_streak_ozet_metrikleri():
    kayitlar = [_kayit("A", "4h", i, "stop") for i in range(0, 100, 20)]  # 5 stop
    _, ozet = streak_uygula(kayitlar)
    # kural altında seri 3'te atlar → sayılmış maks 3; eşik serisi görür
    assert ozet["streak_maks"] == 3
    assert ozet["atlanan"] == 1                       # 4. işlem atlandı (5. sayaç sıfırdan)
    assert ozet["streak_3plus_seri_yuzde"] == 100.0


# --- gün durdurma (eski kural) --------------------------------------------
def test_gun_durdur_iki_stoptan_sonrakini_atlar():
    kayitlar = [
        _kayit("A", "4h", 10, "stop", "2026-06-01", "10:00"),
        _kayit("A", "4h", 30, "stop", "2026-06-01", "14:00"),
        _kayit("A", "4h", 50, "hedef", "2026-06-01", "18:00"),
        _kayit("A", "4h", 70, "stop", "2026-06-02", "10:00"),  # yeni gün
    ]
    out, ozet = gun_durdur_uygula(kayitlar)
    assert out[2]["kural"] == "gun_durdur_atla"
    assert out[3]["kural"] == "kural_yok"             # yeni gün serbest
    assert ozet["tetiklenen_gun_sayisi"] == 1


# --- tavan -----------------------------------------------------------------
def test_tavan_eszamanli_limiti():
    # aynı anda 4 işlem giriş yapıyor → 4.'sü atlanır
    kayitlar = [_kayit("A", "4h", 10 + 20 * i, "hedef", "2026-06-01", "10:00")
                for i in range(4)]
    out, ozet = tavan_uygula(kayitlar, tavan=3)
    atlanan = [r for r in out if r["kural"] == "tavan_atla"]
    assert len(atlanan) == 1
    assert ozet["en_yuksek_eszamanli"] == 3


def test_tavan_aralikli_islemlere_dokunmaz():
    # yeterli arayla (10 bar × 4h = 40 saat > H süresi) → hiçbiri atlanmaz
    kayitlar = []
    for i in range(5):
        gun = f"2026-06-0{1 + i}"
        kayitlar.append(_kayit("A", "4h", 10 + 20 * i, "hedef", gun, "10:00"))
    out, ozet = tavan_uygula(kayitlar, tavan=3)
    assert ozet["atlanan"] == 0
