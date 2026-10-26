"""Tanımsız ad (NameError) koruması — 23 Ekim 2026.

Neden bu test var: canlı alarm kartı 23 Ekim'de "sade" geliyordu. Sebep biçim
değil, iki tanımsız addı:

* `main._attach_domain_context` içinde `atr=atr_alarm` yazılmıştı ama
  `atr_alarm` hiçbir yerde tanımlı değildi → her alarmda `NameError`,
  `except kart_hata` tarafından yutuluyor ve `domain_bolumleri` karta HİÇ
  eklenmiyordu (kartta `◈`/`◇`/`▤`/`engel`/`ters işaret` blokları yok).
* `main._goreli_guc_satiri` içinde `resample_ohlcv` çağrılıyordu; fonksiyon
  `main.py`'ye import edilmemişti → `göreli güç` satırı da her zaman boştu.

İkisi de geniş bir `except Exception` bloğunun içinde olduğu için hiçbir
davranış testi kırılmadı; hata yalnızca log satırında görünüyordu. Bu test
kaynağı **çalıştırmadan** okur: bir modülde Load edilen ama modülün hiçbir
yerinde tanımlanmayan ad varsa kırılır.

Kapsam bilinçli olarak modül geneli: kapsam (scope) analizi yapmıyoruz, yani
bir ad modülün HERHANGİ bir yerinde atanıyorsa tanımlı sayılır. Bu, yanlış alarm
üretmemek için seçilmiş bir over-approximation; gerçek `NameError`ların çoğu
(bu ikisi gibi) hiçbir yerde atanmamış adlardır.

2026-10-26 eki: fonksiyon-içi "kullan-önce-ata" (UnboundLocalError) koruması —
`test_fonksiyonda_atamadan_once_kullanim_yok`. Modül geneli koruma, bir ad
fonksiyonun SONRASINDA atanıyorsa "tanımlı" saydığı için bu sınıfı kaçırır:
`main.scan_all_stocks` içindeki DM musluğu `mtf_uyum`/`bant_mesafe_atr`
değişkenlerini atandıkları satırdan ~140 satır önce okuyordu (2026-10-26
denetimi, bkz. docs/denetim/KOD_DENETIMI_2026-10-26.md). Bu ikinci koruma
kaynağı yine çalıştırmadan okur: bir fonksiyonda Load edilen ad o fonksiyonda
yalnız daha SONRA atanıyorsa kırılır.
"""

from __future__ import annotations

import ast
import builtins
from pathlib import Path

import pytest

# Çalışma zamanının enjekte ettiği adlar (modül gövdesinde atanmazlar).
_RUNTIME_ADLAR = {
    "__name__", "__file__", "__doc__", "__package__", "__spec__",
    "__loader__", "__build_class__", "__annotations__", "__dict__",
}

# Taranan modüller: alarm/kart/görsel zincirinin çekirdeği.
_MODULLER = (
    "main.py",
    "notifier/__init__.py",
    "notifier/util.py",
    "notifier/format_kart.py",
    "notifier/format_summary.py",
    "notifier/api.py",
    "bot/statestore.py",
    "bot/counters.py",
    "bot/heartbeat.py",
    "bot/commands.py",
    "bot/lifecycle_events.py",
    "bot/scan.py",
    "bot/security.py",
    "bot/summary.py",
    "bot/app.py",
    "data/__init__.py",
    "data/fetch.py",
    "data/replay.py",
    "data/backfill.py",
    "data/seed_cache.py",
    "notification_context.py",
    "notification_delivery.py",
    "grafik/__init__.py",
    "grafik/core.py",
    "grafik/geometry.py",
    "grafik/indicators.py",
    "grafik/overlays.py",
    "grafik/panels.py",
    "grafik/markers.py",
    "grafik/tarama.py",
    "grafik/render.py",
    "grafik/kare.py",
    "grafik_uret.py",
    "telegram_alert_flow.py",
    "ampirik_referans.py",
)


