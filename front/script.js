function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

let currentSymbol = "NSE:TCS-EQ";
let currentTF = "5min";

// Support URL parameters for automation
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.has('symbol')) currentSymbol = urlParams.get('symbol');
if (urlParams.has('tf')) currentTF = urlParams.get('tf');
let priceChart, rsiChart, macdChart, cmfChart, cvdChart;
let candleSeries, lineSeries, volumeSeries, ema1Series, ema2Series;
let rsiSeries, rsiSmaSeries, macdSeries, macdSignalSeries, macdHistSeries, cmfSeries, cvdSeries;
let isSyncing = false;
let activeModalPane = null;
let charts = [];
let lastVisibilityState = ""; // To track changes for flex reset
let cvdHighLine = null;
let cvdLowLine = null;

// Replay State
let isReplayMode = false;
let isPlaying = false;
let isJumpPending = false;
let replayBuffer = [];
let replayIndex = 0;
let replayInterval = null;
let replaySpeed = 1000;

// Indicator settings state
let indicatorSettings = {
    rsi: {
        len: 14,
        smaLen: 14,
        showSma: false,
        smaColor: '#58a6ff',
        smaWidth: 2,
        visible: true,
        horizontalLines: [{ level: 70, color: 'rgba(255, 69, 96, 0.3)' }, { level: 30, color: 'rgba(35, 209, 139, 0.3)' }]
    },
    macd: {
        fast: 12,
        slow: 26,
        sig: 9,
        visible: true,
        horizontalLines: [{ level: 0, color: 'rgba(255, 255, 255, 0.1)' }]
    },
    cvd: {
        anchor: "D",
        useCustom: false,
        customTF: "1min",
        visible: true,
        refCandles: 8,
        showHighRef: true,
        showLowRef: true
    },
    cmf: {
        len: 20,
        visible: true,
        horizontalLines: [
            { level: 0, color: '#787B86', style: 0, width: 1 },
            { level: 0.05, color: 'rgb(248, 48, 13)', style: 0, width: 2 },
            { level: -0.05, color: 'rgb(252, 32, 8)', style: 0, width: 2 }
        ]
    },
    frvp: {
        rows: 24,
        vaPct: 70,
        mode: 'UpDown', // Total, UpDown, Delta
        widthPct: 0.3,
        showVA: true,
        showLabels: true,
        extendRight: false,
        pocColor: '#1900ffff',
        pocWidth: 6,
        vaColor: 'rgba(0, 105, 202, 0.6)',
        nonVaColor: 'rgba(0, 105, 202, 0.2)',
        upColor: 'rgba(35, 209, 139, 0.6)',
        downColor: 'rgba(255, 69, 96, 0.6)',
        vahColor: '#fcae07ff',
        valColor: '#fcae07ff',
        vahWidth: 4,
        valWidth: 4,
        vahWidth: 4,
        valWidth: 4,
        visible: true,
        horizontalLines: [],
        isManualRange: false
    },
    ema1: {
        len: 21,
        color: '#f93403ff',
        width: 3,
        visible: true,
        horizontalLines: []
    },
    ema2: {
        len: 9,
        color: '#40ff00ff',
        width: 3,
        visible: true,
        horizontalLines: []
    }
};

// FRVP Tool State
let frvpToolActive = false;
let frvpSelectionStep = 0; // 0: idle, 1: picking start, 2: picking end, 3: active
let frvpRange = { start: null, end: null }; // timestamps
let frvpData = null;
let frvpDragging = null; // 'start', 'end', or null
let frvpCanvas, frvpCtx;
let frvpPriceLines = [];

// Range Tool State
let rangeToolActive = false;
let rangeSelectionStep = 0; // 0: idle, 1: picking start, 2: picking end
let tempRange = { startTime: null, startPrice: null, endTime: null, endPrice: null };
let activeRanges = []; // Array of { startTime, startPrice, endTime, endPrice, id }
let rangeHitAreas = []; // Helper for click detection

// Internal map to store price lines so we can clear them
let priceLinesMap = {
    rsi: [],
    macd: [],
    cmf: [],
    cvd: []
};

// 0️⃣ Load Symbols & Search Logic
let allSymbols = [];
async function loadSymbols() {
    try {
        const resp = await fetch('http://127.0.0.1:5000/symbols');
        allSymbols = await resp.json();
        const searchInput = document.getElementById('symbol-search');
        const currentSymObj = allSymbols.find(s => s.symbol === currentSymbol);
        if (currentSymObj) searchInput.value = currentSymObj.symbol.split(':')[1] || currentSymObj.symbol;

        setupSymbolSearch();
    } catch (e) { console.error("Error loading symbols:", e); }
}

function setupSymbolSearch() {
    const input = document.getElementById('symbol-search');
    const results = document.getElementById('symbol-results');
    let selectedIndex = -1;

    input.addEventListener('input', () => {
        selectedIndex = -1;
        const val = input.value.toLowerCase();
        const matches = allSymbols.filter(s =>
            s.symbol.toLowerCase().includes(val) ||
            s.name.toLowerCase().includes(val)
        );
        renderMatches(matches);
        results.style.display = 'block';
    });

    input.addEventListener('focus', () => {
        selectedIndex = -1;
        const matches = allSymbols.filter(s =>
            s.symbol.toLowerCase().includes(input.value.toLowerCase()) ||
            s.name.toLowerCase().includes(input.value.toLowerCase())
        );
        renderMatches(matches);
        results.style.display = 'block';
    });

    input.addEventListener('keydown', (e) => {
        const items = results.querySelectorAll('.search-item');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            selectedIndex = (selectedIndex + 1) % items.length;
            updateSelection(items);
            e.preventDefault();
        } else if (e.key === 'ArrowUp') {
            selectedIndex = (selectedIndex - 1 + items.length) % items.length;
            updateSelection(items);
            e.preventDefault();
        } else if (e.key === 'Enter') {
            if (selectedIndex > -1) {
                items[selectedIndex].click();
            } else if (items.length > 0) {
                items[0].click();
            }
        } else if (e.key === 'Escape') {
            results.style.display = 'none';
        }
    });

    function updateSelection(items) {
        items.forEach((item, i) => {
            item.classList.toggle('selected', i === selectedIndex);
            if (i === selectedIndex) item.scrollIntoView({ block: 'nearest' });
        });
    }

    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !results.contains(e.target)) {
            results.style.display = 'none';
        }
    });

    function renderMatches(matches) {
        results.innerHTML = matches.map(s => `
            <div class="search-item" onclick="selectSymbol('${s.symbol}')">
                <span class="sym-code">${s.symbol}</span>
                <span class="sym-name">${s.name}</span>
            </div>
        `).join('');
    }
}

function selectSymbol(symbol) {
    currentSymbol = symbol;
    const searchInput = document.getElementById('symbol-search');
    const symObj = allSymbols.find(s => s.symbol === symbol);
    if (symObj) searchInput.value = symObj.symbol.split(':')[1] || symObj.symbol;
    document.getElementById('symbol-results').style.display = 'none';
    changeSymbol(symbol);
}

window.selectSymbol = selectSymbol;

