"""Patch yüzeyi koruması — 2026-10-26 (modülerleştirme Faz 0.5).

NEDEN: Testler 579 `monkeypatch.setattr` çağrısıyla modül özniteliklerini
yamalıyor. `monkeypatch.setattr(..., raising=False)` ile yapılan yamalarda
hedef öznitelik YOKSA pytest sessizce yenisini yaratır ve yama işe yaramaz:
testler gerçek dosyalara/aksiyonlara yazar, sahte nesneler sessizce
atlanır. Modülerleştirme sırasında (bkz.
docs/tasarim/MODULERLESTIRME_PLANI_2026-10-26.md) bir ad taşındığında
tam olarak bu sessizlik riski doğar.

BU TEST NE YAPAR: test_*.py + conftest.py kaynaklarını ÇALIŞTIRMADAN okur;
her `monkeypatch.setattr(<modül ifadesi>, "<ad>", ...)` hedefi için:

  * `<modül ifadesi>` dosyanın import satırlarından çözülür
    (`import main as main_mod` → `main_mod` = `main` modülü;
     `from karne import KarneDefteri` → sınıf/alt-öznitelik);
  * çözülebilen her hedefte `hasattr(modül, "<ad>")` doğrulanır.

Çözülemeyen hedefler (fonksiyon içinde kurulmuş yerel nesneler: `n`, `box`,
`manager`…) bilinçli olarak atlanır — onlar zaten nesne seviyesinde yamadır
ve `raising=False` riski taşımaz.

KULLANIM:  python -m pytest test_patch_yuzeyi.py -q
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

_KOK = Path(__file__).resolve().parent
_TARANAN = sorted([p for p in _KOK.glob("test_*.py")] + [_KOK / "conftest.py"])


def _import_takma_adlari(tree: ast.AST) -> dict:
    """Dosyanın import takma adlarını çöz: `takma` → ("modül", "alt_ad|").

    Desteklenen kalıplar:
      import X            → "X" → ("X", "")
      import X as Y       → "Y" → ("X", "")
      import x.y as Z     → "Z" → ("x.y", "")
      from X import a as b→ "b" → ("X", "a")
      from X import a     → "a" → ("X", "a")
    """
    takma: dict = {}
    for dugum in ast.walk(tree):
        if isinstance(dugum, ast.Import):
            for a in dugum.names:
                ad = a.asname or a.name.split(".")[0]
                takma[ad] = (a.name, "")
        elif isinstance(dugum, ast.ImportFrom):
            if dugum.level or not dugum.module:
                continue  # göreli import: çözülemez, atla
            for a in dugum.names:
                takma[a.asname or a.name] = (dugum.module, a.name)
    return takma


def _skip_mi(dugum) -> bool:
    """Fonksiyon @pytest.mark.skip / skipif ile işaretli mi?"""
    for d in getattr(dugum, "decorator_list", []):
        hedef = d.func if isinstance(d, ast.Call) else d
        adlar = []
        while isinstance(hedef, ast.Attribute):
            adlar.append(hedef.attr)
            hedef = hedef.value
        if isinstance(hedef, ast.Name):
            adlar.append(hedef.id)
        if any(a in ("skip", "skipif", "xfail") for a in adlar):
            return True
    return False


def _setattr_hedefleri(tree: ast.AST):
    """(düğüm) → [(modül_ifadesi_ast, ad, satır)] — yalnız sabit adla yapılanlar.

    @pytest.mark.skip ile işaretli test fonksiyonlarının İÇİ bilinçli olarak
    atlanır: o testler gelecekteki/yürürlükten kalkmış API'leri yamalar
    (bkz. MERGE_MAIN_CELISKI_RAPORU.md §5 — bilinçli ertelenmiş iş) ve hiç
    çalışmazlar.
    """
    pasif_satirlar: set[int] = set()
    for dugum in ast.walk(tree):
        if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)) and _skip_mi(dugum):
            for alt in ast.walk(dugum):
                if hasattr(alt, "lineno"):
                    pasif_satirlar.add(alt.lineno)

    for dugum in ast.walk(tree):
        if not isinstance(dugum, ast.Call):
            continue
        f = dugum.func
        if not (isinstance(f, ast.Attribute) and f.attr == "setattr"):
            continue
        if not (isinstance(f.value, ast.Name) and f.value.id == "monkeypatch"):
            continue
        if len(dugum.args) < 2:
            continue
        if dugum.lineno in pasif_satirlar:
            continue
        hedef, ad = dugum.args[0], dugum.args[1]
        if isinstance(ad, ast.Constant) and isinstance(ad.value, str):
            yield hedef, ad.value, dugum.lineno


def _coz(hedef_ast, takma: dict):
    """Hedef AST'yi (modül_nesnesi, öznitelik_zinciri) olarak çöz; çözülemezse None."""
    if isinstance(hedef_ast, ast.Name):
        kayit = takma.get(hedef_ast.id)
        if kayit is None:
            return None
        modul_ad, alt = kayit
        return modul_ad, ([alt] if alt else [])
    if isinstance(hedef_ast, ast.Attribute):
        zincir = []
        d = hedef_ast
        while isinstance(d, ast.Attribute):
            zincir.append(d.attr)
            d = d.value
        if not isinstance(d, ast.Name):
            return None
        kayit = takma.get(d.id)
        if kayit is None:
            return None
        modul_ad, alt = kayit
        oncekiler = ([alt] if alt else []) + list(reversed(zincir))[:-1]
        son = zincir[-1] if zincir else ""
        return modul_ad, oncekiler + ([son] if son else [])
    return None


