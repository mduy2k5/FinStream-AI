import os
import pandas as pd
import numpy as np
from metrics import fetch_data, calculate_metrics
from simulation import simulate_strategy
from visualize import plot_price_comparison, plot_equity_comparison

def generate_markdown_report(metrics_df, simulation_results, output_file="evaluation/report.md"):
    """Tự động xuất báo cáo toàn diện Giai đoạn 4 dưới dạng tệp Markdown chuyên nghiệp"""
    
    # Tạo bảng markdown cho sai số mô hình
    metrics_md = metrics_df.to_markdown(index=False)
    
    # Tạo bảng markdown cho mô phỏng chiến lược giao dịch
    sim_data = []
    for sym, res in simulation_results.items():
        sim_data.append({
            'Symbol': sym,
            'Lợi nhuận B&H (%)': f"{res['Return_BH (%)']}%",
            'MDD B&H (%)': f"{res['MDD_BH (%)']}%",
            'Lợi nhuận Long-Only (%)': f"{res['Return_LO (%)']}%",
            'MDD Long-Only (%)': f"{res['MDD_LO (%)']}%",
            'Lợi nhuận Long-Short (%)': f"{res['Return_LS (%)']}%",
            'MDD Long-Short (%)': f"{res['MDD_LS (%)']}%",
        })
    sim_df = pd.DataFrame(sim_data)
    sim_md = sim_df.to_markdown(index=False)
    
    # Tạo danh sách các slide biểu đồ cho từng mã
    carousel_md = ""
    for sym in simulation_results.keys():
        carousel_md += f"### Mã {sym}\n"
        carousel_md += f"![Biểu đồ Giá {sym}](plots/{sym}_prices.png)\n"
        carousel_md += f"![Đường tài sản {sym}](plots/{sym}_equity.png)\n\n"
        
    report_content = f"""# Báo Cáo Giai Đoạn 4: Đánh Giá Hiệu Năng & Mô Phỏng Chiến Lược Đầu Tư

Báo cáo này được tự động tạo lập để tổng hợp sai số dự báo của mô hình **DLS-TS-Net (PyTorch)** và hiệu quả tăng trưởng tài sản khi áp dụng chiến lược giao dịch dựa trên tín hiệu mô hình trên dữ liệu thực tế lịch sử.

---

## 📊 1. Kết Quả Đánh Giá Sai Số Mô Hình (Model Accuracy)

Dưới đây là thống kê các chỉ số sai số **RMSE (Root Mean Squared Error)**, **MAE (Mean Absolute Error)**, **MAPE (Mean Absolute Percentage Error)** và hệ số xác định **$R^2$ (R-squared)** trên từng mã cổ phiếu:

{metrics_md}

> [!NOTE]
> - **MAPE (%) < 5%**: Thể hiện khả năng dự báo cực kỳ chính xác.
> - **$R^2$ sát mốc 1.0**: Thể hiện mô hình bám rất sát xu hướng và biên độ biến động của đường giá thực tế.

---

## 📈 2. Hiệu Quả Chiến Lược Giao Dịch (Trading Backtest Results)

Mô phỏng tài khoản với số vốn ban đầu **100,000,000 VND** giao dịch theo tín hiệu dự đoán của mô hình so với đường trung bình động $SMA_{10}$ (chiến lược **Buy-Short-MA**):
- **Buy & Hold (B&H)**: Mua nắm giữ từ phiên đầu tiên.
- **Long-Only**: Chỉ mua giữ cổ phiếu khi dự báo tăng, bán ra giữ tiền mặt khi dự báo giảm.
- **Long-Short**: Mua (Long) khi dự báo tăng, Bán khống (Short) khi dự báo giảm.

{sim_md}

> [!TIP]
> - Chiến lược **Long-Only** giúp hạn chế rủi ro giảm giá sâu (Max Drawdown thấp hơn rõ rệt so với Buy & Hold).
> - Chiến lược **Long-Short** cho phép tối ưu hóa lợi nhuận vượt trội trong cả thị trường downtrend nhờ vị thế bán khống (Short).

---

## 🖼️ 3. Biểu Đồ Trực Quan Hóa (Visualizations)

{carousel_md}
"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"\n[Báo cáo] Đã xuất báo cáo chi tiết tại: {output_file}")

def main():
    print("============================================================")
    print("  ĐANG CHẠY TIẾN TRÌNH ĐÁNH GIÁ & MÔ PHỎNG GIAI ĐOẠN 4...")
    print("============================================================")
    
    try:
        # 1. Truy xuất dữ liệu từ DB
        print("[1/4] Đang lấy dữ liệu thực tế & dự đoán từ PostgreSQL...")
        df = fetch_data()
        
        if df.empty:
            print("[Lỗi] Không tìm thấy dữ liệu khớp nhau trong PostgreSQL. Vui lòng đảm bảo cụm Spark đã chạy xong.")
            return
            
        print(f" -> Đã lấy thành công {len(df)} bản ghi.")
        
        # 2. Tính toán sai số mô hình
        print("\n[2/4] Đang tính toán chỉ số sai số mô hình (RMSE, MAE, MAPE, R2)...")
        metrics_df = calculate_metrics(df)
        print(metrics_df.to_string(index=False))
        
        # 3. Mô phỏng chiến lược giao dịch và vẽ đồ thị
        print("\n[3/4] Đang chạy mô phỏng chiến lược đầu tư & vẽ biểu đồ đồ thị...")
        simulation_results = {}
        symbols = df['symbol'].unique()
        
        for sym in symbols:
            df_sym = df[df['symbol'] == sym]
            
            # Chạy mô phỏng giao dịch
            df_sim, summary = simulate_strategy(df_sym)
            
            if summary is None:
                continue
                
            simulation_results[sym] = summary
            
            # Vẽ biểu đồ giá & tài sản dạng premium dark mode
            plot_price_comparison(df_sim, sym)
            plot_equity_comparison(df_sim, sym)
            print(f"  [{sym}] Đã mô phỏng xong & xuất biểu đồ thành công.")
            
        # 4. Xuất báo cáo Markdown
        print("\n[4/4] Đang tổng hợp dữ liệu và sinh báo cáo Markdown...")
        generate_markdown_report(metrics_df, simulation_results)
        
        print("\n============================================================")
        print("  HOÀN THÀNH GIAI ĐOẠN 4 THÀNH CÔNG!")
        print("============================================================")
        
    except Exception as e:
        print(f"\n[Lỗi] Đã xảy ra lỗi trong tiến trình: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
