/**
 * Authentication utilities for the dashboard
 */

const Auth = {
    /**
     * Get the access token from localStorage
     */
    getToken() {
        return localStorage.getItem('access_token');
    },

    /**
     * Get the refresh token from localStorage
     */
    getRefreshToken() {
        return localStorage.getItem('refresh_token');
    },

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        const token = this.getToken();
        if (!token) return false;

        // Check if token is expired
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.exp * 1000 > Date.now();
        } catch {
            return false;
        }
    },

    /**
     * Refresh the access token using the refresh token
     */
    async refreshToken() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            this.logout();
            return false;
        }

        try {
            const response = await fetch('/api/v1/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken }),
            });

            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                return true;
            } else {
                this.logout();
                return false;
            }
        } catch {
            this.logout();
            return false;
        }
    },

    /**
     * Logout the user
     */
    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
    },

    /**
     * Make an authenticated API request
     */
    async fetch(url, options = {}) {
        // Check if token needs refresh
        if (!this.isAuthenticated()) {
            const refreshed = await this.refreshToken();
            if (!refreshed) {
                throw new Error('Authentication required');
            }
        }

        const token = this.getToken();
        const headers = {
            ...options.headers,
            'Authorization': `Bearer ${token}`,
        };

        const response = await fetch(url, { ...options, headers });

        // Handle 401 by trying to refresh
        if (response.status === 401) {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                // Retry with new token
                headers['Authorization'] = `Bearer ${this.getToken()}`;
                return fetch(url, { ...options, headers });
            }
        }

        return response;
    },

    /**
     * Get current user info
     */
    async getCurrentUser() {
        try {
            const response = await this.fetch('/api/v1/auth/me');
            if (response.ok) {
                return await response.json();
            }
        } catch {
            // Ignore errors
        }
        return null;
    },
};

// Check authentication on page load (except login page)
document.addEventListener('DOMContentLoaded', () => {
    if (!window.location.pathname.startsWith('/login') &&
        !window.location.pathname.startsWith('/register')) {
        if (!Auth.isAuthenticated()) {
            Auth.refreshToken().then(success => {
                if (!success) {
                    window.location.href = '/login';
                }
            });
        }
    }
});

// Export for use in other scripts
window.Auth = Auth;
