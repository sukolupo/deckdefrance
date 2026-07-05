// Tab Navigation
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Deactivate all sidebar items
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.classList.remove('active');
    });

    // Show selected tab
    const tabEl = document.getElementById(tabName);
    if (tabEl) tabEl.classList.add('active');

    // Activate selected sidebar item
    const sidebarItem = document.querySelector(`.sidebar-item[data-tab="${tabName}"]`);
    if (sidebarItem) sidebarItem.classList.add('active');

    // Close sidebar
    closeSidebar();

    // Auto-refresh status tab when active
    if (tabName === 'status') {
        refreshStatusTab();
        if (statusTabInterval) clearInterval(statusTabInterval);
        statusTabInterval = setInterval(refreshStatusTab, 3000);
    } else {
        if (statusTabInterval) {
            clearInterval(statusTabInterval);
            statusTabInterval = null;
        }
    }

    // Load config when switching to config tab
    if (tabName === 'config') {
        loadConfig();
        loadPresets();
    }
}

// Sidebar Navigation
function openSidebar() {
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebar-overlay').classList.add('open');
}

function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('open');
}

document.getElementById('hamburger-btn').addEventListener('click', openSidebar);
document.getElementById('sidebar-close').addEventListener('click', closeSidebar);
document.getElementById('sidebar-overlay').addEventListener('click', closeSidebar);

document.querySelectorAll('.sidebar-item[data-tab]').forEach(item => {
    item.addEventListener('click', (e) => {
        const tabName = e.currentTarget.getAttribute('data-tab');
        switchTab(tabName);
    });
});

// FTP Presets
async function loadPresets() {
    try {
        const res = await fetch('/api/config/presets');
        const presets = await res.json();
        const container = document.getElementById('preset-container');
        container.innerHTML = '';
        Object.entries(presets).forEach(([key, preset]) => {
            const card = document.createElement('div');
            card.className = 'preset-card';
            card.innerHTML = `
                <div class="preset-name">${preset.label}</div>
                <div class="preset-detail">Max trigger: <strong>${preset.max_target_watts}W</strong></div>
                <div class="preset-detail">Race mode: <strong>${preset.power_threshold_race}W</strong></div>
                <div class="preset-detail">Button A: <strong>${preset.power_threshold_button_a}W</strong></div>
                <div class="preset-detail">Cadence: <strong>${preset.cadence_threshold} RPM</strong></div>
            `;
            card.addEventListener('click', () => applyPreset(preset));
            container.appendChild(card);
        });
    } catch (e) {
        console.error('Error loading presets:', e);
    }
}

function applyPreset(preset) {
    document.getElementById('max-watts').value = preset.max_target_watts;
    document.getElementById('cadence-threshold').value = preset.cadence_threshold;
    document.getElementById('power-race').value = preset.power_threshold_race;
    document.getElementById('power-button-a').value = preset.power_threshold_button_a;
    showMessage('config-message', `Preset applied — save to persist`, 'success');
}

// Configuration Management
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        document.getElementById('trainer-mac').value = config.trainer_mac_address || '';
        document.getElementById('max-watts').value = config.max_target_watts || 300;
        document.getElementById('cadence-threshold').value = config.cadence_threshold || 95;
        document.getElementById('power-race').value = config.power_threshold_race || 150;
        document.getElementById('power-button-a').value = config.power_threshold_button_a || 250;
        document.getElementById('gear-multiplier').value = config.gear_multiplier || 2.0;
        renderMappings(config.mappings || []);
    } catch (error) {
        console.error('Error loading config:', error);
        showMessage('config-message', 'Error loading configuration', 'error');
    }
}

// Mapping UI
const SOURCES = ["power", "cadence", "resistance"];
const TARGETS = [
    "right_trigger", "left_trigger",
    "left_stick_x", "left_stick_y",
    "right_stick_x", "right_stick_y",
    "btn_a", "btn_b", "btn_x", "btn_y",
];

function renderMappings(mappings) {
    const container = document.getElementById('mappings-container');
    container.querySelectorAll('.mapping-row:not(.mapping-header)').forEach(el => el.remove());
    mappings.forEach((m, i) => appendMappingRow(container, m, i));
}

function appendMappingRow(container, mapping, index) {
    const row = document.createElement('div');
    row.className = 'mapping-row';
    row.dataset.index = index;

    const sourceOpts = SOURCES.map(s =>
        `<option value="${s}"${mapping.source === s ? ' selected' : ''}>${s.charAt(0).toUpperCase() + s.slice(1)}</option>`
    ).join('');

    const targetOpts = TARGETS.map(t =>
        `<option value="${t}"${mapping.target === t ? ' selected' : ''}>${t.replace(/_/g, ' ').replace(/(^|\s)\S/g, l => l.toUpperCase())}</option>`
    ).join('');

    const isBtn = mapping.target && (mapping.target.startsWith('btn_'));
    const thresholdVal = mapping.threshold || 150;

    row.innerHTML = `
        <select class="mapping-source">${sourceOpts}</select>
        <select class="mapping-target">${targetOpts}</select>
        <input type="number" class="mapping-threshold" value="${thresholdVal}" min="0" max="500" step="5" ${isBtn ? '' : 'style="opacity:0.4;"'}>
        <button class="btn btn-small btn-danger" onclick="this.closest('.mapping-row').remove()">✕</button>
    `;

    row.querySelector('.mapping-target').addEventListener('change', function () {
        const isBtn = this.value.startsWith('btn_');
        const thresholdInput = row.querySelector('.mapping-threshold');
        thresholdInput.style.opacity = isBtn ? '1' : '0.4';
    });

    container.appendChild(row);
}

function addMappingRow() {
    const container = document.getElementById('mappings-container');
    const idx = container.querySelectorAll('.mapping-row:not(.mapping-header)').length;
    appendMappingRow(container, { source: "power", target: "right_trigger", threshold: 150 }, idx);
}