def _atanan_adlar(tree: ast.AST) -> set[str]:
    """Modülde HERHANGİ bir yerde atanan/tanıtılan adlar (kapsam ayrımı yok)."""
    adlar: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            adlar.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            adlar.add(node.name)
        elif isinstance(node, ast.arg):
            adlar.add(node.arg)
        elif isinstance(node, ast.alias):
            adlar.add((node.asname or node.name).split(".")[0])
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            adlar.update(node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            adlar.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            # `from X import *` → X.__all__'daki adlar bu modülde bağlanır
            # (2026-10-26: main.py ince başlatıcı, yüzey bot.__all__'da).
            for a in node.names:
                if a.name == "*" and node.module:
                    adlar |= _star_bagli_adlar(node.module)
    return adlar


def _star_bagli_adlar(modul_adi: str) -> set[str]:
    """Yerel modülün/paketin __all__ kümesi (yoksa boş — koruma yine avlar)."""
    kok = Path(__file__).resolve().parent
    yol = kok / (modul_adi.replace(".", "/") + ".py")
    if not yol.exists():
        yol = kok / modul_adi.replace(".", "/") / "__init__.py"
    if not yol.exists():
        return set()
    for node in ast.walk(ast.parse(yol.read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)):
            try:
                return set(ast.literal_eval(node.value))
            except Exception:
                return set()
    return set()


def _okunan_adlar(tree: ast.AST) -> set[str]:
    return {node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}


def tanimsiz_adlar(kaynak: str) -> list[str]:
    tree = ast.parse(kaynak)
    return sorted(_okunan_adlar(tree) - _atanan_adlar(tree)
                  - set(dir(builtins)) - _RUNTIME_ADLAR)


@pytest.mark.parametrize("dosya", _MODULLER)
def test_modulde_tanimsiz_ad_yok(dosya):
    yol = Path(__file__).resolve().parent / dosya
    kaynak = yol.read_text(encoding="utf-8")
    eksik = tanimsiz_adlar(kaynak)
    assert eksik == [], (
        f"{dosya} tanımsız ad okuyor: {', '.join(eksik)}. "
        "Bu adlar çalışma anında NameError verir; geniş `except` blokları "
        "hatayı yutarsa özellik sessizce kaybolur."
    )


def test_koruma_atr_alarm_hatasini_yakalar():
    """Regresyon: `atr=atr_alarm` (tanımsız) bu testle yakalanmalı."""
    ornek = (
        "def f(df):\n"
        "    return g(df, atr=atr_alarm)\n"
    )
    assert tanimsiz_adlar(ornek) == ["atr_alarm", "g"]


def test_koruma_yerel_importu_gorur():
    """Fonksiyon içinde import edilen ad tanımlı sayılır (yanlış alarm yok)."""
    ornek = (
        "def f(df):\n"
        "    from data import resample_ohlcv\n"
        "    return resample_ohlcv(df, '4h')\n"
    )
    assert tanimsiz_adlar(ornek) == []


# ---------------------------------------------------------------------------
# 2026-10-26: fonksiyon-içi kullan-önce-ata (UnboundLocalError) koruması
# ---------------------------------------------------------------------------

_KAPSAM_DUGUMLERI = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
# comprehension/üreteç kendi kapsamıdır (py3'te hedefleri fonksiyona sızmaz);
# çok satırlı `for k, v in` kalıbı yanlış alarm üretmesin diye tümüyle atlanır.
_COMP_DUGUMLERI = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def atamadan_once_kullanimlar(kaynak: str) -> list[tuple[str, int, str]]:
    """Fonksiyon içinde yalnız daha SONRA atanan adların Load'ları.

    Dönüş: ``(fonksiyon_adi, load_satiri, ad)`` listesi.

    Kapsam kuralları (bilinçli yaklaşım):
      * Argümanlar fonksiyon girişinde atanmış sayılır (yeniden atansalar bile
        ilk Load güvenlidir).
      * İç içe fonksiyon/sınıf/lambda/comprehension gövdeleri kapsam dışıdır:
        ya kendi kapsamları ya da kapama (closure) oldukları için çalışma anı
        farklıdır.
      * ``except ... as e`` hedefi, ``for`` hedefleri ve ``del`` de atama sayılır.
      * ``global``/``nonlocal`` adları kontrol dışıdır.
      * Yalnız kaynak SIRASI kullanılır (``atama_satiri <= load_satiri``); dallı
        kontrolden bağımsız çalıştığı için bu bir over-approximation'dır ve
        bilerek tercih edilmiştir: kullan-önce-ata hatalarının tipik şekli
        (önce oku, döngünün ilerisinde ata) tam olarak budur.
    """
    tree = ast.parse(kaynak)
    sonuclar: list[tuple[str, int, str]] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        atamalar: dict[str, list[int]] = {}
        okumalar: list[tuple[int, str]] = []
        atlanacak: set[str] = set()

        # Argümanlar girişte atanmış sayılır.
        args = list(fn.args.args) + list(fn.args.kwonlyargs)
        if fn.args.vararg:
            args.append(fn.args.vararg)
        if fn.args.kwarg:
            args.append(fn.args.kwarg)
        for a in args:
            atamalar.setdefault(a.arg, []).append(fn.lineno)

        def tara(dugum, ic_ice=False, _atamalar=atamalar, _okumalar=okumalar,
                 _atlanacak=atlanacak):
            for cocuk in ast.iter_child_nodes(dugum):
                alt = (ic_ice or isinstance(cocuk, _KAPSAM_DUGUMLERI)
                       or isinstance(cocuk, _COMP_DUGUMLERI))
                if not alt:
                    if isinstance(cocuk, ast.Name):
                        if isinstance(cocuk.ctx, ast.Store):
                            _atamalar.setdefault(cocuk.id, []).append(cocuk.lineno)
                        elif isinstance(cocuk.ctx, ast.Load):
                            _okumalar.append((cocuk.lineno, cocuk.id))
                    elif isinstance(cocuk, ast.ExceptHandler) and cocuk.name:
                        _atamalar.setdefault(cocuk.name, []).append(cocuk.lineno)
                    elif isinstance(cocuk, (ast.Global, ast.Nonlocal)):
                        _atlanacak.update(cocuk.names)
                tara(cocuk, alt, _atamalar, _okumalar, _atlanacak)

        tara(fn)

        gorulen: set[tuple[int, str]] = set()
        for satir, ad in okumalar:
            if ad in atlanacak:
                continue
            satirlar = atamalar.get(ad)
            if satirlar and min(satirlar) > satir and (satir, ad) not in gorulen:
                gorulen.add((satir, ad))
                sonuclar.append((fn.name, satir, ad))
    return sonuclar


def _taranan_dosyalar() -> list[str]:
    """Depodaki tüm .py dosyaları (venv/gizli dizinler hariç)."""
    kok = Path(__file__).resolve().parent
    return sorted(
        str(p.relative_to(kok))
        for p in kok.rglob("*.py")
        if not any(part.startswith(".") for part in p.relative_to(kok).parts)
    )


@pytest.mark.parametrize("dosya", _taranan_dosyalar())
def test_fonksiyonda_atamadan_once_kullanim_yok(dosya):
    """Bir fonksiyonda ad, atandığı satırdan önce okunuyorsa kırılır.

    Bu kalıp çalışma anında ``UnboundLocalError`` verir (dal hiç çalışmasa da
    okuma önceki döngüden kalmış eski değeri okur — sessiz yanlış sonuç). Geniş
    ``except`` blokları hatayı yutarsa özellik kaybolur; kaynak düzeyinde
    kilitlenmesi bu yüzden.
    """
    yol = Path(__file__).resolve().parent / dosya
    kaynak = yol.read_text(encoding="utf-8")
    hatalar = atamadan_once_kullanimlar(kaynak)
    assert hatalar == [], (
        f"{dosya} içinde atamadan önce okunan adlar var: "
        + ", ".join(f"{ad} ({fn} @ satır {satir})" for fn, satir, ad in hatalar)
        + ". Çalışma anında UnboundLocalError veya önceki turlardan kalmış "
          "eski değerle yanlış hesap demektir."
    )


def test_koruma_kullanim_once_atama_yakalar():
    """Regresyon: 2026-10-26'daki DM musluğu hatasının AYNI şekli yakalanmalı."""
    ornek = (
        "def f(devam):\n"
        "    if devam:\n"
        "        puan = {'x': mtf_uyum}\n"      # Load, atama 5. satırda
        "        return puan\n"
        "    mtf_uyum = 0\n"
        "    return mtf_uyum\n"
    )
    assert atamadan_once_kullanimlar(ornek) == [("f", 3, "mtf_uyum")]


def test_koruma_arguman_yeniden_atamayi_elemez():
    """Yanlış alarm yok: argüman daha sonra yeniden atansa da ilk Load güvenli."""
    ornek = (
        "def f(now=None):\n"
        "    onceki = now\n"           # argüman; güvenli
        "    now = now or 'simdi'\n"   # yeniden atama
        "    return onceki, now\n"
    )
    assert atamadan_once_kullanimlar(ornek) == []


def test_koruma_cok_satirli_comprehensionu_elemez():
    """Yanlış alarm yok: çok satırlı comprehension hedefleri sonraki satırda."""
    ornek = (
        "def f(sozluk):\n"
        "    return {\n"
        "        k: v\n"                 # Load'lar 3. satırda
        "        for k, v in sozluk\n"   # hedef atamaları 4. satırda
        "    }\n"
    )
    assert atamadan_once_kullanimlar(ornek) == []


def test_koruma_kapama_ve_dongu_hedefini_elemez():
    """Yanlış alarm yok: döngü hedefi önce atanır, kapama kendi kapsamıdır."""
    ornek = (
        "def f(elseler):\n"
        "    sonuc = []\n"
        "    def sarma(x):\n"
        "        return x + sonuc\n"     # kapama; sonuc fonksiyon local'i
        "    for e in elseler:\n"
        "        sonuc.append(sarma(e))\n"
        "    return sonuc\n"
    )
    assert atamadan_once_kullanimlar(ornek) == []
