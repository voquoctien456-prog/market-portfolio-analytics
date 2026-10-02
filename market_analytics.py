import argparse
from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

try:
    import vnstock
except ImportError:
    vnstock = None


def parse_args():
    parser = argparse.ArgumentParser(description="Phân tích danh mục đầu tư thị trường Việt Nam")
    parser.add_argument("--symbols", nargs="+", required=True, help="Danh sách mã chứng khoán Việt Nam")
    parser.add_argument(
        "--weights",
        nargs="+",
        type=float,
        default=None,
        help="Trọng số tương ứng với các mã cổ phiếu. Tổng sẽ được chuẩn hóa về 1 nếu khác 1.",
    )
    parser.add_argument("--start", default="2023-01-01", help="Ngày bắt đầu, ví dụ: 2023-01-01")
    parser.add_argument("--end", default=None, help="Ngày kết thúc, mặc định là hôm nay")
    parser.add_argument("--risk-free", type=float, default=0.025, help="Lãi suất phi rủi ro năm, mặc định 2.5%")
    parser.add_argument("--save-csv", action="store_true", help="Lưu file CSV kết quả phân tích")
    return parser.parse_args()


def normalize_weights(symbols, weights):
    if weights is None:
        weights = [1 / len(symbols)] * len(symbols)
    if len(weights) != len(symbols):
        raise ValueError("Số lượng trọng số phải khớp số lượng mã cổ phiếu.")
    weights = np.asarray(weights, dtype=float)
    total = weights.sum()
    if total <= 0:
        raise ValueError("Tổng trọng số phải dương.")
    weights = weights / total
    return pd.Series(weights, index=symbols, dtype=float)


def fetch_vnstock_data(symbols, start, end):
    if vnstock is None:
        raise ImportError("vnstock chưa được cài đặt. Hãy chạy: pip install vnstock")

    frames = []
    for symbol in symbols:
        try:
            df = vnstock.stock_historical(symbol, start_date=start, end_date=end, interval="1D")
            if df is None or df.empty:
                print(f"Cảnh báo: không có dữ liệu cho {symbol}. Bỏ qua.")
                continue

            if "date" in df.columns:
                df = df.copy()
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")

            if "close" in df.columns:
                series = df["close"].rename(symbol)
            elif "Close" in df.columns:
                series = df["Close"].rename(symbol)
            else:
                print(f"Cảnh báo: dữ liệu {symbol} không có cột close phù hợp. Bỏ qua.")
                continue

            frames.append(series)
        except Exception as exc:
            print(f"Cảnh báo: không lấy được dữ liệu cho {symbol}: {exc}")

    if not frames:
        raise ValueError("Không có dữ liệu hợp lệ nào được lấy từ vnstock.")

    combined = pd.concat(frames, axis=1).sort_index()
    return combined


def compute_daily_returns(prices):
    return prices.pct_change().dropna()


def annualized_return(daily_returns, periods=252):
    if daily_returns.empty:
        return 0.0
    cumulative = (1 + daily_returns).prod() - 1
    years = len(daily_returns) / periods
    if years <= 0:
        return 0.0
    return (1 + cumulative) ** (1 / years) - 1


def volatility(daily_returns, periods=252):
    if daily_returns.empty:
        return 0.0
    return daily_returns.std(ddof=1) * np.sqrt(periods)


def sharpe_ratio(daily_returns, risk_free_rate=0.025, periods=252):
    if daily_returns.empty:
        return 0.0
    excess = daily_returns - (risk_free_rate / periods)
    std = excess.std(ddof=1)
    if std == 0:
        return 0.0
    return (excess.mean() * periods) / (std * np.sqrt(periods))


def max_drawdown(prices):
    if prices.empty:
        return 0.0
    rolling_max = prices.cummax()
    drawdown = (prices / rolling_max) - 1
    return float(drawdown.min())


def calculate_asset_metrics(prices, risk_free_rate=0.025, periods=252):
    returns = compute_daily_returns(prices)
    metrics = pd.DataFrame(index=prices.columns)
    metrics["annualized_return"] = returns.apply(lambda s: annualized_return(s, periods=periods))
    metrics["volatility"] = returns.apply(lambda s: volatility(s, periods=periods))
    metrics["sharpe_ratio"] = returns.apply(lambda s: sharpe_ratio(s, risk_free_rate=risk_free_rate, periods=periods))
    metrics["max_drawdown"] = prices.apply(max_drawdown)
    metrics.index.name = "symbol"
    return metrics, returns


def calculate_portfolio_metrics(prices, weights, risk_free_rate=0.025, periods=252):
    returns = compute_daily_returns(prices)
    weighted_returns = returns.mul(weights, axis=1).sum(axis=1)
    portfolio_growth = (1 + weighted_returns).cumprod()

    summary = {
        "portfolio_annualized_return": annualized_return(weighted_returns, periods=periods),
        "portfolio_volatility": volatility(weighted_returns, periods=periods),
        "portfolio_sharpe_ratio": sharpe_ratio(weighted_returns, risk_free_rate=risk_free_rate, periods=periods),
        "portfolio_max_drawdown": max_drawdown(portfolio_growth),
    }
    return summary, weighted_returns


def save_outputs(prices, metrics, portfolio_summary, weighted_returns):
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    prices.reset_index().rename(columns={"index": "date"}).to_csv(out_dir / "market_prices.csv", index=False)
    metrics.reset_index().to_csv(out_dir / "asset_metrics.csv", index=False)
    pd.DataFrame([portfolio_summary]).to_csv(out_dir / "portfolio_summary.csv", index=False)
    pd.DataFrame({"date": weighted_returns.index, "portfolio_daily_return": weighted_returns.values}).to_csv(
        out_dir / "portfolio_daily_returns.csv", index=False
    )

    print(f"\nĐã lưu file CSV vào thư mục: {out_dir}")


def main():
    args = parse_args()
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")

    try:
        weights = normalize_weights(args.symbols, args.weights)
    except ValueError as exc:
        print(f"Lỗi: {exc}")
        sys.exit(1)

    try:
        prices = fetch_vnstock_data(args.symbols, args.start, end_date)
    except Exception as exc:
        print(f"Lỗi khi lấy dữ liệu: {exc}")
        sys.exit(1)

    prices = prices.loc[:, [symbol for symbol in args.symbols if symbol in prices.columns]]
    if prices.empty:
        print("Không có dữ liệu hợp lệ cho các mã cổ phiếu yêu cầu.")
        sys.exit(1)

    metrics, _ = calculate_asset_metrics(prices, risk_free_rate=args.risk_free)
    portfolio_summary, weighted_returns = calculate_portfolio_metrics(
        prices,
        weights,
        risk_free_rate=args.risk_free,
    )

    print("\nBẢNG PHÂN TÍCH TỪNG CỔ PHIẾU")
    print(metrics.round(4).to_string())

    print("\nTỔNG HỢP DANH MỤC")
    for key, value in portfolio_summary.items():
        print(f"{key}: {value:.4f}")

    if args.save_csv:
        save_outputs(prices, metrics, portfolio_summary, weighted_returns)


if __name__ == "__main__":
    main()