function collectMappings() {
    const rows = document.querySelectorAll('#mappings-container .mapping-row:not(.mapping-header)');
    return Array.from(rows).map(row => {
        const source = row.querySelector('.mapping-source').value;
        const target = row.querySelector('.mapping-target').value;
        const threshold = parseInt(row.querySelector('.mapping-threshold').value, 10) || 150;
        return target.startsWith('btn_')
            ? { source, target, threshold }
            : { source, target };
    });
}

const configForm = document.getElementById('config-form');
if (configForm) {
    configForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(e.target);
        const config = {
        trainer_mac_address: formData.get('trainer_mac_address'),
        max_target_watts: parseFloat(formData.get('max_target_watts')),
        cadence_threshold: parseFloat(formData.get('cadence_threshold')),
        power_threshold_race: parseFloat(formData.get('power_threshold_race')),
        power_threshold_button_a: parseFloat(formData.get('power_threshold_button_a')),
        gear_multiplier: parseFloat(formData.get('gear_multiplier')),
        mappings: collectMappings(),
    };

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config),
        });

        if (response.ok) {
            showMessage('config-message', 'Configuration saved successfully!', 'success');
        } else {
            showMessage('config-message', 'Error saving configuration', 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showMessage('config-message', 'Error saving configuration', 'error');
    }
});
}

// Status Tab
async function refreshStatusTab() {
    try {
        const [health, stream] = await Promise.all([
            fetch('/api/health').then(r => r.json()),
            fetch('/api/stream-status').then(r => r.json()),
        ]);

        document.getElementById('status-service').textContent = health.status === 'ok' ? '✓ Running' : '✗ Error';
        document.getElementById('status-service').className = 'status-value ' + (health.status === 'ok' ? 'status-ok' : 'status-err');

        const streamingEl = document.getElementById('status-streaming');
        if (health.streaming) {
            streamingEl.textContent = '✓ Active';
            streamingEl.className = 'status-value status-ok';
        } else {
            streamingEl.textContent = '✗ Stopped';
            streamingEl.className = 'status-value status-err';
        }

        document.getElementById('status-mac').textContent = health.trainer_configured ? 'Configured' : 'Not set';
        document.getElementById('status-mac').className = 'status-value ' + (health.trainer_configured ? 'status-ok' : 'status-muted');

        document.getElementById('status-message').textContent = stream.message || '—';

        const mergeEl = document.getElementById('status-merge');
        if (health.merge_active) {
            mergeEl.textContent = '✓ Active';
            mergeEl.className = 'status-value status-ok';
        } else {
            mergeEl.textContent = '✗ Off';
            mergeEl.className = 'status-value status-err';
        }
    } catch (error) {
        console.error('Error refreshing status tab:', error);
        document.getElementById('status-service').textContent = '✗ Unreachable';
        document.getElementById('status-service').className = 'status-value status-err';
    }
}

let statusTabInterval = null;

// Test Mapping
async function testMapping() {
    const power = parseFloat(document.getElementById('test-power').value);
    const cadence = parseFloat(document.getElementById('test-cadence').value);
    const resistance = parseFloat(document.getElementById('test-resistance').value);

    try {
        const response = await fetch('/api/map', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                trainer_power: power,
                cadence: cadence,
                resistance: resistance,
            }),
        });

        const data = await response.json();
        const mapping = data.mapping;

        const resultHtml = `
Power Input: ${power}W
Cadence Input: ${cadence} RPM
Resistance Input: ${resistance}

MAPPED OUTPUT:
- Cycling Power: ${mapping.cycling_power}W
- Button A: ${mapping.button_a ? '✓ Active' : '✗ Inactive'}
- Button B: ${mapping.button_b ? '✓ Active' : '✗ Inactive'}
- Gear: ${mapping.gear}
- Mode: ${mapping.mode.toUpperCase()}
        `;

        document.getElementById('mapping-result').textContent = resultHtml;
    } catch (error) {
        console.error('Error testing mapping:', error);
        document.getElementById('mapping-result').textContent = 'Error: Unable to test mapping';
    }
}

// Test Trainer Connection
async function testConnection() {
    const btnElement = document.querySelector('[onclick="testConnection()"]');
    const btnText = document.getElementById('test-btn-text');
    const resultDiv = document.getElementById('connection-result');
    const messageDiv = document.getElementById('connection-message');

    btnElement.disabled = true;
    btnText.textContent = 'Testing...';
    resultDiv.style.display = 'none';

    try {
        const response = await fetch('/api/test-trainer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.connected) {
            messageDiv.innerHTML = `
✓ <strong>Trainer Connected!</strong><br>
Device: ${data.device_name || 'Unknown'}<br>
Services: ${data.service_count ?? 'N/A'}
            `;
            document.getElementById('connection-test').innerHTML = '<span class="status-badge connected">✓ Connected</span>';
        } else {
            messageDiv.innerHTML = `
✗ <strong>Trainer Not Connected</strong><br>
Details: ${data.message || 'Unable to reach trainer'}
            `;
            document.getElementById('connection-test').innerHTML = '<span class="status-badge disconnected">✗ Disconnected</span>';
        }

        resultDiv.style.display = 'block';
    } catch (error) {
        console.error('Error testing connection:', error);
        messageDiv.textContent = 'Error: Unable to test connection - ' + error.message;
        resultDiv.style.display = 'block';
        document.getElementById('connection-test').innerHTML = '<span class="status-badge disconnected">✗ Error</span>';
    } finally {
        btnElement.disabled = false;
        btnText.textContent = 'Test Trainer Connection';
    }
}

// Dpad State
let dpadState = { x: 0, y: 0 };

function sendDpadState() {
    fetch('/api/dpad', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dpadState),
    }).catch(() => {});
}

function setDpad(direction, pressed) {
    switch (direction) {
        case 'up':    dpadState.y = pressed ? -1 : 0; break;
        case 'down':  dpadState.y = pressed ? 1 : 0; break;
        case 'left':  dpadState.x = pressed ? -1 : 0; break;
        case 'right': dpadState.x = pressed ? 1 : 0; break;
    }
    sendDpadState();
}

