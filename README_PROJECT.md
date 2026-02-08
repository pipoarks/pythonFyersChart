# LiveTick Pro - Trading System Documentation

LiveTick Pro is a high-performance trading dashboard designed for real-time market analysis, featuring advanced indicators, volume profiling tools, and historical replay functionality.

## 🏗️ System Architecture

The system follows a decoupled Client-Server architecture:

### 1. Backend (Python/Flask)
- **Server (`server.py`)**: The primary API interface handling requests for candles, indicators, and tools like FRVP/FVG.
- **Engine (`core/indicator_engine.py`)**: Orchestrates data processing. It fetches raw data, applies resampling, and calculates all indicators for the UI.
- **Indicators (`indicators/`)**: A modular library of technical indicators:
  - **CVD (Cumulative Volume Delta)**: Tracks buy/sell pressure over time.
  - **FVG (Fair Value Gap)**: Detects price imbalances with mitigation tracking and day-filtering.
  - **FRVP (Fixed Range Volume Profile)**: Calculates volume distribution over specific price levels within a selected range.
  - **Standard Indicators**: VWAP, CMF (Chaikin Money Flow), EMA, RSI, MACD.

### 2. Frontend (HTML5/JavaScript/Canvas)
- **Main UI (`front/index.html`)**: A multi-pane dashboard with split-view support for price, RSI, MACD, CMF, and CVD charts.
- **Charting Logic (`front/script.js`)**: Built on **TradingView Lightweight Charts**.
- **Canvas Overlay Layer**: Uses a high-performance transparent canvas for drawing dynamic tools like FRVP profiles and FVG boxes.

## 🚀 Key Features

### 📉 Advanced Indicators
- **CVD Integration**: Integrated as a dedicated chart pane with daily anchor resets and support for custom reference lines (High/Low of the first N candles).
- **FVG (Fair Value Gap)**: 
  - **Detection**: Based on LuxAlgo logic (High[2] < Low[0] or Low[2] > High[0]).
  - **Mitigation**: Real-time tracking of when gaps are filled.
  - **UI Integration**: Quick toggle in navbar, settings modal, and real-time gap counts in the legend.

### 🛠️ Interactive Tools
- **FRVP (Fixed Range Volume Profile)**: Drag-and-drop tool to analyze volume at price within any historical window. Supports Number of Rows and Ticks Per Row layouts.
- **Range Tool**: Measures price and time differences between two points.

### 🔁 Replay Mode
- Allows users to "Jump To" a point in time and step through historical bars to simulate live market conditions and test strategies.

## ⚙️ Configuration & Data

- **`config.json`**: Centralized configuration for indicator periods, colors, visibility, and default tool settings.
- **Data Persistence**: Uses SQLite (`candles_1min.db` and `ticks.db`) for efficient historical data retrieval.
- **Symbol Management**: Symbols are managed via `symbols.json` and populated dynamically in the UI.

## 🛠️ Setup & Running

1. **Start Backend**:
   ```powershell
   python server.py
   ```
2. **Open Frontend**:
   Navigate to `front/index.html` in your browser.

3. **Parameters**:
   All settings can be modified via the ⚙️ icon next to each indicator in the chart legend or the navbar.
