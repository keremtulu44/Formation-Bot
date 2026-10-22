# -*- coding: utf-8 -*-
"""Termux derin-geçmiş çekicisi regresyonları (scripts/backfill/yahoo_backfill.py).

Kapsam — HEPSİ AĞSIZ, Yahoo'ya tek istek gitmez:
  1. Bağımlılık sözleşmesi: yfinance/pandas MODÜL SEVİYESİNDE import edilmez
     (AST bekçisi). Neden: Termux'ta `--help`, `--probe --limit 0` ve liste
     modları pandas kurulu olmadan da çalışmak zorunda; aksi halde araç
     "kurulum bitmeden denenemez" olur.
  2. Hata sınıflandırması: kalıcı (404/sembol yok) vs geçici (429/timeout/ağ).
     Regresyon: `RemoteDisconnected` bitişik yazılır; data.py:1737'deki ayrık
     "remote disconnected" işareti onu YAKALAMIYOR. Burada kilitli.
  3. Bilinmeyen hata -> KALICI sayılır (sonsuz yeniden deneme = ban riski).
  4. Tempo/ban koruması: ardışık hatada çarpan artar, soğuma eşiğinde uzun mola,
     azami soğuma aşılınca koşu DURUR, başarıda çarpan sıfırlanır.
  5. Devam (resume) kararı: manifest `ok` VE dosya diskte var VE `--zorla` yok.
  6. Manifest: round-trip, bozuk JSON'a dayanıklılık, atomik yazım (.tmp artığı yok).
  7. CSV sözleşmesi: bar_time METİN 'YYYY-MM-DD HH:MM:SS+03:00', başlık sırası,
     NaN/inf -> boş hücre, round-trip sayı hassasiyeti, atomik yazım.
  8. Havuz bütünlüğü: benzersiz/büyük harf + canlı evrenin bilinen-çalışan 48
     hissesi havuzda duruyor (biri listeyi düzenleyip çekirdeği düşürmesin).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent
_SCRIPT = KOK / "scripts" / "backfill" / "yahoo_backfill.py"


def _modul():
    spec = importlib.util.spec_from_file_location("yahoo_backfill_test_mod", _SCRIPT)
    assert spec is not None and spec.loader is not None, f"yüklenemedi: {_SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


yb = _modul()


# === 1) BAĞIMLILIK SÖZLEŞMESİ — Termux'ta çıplak çalışabilirlik ==============
def test_yfinance_ve_pandas_modul_seviyesinde_import_edilmez():
    """Ağır bağımlılıklar yalnız fonksiyon İÇİNDE import edilebilir.

    Neden kilitli: Termux'ta pandas `pkg`'den gelir ve her cihazda kurulu
    olmayabilir. Modül seviyesinde import edilirse `--help` bile ImportError
    verir ve kullanıcı aracın ne yaptığını göremez.
    """
    tree = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    yasakli = {"yfinance", "pandas", "numpy"}
    ihlal = []
    for node in tree.body:  # yalnız MODÜL gövdesi; iç içe importlar serbest
        if isinstance(node, ast.Import):
            ihlal += [a.name.split(".")[0] for a in node.names if a.name.split(".")[0] in yasakli]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in yasakli:
                ihlal.append(node.module.split(".")[0])
    assert not ihlal, f"modül seviyesinde ağır import var (lazy olmalı): {ihlal}"


def test_script_yardimi_bagimlilik_olmadan_calisir():
    """`--help` çıplak yorumlayıcıda patlamamalı (CLI sözleşmesi)."""
    import subprocess

    sonuc = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True, text=True, timeout=60, cwd=str(KOK),
    )
    assert sonuc.returncode == 0, sonuc.stderr[:400]
    assert "--probe" in sonuc.stdout and "--retry-failed" in sonuc.stdout


# === 2/3) HATA SINIFLANDIRMASI ==============================================
@pytest.mark.parametrize("metin,beklenen", [
    # KALICI — tekrar denenmemeli (gereksiz istek = ban riski)
    ("HTTP Error 404: Not Found", False),
    ("$KOZAL.IS: possibly delisted", False),
    ("No data found for this ticker", False),
    ("symbol not found", False),
    ("No timezone found", False),
    # GEÇİCİ — yeniden denenmeli
    ("429 Too Many Requests", True),
    ("Too Many Requests. Rate limited. Try after a while.", True),
    ("YFRateLimitException: rate limited", True),
    ("HTTPSConnectionPool: Read timed out. (read timeout=30)", True),
    ("Connection aborted.", True),
    ("ConnectionResetError(104, 'Connection reset by peer')", True),
    ("503 Service Unavailable", True),
    ("Bad Gateway", True),
    ("Network is unreachable", True),
    ("HTTPSConnectionPool(host='query1.finance.yahoo.com'): Max retries exceeded", True),
    ("Failed to establish a new connection", True),
    ("ChunkedEncodingError: IncompleteRead", True),
    ("Temporary failure in name resolution", True),
    # REGRESYON: exception adı BİTİŞİK lower() olur; data.py:1737 bunu kaçırıyor
    ("RemoteDisconnected('Remote end closed connection without response')", True),
    ("BrokenPipeError(32, 'Broken pipe')", True),
    ("ProtocolError('Connection aborted.')", True),
])
def test_hata_siniflandirmasi(metin, beklenen):
    assert yb.hata_gecici_mi(metin) is beklenen, metin


def test_bilinmeyen_hata_kalici_sayilir():
    """Bilinmeyeni geçici saymak sonsuz yeniden deneme -> ban demektir."""
    for metin in ("Yahoo boş veri döndürdü", "", "beklenmedik bir şey oldu"):
        assert yb.hata_gecici_mi(metin) is False, metin


# === 4) TEMPO / BAN KORUMASI =================================================
def _tempo(uykular):
    return yb.Tempo(
        grup=yb.GRUP_BOYUTU,
        log=lambda *_: None,
        sleep_fn=uykular.append,
        uniform_fn=lambda a, b: a,          # deterministik: alt sınırı al
        monotonic_fn=lambda: 0.0,           # "hiç zaman geçmedi" -> tam bekleme
        soguma_suresi_sn=1.0,               # gerçek 5 dk yerine 1 sn (test hızlı koşsun)
    )


def test_tempo_grup_sonrasi_uzun_mola_verir():
    """Grup İÇİNDE kısa istek arası, grup DOLUNCA uzun mola.

    uniform_fn alt sınırı döndürdüğü ve monotonic_fn sabit 0 olduğu için
    beklenen kısa ara tam olarak ISTEK_ARA_MIN_SN'dir. İlk bekleyişte
    `_son_bitis` henüz None -> hiç uyku yok (soğuk başlangıçta boşuna beklenmez).
    """
    uykular = []
    t = _tempo(uykular)
    for _ in range(yb.GRUP_BOYUTU):
        t.bekle()
        t.istek_bitti()
        t.basarili()
    assert t.toplam_istek == yb.GRUP_BOYUTU
    # ilk istekte uyku yok, sonraki 9'unda kısa ara
    assert len(uykular) == yb.GRUP_BOYUTU - 1
    assert all(u == pytest.approx(yb.ISTEK_ARA_MIN_SN) for u in uykular), uykular
    assert all(u < yb.GRUP_MOLA_MIN_SN for u in uykular), "grup içinde uzun mola olmamalı"

    t.bekle()  # grup doldu -> uzun mola
    assert uykular[-1] == pytest.approx(yb.GRUP_MOLA_MIN_SN)
    assert t._grup_icinde == 1, "uzun moladan sonra grup sayacı sıfırlanmalı"


def test_tempo_ardisik_hatada_carpani_artirir_ve_basarida_sifirlar():
    t = _tempo([])
    t.gecici_hata("429")
    assert t.carpan == pytest.approx(2.0)
    t.gecici_hata("429")
    assert t.carpan == pytest.approx(4.0)
    t.gecici_hata("429")  # tavan: AZAMI_TEMPO_CARPANI
    assert t.carpan == pytest.approx(yb.AZAMI_TEMPO_CARPANI)
    t.basarili()
    assert t.carpan == 1.0 and t.ardisik_gecici_hata == 0


def test_tempo_soguma_esiginde_uzun_mola_verir():
    uykular = []
    t = _tempo(uykular)
    for _ in range(yb.SOGUMA_ESIK_ARDISIK_HATA):
        t.gecici_hata("429")
    assert t.soguma_sayisi == 1
    assert t.ardisik_gecici_hata == 0, "soğuma sonrası sayaç sıfırlanmalı"
    assert any(u == pytest.approx(1.0) for u in uykular), "soğuma molası verilmeli"
    assert t.beklenen_sn > 0


def test_tempo_azami_soguma_asilinca_kosuyu_durdurur():
    """Ban yemektense koşuyu bırak: dur bayrağı set edilmeli."""
    t = _tempo([])
    for tur in range(yb.AZAMI_SOGUMA + 1):
        for _ in range(yb.SOGUMA_ESIK_ARDISIK_HATA):
            t.gecici_hata("429")
    assert t.dur is True, "azami soğuma aşılınca koşu durmalı"
    assert t.soguma_sayisi == yb.AZAMI_SOGUMA + 1


# === 5) DEVAM (RESUME) KARARI ===============================================
def test_atlanmali_mi_uc_kosulu_birlikte_ister(tmp_path):
    dosya = tmp_path / "THYAO_1h.csv.gz"
    ok = {"durum": "ok", "satir": 2268}

    # manifest ok AMA dosya diskte yok -> ATLANMAZ (veri kaybolmuş)
    assert yb.atlanmali_mi(ok, dosya, zorla=False) is False
    dosya.write_bytes(b"x")
    assert yb.atlanmali_mi(ok, dosya, zorla=False) is True
    # --zorla her şeyi yeniden çeker
    assert yb.atlanmali_mi(ok, dosya, zorla=True) is False
    # başarısız/yarım kayıtlar asla atlanmaz
    for durum in ("kalici_basarisiz", "gecici_basarisiz", "durduruldu", "yazma_hatasi"):
        assert yb.atlanmali_mi({"durum": durum}, dosya, zorla=False) is False, durum
    # kayıt hiç yoksa (ilk koşu) atlanmaz
    assert yb.atlanmali_mi(None, dosya, zorla=False) is False


# === 6) MANIFEST =============================================================
def test_manifest_roundtrip_ve_bozuk_dosya_dayanikliligi(tmp_path):
    m = yb.manifest_oku(tmp_path)
    assert m == {"kayitlar": {}, "kosular": []}, "boş dizinde temiz başlangıç"

    m["kayitlar"][yb.anahtar("THYAO", "1h")] = {"durum": "ok", "satir": 2268}
    m["kayitlar"][yb.anahtar("KOZAL", "1h")] = {"durum": "kalici_basarisiz", "hata": "404"}
    m["kosular"].append({"sure_sn": 12.5})
    yb.manifest_yaz(tmp_path, m)

    geri = yb.manifest_oku(tmp_path)
    assert len(geri["kayitlar"]) == 2
    assert geri["kayitlar"]["THYAO:1h"]["satir"] == 2268
    assert geri["kosular"][0]["sure_sn"] == 12.5
    assert not list(tmp_path.glob("*.tmp")), "atomik yazım .tmp artığı bırakmamalı"

    # Bozuk JSON tüm koşuyu çökertmemeli -> boş manifest ile devam
    (tmp_path / "manifest.json").write_text("{ bozuk json", encoding="utf-8")
    k = yb.manifest_oku(tmp_path)
    assert k["kayitlar"] == {} and k["kosular"] == []


def test_anahtar_bicimi():
    assert yb.anahtar("THYAO", "1h") == "THYAO:1h"


# === 7) CSV SÖZLEŞMESİ =======================================================
def _sahte_ohlcv(mod):
    pd = pytest.importorskip("pandas")
    idx = pd.to_datetime([
        "2026-10-16 09:30:00+03:00",
        "2026-10-16 10:30:00+03:00",
        "2026-10-16 11:30:00+03:00",
    ], utc=True).tz_convert("Europe/Istanbul")
    return pd.DataFrame(
        {
            "open": [10.5, float("nan"), 11.25],
            "high": [11.0, 11.4, 11.75],
            "low": [10.25, 10.9, 11.0],
            "close": [10.75, 11.1, 11.5],
            "volume": [1_000_000.0, 0.0, 1_500_000.0],
        },
        index=idx,
    )


def test_csv_bicim_sozelesmesi(tmp_path):
    """bar_time METİN, başlık sabit, NaN -> boş, hassasiyet round-trip."""
    import gzip

    df = _sahte_ohlcv(yb)
    yol = tmp_path / "THYAO_1h.csv.gz"
    satir = yb._csv_gz_yaz(yol, df)
    assert satir == 3
    assert yol.exists() and not list(tmp_path.glob("*.tmp"))

    with gzip.open(yol, "rt", encoding="utf-8") as fh:
        icerik = fh.read().splitlines()
    assert icerik[0] == ",".join(yb.CSV_ALANLAR)
    # bar_time TEXT sözleşmesi: 'YYYY-MM-DD HH:MM:SS+03:00' (ISO 'T' YOK)
    ilk = icerik[1].split(",")
    assert ilk[0] == "2026-10-16 09:30:00+03:00", ilk[0]
    assert "T" not in ilk[0], "timestamptz/ISO 'T' biçimi arşiv sözleşmesini bozar"
    # NaN -> boş hücre ('nan' yazılmamalı: okuyucuda sayı diye patlar)
    ikinci = icerik[2].split(",")
    assert ikinci[1] == "", f"NaN open boş hücre olmalı, gelen: {ikinci[1]!r}"
    assert "nan" not in icerik[2].lower()
    # sıfır hacim KORUNUR (düşürülmez): kalite kararı ingest katmanınındır
    assert ikinci[5] == "0.0"
    # round-trip: okunan değer birebir geri gelmeli
    assert float(ilk[1]) == 10.5 and float(ilk[4]) == 10.75


def test_sayi_roundtrip_ve_nan_inf():
    assert yb._sayi(None) == ""
    assert yb._sayi("abc") == ""
    assert yb._sayi(float("nan")) == ""
    assert yb._sayi(float("inf")) == "" and yb._sayi(float("-inf")) == ""
    assert float(yb._sayi(12.345678901234)) == 12.345678901234, "hassasiyet kaybolmamalı"
    assert yb._sayi(0) == "0.0"
    assert float(yb._sayi(1e-09)) == 1e-09


def test_kalite_raporu_kirli_veriyi_sayiyor():
    """Kirli bar SESSİZCE düşürülmez, sayılır — eleme ingest katmanının kararı."""
    pd = pytest.importorskip("pandas")
    df = _sahte_ohlcv(yb)
    # split adayı: bir sonraki açılış önceki kapanıştan %10+ uzak
    df.loc[df.index[2], "open"] = df.loc[df.index[1], "close"] * 1.5
    rap = yb._kalite_raporu(df)
    assert rap["toplam_bar"] == 3
    assert rap["nan_ohlc"] == 1
    assert rap["sifir_hacim"] == 1
    assert rap["split_sicramasi_adayi"] == 1


# === 8) HAVUZ BÜTÜNLÜĞÜ ======================================================
def test_aday_havuzu_benzersiz_ve_buyuk_harf():
    havuz = yb.BIST_ADAY_HAVUZU
    assert len(havuz) == len(set(havuz)), "havuzda yinelenen sembol var"
    assert all(s == s.strip().upper() for s in havuz), "semboller büyük harf/temiz olmalı"


def test_havuz_canli_evrenin_bilinen_calisan_hisselerini_icerir():
    """Bilinen-çalışan çekirdek havuzdan düşerse backfill sessizce eksik kalır.

    XU100/XU30/BRENT endeks+emtia; KOZAL/KOZAA Yahoo'da 404 olduğu için ana
    evrende de YOK (config.py:76-78 notu) — havuzda da beklenmez.
    """
    from config import BIST_50, ENDEKS_SEMBOLLERI, MAKRO_SEMBOLLERI

    ozel = ENDEKS_SEMBOLLERI | MAKRO_SEMBOLLERI
    beklenen = {s for s in BIST_50 if s not in ozel}
    eksik = sorted(beklenen - set(yb.BIST_ADAY_HAVUZU))
    assert not eksik, f"canlı evrenin bilinen-çalışan hisseleri havuzda yok: {eksik}"
    # Endeks/emtia/makro da eşlenmesi gereken özel semboller olarak havuzda olmalı
    assert {"XU100", "XU30", "BRENT"} <= set(yb.BIST_ADAY_HAVUZU)


def test_yedek_esleme_ozel_sembolleri_dogru_cevirir():
    """config.py import edilemezse (Termux'ta pytz yok) eşleme yine doğru olmalı."""
    for sembol, beklenen in (("XU100", "XU100.IS"), ("XU30", "XU030.IS"),
                             ("BRENT", "BZ=F"), ("THYAO", "THYAO.IS")):
        assert yb.YEDEK_SAGLAYICI_ESLEMESI.get(sembol, sembol + ".IS") == beklenen


def test_ticker_cozucu_config_yoksa_yedege_duser(monkeypatch):
    def patlayan_import(*_a, **_k):
        raise ImportError("pytz yok (Termux senaryosu)")

    import builtins
    gercek = builtins.__import__

    def secici(name, *a, **k):
        if name == "config":
            raise ImportError("pytz yok (Termux senaryosu)")
        return gercek(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", secici)
    cozucu, kaynak = yb._ticker_cozucu_yukle()
    assert kaynak == "yerel yedek eşleme"
    assert cozucu("THYAO") == "THYAO.IS"
    assert cozucu("BRENT") == "BZ=F"
    monkeypatch.setattr(builtins, "__import__", gercek)


# === SEMBOL LİSTESİ ÇÖZÜMÜ ===================================================
def test_probe_ciktisi_dogrulanmis_listeye_doner(tmp_path, monkeypatch):
    """Probe sonucu -> dogrulanmis_semboller.txt -> sonraki koşunun girdisi."""
    liste = tmp_path / "dogrulanmis_semboller.txt"
    liste.write_text("# yorum satırı\nTHYAO\nGARAN\n\nKOZAL\n", encoding="utf-8")

    class Args:
        semboller = ""
        liste_dosyasi = str(liste)
        hedef = str(tmp_path)
        probe = False
        limit = 0

    cozuken = yb.sembol_listesi_coz(Args())
    assert cozuken == ["GARAN", "KOZAL", "THYAO"], "yorum/boş satır elenmeli, sıralı olmalı"


def test_virgullu_sembol_argumani(tmp_path):
    class Args:
        semboller = " thyao , garan ,,akbnk "
        liste_dosyasi = ""
        hedef = str(tmp_path)
        probe = False
        limit = 0

    assert yb.sembol_listesi_coz(Args()) == ["THYAO", "GARAN", "AKBNK"]
