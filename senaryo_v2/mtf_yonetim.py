"""Deneysel MTF yönetim çekirdeği, yalnız kapanmış as-of snapshotlarla.

Veriyi ve emirleri üretmez. Çağıran kod, her zaman diliminde kapanışın
kanıtlandığını ve işlemden sonra gerçekleştiğini doğrulamalıdır.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
import math

@dataclass(frozen=True)
class Snapshot:
    time: datetime
    close: float
    previous_close: float | None
    atr: float | None
    ms_event: int = 0                 # +1 yukarı, -1 aşağı, 0 yok
    ms_direction: int = 0             # yapısal durum

@dataclass(frozen=True)
class MtfResult:
    two_hour: bool
    one_hour: bool
    four_hour: bool
    signal: bool


def _valid(s: Snapshot | None, now: datetime, max_age: timedelta, *, kalici: bool = False) -> bool:
    """Snapshot kapanmış ve kullanılabilir mi?

    Geçici sinyaller (ters fiyat hareketi, yeni olay) yaş ve aynı-gün tazeliği ister.
    `kalici=True` kalıcı DURUM içindir (ör. 4s yapısal yön): durum, yerine yenisi gelene
    kadar geçerlidir; ona yaş/aynı-gün şartı uygulamak her sabah ilk 4s mumu kapanana
    kadar durumu yok sayar.
    """
    if s is None or s.time > now:
        return False
    if kalici:
        return True
    return bool(now - s.time <= max_age and s.time.date() == now.date())


def _price_reverse(s: Snapshot, direction: int, threshold: float) -> bool:
    return bool(s.previous_close is not None and s.atr is not None and
                math.isfinite(s.atr) and s.atr > 0 and
                direction * (s.close - s.previous_close) <= -threshold * s.atr)


def mtf_signal(now: datetime, direction: int, two: Snapshot | None,
               one: Snapshot | None, four: Snapshot | None, *,
               two_mode: Literal['price', 'event'],
               four_mode: Literal['price', 'state'], threshold: float = .5,
               four_state_kalici: bool = False) -> MtfResult:
    """2s ters hareket/olay VE (1s yeni ters olay VEYA 4s ters durum/hareket).

    İlk deney: 2s sinyali en fazla 2 saat; 1s olay en fazla 1 saat; 4s
    teyit en fazla 4 saat yaşında ve hepsi aynı işlem gününden olmalı.
    Tazelik ve 0,5 ATR araştırma varsayımlarıdır, doğrulanmış eşikler değildir.

    `four_state_kalici=True`: `four_mode='state'` iken 4s yapısal yönü kalıcı durum sayar
    (yaş/aynı-gün şartı yok). Varsayılan False, `mtf_olcum` raporundaki ilk deneyin
    tanımıdır: o tanımda 4s durumu günün ilk 4s mumu kapanana kadar görünmez. Etkisi
    ölçüldü (2026-11-14): sekiz temel "4s durum" kolunda 601 işlemin hepsinde sonuç iki
    tanımla birebir aynı; yani raporun sonucu bu tazelik kuralına bağlı değil.
    """
    if direction not in (-1, 1) or two_mode not in ('price', 'event') or four_mode not in ('price', 'state'):
        raise ValueError('invalid MTF configuration')
    t = _valid(two, now, timedelta(hours=2)) and (
        _price_reverse(two, direction, threshold) if two_mode == 'price' else two.ms_event == -direction)
    o = _valid(one, now, timedelta(hours=1)) and one.ms_event == -direction
    f = _valid(four, now, timedelta(hours=4), kalici=four_state_kalici and four_mode == 'state') and (
        _price_reverse(four, direction, threshold) if four_mode == 'price' else four.ms_direction == -direction)
    return MtfResult(bool(t), bool(o), bool(f), bool(t and (o or f)))


def protected_stop(entry: float, risk: float, direction: int, current_stop: float, lock_r: float) -> float:
    """Yeni stopu yalnız lehine taşır. Gap ve maliyet pozitif getiriyi garanti etmez."""
    if direction not in (-1, 1) or not math.isfinite(risk) or risk <= 0 or lock_r < 0:
        raise ValueError('invalid stop inputs')
    target = entry + direction * lock_r * risk
    return max(current_stop, target) if direction == 1 else min(current_stop, target)

@dataclass(frozen=True)
class ManagementBar:
    """Her barın sonundaki mevcut MTF snapshotları ve intrabar fiyatı."""
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    one: Snapshot | None = None
    two: Snapshot | None = None
    four: Snapshot | None = None

@dataclass(frozen=True)
class ManagementConfig:
    two_mode: Literal['price', 'event'] = 'price'
    four_mode: Literal['price', 'state'] = 'state'
    mtf_action: Literal['none', 'exit', 'protect'] = 'none'
    activate_after_half_r: bool = False
    protect_trigger_r: float | None = None
    protect_lock_r: float = 0.0
    four_state_kalici: bool = False   # bkz. mtf_signal

@dataclass(frozen=True)
class ManagementOutcome:
    gross_r: float
    reason: str
    bar_index: int
    mtf_signals: int
    stop_moved: bool = False          # çıkış anında stop ilk stoptan farklıydı (koruma stopu)


def simulate_management(bars: list[ManagementBar], *, entry: float, stop: float,
                        target: float, direction: int, cfg: ManagementConfig) -> ManagementOutcome:
    """Bar kapanışlarında uyarı; piyasa çıkışı sonraki bar açılışında.

    Stop değişikliği sadece sonraki bar için geçerli. Stop-hedef aynı barda
    sırası bilinmiyorsa stop önce. Gap stop açılış fiyatından doldurulur.
    Verilen son bar, karşılaştırmanın aynı zaman ufkunu taşımalıdır.
    """
    if not bars or direction not in (-1, 1):
        raise ValueError('empty bars or invalid direction')
    risk=abs(entry-stop)
    if risk <= 0 or direction*(entry-stop) <= 0 or direction*(target-entry) <= 0:
        raise ValueError('invalid levels')
    if cfg.mtf_action not in ('none','exit','protect'):
        raise ValueError('invalid action')
    if cfg.protect_trigger_r is not None and (cfg.protect_trigger_r <= cfg.protect_lock_r or cfg.protect_lock_r < 0):
        raise ValueError('lock must be below trigger')
    half_seen=False; exit_pending=False; signals=0; current_stop=stop
    for i,b in enumerate(bars):
        if exit_pending:
            return ManagementOutcome(direction*(b.open-entry)/risk,'MTF_EXIT_OPEN',i,signals)
        # `reason` ilk stop ile taşınmış koruma stopunu ayırmaz; ayrım `stop_moved` ile yapılır.
        moved=current_stop!=stop
        if direction*(b.open-current_stop) <= 0:
            return ManagementOutcome(direction*(b.open-entry)/risk,'STOP_GAP',i,signals,moved)
        adverse=b.low if direction==1 else b.high
        favorable=b.high if direction==1 else b.low
        if direction*(adverse-current_stop) <= 0:
            return ManagementOutcome(direction*(current_stop-entry)/risk,'STOP',i,signals,moved)
        if direction*(favorable-target) >= 0:
            return ManagementOutcome(direction*(target-entry)/risk,'HEDEF',i,signals)
        # Bar sıralaması bilinmediğinden aktivasyon yalnız bu barın kapanışında.
        half_seen = half_seen or direction*(favorable-entry) >= .5*risk
        signal=mtf_signal(b.close_time,direction,b.two,b.one,b.four,
                          two_mode=cfg.two_mode,four_mode=cfg.four_mode,
                          four_state_kalici=cfg.four_state_kalici).signal
        if cfg.mtf_action != 'none' and signal and (not cfg.activate_after_half_r or half_seen):
            signals+=1
            if cfg.mtf_action=='exit': exit_pending=True
            elif cfg.mtf_action=='protect' and direction*(b.close-entry)>0:
                # MTF koruması: başa baş, sonraki bardan itibaren.
                current_stop=protected_stop(entry,risk,direction,current_stop,0)
        if cfg.protect_trigger_r is not None and direction*(favorable-entry)>=cfg.protect_trigger_r*risk:
            current_stop=protected_stop(entry,risk,direction,current_stop,cfg.protect_lock_r)
    return ManagementOutcome(direction*(bars[-1].close-entry)/risk,
                             'MTF_PENDING_HORIZON' if exit_pending else 'ZAMAN_STOPU',len(bars)-1,signals,
                             current_stop!=stop)