document.querySelectorAll('[data-dpad]').forEach(el => {
    const dir = el.getAttribute('data-dpad');
    el.addEventListener('mousedown', e => { e.preventDefault(); setDpad(dir, true); });
    el.addEventListener('mouseup', e => { e.preventDefault(); setDpad(dir, false); });
    el.addEventListener('mouseleave', e => { setDpad(dir, false); });
    el.addEventListener('touchstart', e => { e.preventDefault(); setDpad(dir, true); }, { passive: false });
    el.addEventListener('touchend', e => { e.preventDefault(); setDpad(dir, false); }, { passive: false });
    el.addEventListener('touchcancel', e => { setDpad(dir, false); });
});

// Helper function to show messages
function showMessage(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `message ${type}`;
    setTimeout(() => {
        element.className = 'message';
    }, 5000);
}

// Device Discovery
async function discoverBikeTrainers() {
    const btnElement = document.querySelector('[onclick="discoverBikeTrainers()"]');
    const btnText = document.getElementById('discover-btn-text');
    const listDiv = document.getElementById('discovered-list');

    btnElement.disabled = true;
    btnText.textContent = 'Scanning...';
    listDiv.innerHTML = '<p>Scanning for Trainers... (this may take up to 5 seconds)</p>';

    try {
        const response = await fetch('/api/discover-trainer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.error) {
            listDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
        } else if (data.found === 0) {
            listDiv.innerHTML = '<p>No Trainers found. Make sure your trainer is powered on and in pairing mode.</p>';
        } else {
            let html = '<div class="device-list-items">';
            data.devices.forEach(device => {
                html += `
                    <div class="device-item">
                        <div class="device-name">${device.name}</div>
                        <div class="device-mac">${device.mac_address}</div>
                        <div class="device-signal">Signal: ${device.rssi} dBm</div>
                        <button class="btn btn-small" onclick="selectDevice('${device.mac_address}', '${device.name}')">Select</button>
                    </div>
                `;
            });
            html += '</div>';
            listDiv.innerHTML = html;
        }
    } catch (error) {
        console.error('Error discovering trainers:', error);
        listDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    } finally {
        btnElement.disabled = false;
        btnText.textContent = 'Scan for Trainers';
    }
}

async function discoverAllDevices() {
    const btnElement = document.querySelector('[onclick="discoverAllDevices()"]');
    const btnText = document.getElementById('discover-all-btn-text');
    const listDiv = document.getElementById('all-devices-list');

    btnElement.disabled = true;
    btnText.textContent = 'Scanning...';
    listDiv.style.display = 'block';
    listDiv.innerHTML = '<p>Scanning for all Bluetooth devices... (this may take up to 5 seconds)</p>';

    try {
        const response = await fetch('/api/discover-all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.error) {
            listDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
        } else if (data.found === 0) {
            listDiv.innerHTML = '<p>No Bluetooth devices found.</p>';
        } else {
            let html = '<div class="device-list-items">';
            data.devices.forEach(device => {
                html += `
                    <div class="device-item">
                        <div class="device-name">${device.name}</div>
                        <div class="device-mac">${device.mac_address}</div>
                        <div class="device-signal">Signal: ${device.rssi} dBm</div>
                        <button class="btn btn-small" onclick="selectDevice('${device.mac_address}', '${device.name}')">Select</button>
                    </div>
                `;
            });
            html += '</div>';
            listDiv.innerHTML = html;
        }
    } catch (error) {
        console.error('Error discovering devices:', error);
        listDiv.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    } finally {
        btnElement.disabled = false;
        btnText.textContent = 'Scan All Devices';
    }
}

function selectDevice(macAddress, deviceName) {
    // Set the MAC address in the config tab
    document.getElementById('trainer-mac').value = macAddress;
    
    // Switch to config tab
    switchTab('config');
    
    // Show a success message
    showMessage('config-message', `Selected device: ${deviceName}`, 'success');
}

// Streaming Control
async function startStreaming() {
    console.log('startStreaming() invoked');
    const startBtn = document.getElementById('stream-start-btn');
    const stopBtn = document.getElementById('stream-stop-btn');
    const statusIndicator = document.getElementById('stream-status-indicator');
    const statusMessage = document.getElementById('stream-status-message');
    
    startBtn.disabled = true;
    statusMessage.textContent = 'Starting...';

    try {
        const response = await fetch('/api/start-streaming', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.status === 'streaming') {
            statusIndicator.innerHTML = '<span class="status-badge connected">✓ Streaming</span>';
            statusMessage.textContent = data.message;
            startBtn.disabled = true;
            stopBtn.disabled = false;
            startStreamDataPolling();
        } else if (data.status === 'starting') {
            statusIndicator.innerHTML = '<span class="status-badge idle">⟳ Connecting...</span>';
            statusMessage.textContent = data.message;
            startBtn.disabled = true;
            stopBtn.disabled = true;
            // Poll status in background to update when connected
            if (!statusPollInterval) {
                statusPollInterval = setInterval(refreshStreamStatus, 2000);
            }
        } else {
            statusIndicator.innerHTML = '<span class="status-badge disconnected">✗ Error</span>';
            statusMessage.textContent = data.message;
            startBtn.disabled = false;
        }
    } catch (error) {
        console.error('Error starting stream:', error);
        statusIndicator.innerHTML = '<span class="status-badge disconnected">✗ Error</span>';
        statusMessage.textContent = `Error: ${error.message}`;
        startBtn.disabled = false;
    }
}

async function stopStreaming() {
    const startBtn = document.getElementById('stream-start-btn');
    const stopBtn = document.getElementById('stream-stop-btn');
    const statusIndicator = document.getElementById('stream-status-indicator');
    const statusMessage = document.getElementById('stream-status-message');

    stopBtn.disabled = true;
    statusMessage.textContent = 'Stopping...';
    stopStreamDataPolling();

    try {
        const response = await fetch('/api/stop-streaming', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.status === 'stopped') {
            statusIndicator.innerHTML = '<span class="status-badge disconnected">✗ Stopped</span>';
            statusMessage.textContent = data.message;
            startBtn.disabled = false;
            stopBtn.disabled = true;
        } else {
            statusMessage.textContent = data.message;
        }
    } catch (error) {
        console.error('Error stopping stream:', error);
        statusMessage.textContent = `Error: ${error.message}`;
        stopBtn.disabled = false;
    }
}

