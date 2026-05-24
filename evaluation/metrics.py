import psycopg2
import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

def get_db_connection():
    """Tạo kết nối tới cơ sở dữ liệu PostgreSQL ở local"""
    return psycopg2.connect(
        host="localhost",
        port="5432",
        database="stock_db",
        user="myuser",
        password="mypassword"
    )

def fetch_data():
    """Truy vấn dữ liệu thực tế và dữ liệu dự báo được khớp theo mã và ngày giao dịch"""
    conn = get_db_connection()
    query = """
    SELECT 
        r.symbol, 
        r.trade_date::date AS trade_date, 
        r.close_price AS actual_close, 
        p.predicted_close
    FROM raw_stock_prices r
    JOIN predictions p 
      ON r.symbol = p.symbol 
      AND r.trade_date::date = p.target_date::date
    ORDER BY r.symbol, r.trade_date;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    # Deduplicate đề phòng trường hợp chạy trùng lặp dữ liệu
    df = df.drop_duplicates(subset=['symbol', 'trade_date'])
    return df

def calculate_metrics(df):
    """Tính toán các chỉ số thống kê sai số (RMSE, MAE, MAPE, R2) cho từng mã cổ phiếu"""
    results = []
    symbols = df['symbol'].unique()
    
    for sym in symbols:
        df_sym = df[df['symbol'] == sym].sort_values('trade_date')
        actual = df_sym['actual_close'].values
        predicted = df_sym['predicted_close'].values
        
        if len(actual) < 2:
            continue
            
        rmse = np.sqrt(mean_squared_error(actual, predicted))
        mae = mean_absolute_error(actual, predicted)
        mape = np.mean(np.abs((actual - predicted) / actual)) * 100
        r2 = r2_score(actual, predicted)
        
        results.append({
            'Symbol': sym,
            'Records': len(actual),
            'RMSE': round(rmse, 4),
            'MAE': round(mae, 4),
            'MAPE (%)': round(mape, 2),
            'R2': round(r2, 4)
        })
        
    return pd.DataFrame(results)
