import argparse
from datetime import datetime
from pathlib import Path
import sys
import base64
import io

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.optimize import minimize
from jinja2 import Template

try:
    from weasyprint import HTML, CSS
except ImportError:
    HTML = None

try:
    import vnstock
except ImportError:
    vnstock = None

# Thiết lập style cho biểu đồ
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (14, 8)
plt.rcParams["font.family"] = "DejaVu Sans"


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
    parser.add_argument("--save-plots", action="store_true", help="Lưu biểu đồ PNG")
    parser.add_argument("--save-html", action="store_true", help="Lưu báo cáo HTML")
    parser.add_argument("--save-pdf", action="store_true", help="Lưu báo cáo PDF")
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
    metrics["max_drawdown"] = returns.apply(lambda s: max_drawdown((1 + s).cumprod()))
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


# ============== PORTFOLIO OPTIMIZATION ==============


def optimize_portfolio(prices, risk_free_rate=0.025, objective="sharpe"):
    """Tối ưu hóa danh mục đầu tư theo Sharpe Ratio hoặc Min Variance"""
    returns = compute_daily_returns(prices)
    mean_returns = returns.mean() * 252
    cov_matrix = returns.cov() * 252
    num_assets = len(mean_returns)

    def portfolio_performance(weights):
        portfolio_return = np.sum(mean_returns * weights)
        portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe = (portfolio_return - risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
        return portfolio_return, portfolio_vol, sharpe

    def negative_sharpe(weights):
        return -portfolio_performance(weights)[2]

    def portfolio_volatility(weights):
        return portfolio_performance(weights)[1]

    constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
    bounds = tuple((0, 1) for _ in range(num_assets))
    init_guess = np.array([1.0 / num_assets] * num_assets)

    if objective == "sharpe":
        result = minimize(negative_sharpe, init_guess, method="SLSQP", bounds=bounds, constraints=constraints)
    else:  # min_variance
        result = minimize(portfolio_volatility, init_guess, method="SLSQP", bounds=bounds, constraints=constraints)

    optimal_weights = result.x
    opt_return, opt_vol, opt_sharpe = portfolio_performance(optimal_weights)

    return pd.Series(optimal_weights, index=prices.columns), opt_return, opt_vol, opt_sharpe


# ============== VISUALIZATION FUNCTIONS ==============


def plot_to_base64(fig):
    """Chuyển đổi matplotlib figure thành base64 string"""
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format="png", dpi=100, bbox_inches="tight")
    img_buffer.seek(0)
    img_base64 = base64.b64encode(img_buffer.read()).decode()
    plt.close(fig)
    return img_base64


