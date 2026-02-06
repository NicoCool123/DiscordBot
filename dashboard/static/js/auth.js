const Auth = {
    getToken() {
        return localStorage.getItem('access_token');
    },
    getRefreshToken() {
        return localStorage.getItem('refresh_token');
    },
    isAuthenticated() {
        const token = this.getToken();
        if (!token) return false;
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.exp * 1000 > Date.now();
        } catch {
            return false;
        }
    },
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
            if (!response.ok) {
                this.logout();
                return false;
            }
            const data = await response.json();
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            return true;
        } catch {
            this.logout();
            return false;
        }
    },
    logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
    },
    async fetch(url, options = {}) {
        // Ensure token is valid
        if (!this.isAuthenticated()) {
            const refreshed = await this.refreshToken();
            if (!refreshed) throw new Error('Authentication required');
        }
        const token = this.getToken();
        const headers = { ...options.headers, 'Authorization': `Bearer ${token}` };
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${this.getToken()}`;
                return fetch(url, { ...options, headers });
            }
            this.logout();
        }
        return response;
    }
};

// Check auth on page load
document.addEventListener('DOMContentLoaded', async () => {
    if (!window.location.pathname.startsWith('/login') &&
        !window.location.pathname.startsWith('/register')) {
        if (!Auth.isAuthenticated()) {
            const success = await Auth.refreshToken();
            if (!success) window.location.href = '/login';
        }
    }
});

window.Auth = Auth;