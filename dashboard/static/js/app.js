/**
 * Main application JavaScript
 */

// Initialize bot status checker
document.addEventListener('DOMContentLoaded', () => {
    // Skip on login page
    if (window.location.pathname.startsWith('/login')) {
        return;
    }

    // Check bot status periodically
    checkBotStatus();
    setInterval(checkBotStatus, 30000);

    // Connect to status WebSocket for real-time updates
    connectStatusWebSocket();
});

/**
 * Check bot status via API
 */
async function checkBotStatus() {
    const indicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');

    if (!indicator || !statusText) return;

    try {
        const response = await Auth.fetch('/api/v1/bot/status');
        if (response.ok) {
            const status = await response.json();
            updateStatusDisplay(status.online, status.latency_ms);
        } else {
            updateStatusDisplay(false);
        }
    } catch {
        updateStatusDisplay(false);
    }
}

/**
 * Update the status display in the header
 */
function updateStatusDisplay(online, latencyMs = null) {
    const indicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');

    if (!indicator || !statusText) return;

    if (online) {
        indicator.className = 'w-2 h-2 rounded-full bg-discord-green';
        statusText.textContent = latencyMs ? `Online (${latencyMs.toFixed(0)}ms)` : 'Online';
    } else {
        indicator.className = 'w-2 h-2 rounded-full bg-discord-red';
        statusText.textContent = 'Offline';
    }
}

/**
 * Connect to status WebSocket for real-time updates
 */
function connectStatusWebSocket() {
    window.wsManager.connect('status', {
        onMessage: (data) => {
            if (data.type === 'status') {
                updateStatusDisplay(data.data.online, data.data.latency_ms);
            }
        },
        onClose: () => {
            updateStatusDisplay(false);
        }
    });
}

/**
 * Format a number with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format bytes to human readable
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
}

/**
 * Format duration in seconds to human readable
 */
function formatDuration(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);

    return parts.join(' ');
}

/**
 * Show a toast notification
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 transform transition-all duration-300 translate-y-full opacity-0`;

    const colors = {
        success: 'bg-discord-green text-white',
        error: 'bg-discord-red text-white',
        warning: 'bg-discord-yellow text-black',
        info: 'bg-discord-blurple text-white',
    };

    toast.className += ` ${colors[type] || colors.info}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-full', 'opacity-0');
    });

    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.add('translate-y-full', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Export utilities
window.formatNumber = formatNumber;
window.formatBytes = formatBytes;
window.formatDuration = formatDuration;
window.showToast = showToast;
