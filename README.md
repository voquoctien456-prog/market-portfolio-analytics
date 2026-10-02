# Market & Portfolio Analytics (Vietnam Market)

Dự án phân tích EDA (Exploratory Data Analysis) toàn diện và hiệu suất danh mục đầu tư cho thị trường chứng khoán Việt Nam.

## Mục tiêu

- Thu thập dữ liệu giá cổ phiếu Việt Nam bằng vnstock
- Phân tích EDA chi tiết với thống kê mô tả
- Tính toán tỷ suất sinh lời theo ngày và theo danh mục
- Đo lường độ biến động (Volatility)
- Phân tích tương quan giữa các cổ phiếu
- Đánh giá hiệu suất theo Sharpe Ratio
- Tính Maximum Drawdown
- Tạo biểu đồ trực quan chi tiết
- Xuất báo cáo CSV để theo dõi và cập nhật dữ liệu

## Tính năng chính

### Phân tích EDA
- Thống kê mô tả giá cổ phiếu (Min, Max, Mean, Std)
- Phân tích lợi suất hàng ngày
- Ma trận tương quan giữa các cổ phiếu
- Kiểm tra phân bố chuẩn (Q-Q Plot)
- Lợi suất tích lũy

### Biểu đồ trực quan
1. Phân bố giá - Time series, normalized price, box plot, thống kê mô tả
2. Phân tích lợi suất - Time series returns, histogram, Q-Q plot, lợi suất tích lũy
3. Ma trận tương quan - Heatmap tương quan giữa các mã
4. Biểu đồ Rủi ro - Lợi suất - Scatter plot hiệu suất từng cổ phiếu và danh mục
5. So sánh chỉ số - Annualized Return, Volatility, Sharpe Ratio, Max Drawdown
6. Hiệu suất danh mục - Cumulative returns, daily returns histogram, rolling volatility, drawdown

### Hỗ trợ danh mục
- Lấy dữ liệu lịch sử cổ phiếu Việt Nam
- Tạo phân tích theo từng mã cổ phiếu và toàn bộ danh mục
- Hỗ trợ trọng số danh mục đầu tư tùy ý
- Mặc định chuẩn hóa tổng trọng số về 1
- Xuất kết quả ra màn hình và file CSV trong thư mục `outputs/`

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Chạy phân tích

### Cơ bản (Hiển thị biểu đồ)

```bash
python market_analytics.py \
  --symbols FPT VHM VCB \
  --weights 0.4 0.4 0.2 \
  --start 2023-01-01
```

### Lưu file CSV và biểu đồ PNG

```bash
python market_analytics.py \
  --symbols FPT VHM VCB \
  --weights 0.4 0.4 0.2 \
  --start 2023-01-01 \
  --save-csv \
  --save-plots
```

### Tham số

- `--symbols`: danh sách mã chứng khoán Việt Nam (bắt buộc)
- `--weights`: trọng số tương ứng, tổng sẽ được chuẩn hóa về 1 nếu khác 1 (tùy chọn)
- `--start`: ngày bắt đầu, mặc định "2023-01-01"
- `--end`: ngày kết thúc (mặc định là hôm nay)
- `--risk-free`: lãi suất phi rủi ro hàng năm, mặc định 2.5%
- `--save-csv`: lưu kết quả ra file CSV trong thư mục `outputs/`
- `--save-plots`: lưu biểu đồ PNG trong thư mục `outputs/`

## Chỉ số phân tích

- Daily Return - Lợi suất hàng ngày
- Annualized Return - Lợi suất hàng năm
- Volatility - Độ biến động giá
- Sharpe Ratio - Chỉ số hiệu suất điều chỉnh rủi ro
- Maximum Drawdown - Lớn nhất suy giảm từ đỉnh
- Portfolio Return - Lợi suất danh mục
- Portfolio Volatility - Độ biến động danh mục
- Portfolio Sharpe Ratio - Sharpe Ratio danh mục

## Kết quả đầu ra

### Console Output
- Thống kê mô tả dữ liệu giá
- Thống kê mô tả lợi suất hàng ngày
- Ma trận tương quan
- Bảng phân tích từng cổ phiếu
- Trọng số danh mục
- Tổng hợp danh mục

### File CSV (nếu dùng `--save-csv`)
- `outputs/market_prices.csv` - Giá đóng cửa hàng ngày
- `outputs/asset_metrics.csv` - Chỉ số hiệu suất từng cổ phiếu
- `outputs/portfolio_summary.csv` - Tổng hợp danh mục
- `outputs/portfolio_daily_returns.csv` - Lợi suất hàng ngày danh mục

### File PNG (nếu dùng `--save-plots`)
- `outputs/01_eda_price_distribution.png` - Phân bố giá
- `outputs/02_eda_returns_analysis.png` - Phân tích lợi suất
- `outputs/03_correlation_heatmap.png` - Ma trận tương quan
- `outputs/04_risk_return.png` - Biểu đồ Rủi ro - Lợi suất
- `outputs/05_metrics_comparison.png` - So sánh chỉ số
- `outputs/06_portfolio_performance.png` - Hiệu suất danh mục

## Ví dụ sử dụng

### Phân tích đơn giản
```bash
python market_analytics.py --symbols FPT VHM VCB --start 2023-01-01
```

### Phân tích chi tiết với lưu trữ
```bash
python market_analytics.py \
  --symbols FPT VHM VCB \
  --weights 0.4 0.35 0.25 \
  --start 2023-01-01 \
  --end 2024-10-02 \
  --risk-free 0.03 \
  --save-csv \
  --save-plots
```

## Ghi chú

- Dự án dành cho thị trường Việt Nam và dùng thư viện `vnstock`.
- Dữ liệu tài chính chỉ mang tính tham khảo và không thay thế tư vấn đầu tư chuyên nghiệp.
- Nên kiểm tra lại thời điểm kết thúc và dữ liệu để đảm bảo đánh giá phù hợp với chiến lược đầu tư.
- Biểu đồ được lưu với độ phân giải 300 DPI cho chất lượng tốt khi in ấn.
