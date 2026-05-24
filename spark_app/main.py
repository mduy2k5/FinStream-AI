"""
spark_app/main.py
PySpark Structured Streaming Pipeline (tương thích Spark 3.x và 4.x)
  Kafka  ──►  Tiền xử lý  ──►  DLS-TS-Net Inference  ──►  PostgreSQL

Luồng hoạt động:
  1. Đọc liên tục gói tin JSON từ Kafka topic 'stock_prices_stream'
  2. Parse + chuẩn hóa từng bản ghi (MinMax scaling theo cửa sổ buffer)
  3. Gom nhóm (buffer) đủ seq_len = 20 bản ghi cho mỗi Symbol
  4. Gọi mô hình DLS-TS-Net để dự báo giá Close kỳ tiếp
  5. Ghi kết quả vào bảng 'predictions' trên PostgreSQL
  6. Ghi đồng thời bản ghi thực tế vào bảng 'raw_stock_prices' để so sánh sau
"""

import os
from collections import defaultdict

import torch
import pyspark
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)

from dls_ts_net import DLSTSNet, build_model

# ─────────────────────────────────────────────────
# Cấu hình
# ─────────────────────────────────────────────────
KAFKA_BROKER   = os.getenv("KAFKA_BROKER",   "kafka:9092")
KAFKA_TOPIC    = os.getenv("KAFKA_TOPIC",    "stock_prices_stream")
POSTGRES_URL   = os.getenv("POSTGRES_URL",   "jdbc:postgresql://postgres:5432/stock_db")
POSTGRES_USER  = os.getenv("POSTGRES_USER",  "myuser")
POSTGRES_PASS  = os.getenv("POSTGRES_PASS",  "mypassword")
MODEL_PATH     = os.getenv("MODEL_PATH",     "/app/dls_ts_net.pt")

# Spark version check cho tương thích
SPARK_MAJOR = int(pyspark.__version__.split(".")[0])

# Tham số mô hình – phải khớp với lúc huấn luyện / khởi tạo
SEQ_LEN    = 20          # Cửa sổ trượt: 20 bản ghi / mã
N_FEATURES = 5           # Open, High, Low, Close, Volume
HORIZON    = 1           # Dự báo 1 bước tiếp theo

# Các đặc trưng đầu vào (thứ tự quan trọng để đưa vào tensor đúng chiều)
FEATURE_COLS = ["Open", "High", "Low", "Close", "Volume"]

# ─────────────────────────────────────────────────
# Khai báo schema của gói tin JSON nhận từ Kafka
# ─────────────────────────────────────────────────
STOCK_SCHEMA = StructType([
    StructField("Date",   StringType(), True),
    StructField("Price",  DoubleType(), True),
    StructField("Close",  DoubleType(), True),
    StructField("High",   DoubleType(), True),
    StructField("Low",    DoubleType(), True),
    StructField("Open",   DoubleType(), True),
    StructField("Volume", LongType(),   True),
    StructField("Symbol", StringType(), True),
])

# ─────────────────────────────────────────────────
# Buffer toàn cục: lưu chuỗi thời gian theo từng mã
# ─────────────────────────────────────────────────
# Key: symbol (str)  → Value: list of [Open, High, Low, Close, Volume]
_price_buffer: dict = defaultdict(list)
_model: DLSTSNet | None = None


def _get_model() -> DLSTSNet:
    """
    Lazy-load mô hình DLS-TS-Net.
    Tải từ file .pt nếu tồn tại; ngược lại dùng trọng số ngẫu nhiên (demo).
    """
    global _model
    if _model is None:
        _model = build_model(n_features=N_FEATURES, seq_len=SEQ_LEN, horizon=HORIZON)
        if os.path.exists(MODEL_PATH):
            _model.load_state_dict(
                torch.load(MODEL_PATH, map_location="cpu")
            )
            print(f"[Model] Đã tải trọng số từ {MODEL_PATH}")
        else:
            print("[Model] Không tìm thấy file .pt, chạy với trọng số ngẫu nhiên (demo).")
        _model.eval()
    return _model


def _minmax_scale(window: list[list[float]]) -> list[list[float]]:
    """Chuẩn hóa Min-Max theo từng đặc trưng trong cửa sổ."""
    n_feat = len(window[0])
    mins   = [min(row[f] for row in window) for f in range(n_feat)]
    maxs   = [max(row[f] for row in window) for f in range(n_feat)]

    scaled = []
    for row in window:
        scaled_row = []
        for f in range(n_feat):
            denom = (maxs[f] - mins[f]) or 1e-8   # tránh chia cho 0
            scaled_row.append((row[f] - mins[f]) / denom)
        scaled.append(scaled_row)
    return scaled, mins[3], maxs[3]   # trả thêm min/max của Close để inverse


def predict_next_close(symbol: str, row_features: list[float]) -> float | None:
    """
    Thêm bản ghi mới vào buffer của symbol, nếu đủ SEQ_LEN thì chạy inference.
    Trả về giá Close dự báo (đã inverse scale), hoặc None nếu buffer chưa đủ.
    """
    buf = _price_buffer[symbol]
    buf.append(row_features)

    # Giữ buffer không quá dài
    if len(buf) > SEQ_LEN:
        buf.pop(0)

    if len(buf) < SEQ_LEN:
        return None

    window = buf[-SEQ_LEN:]
    scaled_window, close_min, close_max = _minmax_scale(window)

    # Chuyển sang tensor
    tensor = torch.tensor([scaled_window], dtype=torch.float32)  # (1, seq_len, n_feat)

    model = _get_model()
    with torch.no_grad():
        pred_scaled = model(tensor).item()   # giá trị đã chuẩn hóa ∈ [0, 1]

    # Inverse MinMax cho Close
    pred_close = pred_scaled * (close_max - close_min) + close_min
    return pred_close


