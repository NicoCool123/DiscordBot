/**
 * Main application JavaScript
 * Alpine.js store for toasts + bot status checker + utility functions
 */

// Register Alpine.js stores before Alpine initializes
document.addEventListener('alpine:init', () => {
    Alpine.store('toasts', {
        list: [],
        nextId: 0,
        add(detail) {
            const id = this.nextId++;
            this.list.push({ id, message: detail.message, type: detail.type || 'info' });
            setTimeout(() => this.remove(id), 4000);
        },
        remove(id) {
            this.list = this.list.filter(t => t.id !== id);
        }
    });
});

// Initialize bot status checker
document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname.startsWith('/login') ||
        window.location.pathname.startsWith('/register')) {
        return;
    }

    checkBotStatus();
    setInterval(checkBotStatus, 30000);
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
        indicator.className = 'status-dot-online';
        statusText.textContent = latencyMs != null ? `${Number(latencyMs).toFixed(0)}ms` : 'Online';
        statusText.className = 'text-xs font-medium text-[#23a559]';
    } else {
        indicator.className = 'status-dot-offline';
        statusText.textContent = 'Offline';
        statusText.className = 'text-xs font-medium text-[#64748b]';
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
    if (num == null) return '-';
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
    if (seconds == null) return '-';
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
 * Show a toast notification via Alpine store or DOM fallback
 */
function showToast(message, type = 'info') {
    window.dispatchEvent(new CustomEvent('toast', { detail: { message, type } }));
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Get color for progress bars based on percentage
 */
function getBarColor(percent) {
    if (percent >= 80) return '#f23f43';
    if (percent >= 60) return '#f0b232';
    return '#23a559';
}

// Export utilities
window.formatNumber = formatNumber;
window.formatBytes = formatBytes;
window.formatDuration = formatDuration;
window.showToast = showToast;
window.escapeHtml = escapeHtml;
window.getBarColor = getBarColor;