async function refreshStreamStatus() {
    const statusIndicator = document.getElementById('stream-status-indicator');
    const statusMessage = document.getElementById('stream-status-message');
    const startBtn = document.getElementById('stream-start-btn');
    const stopBtn = document.getElementById('stream-stop-btn');

    try {
        const response = await fetch('/api/stream-status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.streaming) {
            statusIndicator.innerHTML = '<span class="status-badge connected">✓ Streaming</span>';
            startBtn.disabled = true;
            stopBtn.disabled = false;
            if (!streamDataInterval) {
                startStreamDataPolling();
            }
        } else if (data.connecting) {
            statusIndicator.innerHTML = '<span class="status-badge idle">⟳ Connecting...</span>';
            startBtn.disabled = true;
            stopBtn.disabled = true;
        } else {
            statusIndicator.innerHTML = '<span class="status-badge disconnected">✗ Stopped</span>';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
        statusMessage.textContent = data.message;
    } catch (error) {
        console.error('Error refreshing status:', error);
        statusMessage.textContent = `Error: ${error.message}`;
    }
}

// Stream Data Polling
let streamDataInterval = null;
let streamLogInterval = null;
let statusPollInterval = null;

// Rolling buffer for chart (2 min at ~1Hz)
const MAX_CHART_POINTS = 120;
let chartData = [];
let streamChart = null;

function initChart() {
    const canvas = document.getElementById('stream-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    streamChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Watts',
                    data: [],
                    borderColor: '#48bb78',
                    backgroundColor: 'rgba(72, 187, 120, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: true,
                    yAxisID: 'y_watts',
                },
                {
                    label: 'Cadence (RPM)',
                    data: [],
                    borderColor: '#ffd700',
                    backgroundColor: 'rgba(255, 215, 0, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: true,
                    yAxisID: 'y_cadence',
                },
                {
                    label: 'Trigger',
                    data: [],
                    borderColor: '#f56565',
                    backgroundColor: 'rgba(245, 101, 101, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: true,
                    yAxisID: 'y_trigger',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 200 },
            interaction: {
                intersect: false,
                mode: 'index',
            },
            scales: {
                x: {
                    display: true,
                    ticks: {
                        maxTicksLimit: 10,
                        color: '#888',
                    },
                    grid: {
                        color: 'rgba(255,255,255,0.05)',
                    },
                },
                y_watts: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Watts',
                        color: '#48bb78',
                    },
                    min: 0,
                    max: 400,
                    grid: {
                        color: 'rgba(255,255,255,0.05)',
                    },
                    ticks: {
                        color: '#48bb78',
                    },
                },
                y_cadence: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'RPM',
                        color: '#ffd700',
                    },
                    min: 0,
                    max: 150,
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        color: '#ffd700',
                    },
                },
                y_trigger: {
                    type: 'linear',
                    display: false,
                    min: 0,
                    max: 255,
                },
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#ccc',
                        boxWidth: 12,
                        padding: 16,
                    },
                },
            },
        },
    });
}

function updateChart(watts, cadence, trigger) {
    if (!streamChart) return;

    const now = new Date();
    const label = now.toLocaleTimeString();

    chartData.push({ label, watts, cadence, trigger });
    if (chartData.length > MAX_CHART_POINTS) {
        chartData.shift();
    }

    streamChart.data.labels = chartData.map(d => d.label);
    streamChart.data.datasets[0].data = chartData.map(d => d.watts);
    streamChart.data.datasets[1].data = chartData.map(d => d.cadence);
    streamChart.data.datasets[2].data = chartData.map(d => d.trigger);
    streamChart.update('none');
}

async function pollStreamData() {
    try {
        const response = await fetch('/api/stream-data');
        const data = await response.json();

        const watts = data.watts || 0;
        const cadence = data.cadence || 0;
        const max_target_watts = 300;
        const trigger_value = Math.round((Math.min(watts, max_target_watts) / max_target_watts) * 255);

        const updateEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

        updateEl('stream-power', Math.round(watts));
        updateEl('stream-cadence', Math.round(cadence));
        updateEl('stream-trigger', trigger_value);
        updateEl('play-power', Math.round(watts));
        updateEl('play-cadence', Math.round(cadence));
        updateEl('play-trigger', trigger_value);

        if (document.getElementById('enable-debug')?.checked) {
            updateChart(watts, cadence, trigger_value);
        }
    } catch (error) {
        console.error('Error polling stream data:', error);
    }
}

async function pollStreamLog() {
    const debugEnabled = document.getElementById('enable-debug')?.checked;
    if (!debugEnabled) return;

    try {
        const response = await fetch('/api/stream-log', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const entries = await response.json();
        const container = document.getElementById('stream-log-container');

        if (!entries || entries.length === 0) {
            container.innerHTML = '<p class="stream-log-empty">No messages yet. Start streaming to see data.</p>';
            return;
        }

        let html = '';
        entries.slice(-50).reverse().forEach(entry => {
            const t = new Date(entry.time * 1000);
            const timeStr = t.toLocaleTimeString();
            html += `<div class="stream-log-entry">
                <span class="log-time">${timeStr}</span>
                <span class="log-watts">${entry.watts}W</span>
                <span class="log-cadence">${entry.cadence} RPM</span>
                <span class="log-trigger">${Math.round((Math.min(entry.watts, 300) / 300) * 255)}/255</span>
            </div>`;
        });
        container.innerHTML = html;
    } catch (error) {
        console.error('Error polling stream log:', error);
    }
}

function startStreamDataPolling() {
    // Poll every 200ms for smooth updates
    streamDataInterval = setInterval(pollStreamData, 200);
    // Poll log every 1s
    streamLogInterval = setInterval(pollStreamLog, 1000);
    // Check status every 5s while streaming
    statusPollInterval = setInterval(refreshStreamStatus, 5000);
    // Do an initial poll right away
    pollStreamData();
    pollStreamLog();
}

function stopStreamDataPolling() {
    if (streamDataInterval) {
        clearInterval(streamDataInterval);
        streamDataInterval = null;
    }
    if (streamLogInterval) {
        clearInterval(streamLogInterval);
        streamLogInterval = null;
    }
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
    }
    // Reset display
    document.getElementById('stream-power').textContent = '0';
    document.getElementById('stream-cadence').textContent = '0';
    document.getElementById('stream-trigger').textContent = '0';
    document.getElementById('stream-log-container').innerHTML = '<p class="stream-log-empty">No messages yet. Start streaming to see data.</p>';
    // Reset chart
    chartData = [];
    if (streamChart) {
        streamChart.data.labels = [];
        streamChart.data.datasets.forEach(ds => ds.data = []);
        streamChart.update('none');
    }
}