def _hedef_kayitlari():
    """Tüm statik çözülebilen yama hedefleri: (dosya, satır, modül, zincir)."""
    kayitlar = []
    for yol in _TARANAN:
        kaynak = yol.read_text(encoding="utf-8")
        tree = ast.parse(kaynak)
        takma = _import_takma_adlari(tree)
        for hedef_ast, ad, satir in _setattr_hedefleri(tree):
            cozum = _coz(hedef_ast, takma)
            if cozum is None:
                continue
            modul_ad, zincir = cozum
            if ad:
                zincir = zincir + [ad]
            kayitlar.append((yol.name, satir, modul_ad, zincir))
    return kayitlar


_KAYITLAR = _hedef_kayitlari()


@pytest.mark.parametrize("dosya,satir,modul_ad,zincir", _KAYITLAR,
                         ids=[f"{d}:{s}:{'.'.join([m] + z)}"
                              for d, s, m, z in _KAYITLAR])
def test_patch_hedefi_var(dosya, satir, modul_ad, zincir):
    """Yama hedefi gerçekten var mı? Yoksa `raising=False` yaması sessizce
    işe yaramaz ve test gerçeği yamaladığını sanır."""
    try:
        modul = importlib.import_module(modul_ad)
    except Exception as hata:  # pragma: no cover - import kırılırsa zaten her şey kırılır
        pytest.fail(f"{dosya}:{satir}: {modul_ad} import edilemedi: {hata}")

    # `from state import formation_history` gibi kalıplarda ilk halka bir
    # ALT MODÜLDÜR: önce uzun yoldan import denenir, olmazsa öznitelik sayılır.
    kalan = list(zincir)
    for i in range(len(kalan), 0, -1):
        yol = ".".join([modul_ad] + kalan[:i])
        try:
            modul = importlib.import_module(yol)
        except ImportError:
            continue
        kalan = kalan[i:]
        break
    if not kalan:
        return  # hedefin kendisi bir modül (nadiren); import başarılıysa yeterli

    # Zincirin yalnız İLK halkası doğrulanır (ör. `main_mod._live_state.status`):
    # devamı çalışma anı nesnesinin durumudur (None olabilir, mock'lanabilir).
    ilk = kalan[0]
    if not hasattr(modul, ilk):
        pytest.fail(
            f"{dosya}:{satir}: yama hedefi '{modul_ad}.{'.'.join(zincir)}' yok "
            f"('{modul.__name__}' üzerinde '{ilk}' bulunamadı). "
            "Modülerleştirme sırasında isim taşındıysa bu testi bilerek güncelleyin "
            "(plan §3: yama, okuyan modülün namespace'ini işaret etmeli)."
        )
    if len(kalan) == 1:
        return
    nesne = getattr(modul, ilk)
    son = kalan[-1]
    if nesne is not None and not hasattr(nesne, son):
        pytest.fail(
            f"{dosya}:{satir}: yama hedefi '{modul_ad}.{'.'.join(zincir)}' zinciri "
            f"'{ilk}' üzerinde '{son}' taşımıyor."
        )


def test_envanter_uretiliyor():
    """Korumanın kendisi: en azından bilinen yama yüzeyini görmeli."""
    assert len(_KAYITLAR) > 100, f"yama hedefi az bulundu: {len(_KAYITLAR)}"
    moduller = {m for _, _, m, _ in _KAYITLAR}
    assert "main" in moduller, "main yama yüzeyi görünmüyor"
