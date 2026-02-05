/**
 * WebSocket utilities for real-time updates
 */

class WebSocketManager {
    constructor() {
        this.connections = new Map();
        this.reconnectAttempts = new Map();
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
    }

    /**
     * Connect to a WebSocket endpoint
     */
    connect(channel, options = {}) {
        if (this.connections.has(channel)) {
            return this.connections.get(channel);
        }

        const token = localStorage.getItem('access_token');
        const baseUrl = `ws://${window.location.host}/ws`;
        const url = `${baseUrl}/${channel}?token=${token}`;

        const ws = new WebSocket(url);

        ws.onopen = () => {
            console.log(`WebSocket connected: ${channel}`);
            this.reconnectAttempts.set(channel, 0);
            if (options.onOpen) options.onOpen();
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (options.onMessage) options.onMessage(data);
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        ws.onclose = (event) => {
            console.log(`WebSocket closed: ${channel}`, event.code);
            this.connections.delete(channel);

            if (options.onClose) options.onClose(event);

            // Attempt reconnect if not intentional close
            if (event.code !== 1000 && event.code !== 4001) {
                this.attemptReconnect(channel, options);
            }
        };

        ws.onerror = (error) => {
            console.error(`WebSocket error: ${channel}`, error);
            if (options.onError) options.onError(error);
        };

        this.connections.set(channel, ws);
        return ws;
    }

    /**
     * Attempt to reconnect to a WebSocket
     */
    attemptReconnect(channel, options) {
        const attempts = this.reconnectAttempts.get(channel) || 0;

        if (attempts >= this.maxReconnectAttempts) {
            console.log(`Max reconnect attempts reached for ${channel}`);
            return;
        }

        const delay = this.reconnectDelay * Math.pow(2, attempts);
        console.log(`Reconnecting to ${channel} in ${delay}ms (attempt ${attempts + 1})`);

        setTimeout(() => {
            this.reconnectAttempts.set(channel, attempts + 1);
            this.connect(channel, options);
        }, delay);
    }

    /**
     * Send a message through a WebSocket
     */
    send(channel, message) {
        const ws = this.connections.get(channel);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(message));
            return true;
        }
        return false;
    }

    /**
     * Close a WebSocket connection
     */
    close(channel) {
        const ws = this.connections.get(channel);
        if (ws) {
            ws.close(1000);
            this.connections.delete(channel);
        }
    }

    /**
     * Close all WebSocket connections
     */
    closeAll() {
        for (const [channel] of this.connections) {
            this.close(channel);
        }
    }

    /**
     * Check if connected to a channel
     */
    isConnected(channel) {
        const ws = this.connections.get(channel);
        return ws && ws.readyState === WebSocket.OPEN;
    }
}

// Global WebSocket manager instance
window.wsManager = new WebSocketManager();

// Close connections when leaving page
window.addEventListener('beforeunload', () => {
    window.wsManager.closeAll();
});