// (Removed duplicate overrides and global click handler)

// Virtual Joystick (reusable factory)
function createJoystick(baseId, thumbId, xDisplayId, yDisplayId) {
    const base = document.getElementById(baseId);
    const thumb = document.getElementById(thumbId);
    const joyX = document.getElementById(xDisplayId);
    const joyY = document.getElementById(yDisplayId);

    if (!base || !thumb) return null;

    let RADIUS = 0;
    let active = false;
    let currentX = 0, currentY = 0;
    let lastSend = 0;
    const THROTTLE_MS = 30;

    function getRadius() {
        if (RADIUS > 0) return RADIUS;
        RADIUS = (base.offsetWidth / 2) - (thumb.offsetWidth / 2);
        if (RADIUS <= 0) RADIUS = (200 / 2) - (70 / 2);
        return RADIUS;
    }

    function coordsFromEvent(e) {
        const rect = base.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        return { dx: clientX - cx, dy: clientY - cy };
    }

    function updateThumb(dx, dy) {
        const r = getRadius();
        const dist = Math.sqrt(dx * dx + dy * dy);
        let clampedX = dx, clampedY = dy;
        if (dist > r) {
            clampedX = (dx / dist) * r;
            clampedY = (dy / dist) * r;
        }
        thumb.style.transform = `translate(calc(-50% + ${clampedX}px), calc(-50% + ${clampedY}px))`;
        currentX = +(clampedX / r).toFixed(2);
        currentY = +(clampedY / r).toFixed(2);
        if (joyX) joyX.textContent = currentX.toFixed(2);
        if (joyY) joyY.textContent = currentY.toFixed(2);
    }

    function sendPosition(force) {
        const now = Date.now();
        if (!force && now - lastSend < THROTTLE_MS) return;
        lastSend = now;
        fetch('/api/joystick', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x: currentX, y: currentY }),
        }).catch(() => {});
    }

    function resetJoystick() {
        active = false;
        thumb.style.transform = 'translate(-50%, -50%)';
        currentX = 0;
        currentY = 0;
        if (joyX) joyX.textContent = '0.00';
        if (joyY) joyY.textContent = '0.00';
        sendPosition(true);
    }

    function onStart(e) {
        e.preventDefault();
        active = true;
        const { dx, dy } = coordsFromEvent(e);
        updateThumb(dx, dy);
        sendPosition();
    }

    function onMove(e) {
        if (!active) return;
        const { dx, dy } = coordsFromEvent(e);
        updateThumb(dx, dy);
        sendPosition();
    }

    function onEnd(e) {
        if (!active) return;
        resetJoystick();
    }

    base.addEventListener('mousedown', onStart);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onEnd);
    base.addEventListener('touchstart', onStart, { passive: false });
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onEnd, { passive: false });
    document.addEventListener('touchcancel', onEnd, { passive: false });

    return { reset: resetJoystick };
}

// Initialize both joysticks on load
let steerJoystick = null;
let playJoystick = null;
document.addEventListener('DOMContentLoaded', () => {
    steerJoystick = createJoystick('joystick-base', 'joystick-thumb', 'joy-x', 'joy-y');
    playJoystick = createJoystick('play-joystick-base', 'play-joystick-thumb', 'play-joy-x', 'play-joy-y');
});

// Virtual Buttons
function sendButton(btn, pressed) {
    fetch('/api/button', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ button: btn, pressed }),
    }).catch(() => {});
}

(function () {
    document.querySelectorAll('[data-btn]').forEach(el => {
        const btn = el.getAttribute('data-btn');
        el.addEventListener('mousedown', e => { e.preventDefault(); sendButton(btn, true); });
        el.addEventListener('mouseup', e => { e.preventDefault(); sendButton(btn, false); });
        el.addEventListener('mouseleave', e => { sendButton(btn, false); });
        el.addEventListener('touchstart', e => { e.preventDefault(); sendButton(btn, true); }, { passive: false });
        el.addEventListener('touchend', e => { e.preventDefault(); sendButton(btn, false); }, { passive: false });
        el.addEventListener('touchcancel', e => { sendButton(btn, false); });
    });
})();

