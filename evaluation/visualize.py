import os
import matplotlib.pyplot as plt
import seaborn as sns

def set_premium_dark_style():
    """Thiết lập phong cách biểu đồ Dark Mode cực kỳ sang trọng, hiện đại"""
    plt.style.use('dark_background')
    
    # Cấu hình chi tiết qua rcParams
    plt.rcParams['figure.facecolor'] = '#18181B'  # Màu nền ngoài (Zinc 900)
    plt.rcParams['axes.facecolor'] = '#09090B'    # Màu nền trong biểu đồ (Zinc 950)
    plt.rcParams['axes.edgecolor'] = '#27272A'    # Màu viền (Zinc 800)
    plt.rcParams['grid.color'] = '#18181B'         # Màu lưới
    plt.rcParams['grid.alpha'] = 0.5
    plt.rcParams['text.color'] = '#E4E4E7'         # Màu chữ (Zinc 200)
    plt.rcParams['axes.labelcolor'] = '#A1A1AA'    # Màu nhãn trục (Zinc 400)
    plt.rcParams['xtick.color'] = '#71717A'        # Màu chia độ X
    plt.rcParams['ytick.color'] = '#71717A'        # Màu chia độ Y
    plt.rcParams['font.size'] = 11
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['figure.autolayout'] = True

def plot_price_comparison(df_sym, symbol, output_dir="evaluation/plots"):
    """Vẽ biểu đồ so sánh Giá thực tế vs Giá dự báo"""
    os.makedirs(output_dir, exist_ok=True)
    set_premium_dark_style()
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Vẽ đường giá
    ax.plot(df_sym['trade_date'], df_sym['actual_close'], 
            label="Giá Close thực tế", color="#06B6D4", linewidth=2, alpha=0.9)
    ax.plot(df_sym['trade_date'], df_sym['predicted_close'], 
            label="Dự báo DLS-TS-Net", color="#F43F5E", linewidth=1.8, linestyle="--", alpha=0.9)
    
    # Định dạng
    ax.set_title(f"Mô hình DLS-TS-Net: Giá thực tế vs Dự báo - Mã {symbol}", 
                 fontsize=15, fontweight='bold', color='#F4F4F5', pad=15)
    ax.set_xlabel("Thời gian (Ngày giao dịch)", fontsize=12, labelpad=10)
    ax.set_ylabel("Giá đóng cửa (VND)", fontsize=12, labelpad=10)
    ax.legend(frameon=True, facecolor='#18181B', edgecolor='#27272A', loc='upper left')
    ax.grid(True, linestyle=":", alpha=0.6)
    
    # Định dạng tiền tệ Y-axis
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
    
    output_path = os.path.join(output_dir, f"{symbol}_prices.png")
    plt.savefig(output_path, dpi=300, facecolor='#18181B')
    plt.close()
    return output_path

def plot_equity_comparison(df_sym, symbol, output_dir="evaluation/plots"):
    """Vẽ biểu đồ so sánh Sự tăng trưởng tài sản (Equity Curve)"""
    os.makedirs(output_dir, exist_ok=True)
    set_premium_dark_style()
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Vẽ các đường tài sản
    ax.plot(df_sym['trade_date'], df_sym['equity_bh'], 
            label="Buy & Hold (Mặc định)", color="#71717A", linewidth=1.5, alpha=0.7)
    ax.plot(df_sym['trade_date'], df_sym['equity_lo'], 
            label="Chiến lược Long-Only", color="#10B981", linewidth=2.2, alpha=0.9)
    ax.plot(df_sym['trade_date'], df_sym['equity_ls'], 
            label="Chiến lược Long-Short", color="#F59E0B", linewidth=2.2, alpha=0.9)
    
    # Định dạng
    ax.set_title(f"Hiệu quả tăng trưởng tài sản - Mã {symbol}", 
                 fontsize=15, fontweight='bold', color='#F4F4F5', pad=15)
    ax.set_xlabel("Thời gian (Ngày giao dịch)", fontsize=12, labelpad=10)
    ax.set_ylabel("Tài sản (VND)", fontsize=12, labelpad=10)
    ax.legend(frameon=True, facecolor='#18181B', edgecolor='#27272A', loc='upper left')
    ax.grid(True, linestyle=":", alpha=0.6)
    
    # Định dạng tiền tệ Y-axis
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
    
    output_path = os.path.join(output_dir, f"{symbol}_equity.png")
    plt.savefig(output_path, dpi=300, facecolor='#18181B')
    plt.close()
    return output_path
