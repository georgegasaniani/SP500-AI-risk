"""Small helpers shared by several scripts."""
import numpy as np
import pandas as pd

# Split ratios that actually occur (2-for-1, 3-for-2, 1-for-10 reverse splits...).
_NICE = np.array(sorted({a / b for a in range(1, 51) for b in range(1, 11)
                         if (a % b or b == 1) and 1.15 <= max(a / b, b / a) <= 50}
                        | {1 / a for a in range(2, 51)}))


def split_factor(q_ratio, p_ratio):
    """Split factor implied by one company's holdings on two consecutive files.

    q_ratio: change in the fund's quantity of the stock, divided by the fund's overall
             change in quantities that day (the median over all stocks), so that fund
             inflows and outflows cancel out
    p_ratio: price today / price on the previous file

    A split multiplies the quantity by k and divides the price by k, so the price change
    after undoing the split, p_ratio * k, looks like a normal day. Returns k (snapped to
    the nearest usual split ratio when one is within 2%), or 1 when there was no split.
    A quantity jump without the matching price drop (the index raising the share count
    after a merger, for example) is not a split.
    """
    q = np.asarray(q_ratio, dtype=float)
    p = np.asarray(p_ratio, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        idx = np.clip(np.searchsorted(_NICE, q), 1, len(_NICE) - 1)
        lo, hi = _NICE[idx - 1], _NICE[idx]
        near = np.where(np.abs(np.log(q / lo)) < np.abs(np.log(q / hi)), lo, hi)
        k = np.where(np.abs(np.log(q / near)) < 0.02, near, q)
        is_split = ((np.abs(np.log(q)) > np.log(1.15))
                    & (np.abs(np.log(p * k)) < 0.25)
                    & (np.abs(np.log(p * k)) < np.abs(np.log(p)) / 2))
    return pd.Series(np.where(is_split, k, 1.0)).fillna(1.0).values