# ─────────────────────────────────────────────────
# Ghi batch vào PostgreSQL qua JDBC
# ─────────────────────────────────────────────────
POSTGRES_PROPS = {
    "user":   POSTGRES_USER,
    "password": POSTGRES_PASS,
    "driver": "org.postgresql.Driver",
}


def write_to_postgres(df, table_name: str) -> None:
    """Ghi DataFrame vào PostgreSQL theo chế độ append."""
    df.write.jdbc(
        url=POSTGRES_URL,
        table=table_name,
        mode="append",
        properties=POSTGRES_PROPS,
    )


# ─────────────────────────────────────────────────
# Hàm xử lý từng micro-batch (foreachBatch)
# ─────────────────────────────────────────────────
def process_batch(batch_df, batch_id: int) -> None:
    """
    Được gọi mỗi micro-batch bởi Spark Structured Streaming.
    Thực hiện inference và ghi kết quả vào PostgreSQL.
    """
    if batch_df.isEmpty():
        return

    rows = batch_df.collect()
    print(f"\n[Batch {batch_id}] Xử lý {len(rows)} bản ghi...")

    raw_records    = []
    pred_records   = []

    for row in rows:
        symbol = row["Symbol"] or "UNKNOWN"
        date   = row["Date"]   or ""
        close  = row["Close"]  or 0.0
        high   = row["High"]   or 0.0
        low    = row["Low"]    or 0.0
        open_  = row["Open"]   or 0.0
        volume = row["Volume"] or 0

        # Bản ghi raw
        raw_records.append((symbol, date, open_, high, low, close, volume))

        # Chạy inference
        features = [open_, high, low, close, float(volume)]
        pred_close = predict_next_close(symbol, features)

        if pred_close is not None:
            pred_records.append((symbol, date, round(pred_close, 4)))
            print(f"  [{symbol}] {date}  Close thực={close:,.2f}  Dự báo={pred_close:,.2f}")

    spark = SparkSession.getActiveSession()

    # ── Ghi raw prices ──
    if raw_records:
        raw_schema = StructType([
            StructField("symbol",      StringType(), True),
            StructField("trade_date",  StringType(), True),
            StructField("open_price",  DoubleType(), True),
            StructField("high_price",  DoubleType(), True),
            StructField("low_price",   DoubleType(), True),
            StructField("close_price", DoubleType(), True),
            StructField("volume",      LongType(),   True),
        ])
        raw_df = spark.createDataFrame(raw_records, schema=raw_schema)
        # Cast trade_date to TimestampType so it matches PostgreSQL TIMESTAMP
        raw_df = raw_df.withColumn("trade_date", col("trade_date").cast("timestamp"))
        write_to_postgres(raw_df, "raw_stock_prices")

    # ── Ghi predictions ──
    if pred_records:
        pred_schema = StructType([
            StructField("symbol",          StringType(), True),
            StructField("target_date",     StringType(), True),
            StructField("predicted_close", DoubleType(), True),
        ])
        pred_df = spark.createDataFrame(pred_records, schema=pred_schema)
        # Cast target_date to TimestampType so it matches PostgreSQL TIMESTAMP
        pred_df = pred_df.withColumn("target_date", col("target_date").cast("timestamp"))
        write_to_postgres(pred_df, "predictions")

    print(f"[Batch {batch_id}] Hoàn tất. Đã dự báo {len(pred_records)} bản ghi.")


# ─────────────────────────────────────────────────
# Khởi tạo Spark và bắt đầu Streaming
# ─────────────────────────────────────────────────
def main():
    spark = (
        SparkSession.builder
        .appName("DLS-TS-Net Stock Streaming")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    print("=" * 60)
    print("  DLS-TS-Net Stock Price Forecasting Pipeline  ")
    print(f"  Kafka  : {KAFKA_BROKER}  →  {KAFKA_TOPIC}")
    print(f"  Postgres: {POSTGRES_URL}")
    print("=" * 60)

    # ── Đọc từ Kafka ──
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BROKER)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "earliest")   # ← đọc TẤT CẢ message từ đầu topic
        .option("failOnDataLoss", "false")
        .load()
    )

    # ── Parse JSON ──
    parsed_stream = (
        raw_stream
        .selectExpr("CAST(value AS STRING) AS json_str")
        .select(from_json(col("json_str"), STOCK_SCHEMA).alias("data"))
        .select("data.*")
    )

    # ── Streaming query: dùng foreachBatch để gọi PyTorch và ghi PostgreSQL ──
    query = (
        parsed_stream
        .writeStream
        .trigger(processingTime="5 seconds")    # xử lý mỗi 5 giây
        .foreachBatch(process_batch)
        .option("checkpointLocation", "/tmp/spark_checkpoint")
        .start()
    )

    print("Streaming đã bắt đầu. Nhấn Ctrl+C để dừng.")
    query.awaitTermination()


if __name__ == "__main__":
    main()
