import os
import time
import json
import csv
from kafka import KafkaProducer

# Cấu hình
KAFKA_BROKER = 'localhost:9092'
TOPIC_NAME = 'stock_prices_stream'
DATA_DIR = '../data/raw_csv'

def json_serializer(data):
    """Serialize dictionary sang định dạng JSON byte"""
    return json.dumps(data).encode('utf-8')

def main():
    print(f"Đang kết nối tới Kafka Broker tại {KAFKA_BROKER}...")
    
    # Khởi tạo Kafka Producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=json_serializer
        )
        print("Kết nối Kafka thành công!")
    except Exception as e:
        print(f"Lỗi kết nối Kafka: {e}")
        print("Vui lòng đảm bảo bạn đã chạy 'docker-compose up -d' và Kafka đang hoạt động.")
        return

    # Đọc tất cả các file CSV trong thư mục data
    print(f"Đang đọc dữ liệu từ thư mục {DATA_DIR}...")
    all_data = []
    
    if not os.path.exists(DATA_DIR):
        print(f"Thư mục {DATA_DIR} không tồn tại.")
        return

    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            # Lấy tên mã cổ phiếu từ tên file (vd: FPT.csv -> FPT)
            symbol = filename.replace('.csv', '')
            filepath = os.path.join(DATA_DIR, filename)
            
            try:
                # Đọc CSV bằng thư viện csv chuẩn của Python (không cần pandas)
                with open(filepath, mode='r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    count = 0
                    for row in reader:
                        parsed_row = {}
                        for k, v in row.items():
                            # Xóa khoảng trắng thừa của key (phòng hờ file csv lỗi format)
                            k = k.strip() if k else k
                            v = v.strip() if v else v
                            
                            if not v:
                                parsed_row[k] = None
                            else:
                                try:
                                    # Thử parse sang float/int
                                    parsed_row[k] = float(v) if '.' in v else int(v)
                                except ValueError:
                                    parsed_row[k] = v # Giữ nguyên chuỗi nếu không phải là số (như cột Date)
                                    
                        parsed_row['Symbol'] = symbol
                        all_data.append(parsed_row)
                        count += 1
                print(f"Đã đọc {count} dòng từ {filename}")
            except Exception as e:
                print(f"Lỗi khi đọc file {filename}: {e}")

    if not all_data:
        print("Không tìm thấy dữ liệu nào để gửi.")
        return

    # Sắp xếp toàn bộ dữ liệu theo Date để mô phỏng dòng thời gian thực
    print("Đang sắp xếp tổng hợp dữ liệu theo thời gian (Date)...")
    all_data.sort(key=lambda x: str(x.get('Date', '')))

    print(f"Bắt đầu đẩy {len(all_data)} bản ghi lên Kafka topic '{TOPIC_NAME}'...")
    
    for i, record in enumerate(all_data):
        # Gửi dữ liệu lên Kafka
        producer.send(TOPIC_NAME, value=record)
        
        # Log ra màn hình mỗi 500 bản ghi để theo dõi
        if i % 500 == 0:
            print(f"Đã gửi {i} bản ghi... (Gần nhất: {record.get('Symbol')} - {record.get('Date')} - Price: {record.get('Price')})")
        
        # Tạm dừng để mô phỏng streaming (0.05 giây mỗi bản ghi)
        time.sleep(0.05)

    # Đảm bảo tất cả message đã được đẩy đi
    producer.flush()
    print("Đã gửi toàn bộ dữ liệu lên Kafka thành công!")

if __name__ == "__main__":
    main()