// 1️⃣ Initialize Charts
async function initCharts() {
    // Load config first
    try {
        const resp = await fetch('http://127.0.0.1:5000/config');
        if (resp.ok) {
            const config = await resp.json();
            if (config.indicators) {
                Object.keys(config.indicators).forEach(key => {
                    if (indicatorSettings[key]) {
                        const settings = config.indicators[key];
                        if (typeof settings === 'object') {
                            Object.assign(indicatorSettings[key], settings);
                        } else {
                            indicatorSettings[key].visible = settings;
                        }
                    }
                });
            }
            if (config.default_tf && !urlParams.has('tf')) currentTF = config.default_tf;
            if (config.default_symbol && !urlParams.has('symbol')) currentSymbol = config.default_symbol;

            // Update UI for buttons
            document.querySelectorAll('#tf-selector button').forEach(b =>
                b.classList.toggle('active', b.getAttribute('data-val') === currentTF)
            );
        }
    } catch (e) { console.warn("Could not load config.json, using defaults."); }

    const commonOptions = {
        layout: { background: { color: '#0d1117' }, textColor: '#8b949e' },
        grid: { vertLines: { color: '#161b22' }, horzLines: { color: '#161b22' } },
        timeScale: {
            borderColor: '#30363d',
            timeVisible: true,
            secondsVisible: true,
            shiftVisibleRangeOnNewBar: false,
            barSpacing: 6,
            minBarSpacing: 0.5,
        },
        rightPriceScale: {
            borderColor: '#30363d',
            autoScale: true,
            entireTextOnly: true,
            width: 80,
        },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        handleScroll: { kineticScroll: false },
        handleScale: { kineticScroll: false },
    };

    // --- Price Chart ---
    priceChart = LightweightCharts.createChart(document.getElementById('price-pane'), commonOptions);
    candleSeries = priceChart.addCandlestickSeries({
        upColor: '#23d18b', downColor: '#ff4560', borderVisible: false, wickUpColor: '#23d18b', wickDownColor: '#ff4560'
    });
    volumeSeries = priceChart.addHistogramSeries({
        color: '#26a69a', priceFormat: { type: 'volume' }, priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    lineSeries = priceChart.addLineSeries({ color: '#58a6ff', lineWidth: 2, visible: false });
    ema1Series = priceChart.addLineSeries({ color: indicatorSettings.ema1.color, lineWidth: indicatorSettings.ema1.width, visible: indicatorSettings.ema1.visible });
    ema2Series = priceChart.addLineSeries({ color: indicatorSettings.ema2.color, lineWidth: indicatorSettings.ema2.width, visible: indicatorSettings.ema2.visible });

    // --- RSI Chart ---
    rsiChart = LightweightCharts.createChart(document.getElementById('rsi-pane'), {
        ...commonOptions,
        timeScale: { ...commonOptions.timeScale, visible: false }
    });
    rsiSeries = rsiChart.addLineSeries({ color: '#ff9800', lineWidth: 2 });
    rsiSmaSeries = rsiChart.addLineSeries({ color: indicatorSettings.rsi.smaColor, lineWidth: indicatorSettings.rsi.smaWidth });

    // --- MACD Chart ---
    const macdEl = document.getElementById('macd-pane');
    if (macdEl) {
        macdChart = LightweightCharts.createChart(macdEl, {
            ...commonOptions,
            timeScale: { ...commonOptions.timeScale, visible: false }
        });
        macdHistSeries = macdChart.addHistogramSeries({});
        macdSeries = macdChart.addLineSeries({ color: '#2196f3', lineWidth: 1 });
        macdSignalSeries = macdChart.addLineSeries({ color: '#ff5722', lineWidth: 1 });
    }

    // --- CMF Chart ---
    const cmfEl = document.getElementById('cmf-pane');
    if (cmfEl) {
        cmfChart = LightweightCharts.createChart(cmfEl, {
            ...commonOptions,
            timeScale: { ...commonOptions.timeScale, visible: false }
        });
        cmfSeries = cmfChart.addLineSeries({ color: '#43A047', lineWidth: 2 });
    }

    // --- CVD Chart ---
    const cvdEl = document.getElementById('cvd-pane');
    if (cvdEl) {
        cvdChart = LightweightCharts.createChart(cvdEl, {
            ...commonOptions,
            localization: {
                priceFormatter: (price) => {
                    if (Math.abs(price) >= 1000000) return (price / 1000000).toFixed(1) + 'M';
                    if (Math.abs(price) >= 1000) return (price / 1000).toFixed(1) + 'K';
                    return price.toFixed(0);
                }
            }
        });
        cvdSeries = cvdChart.addCandlestickSeries({
            upColor: '#23d18b', downColor: '#ff4560', borderVisible: false, wickUpColor: '#23d18b', wickDownColor: '#ff4560'
        });
    }

    // --- SYNCING LOGIC ---
    const chartObjects = [
        { chart: priceChart, id: 'price-pane' },
        { chart: rsiChart, id: 'rsi-pane' },
        { chart: macdChart, id: 'macd-pane' },
        { chart: cmfChart, id: 'cmf-pane' },
        { chart: cvdChart, id: 'cvd-pane' }
    ].filter(item => item.chart && document.getElementById(item.id));

    charts = chartObjects.map(item => item.chart);

    charts.forEach((chart, index) => {
        chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (isSyncing || !range) return;
            isSyncing = true;
            charts.forEach((otherChart, otherIndex) => {
                if (index !== otherIndex) {
                    try {
                        otherChart.timeScale().setVisibleLogicalRange(range);
                    } catch (e) { }
                }
            });
            isSyncing = false;
        });

        chart.subscribeCrosshairMove(param => {
            charts.forEach((otherChart, otherIndex) => {
                if (index !== otherIndex) {
                    if (!param || !param.time) {
                        otherChart.clearCrosshairPosition();
                    } else {
                        otherChart.setCrosshairPosition(0, param.time, null);
                    }
                }
            });
            // Update FRVP drag if active
            if (chart === priceChart && (frvpToolActive || rangeToolActive)) handleFRVPMouseMove(param);
        });
    });

    frvpCanvas = document.getElementById('frvp-canvas');
    frvpCtx = frvpCanvas.getContext('2d');

    priceChart.subscribeClick(param => {
        if (!frvpToolActive && !rangeToolActive && !isJumpPending) return;
        handleToolClick(param);
    });

    // Handle Dragging specifically for Tools
    const pricePane = document.getElementById('price-pane');
    pricePane.addEventListener('mousedown', (e) => {
        if (rangeToolActive) return; // Add range tool drag if needed
        if (!frvpToolActive || frvpSelectionStep !== 3) return;
        const rect = pricePane.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const timeScale = priceChart.timeScale();
        const yOffset = e.clientY - rect.top;

        // Tolerance for icons (Horizontal layout)
        const xStartPx = timeScale.timeToCoordinate(frvpRange.start);
        if (yOffset < 35) {
            if (Math.abs(xStartPx + 25 - x) < 10) {
                removeFRVP();
                e.stopPropagation();
                return;
            } else if (Math.abs(xStartPx + 45 - x) < 10) {
                openSettings('frvp');
                e.stopPropagation();
                return;
            }
        }

        // Tolerance for clicking near handles (Start/End lines)
        const xEndPx = timeScale.timeToCoordinate(frvpRange.end);
        if (Math.abs(xStartPx - x) < 15) {
            frvpDragging = 'start';
        } else if (Math.abs(xEndPx - x) < 15) {
            frvpDragging = 'end';
        }

        if (frvpDragging) {
            e.stopPropagation(); // Stop chart from panning
            // Disable chart scrolling while dragging handles
            priceChart.applyOptions({
                handleScroll: { pressedMouseMove: false, mouseWheel: false },
                handleScale: { axisPressedMouseMove: false, mouseWheel: false }
            });
        }
    }, true); // Use Capture phase

    pricePane.addEventListener('mousemove', (e) => {
        if (!frvpToolActive || frvpSelectionStep !== 3 || frvpDragging) return;
        const rect = pricePane.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const timeScale = priceChart.timeScale();
        const xs = timeScale.timeToCoordinate(frvpRange.start);
        const xe = timeScale.timeToCoordinate(frvpRange.end);

        if (Math.abs(xs - x) < 15 || Math.abs(xe - x) < 15) {
            pricePane.style.cursor = 'ew-resize';
        } else if (y < 35 && ((Math.abs(xs + 25 - x) < 10) || (Math.abs(xs + 45 - x) < 10))) {
            pricePane.style.cursor = 'pointer';
        } else {
            pricePane.style.cursor = 'crosshair';
        }
    });

    pricePane.addEventListener('dblclick', (e) => {
        if (!frvpToolActive || frvpSelectionStep !== 3) return;
        const rect = pricePane.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const timeScale = priceChart.timeScale();
        const xStartPx = timeScale.timeToCoordinate(frvpRange.start);
        const xEndPx = timeScale.timeToCoordinate(frvpRange.end);

        if (x >= xStartPx && x <= xEndPx) {
            openSettings('frvp');
        }
    });

    window.addEventListener('mouseup', () => {
        if (frvpDragging) {
            frvpDragging = null;
            // Restore chart scrolling
            priceChart.applyOptions({
                handleScroll: { pressedMouseMove: true, mouseWheel: true },
                handleScale: { axisPressedMouseMove: true, mouseWheel: true }
            });
            loadFRVP(); // Final refresh after drag
        }
    });

    window.addEventListener('resize', () => {
        chartObjects.forEach(item => {
            const el = document.getElementById(item.id);
            if (el) item.chart.resize(el.clientWidth, el.clientHeight);
        });
        requestAnimationFrame(drawFRVP);
    });

    // Ensure FRVP redraws on zoom/scroll
    priceChart.timeScale().subscribeVisibleLogicalRangeChange(() => requestAnimationFrame(drawFRVP));
    try {
        priceChart.priceScale('right').subscribeVisiblePriceRangeChange(() => requestAnimationFrame(drawFRVP));
    } catch (e) {
        console.warn("Price scale subscription failed, using fallback.");
    }
}