// Controller Passthrough
async function refreshPassthroughStatus() {
    try {
        const [statusRes, debugRes] = await Promise.all([
            fetch('/api/passthrough/status'),
            fetch('/api/passthrough/debug'),
        ]);
        const status = await statusRes.json();
        const debug = await debugRes.json();
        const statusEl = document.getElementById('passthrough-status');
        const deviceEl = document.getElementById('passthrough-device');
        const startBtn = document.getElementById('passthrough-start-btn');
        const stopBtn = document.getElementById('passthrough-stop-btn');
        const debugRow = document.getElementById('passthrough-debug-row');
        const eventsEl = document.getElementById('passthrough-events');
        const debugJson = document.getElementById('passthrough-debug-json');

        if (status.active) {
            statusEl.textContent = '✓ Active';
            statusEl.className = 'status-value status-ok';
            deviceEl.textContent = status.device_name || status.source || 'Unknown';
            deviceEl.className = 'status-value';
            startBtn.disabled = true;
            stopBtn.disabled = false;

            debugRow.style.display = 'flex';
            eventsEl.textContent = debug.total_events || 0;
            const topEvents = Object.entries(debug.event_counts || {}).slice(0, 15)
                .map(([k, v]) => `${k}: ${v}`).join('\n');
            debugJson.textContent = topEvents || 'No events yet (only active in Gaming Mode)';
        } else {
            statusEl.textContent = '✗ Inactive';
            statusEl.className = 'status-value status-err';
            deviceEl.textContent = 'Not started';
            deviceEl.className = 'status-value status-muted';
            startBtn.disabled = false;
            stopBtn.disabled = true;
            debugRow.style.display = 'none';
            debugJson.textContent = 'Waiting for data...';
        }
    } catch (e) {
        console.error('Error refreshing passthrough status:', e);
    }
}

async function startPassthrough() {
    const startBtn = document.getElementById('passthrough-start-btn');
    const msgEl = document.getElementById('passthrough-message');
    startBtn.disabled = true;
    msgEl.className = 'message';

    try {
        const res = await fetch('/api/passthrough/start', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'started' || data.status === 'already_active') {
            showMessage('passthrough-message', 'Passthrough started — Steam Deck inputs are now forwarded through the Trainer pad', 'success');
        } else {
            showMessage('passthrough-message', data.message || 'Failed to start passthrough', 'error');
        }
        refreshPassthroughStatus();
    } catch (e) {
        showMessage('passthrough-message', 'Error: ' + e.message, 'error');
        startBtn.disabled = false;
    }
}

async function stopPassthrough() {
    const stopBtn = document.getElementById('passthrough-stop-btn');
    const msgEl = document.getElementById('passthrough-message');
    stopBtn.disabled = true;
    msgEl.className = 'message';

    try {
        const res = await fetch('/api/passthrough/stop', { method: 'POST' });
        const data = await res.json();
        showMessage('passthrough-message', 'Passthrough stopped', 'success');
        refreshPassthroughStatus();
    } catch (e) {
        showMessage('passthrough-message', 'Error: ' + e.message, 'error');
        stopBtn.disabled = false;
    }
}

// Merge Tab — External Bluetooth Controller Merge
let _mergeDevice = '';

async function scanMergeDevices() {
    const listEl = document.getElementById('merge-devices-list');
    listEl.innerHTML = '<p style="color:#888;">Scanning...</p>';
    try {
        const res = await fetch('/api/merge/devices');
        const data = await res.json();
        if (!data.devices || data.devices.length === 0) {
            listEl.innerHTML = '<p style="color:#888;">No gamepad devices found. Pair a Bluetooth controller first.</p>';
            return;
        }
        let html = '<div style="display:flex;flex-direction:column;gap:6px;">';
        data.devices.forEach(dev => {
            const path = dev.path;
            const selected = _mergeDevice === path ? 'checked' : '';
            const isSteamVirtual = dev.vendor === '0x28de' && dev.product === '0x11ff';
            const infoParts = [];
            if (dev.phys) infoParts.push(`phys: ${dev.phys}`);
            if (dev.uniq) infoParts.push(`uniq: ${dev.uniq}`);
            infoParts.push(`${dev.vendor}:${dev.product}`);
            const info = infoParts.join(' | ');
            html += '<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:' + (isSteamVirtual ? '#1a1a2e' : '#1e1e2e') + ';border-radius:6px;border:1px solid ' + (isSteamVirtual ? '#2a2a3e' : '#333') + ';">';
            html += `<input type="radio" name="merge-device" value="${path}" ${selected} onchange="_mergeDevice=this.value" style="flex-shrink:0;">`;
            html += `<div style="flex:1;min-width:0;">`;
            html += `<div style="font-weight:600;display:flex;gap:8px;align-items:center;">`;
            html += `<span>${dev.name}</span>`;
            if (isSteamVirtual) {
                html += `<span style="color:#666;font-size:0.65em;background:#2a2a3e;padding:2px 8px;border-radius:4px;white-space:nowrap;">Steam virtual</span>`;
            }
            html += `</div>`;
            html += `<div style="color:#888;font-size:0.7em;word-break:break-all;margin-top:2px;">${path}</div>`;
            html += `<div style="color:#666;font-size:0.7em;word-break:break-all;margin-top:1px;">${info}</div>`;
            html += `</div>`;
            html += `<button class="btn-small btn-secondary" style="flex-shrink:0;padding:4px 10px;font-size:0.7em;" onclick="detectMergeDevice('${path}', this)">Detect</button>`;
            html += '</div>';
        });
        html += '</div>';
        listEl.innerHTML = html;
    } catch (e) {
        listEl.innerHTML = `<p style="color:#f56565;">Error: ${e.message}</p>`;
    }
}

async function detectMergeDevice(path, btn) {
    const origText = btn.textContent;
    btn.textContent = 'Watching...';
    btn.disabled = true;
    try {
        const res = await fetch('/api/merge/probe?source_path=' + encodeURIComponent(path), { method: 'POST' });
        const data = await res.json();
        if (data.detected && data.events.length > 0) {
            const ev = data.events.slice(0, 3).map(e => `${e.code}=${e.value}`).join(', ');
            btn.textContent = `✅ ${data.events.length} events`;
            btn.style.background = '#38a169';
            btn.style.color = '#fff';
        } else {
            btn.textContent = '❌ No activity';
            btn.style.background = '#e53e3e';
            btn.style.color = '#fff';
        }
    } catch (e) {
        btn.textContent = '❌ Error';
        btn.style.background = '#e53e3e';
        btn.style.color = '#fff';
    }
    setTimeout(() => {
        btn.textContent = origText;
        btn.disabled = false;
        btn.style.background = '';
        btn.style.color = '';
    }, 3000);
}