def create_price_chart(prices):
    """Tạo biểu đồ giá"""
    fig, ax = plt.subplots(figsize=(12, 6))
    for col in prices.columns:
        ax.plot(prices.index, prices[col], label=col, linewidth=2, alpha=0.7)
    ax.set_title("Giá đóng cửa theo thời gian", fontsize=12, fontweight="bold")
    ax.set_xlabel("Ngày")
    ax.set_ylabel("Giá (VND)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return plot_to_base64(fig)


def create_cumulative_returns_chart(weighted_returns):
    """Tạo biểu đồ lợi suất tích lũy"""
    fig, ax = plt.subplots(figsize=(12, 6))
    cumulative = (1 + weighted_returns).cumprod() - 1
    ax.plot(cumulative.index, cumulative * 100, linewidth=2.5, color="darkgreen")
    ax.fill_between(cumulative.index, cumulative * 100, alpha=0.3, color="green")
    ax.set_title("Lợi suất tích lũy danh mục", fontsize=12, fontweight="bold")
    ax.set_xlabel("Ngày")
    ax.set_ylabel("Lợi suất tích lũy (%)")
    ax.grid(True, alpha=0.3)
    return plot_to_base64(fig)


def create_risk_return_chart(metrics, weights):
    """Tạo biểu đồ rủi ro - lợi suất"""
    fig, ax = plt.subplots(figsize=(10, 8))
    x = metrics["volatility"] * 100
    y = metrics["annualized_return"] * 100
    colors = plt.cm.viridis(np.linspace(0, 1, len(metrics)))

    for idx, symbol in enumerate(metrics.index):
        ax.scatter(x[symbol], y[symbol], s=300, alpha=0.7, color=colors[idx], label=symbol, edgecolors="black", linewidth=2)
        ax.annotate(symbol, (x[symbol], y[symbol]), xytext=(5, 5), textcoords="offset points", fontsize=10, fontweight="bold")

    portfolio_vol = np.sqrt((weights**2 * metrics["volatility"]**2).sum()) * 100
    portfolio_ret = (weights * metrics["annualized_return"]).sum() * 100
    ax.scatter(portfolio_vol, portfolio_ret, s=400, color="red", marker="*", label="Portfolio", edgecolors="darkred", linewidth=2)
    ax.annotate("Portfolio", (portfolio_vol, portfolio_ret), xytext=(10, 10), textcoords="offset points", fontsize=12, fontweight="bold", color="red")

    ax.set_xlabel("Độ biến động (%)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Lợi suất hàng năm (%)", fontsize=12, fontweight="bold")
    ax.set_title("Rủi ro - Lợi suất", fontsize=14, fontweight="bold")
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, alpha=0.3)
    return plot_to_base64(fig)


def create_correlation_chart(returns):
    """Tạo bản đồ tương quan"""
    fig, ax = plt.subplots(figsize=(10, 8))
    correlation = returns.corr()
    sns.heatmap(correlation, annot=True, fmt=".3f", cmap="coolwarm", center=0, square=True, linewidths=1, cbar_kws={"label": "Correlation"}, ax=ax)
    ax.set_title("Ma trận tương quan", fontsize=14, fontweight="bold")
    return plot_to_base64(fig)


# ============== REPORT GENERATION ==============


