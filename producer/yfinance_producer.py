import os
import time
import json
import argparse
import yfinance as yf
from kafka import KafkaProducer

# ── Tải cấu hình từ config.py (không được push lên GitHub) ───
try:
    from config import KAFKA_BROKER, TOPIC_NAME, TICKERS, DEFAULT_HISTORY_START
except ImportError:
    raise SystemExit(
        "\n[Lỗi] Không tìm thấy file config.py!\n"
        "Vui lòng tạo file config.py từ template:\n"
        "  cp config.example.py config.py\n"
        "Sau đó điền thông tin cấu hình thực tế vào config.py.\n"
    )

# Cho phép override KAFKA_BROKER bằng biến môi trường Docker (ưu tiên cao hơn config.py)
KAFKA_BROKER = os.getenv('KAFKA_BROKER', KAFKA_BROKER)

def json_serializer(data):
    """Serialize dictionary sang định dạng JSON byte"""
    return json.dumps(data).encode('utf-8')

def fetch_and_produce(mode="latest", start_date=None, end_date=None):
    """
    Tải dữ liệu từ Yahoo Finance API và đẩy vào Kafka:
    - Chế độ 'latest': lấy dữ liệu của phiên giao dịch mới nhất (dùng chạy hàng ngày).
    - Chế độ 'history': lấy toàn bộ dữ liệu lịch sử từ ngày bắt đầu để backfill lại CSDL.
    """
    print("============================================================")
    print(f"  KHỞI CHẠY YFINANCE KAFKA PRODUCER (Mode: {mode.upper()})")
    print(f"  Broker: {KAFKA_BROKER}  →  Topic: {TOPIC_NAME}")
    print("============================================================")

    # 1. Khởi tạo Kafka Producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=json_serializer
        )
        print("Kết nối Kafka Broker thành công!")
    except Exception as e:
        print(f"[Lỗi] Không thể kết nối Kafka Broker: {e}")
        print("Vui lòng đảm bảo các container Docker đang hoạt động.")
        return

    all_records = []
    
    # 2. Tải dữ liệu từng mã qua yfinance
    for yf_ticker, display_symbol in TICKERS.items():
        print(f"Đang tải dữ liệu từ Yahoo Finance cho: {display_symbol} ({yf_ticker})...")
        try:
            ticker_obj = yf.Ticker(yf_ticker)
            if mode == "history":
                start = start_date if start_date else DEFAULT_HISTORY_START
                df = ticker_obj.history(start=start, end=end_date)
            else:
                df = ticker_obj.history(period="1d")
                
            if df.empty:
                print(f"  [Cảnh báo] Không tìm thấy dữ liệu cho {display_symbol}")
                continue
                
            df = df.reset_index()
            # Chuyển đổi định dạng ngày có múi giờ của yfinance về YYYY-MM-DD
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
            
            for _, row in df.iterrows():
                record = {
                    'Date': row['Date'],
                    'Open': round(float(row['Open']), 2),
                    'High': round(float(row['High']), 2),
                    'Low': round(float(row['Low']), 2),
                    'Close': round(float(row['Close']), 2),
                    'Price': round(float(row['Close']), 2),  # Đặt Price bằng Close khớp với định nghĩa cũ
                    'Volume': int(row['Volume']),
                    'Symbol': display_symbol
                }
                all_records.append(record)
            print(f"  -> Tải thành công {len(df)} phiên cho {display_symbol}")
        except Exception as e:
            print(f"  [Lỗi] Lỗi tải dữ liệu mã {display_symbol}: {e}")

    if not all_records:
        print("\n[Hoàn tất] Không có bản ghi dữ liệu mới nào để gửi.")
        return

    # 3. Sắp xếp toàn bộ dữ liệu tăng dần theo thời gian trước khi đẩy
    print("\nĐang sắp xếp dữ liệu tổng hợp theo thời gian thực...")
    all_records.sort(key=lambda x: (x['Date'], x['Symbol']))
    
    # 4. Đẩy dữ liệu lên Kafka
    print(f"Bắt đầu đẩy {len(all_records)} bản ghi lên topic '{TOPIC_NAME}'...")
    
    for i, record in enumerate(all_records):
        producer.send(TOPIC_NAME, value=record)
        
        # Log theo dõi mỗi 500 bản ghi (hoặc 1 bản ghi nếu là mode latest)
        log_interval = 500 if mode == "history" else 1
        if i % log_interval == 0 or i == len(all_records) - 1:
            print(f"  [Đã gửi] {i+1}/{len(all_records)} bản ghi. (Gần nhất: {record['Symbol']} - {record['Date']} - Close: {record['Close']:,})")
            
        # Nghỉ một khoảng cực nhỏ để tránh nghẽn luồng nếu gửi số lượng lớn
        if mode == "history":
            time.sleep(0.002)
        else:
            time.sleep(0.05)
            
    producer.flush()
    print("\n============================================================")
    print("  ĐÃ GỬI TOÀN BỘ DỮ LIỆU YFINANCE LÊN KAFKA THÀNH CÔNG!")
    print("============================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Yahoo Finance Kafka Ingestion Producer')
    parser.add_argument('--mode', type=str, default='latest', choices=['latest', 'history'],
                        help='latest (lấy phiên gần nhất) hoặc history (lấy dữ liệu lịch sử)')
    parser.add_argument('--start', type=str, default=None, help='Ngày bắt đầu YYYY-MM-DD (chỉ dùng cho history)')
    parser.add_argument('--end', type=str, default=None, help='Ngày kết thúc YYYY-MM-DD (chỉ dùng cho history)')
    
    args = parser.parse_args()
    fetch_and_produce(mode=args.mode, start_date=args.start, end_date=args.end)
