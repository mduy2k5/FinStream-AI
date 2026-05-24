-- Script tạo bảng tự động chạy khi khởi tạo PostgreSQL container
CREATE TABLE IF NOT EXISTS raw_stock_prices (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10),
    trade_date TIMESTAMP,
    open_price NUMERIC,
    high_price NUMERIC,
    low_price NUMERIC,
    close_price NUMERIC,
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10),
    target_date TIMESTAMP,
    predicted_close NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