// 2️⃣ Splitter Logic
function initSplitters() {
    const allSplitters = [
        document.getElementById('splitter-1'),
        document.getElementById('splitter-2'),
        document.getElementById('splitter-3'),
        document.getElementById('splitter-4')
    ];
    const allPanes = [
        document.getElementById('price-pane'),
        document.getElementById('rsi-pane'),
        document.getElementById('macd-pane'),
        document.getElementById('cmf-pane'),
        document.getElementById('cvd-pane')
    ];

    let draggingSplitter = null;
    let startY, startPrevHeight, startNextHeight;
    let prevPane, nextPane;

    allSplitters.forEach((splitter) => {
        if (!splitter) return;

        splitter.addEventListener('mousedown', (e) => {
            // Find nearest visible panes
            prevPane = null;
            nextPane = null;

            // Search upwards
            let curr = splitter.previousElementSibling;
            while (curr) {
                if (curr.classList.contains('chart-pane') && curr.style.display !== 'none') {
                    prevPane = curr;
                    break;
                }
                curr = curr.previousElementSibling;
            }

            // Search downwards
            curr = splitter.nextElementSibling;
            while (curr) {
                if (curr.classList.contains('chart-pane') && curr.style.display !== 'none') {
                    nextPane = curr;
                    break;
                }
                curr = curr.nextElementSibling;
            }

            if (!prevPane || !nextPane) return;

            draggingSplitter = splitter;
            startY = e.clientY;
            startPrevHeight = prevPane.getBoundingClientRect().height;
            startNextHeight = nextPane.getBoundingClientRect().height;

            splitter.classList.add('dragging');
            document.body.style.cursor = 'row-resize';

            // Set fixed flex basis for all visible panes to allow resizing
            allPanes.forEach(p => {
                if (p.style.display !== 'none') {
                    p.style.flex = `0 0 ${p.getBoundingClientRect().height}px`;
                }
            });

            e.preventDefault();
        });
    });

    document.addEventListener('mousemove', (e) => {
        if (!draggingSplitter) return;

        const deltaY = e.clientY - startY;
        const newPrevHeight = startPrevHeight + deltaY;
        const newNextHeight = startNextHeight - deltaY;

        if (newPrevHeight > 60 && newNextHeight > 60) {
            prevPane.style.flex = `0 0 ${newPrevHeight}px`;
            nextPane.style.flex = `0 0 ${newNextHeight}px`;

            [priceChart, rsiChart, macdChart, cmfChart, cvdChart].forEach((chart, i) => {
                const p = allPanes[i];
                if (chart && p && p.style.display !== 'none') {
                    chart.resize(p.clientWidth, p.clientHeight);
                }
            });
            requestAnimationFrame(drawFRVP);
        }
    });

    document.addEventListener('mouseup', () => {
        if (draggingSplitter) {
            draggingSplitter.classList.remove('dragging');
            draggingSplitter = null;
            document.body.style.cursor = 'default';
        }
    });
}

// 3️⃣ Load Data
async function loadData(isInitial = false) {
    const endpoint = currentTF === 'tick' ? '/ticks' : '/candles';

    // Construct URL with dynamic settings
    const rsi = indicatorSettings.rsi;
    const macd = indicatorSettings.macd;
    const cvd = indicatorSettings.cvd;
    const ema1 = indicatorSettings.ema1;
    const ema2 = indicatorSettings.ema2;

    let url = `http://127.0.0.1:5000${endpoint}?symbol=${currentSymbol}&tf=${currentTF}`;

    if (currentTF !== 'tick') {
        url += `&anchor=${cvd.anchor}`;
        if (cvd.useCustom) url += `&intrabar_tf=${cvd.customTF}`;
        url += `&rsi_len=${rsi.len}`;
        if (rsi.showSma) url += `&rsi_sma_len=${rsi.smaLen}`;
        url += `&macd_fast=${macd.fast}&macd_slow=${macd.slow}&macd_sig=${macd.sig}`;
        if (ema1.visible) url += `&ema1_len=${ema1.len}`;
        if (ema2.visible) url += `&ema2_len=${ema2.len}`;
        url += `&cmf_len=${indicatorSettings.cmf.len}`;
    }

    try {
        const resp = await fetch(url);
        const data = await resp.json();

        if (currentTF === 'tick') {
            if (frvpToolActive) removeFRVP();
            if (candleSeries) candleSeries.setData([]);
            if (volumeSeries) volumeSeries.setData([]);
            if (rsiSeries) rsiSeries.setData([]);
            if (rsiSmaSeries) rsiSmaSeries.setData([]);
            if (macdSeries) macdSeries.setData([]);
            if (macdSignalSeries) macdSignalSeries.setData([]);
            if (macdHistSeries) macdHistSeries.setData([]);
            if (cvdSeries) cvdSeries.setData([]);
            if (cmfSeries) cmfSeries.setData([]);
            if (cvdSeries) cvdSeries.setData([]);

            if (candleSeries) candleSeries.applyOptions({ visible: false });

            if (lineSeries) {
                lineSeries.applyOptions({ visible: true });
                lineSeries.setData(data);
            }
            if (ema1Series) ema1Series.setData([]);
            if (ema2Series) ema2Series.setData([]);
            updateLegend(); // Clear legend in tick mode

            // Hide all indicator panes in tick mode
            ['rsi', 'macd', 'cmf', 'cvd'].forEach(id => {
                const pane = document.getElementById(`${id}-pane`);
                const splitter = pane ? pane.previousElementSibling : null;
                if (pane) pane.style.display = 'none';
                if (splitter && splitter.classList.contains('splitter')) splitter.style.display = 'none';
            });
        } else {
            // Check if visibility changed to decide on flex reset
            let currentVisibility = ['rsi', 'macd', 'cvd'].map(id => indicatorSettings[id].visible).join(',');
            const visibilityChanged = currentVisibility !== lastVisibilityState;
            lastVisibilityState = currentVisibility;

            // Show/Hide panes based on config or TF
            ['rsi', 'macd', 'cmf', 'cvd'].forEach(id => {
                const isVisible = indicatorSettings[id].visible;
                const pane = document.getElementById(`${id}-pane`);
                // Splitter is PREVIOUS sibling
                const splitter = pane ? pane.previousElementSibling : null;

                if (pane) {
                    pane.style.display = isVisible ? 'block' : 'none';
                    if (visibilityChanged || isInitial) pane.style.flex = ''; // Only reset if changed or initial
                }
                if (splitter && splitter.classList.contains('splitter')) {
                    splitter.style.display = isVisible ? 'block' : 'none';
                }
            });
            if (visibilityChanged || isInitial) document.getElementById('price-pane').style.flex = '';

            // Resize charts after DOM update
            requestAnimationFrame(() => {
                [
                    { chart: priceChart, id: 'price-pane' },
                    { chart: rsiChart, id: 'rsi-pane' },
                    { chart: macdChart, id: 'macd-pane' },
                    { chart: cmfChart, id: 'cmf-pane' },
                    { chart: cvdChart, id: 'cvd-pane' }
                ].forEach(item => {
                    const el = document.getElementById(item.id);
                    if (item.chart && el && el.style.display !== 'none') {
                        item.chart.resize(el.clientWidth, el.clientHeight);
                    }
                });
            });

            if (lineSeries) {
                lineSeries.setData([]);
                lineSeries.applyOptions({ visible: false });
            }
            if (candleSeries) candleSeries.applyOptions({ visible: true });

            updateSeriesData(data, isInitial);
        }

        if (isInitial) {
        }

        if (isInitial) {
            priceChart.timeScale().fitContent();
            // Ensure others follow the fit immediately
            const range = priceChart.timeScale().getVisibleRange();
            if (range) {
                charts.forEach(c => {
                    if (c !== priceChart) c.timeScale().setVisibleRange(range);
                });
            }
        }
    } catch (e) { console.error("Error loadData:", e); }
}

function updateHorizontalLines() {
    const seriesMap = { rsi: rsiSeries, macd: macdSeries, cmf: cmfSeries, cvd: cvdSeries };
    Object.keys(seriesMap).forEach(pane => {
        const series = seriesMap[pane];
        if (!series) return;

        // Remove old lines
        priceLinesMap[pane].forEach(line => {
            try { series.removePriceLine(line); } catch (e) { }
        });
        priceLinesMap[pane] = [];
        // Add new lines
        const settings = indicatorSettings[pane];
        if (settings.horizontalLines) {
            settings.horizontalLines.forEach(h => {
                const line = series.createPriceLine({
                    price: h.level,
                    color: h.color,
                    lineWidth: h.width || 1,
                    lineStyle: h.style !== undefined ? h.style : 0,
                    title: h.level.toString(),
                    axisLabelVisible: true,
                });
                priceLinesMap[pane].push(line);
            });
        }
    });
}

