// Tab Navigation
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const tabName = e.target.getAttribute('data-tab');
        switchTab(tabName);
    });
});

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Deactivate all buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName).classList.add('active');

    // Activate selected button
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Load config when switching to config tab
    if (tabName === 'config') {
        loadConfig();
    }
}

// Configuration Management
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        document.getElementById('tacx-mac').value = config.tacx_mac_address || '';
        document.getElementById('max-watts').value = config.max_target_watts || 300;
        document.getElementById('cadence-threshold').value = config.cadence_threshold || 95;
        document.getElementById('power-race').value = config.power_threshold_race || 150;
        document.getElementById('power-button-a').value = config.power_threshold_button_a || 250;
        document.getElementById('gear-multiplier').value = config.gear_multiplier || 2.0;
    } catch (error) {
        console.error('Error loading config:', error);
        showMessage('config-message', 'Error loading configuration', 'error');
    }
}

document.getElementById('config-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const config = {
        tacx_mac_address: formData.get('tacx_mac_address'),
        max_target_watts: parseFloat(formData.get('max_target_watts')),
        cadence_threshold: parseFloat(formData.get('cadence_threshold')),
        power_threshold_race: parseFloat(formData.get('power_threshold_race')),
        power_threshold_button_a: parseFloat(formData.get('power_threshold_button_a')),
        gear_multiplier: parseFloat(formData.get('gear_multiplier')),
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

// Status Check
async function checkStatus() {
    try {
        const response = await fetch('/');
        const data = await response.json();
        document.getElementById('service-status').textContent = data.status === 'ok' ? '✓ Running' : '✗ Error';
    } catch (error) {
        document.getElementById('service-status').textContent = '✗ Unreachable';
    }
}

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
        btnText.textContent = 'Test Tacx Connection';
    }
}

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
async function discoverTacxTrainers() {
    const btnElement = document.querySelector('[onclick="discoverTacxTrainers()"]');
    const btnText = document.getElementById('discover-btn-text');
    const listDiv = document.getElementById('discovered-list');

    btnElement.disabled = true;
    btnText.textContent = 'Scanning...';
    listDiv.innerHTML = '<p>Scanning for Tacx trainers... (this may take up to 5 seconds)</p>';

    try {
        const response = await fetch('/api/discover-tacx', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.error) {
            listDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
        } else if (data.found === 0) {
            listDiv.innerHTML = '<p>No Tacx trainers found. Make sure your trainer is powered on and in pairing mode.</p>';
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
        btnText.textContent = 'Scan for Tacx Trainers';
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
    document.getElementById('tacx-mac').value = macAddress;
    
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
            // Auto-start polling if streaming is active but polling isn't running
            if (!streamDataInterval) {
                startStreamDataPolling();
            }
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
let chartUpdateInterval = null;

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
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
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
                        color: '#667eea',
                    },
                    min: 0,
                    max: 150,
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        color: '#667eea',
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
        const response = await fetch('/api/stream-data', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        const watts = data.watts || 0;
        const cadence = data.cadence || 0;
        const max_target_watts = 300;
        const trigger_value = Math.round((Math.min(watts, max_target_watts) / max_target_watts) * 255);

        // Update power display
        document.getElementById('stream-power').textContent = Math.round(watts);
        
        // Update cadence display
        document.getElementById('stream-cadence').textContent = Math.round(cadence);
        
        // Calculate and display controller output (0-255 trigger value)
        document.getElementById('stream-trigger').textContent = trigger_value;

        // Feed chart
        updateChart(watts, cadence, trigger_value);
    } catch (error) {
        console.error('Error polling stream data:', error);
    }
}

async function pollStreamLog() {
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    loadConfig();
    initChart();
    // If streaming is already active, start data polling
    refreshStreamStatus().then(() => {
        const statusIndicator = document.getElementById('stream-status-indicator');
        if (statusIndicator && statusIndicator.textContent.includes('Streaming')) {
            startStreamDataPolling();
        }
    });
    // Keep polling status every 5s to auto-resume on page if streaming starts
    setInterval(() => {
        refreshStreamStatus();
    }, 5000);
});
