"""Yahoo Finance isteklerini tek iş parçacığında, kontrollü aralıklarla yürütür."""

import random
import time
from contextlib import contextmanager
from typing import Callable, Iterator, Optional


class YahooRequestPacer:
    """İstekler arasında bekler ve her grup isteğinden sonra daha uzun ara verir.

    Grup boyutu, hisse sayısından ziyade gerçek Yahoo isteklerini sayar. Örneğin bir
    sembol için hem 1H hem 1D veri gerektiğinde iki istek de rate-limit'e tabidir.
    """

    def __init__(
        self,
        batch_size: int,
        request_delay_min: float,
        request_delay_max: float,
        batch_pause_min: float,
        batch_pause_max: float,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
        uniform_fn: Callable[[float, float], float] = random.uniform,
        logger=None,
    ):
        if batch_size < 1:
            raise ValueError("batch_size en az 1 olmalı")
        if request_delay_min < 0 or request_delay_max < request_delay_min:
            raise ValueError("İstek bekleme aralığı geçersiz")
        if batch_pause_min < 0 or batch_pause_max < batch_pause_min:
            raise ValueError("Grup bekleme aralığı geçersiz")

        self.batch_size = batch_size
        self.request_delay_min = request_delay_min
        self.request_delay_max = request_delay_max
        self.batch_pause_min = batch_pause_min
        self.batch_pause_max = batch_pause_max
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn
        self.uniform_fn = uniform_fn
        self.logger = logger
        self._requests_in_batch = 0
        self._last_request_finished: Optional[float] = None

    def reset_batch(self) -> None:
        """Backoff sonrası yeniden deneme grubuna temiz bir başlangıç ver."""
        self._requests_in_batch = 0

    def _wait_for_slot(self, label: str) -> None:
        if self._requests_in_batch >= self.batch_size:
            pause = self.uniform_fn(self.batch_pause_min, self.batch_pause_max)
            if self.logger:
                self.logger.info(
                    f"Yahoo istek grubu tamamlandı ({self.batch_size} istek); "
                    f"{pause:.1f} sn ara veriliyor"
                )
            self.sleep_fn(pause)
            self._requests_in_batch = 0
        elif self._last_request_finished is not None:
            target_delay = self.uniform_fn(
                self.request_delay_min, self.request_delay_max
            )
            elapsed = self.monotonic_fn() - self._last_request_finished
            remaining = max(0.0, target_delay - elapsed)
            if remaining > 0:
                if self.logger:
                    self.logger.debug(
                        f"{label} Yahoo isteği öncesi {remaining:.1f} sn bekleniyor"
                    )
                self.sleep_fn(remaining)

        self._requests_in_batch += 1

    @contextmanager
    def request(self, label: str = "") -> Iterator[None]:
        """İstek çevresinde pacing uygular; hata olsa da sonraki isteği zamanlar."""
        self._wait_for_slot(label)
        try:
            yield
        finally:
            self._last_request_finished = self.monotonic_fn()
