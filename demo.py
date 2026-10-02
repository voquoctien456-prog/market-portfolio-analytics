from market_analytics import resolve_symbols, fetch_vnstock_data, calculate_asset_metrics, calculate_portfolio_metrics, optimize_portfolio
from pathlib import Path
import pandas as pd


SYMBOLS = None  # Nếu None thì tự động lấy HOSE / mặc định
START_DATE = "2023-01-01"
END_DATE = "2024-10-02"
RISK_FREE = 0.025


def run_demo():
    symbols = resolve_symbols(type("Args", (), {"symbols": SYMBOLS, "all_hose": True, "top_n": 10, "sample_every_n": 1})())
    weights = pd.Series([1 / len(symbols)] * len(symbols), index=symbols)
    prices = fetch_vnstock_data(symbols, START_DATE, END_DATE)
    metrics, _ = calculate_asset_metrics(prices, RISK_FREE)
    summary, weighted_returns = calculate_portfolio_metrics(prices, weights, RISK_FREE)
    opt_weights, opt_return, opt_vol, opt_sharpe = optimize_portfolio(prices, RISK_FREE)

    print("\nBảng chỉ số từng cổ phiếu")
    print(metrics.round(4).to_string())
    print("\nTổng hợp danh mục")
    for k, v in summary.items():
        print(f"{k}: {v:.4f}")
    print("\nDanh mục tối ưu")
    print(opt_weights.to_string())
    print(f"Sharpe: {opt_sharpe:.4f}")

    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    prices.reset_index().rename(columns={"index": "date"}).to_csv(out_dir / "demo_market_prices.csv", index=False)
    metrics.reset_index().to_csv(out_dir / "demo_asset_metrics.csv", index=False)
    pd.DataFrame([summary]).to_csv(out_dir / "demo_summary.csv", index=False)
    print("\nĐã lưu file demo trong outputs/")


if __name__ == "__main__":
    run_demo()