async function refreshMergeStatus() {
    try {
        const [statusRes, configRes] = await Promise.all([
            fetch('/api/merge/status'),
            fetch('/api/config'),
        ]);
        const data = await statusRes.json();
        const config = await configRes.json();
        const statusEl = document.getElementById('merge-status');
        const startBtn = document.getElementById('merge-start-btn');
        const stopBtn = document.getElementById('merge-stop-btn');
        const autoBadge = document.getElementById('merge-auto-badge');

        const autoPath = config.auto_merge_device || '';

        if (data.active) {
            statusEl.innerHTML = `<span class="status-badge connected">Active</span> &mdash; ${data.device_name || data.source}`;
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusEl.innerHTML = '<span class="status-badge idle">Inactive</span>';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }

        if (autoPath) {
            autoBadge.style.display = 'inline';
            autoBadge.title = `Auto-merge: ${autoPath}`;
        } else {
            autoBadge.style.display = 'none';
        }
    } catch (e) {
        console.error('Error refreshing merge status:', e);
    }
}

async function startMerge() {
    if (!_mergeDevice) {
        alert('Select a controller from the scan list first.');
        return;
    }
    const startBtn = document.getElementById('merge-start-btn');
    startBtn.disabled = true;
    try {
        const res = await fetch('/api/merge/start?source_path=' + encodeURIComponent(_mergeDevice), { method: 'POST' });
        const data = await res.json();
        if (data.status === 'started' || data.status === 'already_active') {
            refreshMergeStatus();
        } else {
            alert(data.message || 'Failed to start merge');
            startBtn.disabled = false;
        }
    } catch (e) {
        alert('Error: ' + e.message);
        startBtn.disabled = false;
    }
}

async function stopMerge() {
    const stopBtn = document.getElementById('merge-stop-btn');
    stopBtn.disabled = true;
    try {
        await fetch('/api/merge/stop', { method: 'POST' });
        refreshMergeStatus();
    } catch (e) {
        alert('Error: ' + e.message);
        stopBtn.disabled = false;
    }
}