// 4️⃣ Settings Management
function openSettings(pane) {
    activeModalPane = pane;
    const modal = document.getElementById('settings-modal');
    const body = document.getElementById('modal-body');
    const title = document.getElementById('modal-title');
    const settings = indicatorSettings[pane];

    title.innerText = `${pane.toUpperCase()} Settings`;
    let html = '';

    if (pane === 'rsi') {
        html += `
            <div class="setting-row"><label>RSI Period</label><input type="number" id="set-rsi-len" value="${settings.len}"></div>
            <div class="setting-row"><label>Show SMA</label><input type="checkbox" id="set-rsi-showSma" ${settings.showSma ? 'checked' : ''}></div>
            <div class="setting-row"><label>SMA Period</label><input type="number" id="set-rsi-smaLen" value="${settings.smaLen}"></div>
            <div class="setting-row"><label>SMA Color</label><input type="color" id="set-rsi-smaColor" value="${settings.smaColor}"></div>
            <div class="setting-row"><label>SMA Width</label><input type="number" id="set-rsi-smaWidth" value="${settings.smaWidth}"></div>
            <div class="setting-row"><label>Visible</label><input type="checkbox" id="set-rsi-visible" ${settings.visible ? 'checked' : ''}></div>
        `;
    } else if (pane === 'macd') {
        html += `
            <div class="setting-row"><label>Fast Period</label><input type="number" id="set-macd-fast" value="${settings.fast}"></div>
            <div class="setting-row"><label>Slow Period</label><input type="number" id="set-macd-slow" value="${settings.slow}"></div>
            <div class="setting-row"><label>Signal Period</label><input type="number" id="set-macd-sig" value="${settings.sig}"></div>
            <div class="setting-row"><label>Visible</label><input type="checkbox" id="set-macd-visible" ${settings.visible ? 'checked' : ''}></div>
        `;
    } else if (pane === 'cvd') {
        html += `
            <div class="setting-row"><label>Anchor</label>
                <select id="set-cvd-anchor">
                    <option value="D" ${settings.anchor === 'D' ? 'selected' : ''}>Day</option>
                    <option value="W" ${settings.anchor === 'W' ? 'selected' : ''}>Week</option>
                    <option value="M" ${settings.anchor === 'M' ? 'selected' : ''}>Month</option>
                </select>
            </div>
            <div class="setting-row"><label>Custom Intrabar</label><input type="checkbox" id="set-cvd-useCustom" ${settings.useCustom ? 'checked' : ''}></div>
            <div class="setting-row"><label>Intrabar TF</label>
                <select id="set-cvd-customTF">
                    <option value="1min" ${settings.customTF === '1min' ? 'selected' : ''}>1m</option>
                    <option value="3min" ${settings.customTF === '3min' ? 'selected' : ''}>3m</option>
                    <option value="5min" ${settings.customTF === '5min' ? 'selected' : ''}>5m</option>
                </select>
            </div>
            <div class="setting-row"><label>Ref Candles (1st N)</label><input type="number" id="set-cvd-refCandles" value="${settings.refCandles}"></div>
            <div class="setting-row"><label>Show High Ref</label><input type="checkbox" id="set-cvd-showHighRef" ${settings.showHighRef ? 'checked' : ''}></div>
            <div class="setting-row"><label>Show Low Ref</label><input type="checkbox" id="set-cvd-showLowRef" ${settings.showLowRef ? 'checked' : ''}></div>
            <div class="setting-row"><label>Visible</label><input type="checkbox" id="set-cvd-visible" ${settings.visible ? 'checked' : ''}></div>
        `;
    } else if (pane === 'cmf') {
        html += `
            <div class="setting-row"><label>CMF Period</label><input type="number" id="set-cmf-len" value="${settings.len}"></div>
            <div class="setting-row"><label>Visible</label><input type="checkbox" id="set-cmf-visible" ${settings.visible ? 'checked' : ''}></div>
        `;
    } else if (pane === 'frvp') {
        html += `
            <div class="setting-row"><label>Rows Layout</label>
                <select id="set-frvp-layout">
                    <option value="NumberOfRows" ${settings.layout === 'NumberOfRows' ? 'selected' : ''}>Number of Rows</option>
                    <option value="TicksPerRow" ${settings.layout === 'TicksPerRow' ? 'selected' : ''}>Ticks Per Row</option>
                </select>
            </div>
            <div class="setting-row"><label>Row Size</label><input type="number" id="set-frvp-rows" value="${settings.rows}"></div>
            <div class="setting-row"><label>Value Area (%)</label><input type="number" id="set-frvp-vaPct" value="${settings.vaPct}"></div>
            <div class="setting-row"><label>Mode</label>
                <select id="set-frvp-mode">
                    <option value="Total" ${settings.mode === 'Total' ? 'selected' : ''}>Total</option>
                    <option value="UpDown" ${settings.mode === 'UpDown' ? 'selected' : ''}>Up/Down</option>
                    <option value="Delta" ${settings.mode === 'Delta' ? 'selected' : ''}>Delta</option>
                </select>
            </div>
            <div class="setting-row"><label>Width (%)</label><input type="number" id="set-frvp-width" value="${settings.widthPct * 100}"></div>
            <div class="setting-row"><label>Show Labels</label><input type="checkbox" id="set-frvp-showLabels" ${settings.showLabels ? 'checked' : ''}></div>
            <div class="setting-row"><label>Extend Right</label><input type="checkbox" id="set-frvp-extendRight" ${settings.extendRight ? 'checked' : ''}></div>
            <hr><div class="modal-subheader">Advanced Styling</div>
            <div class="setting-row"><label>POC Color</label><input type="color" id="set-frvp-pocColor" value="${settings.pocColor}"></div>
            <div class="setting-row"><label>POC Width</label><input type="number" id="set-frvp-pocWidth" value="${settings.pocWidth}"></div>
            <div class="setting-row"><label>VAH Color</label><input type="color" id="set-frvp-vahColor" value="${settings.vahColor}"></div>
            <div class="setting-row"><label>VAH Width</label><input type="number" id="set-frvp-vahWidth" value="${settings.vahWidth}"></div>
            <div class="setting-row"><label>VAL Color</label><input type="color" id="set-frvp-valColor" value="${settings.valColor}"></div>
            <div class="setting-row"><label>VAL Width</label><input type="number" id="set-frvp-valWidth" value="${settings.valWidth}"></div>
        `;
    } else if (pane === 'ema1' || pane === 'ema2') {
        html += `
            <div class="setting-row"><label>Period</label><input type="number" id="set-ema-len" value="${settings.len}"></div>
            <div class="setting-row"><label>Color</label><input type="color" id="set-ema-color" value="${settings.color}"></div>
            <div class="setting-row"><label>Width</label><input type="number" id="set-ema-width" value="${settings.width}"></div>
            <div class="setting-row"><label>Visible</label><input type="checkbox" id="set-ema-visible" ${settings.visible ? 'checked' : ''}></div>
        `;
    }

    // Horizontal Lines Section
    html += '<hr><div class="modal-subheader">Horizontal Lines</div>';
    settings.horizontalLines.forEach((h, i) => {
        html += `
            <div class="setting-row">
                <input type="number" class="h-level" data-index="${i}" value="${h.level}" step="0.1">
                <input type="color" class="h-color" data-index="${i}" value="${h.color.startsWith('rgba') ? '#ffffff' : h.color}">
                <button class="btn-del" onclick="removeHorizontalLine(${i})">🗑️</button>
            </div>
        `;
    });
    html += '<div class="btn-add" onclick="addHorizontalLine()">+ Add Level</div>';

    body.innerHTML = html;
    modal.style.display = 'block';
}

function closeSettings() {
    document.getElementById('settings-modal').style.display = 'none';
    activeModalPane = null;
}

function saveSettings() {
    const pane = activeModalPane;
    const settings = indicatorSettings[pane];

    if (pane === 'rsi') {
        settings.len = parseInt(document.getElementById('set-rsi-len').value);
        settings.showSma = document.getElementById('set-rsi-showSma').checked;
        settings.smaLen = parseInt(document.getElementById('set-rsi-smaLen').value);
        settings.smaColor = document.getElementById('set-rsi-smaColor').value;
        settings.smaWidth = parseInt(document.getElementById('set-rsi-smaWidth').value);
        settings.visible = document.getElementById('set-rsi-visible').checked;
    } else if (pane === 'macd') {
        settings.fast = parseInt(document.getElementById('set-macd-fast').value);
        settings.slow = parseInt(document.getElementById('set-macd-slow').value);
        settings.sig = parseInt(document.getElementById('set-macd-sig').value);
        settings.visible = document.getElementById('set-macd-visible').checked;
    } else if (pane === 'cvd') {
        settings.anchor = document.getElementById('set-cvd-anchor').value;
        settings.useCustom = document.getElementById('set-cvd-useCustom').checked;
        settings.customTF = document.getElementById('set-cvd-customTF').value;
        settings.refCandles = parseInt(document.getElementById('set-cvd-refCandles').value);
        settings.showHighRef = document.getElementById('set-cvd-showHighRef').checked;
        settings.showLowRef = document.getElementById('set-cvd-showLowRef').checked;
        settings.visible = document.getElementById('set-cvd-visible').checked;
    } else if (pane === 'cmf') {
        settings.len = parseInt(document.getElementById('set-cmf-len').value);
        settings.visible = document.getElementById('set-cmf-visible').checked;
        loadData(false);
    } else if (pane === 'frvp') {
        settings.layout = document.getElementById('set-frvp-layout').value;
        settings.rows = parseInt(document.getElementById('set-frvp-rows').value);
        settings.vaPct = parseInt(document.getElementById('set-frvp-vaPct').value);
        settings.mode = document.getElementById('set-frvp-mode').value;
        settings.widthPct = parseFloat(document.getElementById('set-frvp-width').value) / 100;
        settings.showLabels = document.getElementById('set-frvp-showLabels').checked;
        settings.extendRight = document.getElementById('set-frvp-extendRight').checked;

        settings.pocColor = document.getElementById('set-frvp-pocColor').value;
        settings.pocWidth = parseInt(document.getElementById('set-frvp-pocWidth').value);

        settings.vahColor = document.getElementById('set-frvp-vahColor').value;
        settings.vahWidth = parseInt(document.getElementById('set-frvp-vahWidth').value);
        settings.valColor = document.getElementById('set-frvp-valColor').value;
        settings.valWidth = parseInt(document.getElementById('set-frvp-valWidth').value);

        loadFRVP(); // Refresh profile with new settings
    } else if (pane === 'ema1' || pane === 'ema2') {
        settings.len = parseInt(document.getElementById('set-ema-len').value);
        settings.color = document.getElementById('set-ema-color').value;
        settings.width = parseInt(document.getElementById('set-ema-width').value);
        settings.visible = document.getElementById('set-ema-visible').checked;
        updateLegend();
    }

    // Save Horizontal Lines
    const levels = document.querySelectorAll('.h-level');
    const colors = document.querySelectorAll('.h-color');
    settings.horizontalLines = [];
    levels.forEach((lvl, i) => {
        settings.horizontalLines.push({
            level: parseFloat(lvl.value),
            color: colors[i].value
        });
    });

    closeSettings();
    loadData(false);
}

