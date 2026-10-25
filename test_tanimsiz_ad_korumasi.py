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
    "notifier.py",
    "notification_context.py",
    "notification_delivery.py",
    "grafik.py",
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
    return adlar


def _okunan_adlar(tree: ast.AST) -> set[str]:
    return {node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}


def tanimsiz_adlar(kaynak: str) -> list[str]:
    tree = ast.parse(kaynak)
    return sorted(_okunan_adlar(tree) - _atanan_adlar(tree)
                  - set(dir(builtins)) - _RUNTIME_ADLAR)


@pytest.mark.parametrize("dosya", _MODULLER)
def test_modulde_tanimsiz_ad_yok(dosya):
    yol = Path(__file__).with_name(dosya)
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
