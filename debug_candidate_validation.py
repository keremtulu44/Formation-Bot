import numpy as np
import pandas as pd

from patterns import (
    find_best_triangle_candidate,
    find_pivots,
    calculate_atr,
    f_line_price,
)


def create_random_walk(n_bars=250, start_price=100.0):
    np.random.seed(42)

    returns = np.random.normal(0, 1.0, n_bars)
    close = start_price + np.cumsum(returns)
    close = np.maximum(close, 1.0)

    high = close + np.abs(np.random.normal(0, 0.5, n_bars))
    low = close - np.abs(np.random.normal(0, 0.5, n_bars))

    return pd.DataFrame({
        "close": close,
        "high": high,
        "low": low,
    })


print()
print("=" * 70)
print("CANDIDATE INDEPENDENT VALIDATION")
print("=" * 70)

df = create_random_walk()

candidate, logs = find_best_triangle_candidate(
    df,
    profile="Dengeli",
    verbose=False
)

if candidate is None or not candidate.valid:
    print("Aday bulunamadı.")
    raise SystemExit(0)

print()
print("--- CANDIDATE ---")
print("Pattern       :", candidate.pattern_type)
print("Quality       :", candidate.raw_quality)
print("Start         :", candidate.start_bar)
print("End           :", candidate.end_bar)
print("Current       :", len(df) - 1)
print("Apex          :", candidate.apex_bar)

atr = calculate_atr(df, 14)
current_atr = float(atr.iloc[-1])

print()
print("--- CURRENT STATE ---")

for i in range(candidate.end_bar, len(df)):
    close = float(df["close"].iloc[i])
    high = float(df["high"].iloc[i])
    low = float(df["low"].iloc[i])

    upper = f_line_price(
        candidate.hb1,
        candidate.hp1,
        candidate.hb2,
        candidate.hp2,
        i
    )

    lower = f_line_price(
        candidate.lb1,
        candidate.lp1,
        candidate.lb2,
        candidate.lp2,
        i
    )

    if close > upper:
        state = "CLOSE > UPPER"
    elif close < lower:
        state = "CLOSE < LOWER"
    elif high > upper:
        state = "WICK > UPPER"
    elif low < lower:
        state = "WICK < LOWER"
    else:
        state = "INSIDE"

    print(
        f"bar={i:3d} "
        f"close={close:9.3f} "
        f"upper={upper:9.3f} "
        f"lower={lower:9.3f} "
        f"state={state}"
    )

print()
print("--- INDEPENDENT PIVOT CHECK ---")

pivot_len = 5
high_pivots, low_pivots = find_pivots(df, pivot_len)

selected_high = {
    candidate.hb1,
    candidate.hb2,
}

selected_low = {
    candidate.lb1,
    candidate.lb2,
}

independent_high = [
    p for p in high_pivots
    if candidate.start_bar <= p["bar"] <= candidate.end_bar
    and p["bar"] not in selected_high
]

independent_low = [
    p for p in low_pivots
    if candidate.start_bar <= p["bar"] <= candidate.end_bar
    and p["bar"] not in selected_low
]

print("Independent high pivots:", len(independent_high))
print("Independent low pivots :", len(independent_low))

print()
print("HIGH PIVOTS")

for p in independent_high:
    expected = f_line_price(
        candidate.hb1,
        candidate.hp1,
        candidate.hb2,
        candidate.hp2,
        p["bar"]
    )

    distance = p["price"] - expected

    print(
        f"bar={p['bar']:3d} "
        f"price={p['price']:9.3f} "
        f"line={expected:9.3f} "
        f"distance={distance:9.3f} "
        f"ATR_dist={distance / current_atr:7.3f}"
    )

print()
print("LOW PIVOTS")

for p in independent_low:
    expected = f_line_price(
        candidate.lb1,
        candidate.lp1,
        candidate.lb2,
        candidate.lp2,
        p["bar"]
    )

    distance = p["price"] - expected

    print(
        f"bar={p['bar']:3d} "
        f"price={p['price']:9.3f} "
        f"line={expected:9.3f} "
        f"distance={distance:9.3f} "
        f"ATR_dist={distance / current_atr:7.3f}"
    )

print()
print("--- ACTUAL PRICE WIDTH ---")

for i in [
    candidate.start_bar,
    candidate.end_bar,
    len(df) - 1
]:
    high = float(df["high"].iloc[i])
    low = float(df["low"].iloc[i])
    actual_width = high - low

    upper = f_line_price(
        candidate.hb1,
        candidate.hp1,
        candidate.hb2,
        candidate.hp2,
        i
    )

    lower = f_line_price(
        candidate.lb1,
        candidate.lp1,
        candidate.lb2,
        candidate.lp2,
        i
    )

    line_width = upper - lower

    print(
        f"bar={i:3d} "
        f"actual_width={actual_width:9.3f} "
        f"line_width={line_width:9.3f}"
    )

print()
print("=" * 70)
print("END")
print("=" * 70)