function addHorizontalLine() {
    indicatorSettings[activeModalPane].horizontalLines.push({ level: 50, color: '#ffffff' });
    openSettings(activeModalPane);
}

function removeHorizontalLine(index) {
    indicatorSettings[activeModalPane].horizontalLines.splice(index, 1);
    openSettings(activeModalPane);
}

function changeSymbol(symbol) {
    if (isReplayMode) exitReplayMode();
    currentSymbol = symbol;
    frvpData = null; // Force refresh profile for new symbol
    window.lastFRVPLogTime = null; // Allow new logs
    loadData(true);
}
function changeTF(tf) {
    if (isReplayMode) exitReplayMode();
    currentTF = tf;
    frvpData = null; // Force refresh profile for new timeframe
    window.lastFRVPLogTime = null; // Allow new logs
    document.querySelectorAll('#tf-selector button').forEach(b => b.classList.toggle('active', b.getAttribute('data-val') === tf));
    loadData(true);
}

// Start
initCharts().then(() => {
    initSplitters();
    loadSymbols().then(() => loadData(true));
    // Auto-refresh every 3 seconds
    window.liveInterval = setInterval(() => loadData(false), 3000);
});
// 5️⃣ FRVP Tool Functions
function toggleFRVPTool() {
    if (currentTF === 'tick') {
        alert("FRVP Tool is only available on Candle Timeframes.");
        return;
    }
    frvpToolActive = !frvpToolActive;
    const btn = document.getElementById('frvp-btn');
    btn.classList.toggle('active', frvpToolActive);

    if (frvpToolActive) {
        frvpSelectionStep = 1;
        document.body.style.cursor = 'crosshair';
        console.log("FRVP: Pick start point");
        animateFRVP();
    } else {
        frvpSelectionStep = 0;
        frvpData = null;
        frvpRange = { start: null, end: null };
        document.getElementById('frvp-settings-icon').style.display = 'none';
        document.body.style.cursor = 'default';
        requestAnimationFrame(drawFRVP);
    }
}

function handleToolClick(param) {
    if (!param.time || !param.point) return;

    // First check if user clicked an individual Range 'X' close button
    const hitRect = rangeHitAreas.find(h =>
        param.point.x >= h.x && param.point.x <= h.x + h.w &&
        param.point.y >= h.y && param.point.y <= h.y + h.h
    );
    if (hitRect) {
        activeRanges = activeRanges.filter(r => r.id !== hitRect.id);
        requestAnimationFrame(drawFRVP);
        return;
    }

    if (isJumpPending) {
        handleJumpTo(param.time);
        return;
    }

    if (rangeToolActive) {
        handleRangeClick(param);
        return;
    }

    if (frvpToolActive) {
        handleFRVPClick(param);
    }
}

function handleFRVPClick(param) {
    if (frvpSelectionStep === 1) {
        frvpRange.start = param.time;
        frvpSelectionStep = 2;
        console.log("FRVP: Pick end point");
    } else if (frvpSelectionStep === 2) {
        frvpRange.end = param.time;
        // Ensure chronological
        if (frvpRange.start > frvpRange.end) {
            let tmp = frvpRange.start;
            frvpRange.start = frvpRange.end;
            frvpRange.end = tmp;
        }
        frvpSelectionStep = 3;
        indicatorSettings.frvp.isManualRange = true;
        document.body.style.cursor = 'default';
        const icon = document.getElementById('frvp-settings-icon');
        if (icon) icon.style.display = 'inline-block';
        loadFRVP();
    }
}

function handleRangeClick(param) {
    if (!param.point) return;
    const price = candleSeries.coordinateToPrice(param.point.y);

    if (rangeSelectionStep === 1) {
        tempRange.startTime = param.time;
        tempRange.startPrice = price;
        rangeSelectionStep = 2;
        console.log("Range Tool: Pick end point");
    } else if (rangeSelectionStep === 2) {
        tempRange.endTime = param.time;
        tempRange.endPrice = price;

        // Save this range instance
        activeRanges.push({
            ...tempRange,
            id: Date.now()
        });

        // Reset for next one if still active, or deactivate
        tempRange = { startTime: null, startPrice: null, endTime: null, endPrice: null };
        rangeSelectionStep = 1; // Stay in mode to allow another range

        requestAnimationFrame(drawFRVP);
    }
}

let frvpThrottleTimer = null;
function handleFRVPMouseMove(param) {
    if (!param.time) return;

    if (rangeToolActive && rangeSelectionStep === 2) {
        tempRange.endTime = param.time;
        tempRange.endPrice = candleSeries.coordinateToPrice(param.point.y);
        requestAnimationFrame(drawFRVP);
    }

    if (frvpDragging && param.time) {
        if (frvpDragging === 'start') frvpRange.start = param.time;
        else if (frvpDragging === 'end') frvpRange.end = param.time;
        indicatorSettings.frvp.isManualRange = true;

        // Dynamic visual update
        requestAnimationFrame(drawFRVP);

        // Throttled data update
        if (!frvpThrottleTimer) {
            frvpThrottleTimer = setTimeout(() => {
                loadFRVP();
                frvpThrottleTimer = null;
            }, 100); // 100ms throttle for smoothness without lag
        }
    }

    // Also draw selection preview if picking
    if (frvpSelectionStep === 2) {
        frvpRange.end = param.time;
        requestAnimationFrame(drawFRVP);
    }
}

let frvpLoading = false;
async function loadFRVP() {
    if (frvpLoading || !frvpRange.start || !frvpRange.end) return;

    const settings = indicatorSettings.frvp;
    let endTime = frvpRange.end;

    if ((isReplayMode || settings.extendRight) && window.lastCandleTime) {
        endTime = window.lastCandleTime;
    }

    frvpLoading = true;
    try {
        const url = `http://127.0.0.1:5000/frvp?symbol=${currentSymbol}&start_time=${frvpRange.start}&end_time=${endTime}&chart_tf=${currentTF}&row_size=${settings.rows}&value_area_pct=${settings.vaPct}`;

        console.log(`[FRVP-DEBUG] Fetching Vol Profile: ${currentSymbol} @ ${currentTF}`);

        try {
            const resp = await fetch(url);
            if (!resp.ok) {
                console.error(`[FRVP-DEBUG] API error: ${resp.status}`);
                return;
            }
            frvpData = await resp.json();
            if (frvpData && frvpData.profile) {
                updateFRVPAxisLabels();
                requestAnimationFrame(drawFRVP);
            }
        } catch (e) {
            console.error("[FRVP Load Error]:", e);
        }
    } finally {
        frvpLoading = false;
    }
}