async function saveAutoMerge() {
    if (!_mergeDevice) {
        alert('Select a controller from the scan list first.');
        return;
    }
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_merge_device: _mergeDevice }),
        });
        const data = await res.json();
        if (data.auto_merge_device) {
            alert(`Auto-merge saved: ${_mergeDevice}\nRestart server to apply.`);
            refreshMergeStatus();
        } else {
            alert('Failed to save auto-merge config');
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// Commands Tab — TDF Official Controls
const COMMANDS = [
    { section: "Normal Race", items: [
        { label: "L-Stick", desc: "Turn — steer left/right", action: "steer", chip: "L-STICK" },
        { label: "RT", desc: "Pedal — hold longer = stronger effort", chip: "RT" },
        { label: "LT", desc: "Brake — hold longer = harder braking", chip: "LT" },
        { label: "A", desc: "Attack / Sprint — press repeatedly", buttons: ["btn_a"], chip: "A", cls: "a" },
        { label: "A (hold)", desc: "Sustained effort — hold for max power", buttons: ["btn_a"], hold: true, chip: "A", cls: "a" },
        { label: "X (hold)", desc: "Follow another rider — hold to stay close", buttons: ["btn_x"], hold: true, chip: "X", cls: "x" },
        { label: "Y", desc: "Take a feed — hold to consume, tap to choose", buttons: ["btn_y"], chip: "Y", cls: "y" },
        { label: "B", desc: "Team Comm — open team command menu", buttons: ["btn_b"], chip: "B", cls: "b" },
        { label: "RB", desc: "Aero position downhill / Bike launch at sprint", buttons: ["btn_rb"], chip: "RB", cls: "rb" },
        { label: "X", desc: "Force regulator — then LB/RB to adjust", buttons: ["btn_x"], chip: "X", cls: "x" },
        { label: "D-pad →", desc: "Race info — cycle through standings", action: "dpad_right", chip: "→", cls: "dpad" },
        { label: "R3", desc: "Camera — cycle close-up/aerial/first-person", buttons: ["btn_r3"], chip: "R3", cls: "r3" },
    ]},
    { section: "Criterium Combos \u2014 press both together", items: [
        { label: "LB + \u2191", desc: "Ask for relays", combo: ["btn_lb", "dpad_up"], chip: "LB+\u2191", cls: "combo" },
        { label: "LB + \u2190", desc: "Ask for reduction in tempo", combo: ["btn_lb", "dpad_left"], chip: "LB+\u2190", cls: "combo" },
        { label: "LB + \u2193", desc: "Indicate waiting", combo: ["btn_lb", "dpad_down"], chip: "LB+\u2193", cls: "combo" },
        { label: "LB + A", desc: "Pretend to attack", combo: ["btn_lb", "btn_a"], chip: "LB+A", cls: "combo" },
        { label: "LB + Y", desc: "Pretend to take a feed", combo: ["btn_lb", "btn_y"], chip: "LB+Y", cls: "combo" },
        { label: "LB + B", desc: "Pretend to give instructions", combo: ["btn_lb", "btn_b"], chip: "LB+B", cls: "combo" },
        { label: "LB + RB", desc: "Pretend to be at full speed", combo: ["btn_lb", "btn_rb"], chip: "LB+RB", cls: "combo" },
    ]},
    { section: "Time Trial", items: [
        { label: "L-Stick", desc: "Turn", action: "steer", chip: "L-STICK" },
        { label: "RT", desc: "Pedal — hold for stronger effort", chip: "RT" },
        { label: "LT", desc: "Brake — hold for harder braking", chip: "LT" },
        { label: "A", desc: "Step on the pedal (attack)", buttons: ["btn_a"], chip: "A", cls: "a" },
        { label: "X (hold)", desc: "Time-trial position — reduce drag", buttons: ["btn_x"], hold: true, chip: "X", cls: "x" },
        { label: "B", desc: "Pass lead to teammate (team TT)", buttons: ["btn_b"], chip: "B", cls: "b" },
        { label: "B", desc: "Team Comm — give instructions (team TT)", buttons: ["btn_b"], chip: "B", cls: "b" },
        { label: "D-pad →", desc: "Intermediate times — cycle standings", action: "dpad_right", chip: "→", cls: "dpad" },
    ]},
];

const CHIP_CLS = {
    a: "cmd-chip-a", b: "cmd-chip-b", x: "cmd-chip-x", y: "cmd-chip-y",
    lb: "cmd-chip-lb", rb: "cmd-chip-rb", l3: "cmd-chip-l3", r3: "cmd-chip-r3",
    select: "cmd-chip-select", start: "cmd-chip-start", guide: "cmd-chip-guide",
    dpad: "cmd-chip-dpad", rt: "cmd-chip-rt", lt: "cmd-chip-lt",
    combo: "cmd-chip-combo",
};

function cmdChip(text, cls) {
    const c = document.createElement("span");
    c.className = "cmd-chip " + (CHIP_CLS[cls] || "cmd-chip-dpad");
    c.textContent = text;
    return c;
}

function renderCommands() {
    const root = document.getElementById("commands-root");
    if (!root) return;

    COMMANDS.forEach(group => {
        const sec = document.createElement("div");
        sec.className = "cmd-section";

        const title = document.createElement("div");
        title.className = "cmd-section-title";
        title.textContent = group.section;
        sec.appendChild(title);

        group.items.forEach(item => {
            const row = document.createElement("div");
            row.className = "cmd-item";

            const badge = document.createElement("div");
            badge.className = "cmd-badge";

            if (item.combo) {
                // Multi-button combo
                item.combo.forEach((c, i) => {
                    if (i > 0) {
                        const plus = document.createElement("span");
                        plus.textContent = "+";
                        plus.style.cssText = "color:#888;font-size:0.75em;font-weight:700;margin:0 1px;";
                        badge.appendChild(plus);
                    }
                    const isBtn = c.startsWith("btn_");
                    const short = isBtn ? c.replace("btn_", "").toUpperCase() : c.replace("dpad_", "").toUpperCase();
                    const cls = isBtn ? c.replace("btn_", "") : "dpad";
                    badge.appendChild(cmdChip(short, cls));
                });
            } else if (item.buttons) {
                // Single button
                const short = item.buttons[0].replace("btn_", "").toUpperCase();
                const cls = item.buttons[0].replace("btn_", "");
                badge.appendChild(cmdChip(short, cls));
                if (item.hold) {
                    const hl = document.createElement("span");
                    hl.textContent = "(hold)";
                    hl.style.cssText = "font-size:0.6em;color:#888;margin-left:2px;";
                    badge.appendChild(hl);
                }
            } else {
                // Axis / steer / trigger
                badge.appendChild(cmdChip(item.chip || item.label, "dpad"));
            }

            row.appendChild(badge);

            const desc = document.createElement("span");
            desc.className = "cmd-desc";
            desc.textContent = item.desc;
            row.appendChild(desc);

            // Event handlers
            if (item.combo) {
                row.addEventListener("mousedown", e => { e.preventDefault(); execCombo(item.combo, true); });
                row.addEventListener("mouseup", e => { e.preventDefault(); execCombo(item.combo, false); });
                row.addEventListener("mouseleave", () => execCombo(item.combo, false));
                row.addEventListener("touchstart", e => { e.preventDefault(); execCombo(item.combo, true); }, { passive: false });
                row.addEventListener("touchend", e => { e.preventDefault(); execCombo(item.combo, false); }, { passive: false });
                row.addEventListener("touchcancel", () => execCombo(item.combo, false));
            } else if (item.buttons) {
                row.addEventListener("mousedown", e => { e.preventDefault(); sendButton(item.buttons[0], true); });
                row.addEventListener("mouseup", e => { e.preventDefault(); sendButton(item.buttons[0], false); });
                row.addEventListener("mouseleave", () => sendButton(item.buttons[0], false));
                row.addEventListener("touchstart", e => { e.preventDefault(); sendButton(item.buttons[0], true); }, { passive: false });
                row.addEventListener("touchend", e => { e.preventDefault(); sendButton(item.buttons[0], false); }, { passive: false });
                row.addEventListener("touchcancel", () => sendButton(item.buttons[0], false));
            } else if (item.action === "dpad_right") {
                row.addEventListener("mousedown", e => { e.preventDefault(); setDpad("right", true); });
                row.addEventListener("mouseup", e => { e.preventDefault(); setDpad("right", false); });
                row.addEventListener("mouseleave", () => setDpad("right", false));
                row.addEventListener("touchstart", e => { e.preventDefault(); setDpad("right", true); }, { passive: false });
                row.addEventListener("touchend", e => { e.preventDefault(); setDpad("right", false); }, { passive: false });
                row.addEventListener("touchcancel", () => setDpad("right", false));
            }

            sec.appendChild(row);
        });

        root.appendChild(sec);
    });
}

function execCombo(actions, pressed) {
    actions.forEach(a => {
        if (a.startsWith("btn_")) {
            sendButton(a, pressed);
        } else if (a.startsWith("dpad_")) {
            setDpad(a.replace("dpad_", ""), pressed);
        }
    });
}

// Render commands on page load
document.addEventListener("DOMContentLoaded", renderCommands);

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    try { refreshStatusTab(); } catch (e) {}
    try { statusTabInterval = setInterval(refreshStatusTab, 3000); } catch (e) {}
    try { loadConfig(); } catch (e) {}
    try { initChart(); } catch (e) {}
    try {
        refreshStreamStatus().then(() => {
            const statusIndicator = document.getElementById('stream-status-indicator');
            if (statusIndicator && statusIndicator.textContent.includes('Streaming')) {
                startStreamDataPolling();
            }
        });
    } catch (e) {}
    try { refreshPassthroughStatus(); } catch (e) {}
    try { setInterval(refreshPassthroughStatus, 3000); } catch (e) {}
});

// Register service worker for PWA support
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js').catch(() => {});
    });
}
