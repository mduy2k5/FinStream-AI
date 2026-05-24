import pandas as pd
import numpy as np

def simulate_strategy(df_sym, initial_capital=100000000):
    """
    Mô phỏng chiến lược đầu tư cho một mã cổ phiếu:
    1. Buy & Hold (Mua và nắm giữ)
    2. Long-Only Buy-MA (Chỉ mua khi dự báo tăng hơn SMA_10, nếu không thì giữ tiền mặt)
    3. Long-Short Buy-MA (Mua khi dự báo tăng, Bán khống khi dự báo giảm hơn SMA_10)
    """
    df_sym = df_sym.sort_values('trade_date').copy()
    
    # Chỉ mô phỏng nếu có đủ ít nhất 15 bản ghi để tính SMA_10 và chạy backtest
    if len(df_sym) < 15:
        return df_sym, None
        
    # Tính toán SMA_10 của giá Close thực tế
    df_sym['sma_10'] = df_sym['actual_close'].rolling(window=10).mean()
    
    # Tính toán lợi nhuận phần trăm hàng ngày (Daily Return) của ngày tiếp theo
    # Return từ t sang t+1: (Close_{t+1} - Close_t) / Close_t
    df_sym['daily_return'] = df_sym['actual_close'].pct_change().shift(-1)
    
    # Sinh tín hiệu đầu tư tại ngày t cho ngày giao dịch t+1:
    # So sánh giá dự báo cho ngày mai (predicted_close) với giá dự báo cho hôm nay (predicted_close_prev)
    # Phương pháp này miễn dịch hoàn toàn với sai số lệch tỷ lệ (bias underprediction) của mô hình.
    df_sym['predicted_close_prev'] = df_sym['predicted_close'].shift(1)
    df_sym['signal_long_only'] = np.where(df_sym['predicted_close'] > df_sym['predicted_close_prev'], 1, 0)
    df_sym['signal_long_short'] = np.where(df_sym['predicted_close'] > df_sym['predicted_close_prev'], 1, -1)
    
    # Trễ tín hiệu đi 1 ngày vì tín hiệu sinh ra cuối ngày t sẽ được giao dịch vào ngày t+1
    df_sym['trade_signal_lo'] = df_sym['signal_long_only'].shift(1)
    df_sym['trade_signal_ls'] = df_sym['signal_long_short'].shift(1)
    
    # Điền giá trị rỗng
    df_sym['trade_signal_lo'] = df_sym['trade_signal_lo'].fillna(0)
    df_sym['trade_signal_ls'] = df_sym['trade_signal_ls'].fillna(0)
    df_sym['daily_return'] = df_sym['daily_return'].fillna(0)
    
    # Chuỗi vốn tăng trưởng hàng ngày (Equity Curve)
    equity_bh = [initial_capital]
    equity_lo = [initial_capital]
    equity_ls = [initial_capital]
    
    returns = df_sym['daily_return'].values
    signals_lo = df_sym['trade_signal_lo'].values
    signals_ls = df_sym['trade_signal_ls'].values
    
    for i in range(len(returns) - 1):
        r = returns[i]
        
        # 1. Buy & Hold: Lợi nhuận nhân trực tiếp
        equity_bh.append(equity_bh[-1] * (1 + r))
        
        # 2. Long-Only: Lợi nhuận = tín hiệu Mua (0 hoặc 1) * return ngày tiếp theo
        equity_lo.append(equity_lo[-1] * (1 + signals_lo[i] * r))
        
        # 3. Long-Short: Lợi nhuận = tín hiệu (1 hoặc -1) * return ngày tiếp theo
        equity_ls.append(equity_ls[-1] * (1 + signals_ls[i] * r))
        
    df_sym['equity_bh'] = equity_bh
    df_sym['equity_lo'] = equity_lo
    df_sym['equity_ls'] = equity_ls
    
    # Tính toán kết quả tổng kết
    final_bh = equity_bh[-1]
    final_lo = equity_lo[-1]
    final_ls = equity_ls[-1]
    
    return_bh = (final_bh - initial_capital) / initial_capital * 100
    return_lo = (final_lo - initial_capital) / initial_capital * 100
    return_ls = (final_ls - initial_capital) / initial_capital * 100
    
    # Tính Max Drawdown của chiến lược Long-Short để đánh giá rủi ro
    def calculate_max_drawdown(equity_series):
        arr = np.array(equity_series)
        cum_max = np.maximum.accumulate(arr)
        drawdowns = (arr - cum_max) / cum_max
        return round(np.min(drawdowns) * 100, 2)
        
    mdd_bh = calculate_max_drawdown(equity_bh)
    mdd_lo = calculate_max_drawdown(equity_lo)
    mdd_ls = calculate_max_drawdown(equity_ls)
    
    summary = {
        'Return_BH (%)': round(return_bh, 2),
        'Return_LO (%)': round(return_lo, 2),
        'Return_LS (%)': round(return_ls, 2),
        'MDD_BH (%)': mdd_bh,
        'MDD_LO (%)': mdd_lo,
        'MDD_LS (%)': mdd_ls
    }
    
    return df_sym, summary
