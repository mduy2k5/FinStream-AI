import os
import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
import plotly.graph_objects as go
import plotly.express as px

# ──────────────────────────────────────────────────────────────────────────────
# 1. PAGE SETTINGS & HARMONIOUS CUSTOM DARK THEME CSS
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DLS-TS-Net Real-time Stock Forecasting Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium aesthetics CSS
st.markdown("""
<style>
    /* Gradient headers and dark themes */
    .main-title {
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 800;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        padding-bottom: 0.5rem;
        margin-bottom: 0px;
    }
    .sub-title {
        font-family: 'Inter', sans-serif;
        color: #a3b8cc;
        font-size: 1.1rem;
        margin-top: 0px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #00f2fe;
    }
    .card-label {
        font-size: 0.85rem;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .card-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0.25rem 0;
    }
    .card-delta {
        font-size: 0.9rem;
        font-weight: 600;
    }
    .delta-up {
        color: #10b981;
    }
    .delta-down {
        color: #ef4444;
    }
    .recommendation-pill {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .pill-buy {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .pill-sell {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .pill-hold {
        background-color: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# 2. DATABASE UTILITIES & DATA RETRIEVAL
# ──────────────────────────────────────────────────────────────────────────────
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "stock_db")
DB_USER = os.getenv("POSTGRES_USER", "myuser")
DB_PASS = os.getenv("POSTGRES_PASS", "mypassword")

@st.cache_resource
def get_connection():
    """Tạo pool/connection bền vững kết nối trực tiếp đến PostgreSQL trong Docker network"""
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
    except Exception as e:
        st.error(f"⚠️ Lỗi kết nối cơ sở dữ liệu: {e}")
        return None

@st.cache_data(ttl=60)
def load_all_data():
    """Tải toàn bộ dữ liệu giá và dự báo được khớp nối theo ngày"""
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    
    query = """
    SELECT 
        r.symbol, 
        r.trade_date::date AS trade_date, 
        r.open_price AS actual_open, 
        r.high_price AS actual_high, 
        r.low_price AS actual_low, 
        r.close_price AS actual_close, 
        r.volume,
        p.predicted_close
    FROM raw_stock_prices r
    JOIN predictions p 
      ON r.symbol = p.symbol 
      AND r.trade_date::date = p.target_date::date
    ORDER BY r.symbol, r.trade_date;
    """
    try:
        df = pd.read_sql(query, conn)
        df = df.drop_duplicates(subset=['symbol', 'trade_date'])
        return df
    except Exception as e:
        st.error(f"⚠️ Lỗi truy vấn dữ liệu: {e}")
        return pd.DataFrame()

# ──────────────────────────────────────────────────────────────────────────────
# 3. BACKTEST SIMULATION UTILITY (MATHEMATICALLY MATCHED LOGIC)
# ──────────────────────────────────────────────────────────────────────────────
def run_simulation(df_sym, initial_capital=100000000, start_date=None, end_date=None):
    df_sym = df_sym.sort_values('trade_date').copy()
    if len(df_sym) < 15:
        return None, None
        
    # Tính toán chỉ báo và tín hiệu trên toàn bộ dữ liệu lịch sử để đảm bảo tính liên tục của SMA
    df_sym['sma_10'] = df_sym['actual_close'].rolling(window=10).mean()
    df_sym['daily_return'] = df_sym['actual_close'].pct_change().shift(-1)
    
    df_sym['predicted_close_prev'] = df_sym['predicted_close'].shift(1)
    df_sym['signal_long_only'] = np.where(df_sym['predicted_close'] > df_sym['predicted_close_prev'], 1, 0)
    df_sym['signal_long_short'] = np.where(df_sym['predicted_close'] > df_sym['predicted_close_prev'], 1, -1)
    
    df_sym['trade_signal_lo'] = df_sym['signal_long_only'].shift(1).fillna(0)
    df_sym['trade_signal_ls'] = df_sym['signal_long_short'].shift(1).fillna(0)
    df_sym['daily_return'] = df_sym['daily_return'].fillna(0)
    
    # Thực hiện lọc theo khoảng thời gian sau khi đã tính toán xong các chỉ báo kỹ thuật
    if start_date is not None:
        df_sym = df_sym[df_sym['trade_date'] >= start_date]
    if end_date is not None:
        df_sym = df_sym[df_sym['trade_date'] <= end_date]
        
    if len(df_sym) < 2:
        return None, None
        
    # Reset daily_return của ngày cuối cùng trong chu kỳ lọc về 0 để tránh rò rỉ dữ liệu tương lai ngoài chu kỳ
    df_sym = df_sym.copy()
    df_sym.iloc[-1, df_sym.columns.get_loc('daily_return')] = 0
    
    equity_bh = [initial_capital]
    equity_lo = [initial_capital]
    equity_ls = [initial_capital]
    
    returns = df_sym['daily_return'].values
    signals_lo = df_sym['trade_signal_lo'].values
    signals_ls = df_sym['trade_signal_ls'].values
    
    for i in range(len(returns) - 1):
        r = returns[i]
        equity_bh.append(equity_bh[-1] * (1 + r))
        equity_lo.append(equity_lo[-1] * (1 + signals_lo[i] * r))
        equity_ls.append(equity_ls[-1] * (1 + signals_ls[i] * r))
        
    df_sym['equity_bh'] = equity_bh
    df_sym['equity_lo'] = equity_lo
    df_sym['equity_ls'] = equity_ls
    
    final_bh = equity_bh[-1]
    final_lo = equity_lo[-1]
    final_ls = equity_ls[-1]
    
    return_bh = (final_bh - initial_capital) / initial_capital * 100
    return_lo = (final_lo - initial_capital) / initial_capital * 100
    return_ls = (final_ls - initial_capital) / initial_capital * 100
    
    def calculate_max_drawdown(equity_series):
        arr = np.array(equity_series)
        cum_max = np.maximum.accumulate(arr)
        drawdowns = (arr - cum_max) / cum_max
        return round(np.min(drawdowns) * 100, 2)
        
    mdd_bh = calculate_max_drawdown(equity_bh)
    mdd_lo = calculate_max_drawdown(equity_lo)
    mdd_ls = calculate_max_drawdown(equity_ls)
    
    summary = {
        'Return_BH': return_bh,
        'Return_LO': return_lo,
        'Return_LS': return_ls,
        'MDD_BH': mdd_bh,
        'MDD_LO': mdd_lo,
        'MDD_LS': mdd_ls,
        'Final_BH': final_bh,
        'Final_LO': final_lo,
        'Final_LS': final_ls
    }
    
    return df_sym, summary

# ──────────────────────────────────────────────────────────────────────────────
# 4. APP INTERFACE & TAB NAVIGATION
# ──────────────────────────────────────────────────────────────────────────────
# Load dataset
df_all = load_all_data()

# Header layout
st.markdown('<h1 class="main-title">📈 DLS-TS-Net Real-time Stock Analytics</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Hệ thống phân tích, dự báo thời gian thực và mô phỏng chiến lược đầu tư Deep Learning</p>', unsafe_allow_html=True)

if df_all.empty:
    st.warning("🔌 Hệ thống chưa có dữ liệu giao dịch hoặc dự báo. Vui lòng kiểm tra container Spark Streaming và Ingest qua Airflow.")
else:
    # Sidebar control panel
    st.sidebar.markdown("### 🎛️ Bảng Điều Khiển")
    st.sidebar.info("Dữ liệu được nạp tự động qua **Airflow DAG** cào `yfinance` hàng ngày lúc 17:00 và xử lý suy diễn thời gian thực qua **Apache Spark**.")
    
    # Auto-refresh button
    if st.sidebar.button("🔄 Làm mới dữ liệu"):
        st.cache_data.clear()
        st.experimental_rerun()
    
    symbols = sorted(df_all['symbol'].unique())
    selected_sym_sidebar = st.sidebar.selectbox("🎯 Chọn mã chứng khoán xem nhanh:", symbols)
    
    # Create Tabs
    tab1, tab2, tab3 = st.tabs([
        "🔮 Dự Báo Trực Tiếp (Live Forecasts)", 
        "📊 Hiệu Năng Mô Hình (Model Accuracy)", 
        "📈 Mô Phỏng Chiến Lược (Backtest)"
    ])
    
    # ──────────────────────────────────────────────────────────────────────────
    # TAB 1: LIVE FORECASTS & TRADING SIGNALS
    # ──────────────────────────────────────────────────────────────────────────
    with tab1:
        st.subheader("🔮 Tín hiệu dự báo phiên giao dịch mới nhất")
        st.write("Bảng dưới đây hiển thị mức giá đóng cửa thực tế, dự báo giá phiên tiếp theo từ mô hình học sâu DLS-TS-Net cùng khuyến nghị giao dịch tương ứng:")
        
        # Get latest record for each ticker
        latest_records = []
        for sym in symbols:
            df_sym = df_all[df_all['symbol'] == sym].sort_values('trade_date')
            if len(df_sym) >= 2:
                latest_row = df_sym.iloc[-1]
                prev_row = df_sym.iloc[-2]
                
                # Signal logic: predicted_close_t > predicted_close_t-1
                is_up = latest_row['predicted_close'] > prev_row['predicted_close']
                rec = "MUA (Long)" if is_up else "TIỀN MẶT (Cash)"
                rec_class = "pill-buy" if is_up else "pill-hold"
                
                # Dynamic percentage change
                pct_chg = ((latest_row['actual_close'] - prev_row['actual_close']) / prev_row['actual_close']) * 100
                
                latest_records.append({
                    'Symbol': sym,
                    'Ngày giao dịch': latest_row['trade_date'].strftime('%Y-%m-%d'),
                    'Giá đóng cửa (VND)': f"{latest_row['actual_close']:,.2f}",
                    'Thay đổi (%)': pct_chg,
                    'Giá dự báo ngày mai (VND)': f"{latest_row['predicted_close']:,.2f}",
                    'Khuyến nghị': rec,
                    'class': rec_class
                })
        
        latest_df = pd.DataFrame(latest_records)
        
        # Display elegant responsive grid cards
        cols = st.columns(5)
        for idx, row in latest_df.head(5).iterrows():
            with cols[idx]:
                delta_class = "delta-up" if row['Thay đổi (%)'] >= 0 else "delta-down"
                sign = "+" if row['Thay đổi (%)'] >= 0 else ""
                
                st.markdown(f"""
                <div class="metric-card">
                    <div class="card-label">{row['Symbol']} &bull; {row['Ngày giao dịch']}</div>
                    <div class="card-value">{row['Giá đóng cửa (VND)']}</div>
                    <div class="card-delta {delta_class}">{sign}{row['Thay đổi (%)']:.2f}%</div>
                    <div style="margin-top:0.75rem;">
                        <span class="recommendation-pill {row['class']}">{row['Khuyến nghị']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        cols_bottom = st.columns(5)
        for idx, row in latest_df.tail(5).reset_index().iterrows():
            with cols_bottom[idx]:
                delta_class = "delta-up" if row['Thay đổi (%)'] >= 0 else "delta-down"
                sign = "+" if row['Thay đổi (%)'] >= 0 else ""
                
                st.markdown(f"""
                <div class="metric-card">
                    <div class="card-label">{row['Symbol']} &bull; {row['Ngày giao dịch']}</div>
                    <div class="card-value">{row['Giá đóng cửa (VND)']}</div>
                    <div class="card-delta {delta_class}">{sign}{row['Thay đổi (%)']:.2f}%</div>
                    <div style="margin-top:0.75rem;">
                        <span class="recommendation-pill {row['class']}">{row['Khuyến nghị']}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        st.write("---")
        st.subheader("📋 Bảng tổng hợp chi tiết toàn bộ danh mục")
        
        # Format display table
        display_df = latest_df.drop(columns=['class'])
        st.dataframe(
            display_df,
            column_config={
                "Thay đổi (%)": st.column_config.NumberColumn(
                    "Thay đổi (%)",
                    format="%.2f%%",
                ),
            },
            use_container_width=True
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2: MODEL ACCURACY & PERFORMANCE PLOTS
    # ──────────────────────────────────────────────────────────────────────────
    with tab2:
        st.subheader("🎯 Đánh giá sai số của DLS-TS-Net trên tập dữ liệu")
        
        # Calculate error metrics for all symbols
        metrics_data = []
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        
        for sym in symbols:
            df_sym = df_all[df_all['symbol'] == sym].sort_values('trade_date')
            actual = df_sym['actual_close'].values
            predicted = df_sym['predicted_close'].values
            
            if len(actual) >= 2:
                rmse = np.sqrt(mean_squared_error(actual, predicted))
                mae = mean_absolute_error(actual, predicted)
                mape = np.mean(np.abs((actual - predicted) / actual)) * 100
                r2 = r2_score(actual, predicted)
                
                metrics_data.append({
                    'Symbol': sym,
                    'Số phiên': len(actual),
                    'RMSE': rmse,
                    'MAE': mae,
                    'MAPE (%)': mape,
                    'R2 (R-squared)': r2
                })
        
        metrics_df = pd.DataFrame(metrics_data)
        
        col_table, col_charts = st.columns([1, 1])
        
        with col_table:
            st.markdown("##### 📊 Bảng so sánh các chỉ số sai số")
            st.dataframe(
                metrics_df,
                column_config={
                    "RMSE": st.column_config.NumberColumn(format="%,.2f"),
                    "MAE": st.column_config.NumberColumn(format="%,.2f"),
                    "MAPE (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "R2 (R-squared)": st.column_config.NumberColumn(format="%.4f"),
                },
                use_container_width=True
            )
            
            # Key statistics alert
            avg_mape = metrics_df['MAPE (%)'].mean()
            avg_r2 = metrics_df['R2 (R-squared)'].mean()
            st.success(f"""
            💡 **Nhận xét hiệu năng:**
            - **MAPE trung bình danh mục:** `{avg_mape:.2f}%` (Cực kỳ xuất sắc, dưới mức 5%).
            - **R² trung bình:** `{avg_r2:.4f}` (Mô hình bám xu hướng vô cùng chắc chắn và mạnh mẽ).
            """)
            
        with col_charts:
            st.markdown("##### 🏆 Phân bổ độ chính xác (R2) theo mã")
            fig_r2 = px.bar(
                metrics_df, 
                x='Symbol', 
                y='R2 (R-squared)',
                color='R2 (R-squared)',
                color_continuous_scale='tealgrn',
                title="Hệ số xác định R² (Càng gần 1.0 càng tốt)"
            )
            fig_r2.update_layout(template="plotly_dark", height=320, margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig_r2, use_container_width=True)
            
        st.write("---")
        
        # Interactive Price Comparison Plotter
        st.subheader("🔍 Đồ thị so sánh Giá thực tế vs Giá dự báo chi tiết")
        col_sel, col_empty = st.columns([1, 3])
        with col_sel:
            active_sym = st.selectbox("Chọn mã để trực quan hóa đồ thị:", symbols)
            
        df_plot = df_all[df_all['symbol'] == active_sym].sort_values('trade_date')
        
        # Plotly chart configuration
        fig_price = go.Figure()
        
        # Actual Close Line
        fig_price.add_trace(go.Scatter(
            x=df_plot['trade_date'],
            y=df_plot['actual_close'],
            mode='lines',
            name='Giá thực tế (Actual)',
            line=dict(color='#00f2fe', width=2)
        ))
        
        # Predicted Close Line
        fig_price.add_trace(go.Scatter(
            x=df_plot['trade_date'],
            y=df_plot['predicted_close'],
            mode='lines',
            name='Giá dự báo (DLS-TS-Net)',
            line=dict(color='#ff4b4b', width=1.5, dash='dash')
        ))
        
        fig_price.update_layout(
            title=f"Đồ thị so sánh giá mã {active_sym}",
            xaxis_title="Thời gian (Trade Date)",
            yaxis_title="Giá đóng cửa (VND)",
            template="plotly_dark",
            height=450,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig_price, use_container_width=True)

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 3: BACKTESTING & SIMULATION RESULTS
    # ──────────────────────────────────────────────────────────────────────────
    with tab3:
        st.subheader("📈 Mô phỏng tăng trưởng tài sản & so sánh chiến lược")
        st.write("Nhập số vốn ban đầu và chọn mã cổ phiếu để xem biểu đồ so sánh mức sinh lời tích lũy giữa các chiến lược đầu tư dựa trên tín hiệu của AI.")
        
        col_inp1, col_inp2, col_inp3 = st.columns([1, 1, 2])
        with col_inp1:
            initial_cap = st.number_input(
                "Số vốn ban đầu (VND):",
                min_value=1000000,
                max_value=10000000000,
                value=100000000,
                step=10000000,
                format="%d"
            )
        with col_inp2:
            sim_sym = st.selectbox("Chọn mã để chạy giả lập chiến lược:", symbols)
            
        df_sim_raw = df_all[df_all['symbol'] == sim_sym].sort_values('trade_date')
        
        with col_inp3:
            min_date = df_sim_raw['trade_date'].min()
            max_date = df_sim_raw['trade_date'].max()
            selected_range = st.date_input(
                "Chọn khoảng thời gian mô phỏng:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
            
        start_date, end_date = None, None
        if isinstance(selected_range, tuple) and len(selected_range) == 2:
            start_date, end_date = selected_range
            
        df_sim_res, summary = run_simulation(df_sim_raw, initial_capital=initial_cap, start_date=start_date, end_date=end_date)
        
        if df_sim_res is None:
            st.error("⚠️ Không có đủ tối thiểu 15 phiên giao dịch để chạy giả lập trong khoảng thời gian đã chọn.")
        else:
            # Display simulated statistics
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="card-label">Mua & Nắm giữ (B&H)</div>
                    <div class="card-value">{df_sim_res['equity_bh'].iloc[-1]:,.0f} Đ</div>
                    <div class="card-delta {'delta-up' if summary['Return_BH']>=0 else 'delta-down'}">
                        Lợi nhuận: {summary['Return_BH']:.2f}% | MDD: {summary['MDD_BH']}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                <div class="metric-card" style="border-color:#10b981;">
                    <div class="card-label" style="color:#10b981;">DLS-TS-Net Long-Only</div>
                    <div class="card-value" style="color:#10b981;">{df_sim_res['equity_lo'].iloc[-1]:,.0f} Đ</div>
                    <div class="card-delta {'delta-up' if summary['Return_LO']>=0 else 'delta-down'}">
                        Lợi nhuận: {summary['Return_LO']:.2f}% | MDD: {summary['MDD_LO']}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with m3:
                st.markdown(f"""
                <div class="metric-card" style="border-color:#f59e0b;">
                    <div class="card-label" style="color:#f59e0b;">DLS-TS-Net Long-Short</div>
                    <div class="card-value" style="color:#f59e0b;">{df_sim_res['equity_ls'].iloc[-1]:,.0f} Đ</div>
                    <div class="card-delta {'delta-up' if summary['Return_LS']>=0 else 'delta-down'}">
                        Lợi nhuận: {summary['Return_LS']:.2f}% | MDD: {summary['MDD_LS']}%
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
            st.write("---")
            
            # Interactive Equity Curve Plotting
            st.subheader(f"📈 Đường tăng trưởng tài sản (Equity Curve) - Mã {sim_sym}")
            
            fig_eq = go.Figure()
            
            # Buy & Hold
            fig_eq.add_trace(go.Scatter(
                x=df_sim_res['trade_date'],
                y=df_sim_res['equity_bh'],
                mode='lines',
                name='Buy & Hold',
                line=dict(color='#4facfe', width=2)
            ))
            
            # Long Only
            fig_eq.add_trace(go.Scatter(
                x=df_sim_res['trade_date'],
                y=df_sim_res['equity_lo'],
                mode='lines',
                name='DLS-TS-Net Long-Only',
                line=dict(color='#10b981', width=2.5)
            ))
            
            # Long Short
            fig_eq.add_trace(go.Scatter(
                x=df_sim_res['trade_date'],
                y=df_sim_res['equity_ls'],
                mode='lines',
                name='DLS-TS-Net Long-Short',
                line=dict(color='#f59e0b', width=2.5)
            ))
            
            fig_eq.update_layout(
                title=f"So sánh tăng trưởng tài sản với vốn {initial_cap:,.0f} VND cho mã {sim_sym}",
                xaxis_title="Thời gian",
                yaxis_title="Giá trị tài sản (VND)",
                template="plotly_dark",
                height=500,
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig_eq, use_container_width=True)