function drawFRVP() {
    if (!frvpCanvas || !frvpCtx) return;

    // Match canvas size to container properly (accounting for device pixel ratio if needed)
    const rect = frvpCanvas.parentElement.getBoundingClientRect();
    if (frvpCanvas.width !== rect.width || frvpCanvas.height !== rect.height) {
        frvpCanvas.width = rect.width;
        frvpCanvas.height = rect.height;
    }

    frvpCtx.clearRect(0, 0, frvpCanvas.width, frvpCanvas.height);

    if (rangeToolActive || activeRanges.length > 0) drawRangeTool();

    if (!frvpToolActive || currentTF === 'tick' || !indicatorSettings.frvp.visible) return;
    if (!frvpRange.start) return;

    const timeScale = priceChart.timeScale();
    const xStart = timeScale.timeToCoordinate(frvpRange.start);
    const xEnd = frvpRange.end ? timeScale.timeToCoordinate(frvpRange.end) : xStart;

    // Draw Range Shade
    frvpCtx.fillStyle = 'rgba(88, 166, 255, 0.05)';
    frvpCtx.fillRect(xStart, 0, xEnd - xStart, frvpCanvas.height);

    // Draw Vertical Handles
    const opacity = (Math.sin(frvpPulse) + 1) / 2;
    frvpCtx.strokeStyle = frvpSelectionStep < 3 ? `rgba(88, 166, 255, ${0.4 + 0.4 * opacity})` : 'rgba(88, 166, 255, 0.4)';
    frvpCtx.lineWidth = frvpSelectionStep < 3 ? 2 : 1;
    frvpCtx.strokeRect(xStart, 0, xEnd - xStart, frvpCanvas.height);

    // Draw lines
    const midX = (xStart + xEnd) / 2;
    // ... rest of custom drawing




    frvpCtx.setLineDash([5, 5]);
    frvpCtx.beginPath();
    frvpCtx.moveTo(xStart, 0); frvpCtx.lineTo(xStart, frvpCanvas.height);
    frvpCtx.moveTo(xEnd, 0); frvpCtx.lineTo(xEnd, frvpCanvas.height);
    frvpCtx.stroke();
    frvpCtx.setLineDash([]);

    // Selection Point Indicators
    if (frvpSelectionStep === 1 || frvpSelectionStep === 2) {
        frvpCtx.fillStyle = '#58a6ff';
        frvpCtx.beginPath();
        frvpCtx.arc(xStart, frvpCanvas.height / 2, 5 + 3 * opacity, 0, Math.PI * 2);
        frvpCtx.fill();
    }
    if (frvpSelectionStep === 2) {
        frvpCtx.beginPath();
        frvpCtx.arc(xEnd, frvpCanvas.height / 2, 5 + 3 * opacity, 0, Math.PI * 2);
        frvpCtx.fill();
    }

    if (frvpSelectionStep !== 3) return;

    // Draggable Handles (Separate circles to prevent "triangle" fill)
    frvpCtx.fillStyle = '#58a6ff';
    [10, frvpCanvas.height - 10].forEach(y => {
        frvpCtx.beginPath(); frvpCtx.arc(xStart, y, 6, 0, Math.PI * 2); frvpCtx.fill();
        frvpCtx.beginPath(); frvpCtx.arc(xEnd, y, 6, 0, Math.PI * 2); frvpCtx.fill();
    });

    // Icons to the right (Horizontal layout, further away from handle)
    frvpCtx.fillStyle = 'rgba(255, 69, 96, 0.9)';
    frvpCtx.font = 'bold 16px Arial';
    frvpCtx.fillText('×', xStart + 25, 20); // Removal X

    frvpCtx.fillStyle = 'rgba(88, 166, 255, 0.9)';
    frvpCtx.fillText('⚙️', xStart + 45, 20); // Settings Gear

    if (frvpSelectionStep !== 3 || !frvpData || !frvpData.profile || frvpData.profile.length === 0) return;

    const settings = indicatorSettings.frvp;
    const { profile, poc, vah, val } = frvpData;

    // Draw Bars
    const maxVol = Math.max(...profile.map(r => r.total));
    const binWidthPx = frvpCanvas.height / profile.length;
    const maxWidth = frvpCanvas.width * settings.widthPct;

    // Draw from left (xStart) or fixed position? 
    // Usually FRVP sticks to the start of the range or right side.
    // We'll draw it starting from xStart protruding right.

    profile.forEach((row, i) => {
        const priceStep = profile.length > 1 ? (profile[1].price - profile[0].price) : row.price * 0.001;
        const yTop = candleSeries.priceToCoordinate(row.price + priceStep);
        const yBottom = candleSeries.priceToCoordinate(row.price);
        const h = Math.abs(yBottom - yTop);

        const isVA = row.price >= val && row.price <= vah;
        const totalW = (row.total / maxVol) * maxWidth;

        if (settings.mode === 'UpDown') {
            const upW = (row.up / row.total) * totalW;
            const downW = totalW - upW;

            // Up Volume
            frvpCtx.fillStyle = isVA ? settings.upColor : hexToRgba(settings.upColor.startsWith('rgba') ? '#23d18b' : settings.upColor, 0.2);
            frvpCtx.fillRect(xStart, yTop, upW, h - 1);

            // Down Volume
            frvpCtx.fillStyle = isVA ? settings.downColor : hexToRgba(settings.downColor.startsWith('rgba') ? '#ff4560' : settings.downColor, 0.2);
            frvpCtx.fillRect(xStart + upW, yTop, downW, h - 1);
        } else if (settings.mode === 'Delta') {
            const delta = row.up - row.down;
            const deltaW = (Math.abs(delta) / maxVol) * maxWidth;
            frvpCtx.fillStyle = delta >= 0 ? settings.upColor : settings.downColor;
            frvpCtx.fillRect(xStart, yTop, deltaW, h - 1);
        } else { // Total
            frvpCtx.fillStyle = isVA ? settings.vaColor : settings.nonVaColor;
            frvpCtx.fillRect(xStart, yTop, totalW, h - 1);
        }
    });

    // VAH Line
    frvpCtx.setLineDash([]);
    frvpCtx.lineWidth = settings.vahWidth;
    frvpCtx.strokeStyle = settings.vahColor;
    const yVah = candleSeries.priceToCoordinate(vah);
    frvpCtx.beginPath();
    frvpCtx.moveTo(xStart, yVah); frvpCtx.lineTo(xEnd, yVah);
    frvpCtx.stroke();

    // VAL Line
    frvpCtx.lineWidth = settings.valWidth;
    frvpCtx.strokeStyle = settings.valColor;
    const yVal = candleSeries.priceToCoordinate(val);
    frvpCtx.beginPath();
    frvpCtx.moveTo(xStart, yVal); frvpCtx.lineTo(xEnd, yVal);
    frvpCtx.stroke();

    // POC
    frvpCtx.lineWidth = settings.pocWidth;
    frvpCtx.strokeStyle = settings.pocColor;
    const yPoc = candleSeries.priceToCoordinate(poc);
    frvpCtx.beginPath();
    frvpCtx.moveTo(xStart, yPoc); frvpCtx.lineTo(xEnd, yPoc);
    frvpCtx.stroke();

    if (settings.showLabels) {
        frvpCtx.fillStyle = settings.pocColor;
        frvpCtx.font = '10px Outfit';
        frvpCtx.fillText(`POC: ${poc.toFixed(2)}`, xEnd + 5, yPoc + 3);
    }
}

// Ensure draw loop for FRVP (Subscription moved to initCharts)

function removeFRVP() {
    frvpToolActive = false;
    frvpSelectionStep = 0;
    frvpData = null;
    frvpRange = { start: null, end: null };
    indicatorSettings.frvp.isManualRange = false;
    const btn = document.getElementById('frvp-btn');
    if (btn) btn.classList.remove('active');
    const icon = document.getElementById('frvp-settings-icon');
    if (icon) icon.style.display = 'none';
    requestAnimationFrame(drawFRVP);
    updateFRVPAxisLabels(); // Clear lines
}

function toggleRangeTool() {
    if (currentTF === 'tick') {
        alert("Range Tool is only available on Candle Timeframes.");
        return;
    }
    rangeToolActive = !rangeToolActive;
    const btn = document.getElementById('range-btn');
    if (btn) btn.classList.toggle('active', rangeToolActive);

    if (rangeToolActive) {
        if (frvpToolActive) toggleFRVPTool();
        rangeSelectionStep = 1;
        document.body.style.cursor = 'crosshair';
        console.log("Range Tool: Pick start point");
    } else {
        removeRangeTool();
    }
}

function removeRangeTool() {
    rangeToolActive = false;
    rangeSelectionStep = 0;
    tempRange = { startTime: null, startPrice: null, endTime: null, endPrice: null };
    document.body.style.cursor = 'default';
    const btn = document.getElementById('range-btn');
    if (btn) btn.classList.remove('active');
    requestAnimationFrame(drawFRVP);
}

function drawRangeTool() {
    rangeHitAreas = []; // Reset hit areas for each redraw

    // 1. Draw Saved Ranges
    activeRanges.forEach(range => {
        drawSingleRange(range);
    });

    // 2. Draw Temporary Selection (Preview)
    if (rangeSelectionStep > 0 && tempRange.startTime) {
        drawSingleRange(tempRange, true);
    }
}

