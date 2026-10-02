# Market Data Dashboard

Dự án hiện chỉ tập trung vào dữ liệu OHLCV và dashboard tương tác cho thị trường chứng khoán Việt Nam.

## File chính
- `app.py` - dashboard Dash/Plotly
- `fetch_data.py` - tải dữ liệu OHLCV từ `vnstock`
- `requirements.txt` - phụ thuộc của dự án

## Chạy nhanh
```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Sau đó mở trình duyệt tại: `http://localhost:8050`

## Lấy dữ liệu
```bash
python fetch_data.py --symbols FPT VHM VCB --start 2025-01-01 --end 2026-10-02 --save-csv
```

## Ghi chú
- `market_analytics.py` và `demo.py` đã được dọn bỏ khỏi luồng chính của dự án vì không còn được dùng.
