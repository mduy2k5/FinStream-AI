"""
DLS-TS-Net: Deep Learning Stock Time Series Network
Kiến trúc kết hợp CNN + LSTM + GRU + AutoRegressive (AR)
Dựa theo bài báo: "DLS-TS-Net for stock price forecasting"

Luồng dữ liệu:
    Input (batch, seq_len, n_features)
        ├─── CNN Branch  ──► LSTM ──► GRU ──► deep_out
        └─── AR Branch (Linear) ──────────────► ar_out
                                    └─── concat ──► output (batch, horizon)
"""

import torch
import torch.nn as nn


class CNNBlock(nn.Module):
    """
    Trích xuất đặc trưng cục bộ từ chuỗi thời gian bằng 1D Convolution.
    Input shape : (batch, seq_len, n_features)
    Output shape: (batch, seq_len, cnn_channels)
    """

    def __init__(self, n_features: int, cnn_channels: int, kernel_size: int = 3):
        super().__init__()
        self.conv = nn.Conv1d(
            in_channels=n_features,
            out_channels=cnn_channels,
            kernel_size=kernel_size,
            padding=kernel_size // 2,   # same padding giữ nguyên độ dài chuỗi
        )
        self.relu = nn.ReLU()
        self.bn   = nn.BatchNorm1d(cnn_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Conv1d yêu cầu (batch, channel, length)
        x = x.permute(0, 2, 1)         # (batch, n_features, seq_len)
        x = self.relu(self.bn(self.conv(x)))
        x = x.permute(0, 2, 1)         # (batch, seq_len, cnn_channels)
        return x


class ARBlock(nn.Module):
    """
    AutoRegressive Branch: lớp tuyến tính song song để nắm bắt thành phần tuyến tính
    của chuỗi thời gian (giữ lại xu hướng tuyến tính mà RNN dễ bỏ qua).
    Input shape : (batch, seq_len, n_features)  – chỉ dùng giá Close (feature index 0)
    Output shape: (batch, horizon)
    """

    def __init__(self, seq_len: int, horizon: int):
        super().__init__()
        self.linear = nn.Linear(seq_len, horizon)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Chỉ lấy đặc trưng đầu tiên (Close price) theo đúng bài báo
        close = x[:, :, 0]              # (batch, seq_len)
        return self.linear(close)       # (batch, horizon)


class DLSTSNet(nn.Module):
    """
    DLS-TS-Net: Deep Learning Stock – Time Series Network

    Tham số khởi tạo:
        n_features  : số chiều đặc trưng đầu vào (Open, High, Low, Close, Volume → 5)
        seq_len     : độ dài cửa sổ trượt (sliding window), ví dụ 20 ngày
        horizon     : số bước dự báo tương lai, ví dụ 1 (ngày tiếp theo)
        cnn_channels: số bộ lọc (filter) của lớp CNN
        lstm_hidden : số đơn vị ẩn (hidden units) của LSTM
        gru_hidden  : số đơn vị ẩn của GRU
        dropout     : tỉ lệ dropout để chống overfit
    """

    def __init__(
        self,
        n_features: int  = 5,
        seq_len: int     = 20,
        horizon: int     = 1,
        cnn_channels: int = 64,
        lstm_hidden: int  = 128,
        gru_hidden: int   = 64,
        dropout: float    = 0.2,
    ):
        super().__init__()
        self.seq_len  = seq_len
        self.horizon  = horizon

        # --- CNN Branch ---
        self.cnn = CNNBlock(n_features, cnn_channels)

        # --- LSTM: nắm bắt xu hướng dài hạn ---
        self.lstm = nn.LSTM(
            input_size=cnn_channels,
            hidden_size=lstm_hidden,
            batch_first=True,
            dropout=dropout,
        )

        # --- GRU: nắm bắt biến động ngắn hạn ---
        self.gru = nn.GRU(
            input_size=lstm_hidden,
            hidden_size=gru_hidden,
            batch_first=True,
            dropout=dropout,
        )

        # --- AR Branch ---
        self.ar = ARBlock(seq_len, horizon)

        # --- Lớp kết hợp đầu ra (Fusion Layer) ---
        self.dropout = nn.Dropout(dropout)
        self.fc      = nn.Linear(gru_hidden + horizon, horizon)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (batch, seq_len, n_features)
        returns: (batch, horizon)
        """
        # ── Nhánh sâu: CNN → LSTM → GRU ──
        cnn_out  = self.cnn(x)                          # (batch, seq_len, cnn_channels)
        lstm_out, _ = self.lstm(cnn_out)                # (batch, seq_len, lstm_hidden)
        gru_out, _  = self.gru(lstm_out)                # (batch, seq_len, gru_hidden)
        deep_out = gru_out[:, -1, :]                    # Lấy bước cuối (batch, gru_hidden)
        deep_out = self.dropout(deep_out)

        # ── Nhánh AR tuyến tính ──
        ar_out = self.ar(x)                             # (batch, horizon)

        # ── Fusion: ghép nối và chiếu ra horizon ──
        combined = torch.cat([deep_out, ar_out], dim=1) # (batch, gru_hidden + horizon)
        output   = self.fc(combined)                    # (batch, horizon)

        return output


# ──────────────────────────────────────────────
# Hàm tiện ích: tải/lưu model
# ──────────────────────────────────────────────

def build_model(
    n_features: int  = 5,
    seq_len: int     = 20,
    horizon: int     = 1,
    cnn_channels: int = 64,
    lstm_hidden: int  = 128,
    gru_hidden: int   = 64,
    dropout: float    = 0.2,
) -> DLSTSNet:
    """Khởi tạo mô hình với các tham số mặc định theo bài báo."""
    model = DLSTSNet(
        n_features=n_features,
        seq_len=seq_len,
        horizon=horizon,
        cnn_channels=cnn_channels,
        lstm_hidden=lstm_hidden,
        gru_hidden=gru_hidden,
        dropout=dropout,
    )
    return model


def save_model(model: DLSTSNet, path: str = "dls_ts_net.pt") -> None:
    torch.save(model.state_dict(), path)
    print(f"Model đã được lưu tại: {path}")


def load_model(path: str, **kwargs) -> DLSTSNet:
    model = build_model(**kwargs)
    model.load_state_dict(torch.load(path, map_location="cpu"))
    model.eval()
    print(f"Model đã được tải từ: {path}")
    return model


if __name__ == "__main__":
    # Kiểm tra nhanh kiến trúc model
    model = build_model(n_features=5, seq_len=20, horizon=1)
    print(model)

    dummy_input = torch.randn(8, 20, 5)         # batch=8, seq=20, features=5
    output = model(dummy_input)
    print(f"\nInput shape  : {dummy_input.shape}")
    print(f"Output shape : {output.shape}")     # Kỳ vọng: (8, 1)

    # Đếm tổng số tham số
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Tổng tham số : {total_params:,}")
