import argparse
from pathlib import Path
import pandas as pd
from datetime import datetime

try:
    import vnstock
except ImportError:
    vnstock = None


def fetch_ohlcv(symbols, start_date, end_date):
    """
    Lấy dữ liệu OHLCV từ vnstock
    
    Args:
        symbols: list of stock symbols
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
    
    Returns:
        dict: {symbol: DataFrame with OHLCV}
    """
    if vnstock is None:
        raise ImportError("vnstock chưa cài. Chạy: pip install vnstock")
    
    data = {}
    
    for symbol in symbols:
        try:
            print(f"Lấy dữ liệu {symbol}...")
            df = vnstock.stock_historical(
                symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1D"
            )
            
            if df is None or df.empty:
                print(f"  ⚠ Không có dữ liệu cho {symbol}")
                continue
            
            # Chuẩn hóa tên cột
            df = df.copy()
            df.columns = [col.lower() for col in df.columns]
            
            # Đảm bảo có cột date
            if 'date' not in df.columns:
                df = df.reset_index()
            
            # Chọn cột OHLCV
            ohlcv_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            available_cols = [col for col in ohlcv_cols if col in df.columns]
            
            if 'date' not in available_cols:
                print(f"  ⚠ Không có cột date cho {symbol}")
                continue
            
            df = df[available_cols].copy()
            df['date'] = pd.to_datetime(df['date'])
            df['symbol'] = symbol
            data[symbol] = df
            print(f"  ✓ {len(df)} ngày dữ liệu")
            
        except Exception as e:
            print(f"  ✗ Lỗi {symbol}: {e}")
    
    return data


def save_to_csv(data, output_dir='outputs'):
    """
    Lưu dữ liệu OHLCV vào file CSV
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    for symbol, df in data.items():
        filepath = output_dir / f"{symbol}_ohlcv.csv"
        df.to_csv(filepath, index=False)
        print(f"✓ Lưu {symbol}: {filepath}")
    
    # Lưu tất cả vào file chung
    all_data = pd.concat(data.values(), ignore_index=True)
    all_filepath = output_dir / "all_ohlcv.csv"
    all_data.to_csv(all_filepath, index=False)
    print(f"✓ Lưu tất cả: {all_filepath}")


def main():
    parser = argparse.ArgumentParser(description="Lấy dữ liệu OHLCV")
    parser.add_argument("--symbols", nargs="+", required=True, help="Mã chứng khoán")
    parser.add_argument("--start", default="2025-01-01", help="Ngày bắt đầu YYYY-MM-DD")
    parser.add_argument("--end", default="2026-10-02", help="Ngày kết thúc YYYY-MM-DD")
    parser.add_argument("--save-csv", action="store_true", help="Lưu CSV")
    
    args = parser.parse_args()
    
    print(f"\n📊 Lấy dữ liệu OHLCV từ {args.start} đến {args.end}")
    print(f"Mã: {', '.join(args.symbols)}\n")
    
    data = fetch_ohlcv(args.symbols, args.start, args.end)
    
    if not data:
        print("✗ Không lấy được dữ liệu nào")
        return
    
    if args.save_csv:
        save_to_csv(data)
    
    # In thống kê
    print(f"\n📊 Tóm tắt dữ liệu")
    for symbol, df in data.items():
        print(f"\n{symbol}:")
        print(f"  Ngày: {df['date'].min().date()} → {df['date'].max().date()}")
        print(f"  Giá: {df['close'].min():.2f} - {df['close'].max():.2f} VND")
        print(f"  Khối lượng: {df['volume'].mean():.0f} cổ phiếu/ngày")


if __name__ == "__main__":
    main()
