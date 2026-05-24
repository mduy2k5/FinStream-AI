# ============================================================
#  config.example.py  —  TEMPLATE CẤU HÌNH MẪU
#  Sao chép file này thành config.py rồi điền thông tin thực.
#
#  $ cp config.example.py config.py
# ============================================================

# ── Kafka ────────────────────────────────────────────────────
KAFKA_BROKER = "kafka:9092"           # Đổi thành địa chỉ broker của bạn
TOPIC_NAME   = "stock_prices_stream"  # Tên topic Kafka

# ── Danh sách cổ phiếu theo dõi ─────────────────────────────
# Key   : mã Yahoo Finance (thêm hậu tố .VN cho cổ phiếu Việt Nam)
# Value : mã hiển thị / khớp với schema CSDL
#
# Ví dụ cổ phiếu Việt Nam:
#   "FPT.VN" -> "FPT"
#   "VCB.VN" -> "VCB"
#
# Ví dụ cổ phiếu quốc tế:
#   "AAPL"   -> "AAPL"
#   "MSFT"   -> "MSFT"
TICKERS = {
    "TICKER1.VN": "TICKER1",   # Thay bằng mã cổ phiếu thực tế
    "TICKER2.VN": "TICKER2",
    # Thêm mã cổ phiếu tại đây...
}

# ── Tham số lịch sử mặc định ─────────────────────────────────
DEFAULT_HISTORY_START = "2020-01-01"   # Ngày bắt đầu khi chạy mode history
