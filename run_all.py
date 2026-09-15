"""Run the full pipeline in order.

Ordering matters: 10_merge_manual_shares must run after 07_shares (which
rebuilds the shares table from scratch) and before 08_concentration.
"""
import subprocess
import sys
import time
from pathlib import Path

STEPS = [
    "01_membership.py",
    "02_prices_yf.py",
    "04_prices_tiingo.py",
    "06_merge_prices.py",
    "07_shares.py",
    "09_manual_shares.py",
    "10_merge_manual_shares.py",
    "08_concentration.py",
    "11_validate_spy.py",
    "12_risk_l1.py",
    "13_risk_l2.py",
    "14_risk_pca.py",
    "15_risk_decomp.py",
    "16_stress_test.py",
    "17_var_es.py",
    "18_backtest.py",
    "19_rolling_backtest.py",
    "20_evt.py",
    "21_counterfactual.py",
    "22_fundamentals.py",
    "23_capex_analysis.py",
    "25_rolling_risk.py",
    "26_export_summary.py",
    "27_export_methodology.py",
    "24_export_for_bi.py",
]

def main():
    start = time.time()
    for i, step in enumerate(STEPS, 1):
        path = Path("src") / step
        if not path.exists():
            print(f"[{i}/{len(STEPS)}] SKIP {step} (not found)")
            continue
        print(f"\n[{i}/{len(STEPS)}] {step}")
        t = time.time()
        r = subprocess.run([sys.executable, str(path)])
        if r.returncode != 0:
            print(f"\nFAILED at {step}. Stopping.")
            sys.exit(1)
        print(f"  done in {time.time() - t:.0f}s")
    print(f"\nPipeline complete in {(time.time() - start) / 60:.1f} minutes")

if __name__ == "__main__":
    main()