def generate_html_report(
    prices,
    metrics,
    portfolio_summary,
    weighted_returns,
    opt_weights,
    opt_return,
    opt_vol,
    opt_sharpe,
    weights,
    risk_free_rate,
    start_date,
    end_date,
    output_path,
):
    """Tạo báo cáo HTML"""
    returns = compute_daily_returns(prices)

    # Tạo biểu đồ
    price_chart = create_price_chart(prices)
    returns_chart = create_cumulative_returns_chart(weighted_returns)
    risk_return_chart = create_risk_return_chart(metrics, weights)
    correlation_chart = create_correlation_chart(returns)

    # Chuẩn bị dữ liệu cho template
    metrics_html = metrics.to_html(classes="table table-striped", float_format=lambda x: f"{x:.4f}")
    weights_html = weights.to_frame("Weight (%)").mul(100).to_html(classes="table table-striped", float_format=lambda x: f"{x:.2f}")
    opt_weights_html = opt_weights.to_frame("Optimal Weight (%)").mul(100).to_html(classes="table table-striped", float_format=lambda x: f"{x:.2f}")

    template_str = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Báo cáo Phân tích Danh mục Đầu tư</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; background-color: white; }
            header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; border-radius: 10px; margin-bottom: 40px; }
            header h1 { font-size: 2.5em; margin-bottom: 10px; }
            header p { font-size: 1.1em; opacity: 0.9; }
            .section { margin-bottom: 40px; padding: 20px; background-color: #f9f9f9; border-radius: 8px; border-left: 5px solid #667eea; }
            .section h2 { color: #667eea; margin-bottom: 20px; font-size: 1.8em; }
            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            th { background-color: #667eea; color: white; padding: 12px; text-align: left; }
            td { padding: 10px; border-bottom: 1px solid #ddd; }
            tr:hover { background-color: #f0f0f0; }
            .metrics-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 20px 0; }
            .metric-card { background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .metric-card h3 { color: #667eea; margin-bottom: 10px; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; }
            .metric-card .value { font-size: 2em; font-weight: bold; color: #333; }
            .positive { color: #27ae60; }
            .negative { color: #e74c3c; }
            img { max-width: 100%; height: auto; margin: 20px 0; border-radius: 8px; }
            .footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; border-top: 1px solid #ddd; margin-top: 40px; }
            .comparison { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
            .comparison-card { background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .comparison-card h4 { color: #667eea; margin-bottom: 10px; }
            .comparison-card ul { list-style-position: inside; }
            .comparison-card li { margin: 5px 0; }
            .page-break { page-break-after: always; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>📊 Báo cáo Phân tích Danh mục Đầu tư</h1>
                <p>Thị trường Chứng khoán Việt Nam</p>
                <p>Tạo: {{ report_date }}</p>
            </header>

            <!-- Thông tin chung -->
            <div class="section">
                <h2>📋 Thông tin Báo cáo</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Khoảng thời gian</h3>
                        <div class="value">{{ start_date }} → {{ end_date }}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Số ngày giao dịch</h3>
                        <div class="value">{{ num_trading_days }}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Số cổ phiếu</h3>
                        <div class="value">{{ num_symbols }}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Lãi suất phi rủi ro</h3>
                        <div class="value">{{ risk_free_rate }}%</div>
                    </div>
                </div>
            </div>

            <!-- Giá cổ phiếu -->
            <div class="section">
                <h2>📈 Giá Cổ phiếu</h2>
                <img src="data:image/png;base64,{{ price_chart }}" alt="Price Chart">
            </div>

            <!-- Chỉ số hiệu suất -->
            <div class="section">
                <h2>📊 Chỉ số Hiệu suất Từng Cổ phiếu</h2>
                {{ metrics_table }}
                <br>
                <div class="metrics-grid">
                    {% for symbol, row in metrics_data %}
                    <div class="metric-card">
                        <h3>{{ symbol }}</h3>
                        <div>
                            <p>Return: <span class="{% if row.return >= 0 %}positive{% else %}negative{% endif %}">{{ row.return }}%</span></p>
                            <p>Volatility: {{ row.volatility }}%</p>
                            <p>Sharpe Ratio: {{ row.sharpe }}</p>
                            <p>Max Drawdown: <span class="negative">{{ row.drawdown }}%</span></p>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <!-- Danh mục hiện tại -->
            <div class="section">
                <h2>🎯 Danh mục Hiện tại</h2>
                <h3>Trọng số</h3>
                {{ weights_table }}
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Lợi suất hàng năm</h3>
                        <div class="value {% if portfolio_return >= 0 %}positive{% else %}negative{% endif %}">{{ portfolio_return }}%</div>
                    </div>
                    <div class="metric-card">
                        <h3>Volatility</h3>
                        <div class="value">{{ portfolio_volatility }}%</div>
                    </div>
                    <div class="metric-card">
                        <h3>Sharpe Ratio</h3>
                        <div class="value">{{ portfolio_sharpe }}</div>
                    </div>
                    <div class="metric-card">
                        <h3>Max Drawdown</h3>
                        <div class="value negative">{{ portfolio_drawdown }}%</div>
                    </div>
                </div>
            </div>

            <div class="page-break"></div>

            <!-- Portfolio Optimization -->
            <div class="section">
                <h2>🚀 Danh mục Tối ưu (Sharpe Ratio Max)</h2>
                <h3>Trọng số Tối ưu</h3>
                {{ opt_weights_table }}
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Lợi suất hàng năm</h3>
                        <div class="value {% if opt_return >= 0 %}positive{% else %}negative{% endif %}">{{ opt_return }}%</div>
                    </div>
                    <div class="metric-card">
                        <h3>Volatility</h3>
                        <div class="value">{{ opt_volatility }}%</div>
                    </div>
                    <div class="metric-card">
                        <h3>Sharpe Ratio</h3>
                        <div class="value">{{ opt_sharpe }}</div>
                    </div>
                </div>
                <div class="comparison">
                    <div class="comparison-card">
                        <h4>Danh mục Hiện tại</h4>
                        <ul>
                            <li>Return: {{ portfolio_return }}%</li>
                            <li>Volatility: {{ portfolio_volatility }}%</li>
                            <li>Sharpe: {{ portfolio_sharpe }}</li>
                        </ul>
                    </div>
                    <div class="comparison-card">
                        <h4>Danh mục Tối ưu</h4>
                        <ul>
                            <li>Return: {{ opt_return }}%</li>
                            <li>Volatility: {{ opt_volatility }}%</li>
                            <li>Sharpe: {{ opt_sharpe }}</li>
                        </ul>
                    </div>
                </div>
            </div>

            <!-- Biểu đồ hiệu suất -->
            <div class="section">
                <h2>📉 Lợi suất Tích lũy</h2>
                <img src="data:image/png;base64,{{ returns_chart }}" alt="Cumulative Returns">
            </div>

            <!-- Biểu đồ rủi ro -->
            <div class="section">
                <h2>⚖️ Rủi ro - Lợi suất</h2>
                <img src="data:image/png;base64,{{ risk_return_chart }}" alt="Risk Return">
            </div>

            <!-- Tương quan -->
            <div class="section">
                <h2>🔗 Ma trận Tương quan</h2>
                <img src="data:image/png;base64,{{ correlation_chart }}" alt="Correlation Heatmap">
            </div>

            <footer class="footer">
                <p>Báo cáo này được tạo tự động bởi Market & Portfolio Analytics</p>
                <p>Dữ liệu tài chính chỉ mang tính tham khảo và không thay thế tư vấn đầu tư chuyên nghiệp</p>
                <p>© 2026 Vo Quoc Tien | All Rights Reserved</p>
            </footer>
        </div>
    </body>
    </html>
    """

    # Chuẩn bị dữ liệu cho template
    metrics_data = []
    for symbol in metrics.index:
        metrics_data.append(
            (
                symbol,
                {
                    "return": f"{metrics.loc[symbol, 'annualized_return']*100:.2f}",
                    "volatility": f"{metrics.loc[symbol, 'volatility']*100:.2f}",
                    "sharpe": f"{metrics.loc[symbol, 'sharpe_ratio']:.4f}",
                    "drawdown": f"{metrics.loc[symbol, 'max_drawdown']*100:.2f}",
                },
            )
        )

    template = Template(template_str)
    html_content = template.render(
        report_date=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        start_date=start_date,
        end_date=end_date,
        num_trading_days=len(prices),
        num_symbols=len(prices.columns),
        risk_free_rate=f"{risk_free_rate*100:.2f}",
        metrics_table=metrics_html,
        metrics_data=metrics_data,
        weights_table=weights_html,
        opt_weights_table=opt_weights_html,
        price_chart=price_chart,
        returns_chart=returns_chart,
        risk_return_chart=risk_return_chart,
        correlation_chart=correlation_chart,
        portfolio_return=f"{portfolio_summary['portfolio_annualized_return']*100:.2f}",
        portfolio_volatility=f"{portfolio_summary['portfolio_volatility']*100:.2f}",
        portfolio_sharpe=f"{portfolio_summary['portfolio_sharpe_ratio']:.4f}",
        portfolio_drawdown=f"{portfolio_summary['portfolio_max_drawdown']*100:.2f}",
        opt_return=f"{opt_return*100:.2f}",
        opt_volatility=f"{opt_vol*100:.2f}",
        opt_sharpe=f"{opt_sharpe:.4f}",
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Lưu báo cáo HTML: {output_path}")


def generate_pdf_report(html_path, pdf_path):
    """Chuyển HTML thành PDF"""
    if HTML is None:
        print("Cảnh báo: WeasyPrint chưa được cài đặt. Bỏ qua tạo PDF.")
        return

    try:
        HTML(string=open(html_path, encoding="utf-8").read()).write_pdf(pdf_path)
        print(f"Lưu báo cáo PDF: {pdf_path}")
    except Exception as exc:
        print(f"Lỗi khi tạo PDF: {exc}")


def save_outputs(prices, metrics, portfolio_summary, weighted_returns, save_csv=False, save_plots=False):
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    if save_csv:
        prices.reset_index().rename(columns={"index": "date"}).to_csv(out_dir / "market_prices.csv", index=False)
        metrics.reset_index().to_csv(out_dir / "asset_metrics.csv", index=False)
        pd.DataFrame([portfolio_summary]).to_csv(out_dir / "portfolio_summary.csv", index=False)
        pd.DataFrame({"date": weighted_returns.index, "portfolio_daily_return": weighted_returns.values}).to_csv(
            out_dir / "portfolio_daily_returns.csv", index=False
        )
        print(f"Lưu file CSV vào: {out_dir}")


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

    print("\n" + "="*80)
    print("THỐNG KÊ MÔ TẢ DỮ LIỆU GIÁ")
    print("="*80)
    print(prices.describe().round(2))

    metrics, returns = calculate_asset_metrics(prices, risk_free_rate=args.risk_free)
    portfolio_summary, weighted_returns = calculate_portfolio_metrics(prices, weights, risk_free_rate=args.risk_free)

    print("\n" + "="*80)
    print("THỐNG KÊ MÔ TẢ LỢI SUẤT HÀNG NGÀY")
    print("="*80)
    print(returns.describe().round(4))

    print("\n" + "="*80)
    print("MA TRẬN TƯƠNG QUAN")
    print("="*80)
    print(returns.corr().round(4))

    print("\n" + "="*80)
    print("BẢNG PHÂN TÍCH TỪNG CỔ PHIẾU")
    print("="*80)
    print(metrics.round(4).to_string())

    print("\n" + "="*80)
    print("TRỌNG SỐ DANH MỤC HIỆN TẠI")
    print("="*80)
    for symbol, weight in weights.items():
        print(f"{symbol}: {weight*100:.2f}%")

    print("\n" + "="*80)
    print("TỔNG HỢP DANH MỤC HIỆN TẠI")
    print("="*80)
    for key, value in portfolio_summary.items():
        print(f"{key}: {value:.4f}")

    # Portfolio Optimization
    print("\n" + "="*80)
    print("TỐI ƯU HÓA DANH MỤC (Sharpe Ratio Max)")
    print("="*80)
    opt_weights, opt_return, opt_vol, opt_sharpe = optimize_portfolio(prices, risk_free_rate=args.risk_free, objective="sharpe")
    print(f"Trọng số tối ưu:")
    for symbol, weight in opt_weights.items():
        print(f"  {symbol}: {weight*100:.2f}%")
    print(f"\nLợi suất hàng năm: {opt_return*100:.2f}%")
    print(f"Volatility: {opt_vol*100:.2f}%")
    print(f"Sharpe Ratio: {opt_sharpe:.4f}")

    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    # Tạo báo cáo
    if args.save_html or args.save_pdf:
        html_path = out_dir / "portfolio_report.html"
        generate_html_report(
            prices,
            metrics,
            portfolio_summary,
            weighted_returns,
            opt_weights,
            opt_return,
            opt_vol,
            opt_sharpe,
            weights,
            args.risk_free,
            args.start,
            end_date,
            html_path,
        )

        if args.save_pdf:
            pdf_path = out_dir / "portfolio_report.pdf"
            generate_pdf_report(str(html_path), str(pdf_path))

    if args.save_csv:
        save_outputs(prices, metrics, portfolio_summary, weighted_returns, save_csv=True)


if __name__ == "__main__":
    main()