function drawSingleRange(range, isPreview = false) {
    const timeScale = priceChart.timeScale();
    const xStart = timeScale.timeToCoordinate(range.startTime);
    const yStart = candleSeries.priceToCoordinate(range.startPrice);

    if (xStart === null || yStart === null) return;

    let xEnd = range.endTime ? timeScale.timeToCoordinate(range.endTime) : xStart;
    let yEnd = range.endPrice ? candleSeries.priceToCoordinate(range.endPrice) : yStart;

    const rectX = Math.min(xStart, xEnd);
    const rectY = Math.min(yStart, yEnd);
    const rectW = Math.abs(xEnd - xStart);
    const rectH = Math.abs(yEnd - yStart);

    // Box & Cross
    frvpCtx.fillStyle = isPreview ? 'rgba(88, 166, 255, 0.15)' : 'rgba(88, 166, 255, 0.1)';
    frvpCtx.strokeStyle = isPreview ? '#58a6ff' : 'rgba(88, 166, 255, 0.5)';
    frvpCtx.lineWidth = 1;
    frvpCtx.fillRect(rectX, rectY, rectW, rectH);
    frvpCtx.strokeRect(rectX, rectY, rectW, rectH);

    frvpCtx.beginPath();
    frvpCtx.moveTo(rectX, (yStart + yEnd) / 2); frvpCtx.lineTo(rectX + rectW, (yStart + yEnd) / 2);
    frvpCtx.moveTo((xStart + xEnd) / 2, rectY); frvpCtx.lineTo((xStart + xEnd) / 2, rectY + rectH);
    frvpCtx.stroke();

    if (!range.endTime && isPreview) return;

    // Stats
    const pDiff = range.endPrice - range.startPrice;
    const pPct = (pDiff / range.startPrice) * 100;
    let bars = 0, totalVol = 0;
    if (window.lastData) {
        const t1 = Math.min(range.startTime, range.endTime);
        const t2 = Math.max(range.startTime, range.endTime);
        const segment = window.lastData.filter(d => d.time >= t1 && d.time <= t2);
        bars = segment.length;
        totalVol = segment.reduce((s, d) => s + (d.volume || 0), 0);
    }
    const durationSec = Math.abs(range.endTime - range.startTime);
    let durStr = durationSec >= 86400 ? `${(durationSec / 86400).toFixed(1)}d` : `${Math.floor(durationSec / 60)}m`;
    const volStr = totalVol >= 1000000 ? (totalVol / 1000000).toFixed(2) + 'M' : (totalVol / 1000).toFixed(1) + 'K';

    const labelX = xEnd;
    const labelY = Math.min(yStart, yEnd) - 65;

    // Info Label Box
    frvpCtx.fillStyle = 'rgba(255, 255, 255, 0.95)';
    frvpCtx.shadowBlur = 4; frvpCtx.shadowColor = 'rgba(0,0,0,0.3)';
    const lW = 120, lH = 60;
    frvpCtx.beginPath();
    frvpCtx.roundRect(labelX - lW / 2, labelY, lW, lH, 8);
    frvpCtx.fill();
    frvpCtx.shadowBlur = 0;

    // Text
    frvpCtx.fillStyle = 'black';
    frvpCtx.textAlign = 'center';
    frvpCtx.font = 'bold 12px Outfit';
    frvpCtx.fillText(`${pDiff.toFixed(2)} (${pPct.toFixed(2)}%)`, labelX, labelY + 20);
    frvpCtx.font = '11px Outfit';
    frvpCtx.fillStyle = '#444';
    frvpCtx.fillText(`${bars} bars, ${durStr}`, labelX, labelY + 36);
    frvpCtx.fillText(`Vol: ${volStr}`, labelX, labelY + 52);

    // X Icon (Only for permanent ones)
    if (!isPreview) {
        const xPos = labelX + lW / 2 - 18;
        const yPos = labelY + 6;

        // Background circle for X
        frvpCtx.fillStyle = 'rgba(255, 69, 96, 0.1)';
        frvpCtx.beginPath();
        frvpCtx.arc(xPos + 7, yPos + 7, 8, 0, Math.PI * 2);
        frvpCtx.fill();

        frvpCtx.fillStyle = '#ff4560';
        frvpCtx.font = 'bold 14px Arial';
        frvpCtx.fillText('×', xPos + 7, yPos + 11);

        // Save hit area for click detection (expand slightly for ease of use)
        rangeHitAreas.push({ x: xPos - 2, y: yPos - 2, w: 20, h: 20, id: range.id });
    }
}

function updateFRVPAxisLabels() {
    if (!candleSeries) return;
    frvpPriceLines.forEach(l => {
        try { candleSeries.removePriceLine(l); } catch (e) { }
    });
    frvpPriceLines = [];

    if (!frvpData || !frvpToolActive || !indicatorSettings.frvp.visible) return;

    const { poc, vah, val } = frvpData;
    const settings = indicatorSettings.frvp;

    // Add labels to Y-Axis using PriceLines (Line is hidden, only label shows)
    frvpPriceLines.push(candleSeries.createPriceLine({
        price: poc,
        color: settings.pocColor,
        lineWidth: 0,
        title: 'POC',
        axisLabelVisible: true,
    }));

    frvpPriceLines.push(candleSeries.createPriceLine({
        price: vah,
        color: settings.vahColor,
        lineWidth: 0,
        title: 'VAH',
        axisLabelVisible: true,
    }));

    frvpPriceLines.push(candleSeries.createPriceLine({
        price: val,
        color: settings.valColor,
        lineWidth: 0,
        title: 'VAL',
        axisLabelVisible: true,
    }));
}

// Animation State
let frvpPulse = 0;
function animateFRVP() {
    if (frvpSelectionStep > 0 && frvpSelectionStep < 3) {
        frvpPulse = (frvpPulse + 0.05) % (Math.PI * 2);
        requestAnimationFrame(drawFRVP);
        requestAnimationFrame(animateFRVP);
    }
}

function applyDefaultFRVPRange(data) {
    if (!data || data.length < 10) return;

    const settings = indicatorSettings.frvp;
    if (settings.isManualRange) return;

    const def = settings.defaultRange || { start: { h: 15, m: 0 }, end: { h: 15, m: 20 } };

    const getIST = (time) => {
        const d = new Date(time * 1000);
        // Server already adds +5:30 to the timestamp. We use UTC methods to read shifted components.
        return {
            h: d.getUTCHours(),
            m: d.getUTCMinutes(),
            date: d.getUTCDate(),
            month: d.getUTCMonth(),
            year: d.getUTCFullYear(),
            time
        };
    };

    const targetDate = getIST(data[data.length - 1].time);
    const getISTString = (t) => {
        const d = new Date(t * 1000);
        return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
    };

    let startCandle = null;
    let endCandle = null;

    // Search from end backwards to find TODAY'S range
    for (let i = data.length - 1; i >= 0; i--) {
        const t = getIST(data[i].time);

        // Target only the latest day on the chart
        if (t.date !== targetDate.date || t.month !== targetDate.month || t.year !== targetDate.year) continue;

        // Find End
        if (!endCandle) {
            if ((t.h < def.end.h) || (t.h === def.end.h && t.m <= def.end.m)) {
                endCandle = data[i].time;
            }
        }

        // Find Start
        if (endCandle) {
            if (t.h > def.start.h || (t.h === def.start.h && t.m >= def.start.m)) {
                startCandle = data[i].time;
            } else {
                break; // Passed the start window
            }
        }
    }

    if (startCandle && endCandle) {
        if (startCandle >= endCandle) return;

        const rangeChanged = (startCandle !== frvpRange.start) || (endCandle !== frvpRange.end);
        frvpRange.start = startCandle;
        frvpRange.end = endCandle;
        frvpToolActive = true;
        frvpSelectionStep = 3;

        const btn = document.getElementById('frvp-btn');
        if (btn) btn.classList.add('active');
        const icon = document.getElementById('frvp-settings-icon');
        if (icon) icon.style.display = 'inline-block';

        if (rangeChanged || !frvpData) {
            console.log(`✓ [FRVP-AUTO] Found Window: ${getISTString(startCandle)} -> ${getISTString(endCandle)} on ${targetDate.date}/${targetDate.month + 1}`);
            loadFRVP();
        }
    } else if (!frvpToolActive) {
        // Log once per refresh if window not found
        if (window.lastFRVPLogTime !== targetDate.date) {
            console.log(`[FRVP-DEBUG] Searching for ${def.start.h}:${def.start.m} window on ${targetDate.date}/${targetDate.month + 1}...`);
            window.lastFRVPLogTime = targetDate.date;
        }
    }
}

