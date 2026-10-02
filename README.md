# Market Data Dashboard

Lấy dữ liệu OHLCV (Open, High, Low, Close, Volume) từ thị trường chứng khoán Việt Nam và hiển thị trên dashboard tương tác.

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Chạy dashboard

```bash
python app.py
```

Sau đó mở trình duyệt vào: `http://localhost:8050`

## Lấy dữ liệu OHLCV

```bash
python fetch_data.py --symbols FPT VHM VCB --start 2025-01-01 --end 2026-10-02 --save-csv
```

## Tính năng

- Lấy dữ liệu OHLCV từ vnstock
- Dashboard tương tác với Plotly & Dash
- Biểu đồ giá, khối lượng, kỹ thuật
- Xuất dữ liệu CSV
- Cho phép chọn mã, ngày tháng năm

## File chính

- `app.py` - Dashboard Dash
- `fetch_data.py` - Lấy dữ liệu OHLCV
- `requirements.txt` - Dependencies
