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
├─ Cycling Power: ${mapping.cycling_power}W
├─ Button A: ${mapping.button_a ? '✓ Active' : '✗ Inactive'}
├─ Button B: ${mapping.button_b ? '✓ Active' : '✗ Inactive'}
├─ Gear: ${mapping.gear}
└─ Mode: ${mapping.mode.toUpperCase()}
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
✓ <strong>Trainer Connected!</strong>
Device: ${data.device_name || 'Unknown'}
Power: ${data.power || 'N/A'}W
            `;
            document.getElementById('connection-test').innerHTML = '<span class="status-badge connected">✓ Connected</span>';
        } else {
            messageDiv.innerHTML = `
✗ <strong>Trainer Not Connected</strong>
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkStatus();
    loadConfig();
});