function updateLegend() {
    const container = document.getElementById('chart-legend');
    if (!container) return;

    if (currentTF === 'tick') {
        container.innerHTML = '';
        return;
    }

    let html = '';
    ['ema1', 'ema2', 'cmf'].forEach(id => {
        const item = indicatorSettings[id];
        if (!item) return;
        const visIcon = item.visible ? '👁️' : '🚫';
        const label = id === 'cmf' ? `CMF ${item.len}` : `${id.toUpperCase()} ${item.len}`;
        html += `
            <div class="legend-item" style="border-left: 3px solid ${item.color || '#43A047'}">
                <span class="legend-label">${label}</span>
                <div class="legend-controls">
                    <button class="legend-btn" onclick="toggleEmaVisibility('${id}')" title="Toggle Visibility">${visIcon}</button>
                    <button class="legend-btn" onclick="openSettings('${id}')" title="Settings">⚙️</button>
                </div>
            </div>
        `;
    });

    // Add FRVP to Legend if active
    if (frvpToolActive) {
        const frvp = indicatorSettings.frvp;
        const visIcon = frvp.visible ? '👁️' : '🚫';
        html += `
            <div class="legend-item" style="border-left: 3px solid ${frvp.pocColor}">
                <span class="legend-label">FRVP</span>
                <span class="legend-value ignore-click">${frvp.rows}r</span>
                <div class="legend-controls">
                    <button class="legend-btn" onclick="openSettings('frvp')" title="Settings">⚙️</button>
                    <button class="legend-btn" onclick="toggleFrvpVisibility()" title="Toggle Visibility">${visIcon}</button>
                    <button class="legend-btn" onclick="removeFRVP()" title="Remove Tool">🗑️</button>
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
}

function toggleFrvpVisibility() {
    indicatorSettings.frvp.visible = !indicatorSettings.frvp.visible;
    requestAnimationFrame(drawFRVP);
    updateFRVPAxisLabels();
    updateLegend();
}

function updateSeriesData(data, isInitial = false) {
    if (!data || data.length === 0) return;
    window.lastData = data;

    if (candleSeries) {
        candleSeries.setData(data);
        window.lastCandleTime = data[data.length - 1].time;
        if (currentTF !== 'tick' && !isReplayMode) {
            applyDefaultFRVPRange(data);
        }
    }

    if (volumeSeries) {
        volumeSeries.setData(data.map(d => ({
            time: d.time, value: d.volume,
            color: d.close >= d.open ? 'rgba(35, 209, 139, 0.3)' : 'rgba(255, 69, 96, 0.3)'
        })));
    }

    const { ema1, ema2, rsi, macd } = indicatorSettings;

    if (ema1Series) {
        if (ema1.visible) {
            ema1Series.applyOptions({ visible: true, color: ema1.color, lineWidth: ema1.width });
            ema1Series.setData(data.filter(d => d.ema1 !== null).map(d => ({ time: d.time, value: d.ema1 })));
        } else {
            ema1Series.applyOptions({ visible: false });
        }
    }

    if (ema2Series) {
        if (ema2.visible) {
            ema2Series.applyOptions({ visible: true, color: ema2.color, lineWidth: ema2.width });
            ema2Series.setData(data.filter(d => d.ema2 !== null).map(d => ({ time: d.time, value: d.ema2 })));
        } else {
            ema2Series.applyOptions({ visible: false });
        }
    }

    updateLegend();

    if (rsiSeries) rsiSeries.setData(data.filter(d => d.rsi !== null).map(d => ({ time: d.time, value: d.rsi })));

    if (rsiSmaSeries) {
        if (rsi.showSma) {
            rsiSmaSeries.applyOptions({ visible: true, color: rsi.smaColor, lineWidth: rsi.smaWidth });
            rsiSmaSeries.setData(data.filter(d => d.rsi_sma !== null).map(d => ({ time: d.time, value: d.rsi_sma })));
        } else {
            rsiSmaSeries.applyOptions({ visible: false });
        }
    }

    if (macdSeries) macdSeries.setData(data.filter(d => d.macd !== null).map(d => ({ time: d.time, value: d.macd })));
    if (macdSignalSeries) macdSignalSeries.setData(data.filter(d => d.macd_s !== null).map(d => ({ time: d.time, value: d.macd_s })));
    if (macdHistSeries) {
        macdHistSeries.setData(data.filter(d => d.macd_h !== null).map(d => ({
            time: d.time, value: d.macd_h,
            color: d.macd_h >= 0 ? 'rgba(35, 209, 139, 0.5)' : 'rgba(255, 69, 96, 0.5)'
        })));
    }

    if (cvdSeries) {
        cvdSeries.setData(data.filter(d => d.cvd_o !== null).map(d => ({
            time: d.time, open: d.cvd_o, high: d.cvd_h, low: d.cvd_l, close: d.cvd_c
        })));
        updateCVDRefLine(data);
    }

    if (cmfSeries) {
        cmfSeries.setData(data.filter(d => d.cmf !== null).map(d => ({
            time: d.time, value: d.cmf
        })));
    }

    updateHorizontalLines();
}

// --- 6️⃣ Bar Replay Logic ---

function updateCVDRefLine(data) {
    if (!cvdSeries || !cvdChart || !data || data.length === 0) return;

    if (cvdHighLine) {
        try { cvdSeries.removePriceLine(cvdHighLine); } catch (e) { }
        cvdHighLine = null;
    }
    if (cvdLowLine) {
        try { cvdSeries.removePriceLine(cvdLowLine); } catch (e) { }
        cvdLowLine = null;
    }

    const { refCandles, visible } = indicatorSettings.cvd;
    if (!visible) return;

    // Identify the last day's data
    const lastTime = data[data.length - 1].time;
    const lastDayNum = Math.floor(lastTime / 86400);

    // Filter for the current trading day
    const lastDayData = data.filter(d => Math.floor(d.time / 86400) === lastDayNum && d.cvd_c !== null);

    if (lastDayData.length > 0) {
        // Take the first N candles of the day
        const firstNCandles = lastDayData.slice(0, refCandles);

        if (indicatorSettings.cvd.showHighRef) {
            const highestValue = Math.max(...firstNCandles.map(d => d.cvd_h));
            cvdHighLine = cvdSeries.createPriceLine({
                price: highestValue,
                color: '#ff9800',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                title: `High (1st ${firstNCandles.length})`,
                axisLabelVisible: true,
            });
        }

        if (indicatorSettings.cvd.showLowRef) {
            const lowestValue = Math.min(...firstNCandles.map(d => d.cvd_l));
            cvdLowLine = cvdSeries.createPriceLine({
                price: lowestValue,
                color: '#2196f3',
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                title: `Low (1st ${firstNCandles.length})`,
                axisLabelVisible: true,
            });
        }
    }
}

function toggleReplayMode() {
    isReplayMode = !isReplayMode;
    const btn = document.getElementById('replay-btn');
    const toolbar = document.getElementById('replay-toolbar');

    if (isReplayMode) {
        btn.classList.add('active');
        toolbar.style.display = 'flex';
        if (window.liveInterval) clearInterval(window.liveInterval);
        console.log("Replay Mode: Active. Click 'Jump To' then click a bar.");
    } else {
        exitReplayMode();
    }
}

function exitReplayMode() {
    isReplayMode = false;
    isPlaying = false;
    isJumpPending = false;
    if (replayInterval) clearInterval(replayInterval);

    document.getElementById('replay-btn').classList.remove('active');
    document.getElementById('replay-toolbar').style.display = 'none';
    document.body.style.cursor = 'default';

    // Restart live updates
    loadData(true).then(() => {
        window.liveInterval = setInterval(() => loadData(false), 3000);
    });
}

function activateJumpTo() {
    isJumpPending = true;
    document.body.style.cursor = 'crosshair';
    console.log("Replay: Select start point on chart.");
}

function togglePlayback() {
    if (replayBuffer.length === 0) {
        alert("Please select a starting point first using 'Jump To'.");
        return;
    }
    isPlaying = !isPlaying;
    const btn = document.getElementById('replay-play-pause');
    btn.innerText = isPlaying ? '⏸️ Pause' : '▶️ Play';

    if (isPlaying) {
        startPlayback();
    } else {
        if (replayInterval) clearInterval(replayInterval);
    }
}

function startPlayback() {
    if (replayInterval) clearInterval(replayInterval);
    replayInterval = setInterval(() => {
        replayStepForward();
    }, replaySpeed);
}

function updateReplaySpeed(val) {
    const multiplier = parseFloat(val);
    replaySpeed = Math.round(1000 / multiplier);
    document.getElementById('speed-label').innerText = multiplier.toFixed(1) + 'x';
    if (isPlaying) startPlayback();
}

function replayStepForward() {
    if (replayIndex >= replayBuffer.length - 1) {
        if (isPlaying) togglePlayback();
        return;
    }
    replayIndex++;
    updateChartsToCurrentIndex();
}

function updateChartsToCurrentIndex() {
    const dataSlice = replayBuffer.slice(0, replayIndex + 1);
    updateSeriesData(dataSlice);
    if (frvpToolActive) loadFRVP(); // Recalculate FRVP as we play
}

async function handleJumpTo(time) {
    isJumpPending = false;
    document.body.style.cursor = 'default';

    // Disable auto-refresh
    if (window.liveInterval) clearInterval(window.liveInterval);

    const endpoint = currentTF === 'tick' ? '/ticks' : '/candles';
    let url = `http://127.0.0.1:5000${endpoint}?symbol=${currentSymbol}&tf=${currentTF}`;

    const { rsi, macd, cvd, ema1, ema2, cmf } = indicatorSettings;
    url += `&anchor=${cvd.anchor}&rsi_len=${rsi.len}&macd_fast=${macd.fast}&macd_slow=${macd.slow}&macd_sig=${macd.sig}&cmf_len=${cmf.len}`;
    if (ema1.visible) url += `&ema1_len=${ema1.len}`;
    if (ema2.visible) url += `&ema2_len=${ema2.len}`;

    try {
        const resp = await fetch(url);
        replayBuffer = await resp.json();

        // Find the index of the clicked time
        replayIndex = replayBuffer.findIndex(d => d.time === time);
        if (replayIndex === -1) {
            // Fallback: find closest
            replayIndex = replayBuffer.findIndex(d => d.time >= time);
        }

        if (replayIndex !== -1) {
            console.log(`Replay: Jumped to index ${replayIndex} (${new Date(time * 1000).toLocaleString()})`);
            updateChartsToCurrentIndex();
        } else {
            console.warn("Could not find that time in historical data.");
        }
    } catch (e) {
        console.error("Replay Jump Error:", e);
    }
}

// Global scope for legend & replay functions
window.toggleFrvpVisibility = toggleFrvpVisibility;
window.toggleEmaVisibility = toggleEmaVisibility;
window.toggleReplayMode = toggleReplayMode;
window.exitReplayMode = exitReplayMode;
window.activateJumpTo = activateJumpTo;
window.togglePlayback = togglePlayback;
window.replayStepForward = replayStepForward;
window.updateReplaySpeed = updateReplaySpeed;

function toggleEmaVisibility(id) {
    if (indicatorSettings[id]) {
        indicatorSettings[id].visible = !indicatorSettings[id].visible;
        loadData(false);
    }
}

// Global scope for legend functions
window.toggleEmaVisibility = toggleEmaVisibility;
