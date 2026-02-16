const API = "http://localhost:8000";

const Auth = {
    _userCache: null,

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
            const response = await fetch(`${API}/api/v1/auth/refresh`, {
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
            this._userCache = null;
            window.dispatchEvent(new CustomEvent('auth:refreshed'));
            return true;
        } catch {
            this.logout();
            return false;
        }
    },
    async logout() {
        try {
            const token = this.getToken();
            if (token) {
                await fetch(`${API}/api/v1/auth/logout`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                });
            }
        } catch {}
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        this._userCache = null;
        window.dispatchEvent(new CustomEvent('auth:logout'));
        window.location.href = '/login';
    },
    async fetch(url, options = {}) {
        if (!this.isAuthenticated()) {
            const refreshed = await this.refreshToken();
            if (!refreshed) throw new Error('Authentication required');
        }
        const token = this.getToken();
        const headers = { ...options.headers, 'Authorization': `Bearer ${token}` };
        const response = await fetch(`${API}${url}`, { ...options, headers });
        if (response.status === 401) {
            const refreshed = await this.refreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${this.getToken()}`;
                return fetch(`${API}${url}`, { ...options, headers });
            }
            this.logout();
        }
        return response;
    },
    async getUser() {
        if (this._userCache) return this._userCache;
        try {
            const res = await this.fetch('/api/v1/auth/me');
            if (res.ok) {
                this._userCache = await res.json();
                return this._userCache;
            }
        } catch {}
        return null;
    }
};

document.addEventListener('DOMContentLoaded', async () => {
    const path = window.location.pathname;
    if (!path.startsWith('/login') && !path.startsWith('/register') && path !== '/') {
        if (!Auth.isAuthenticated()) {
            const success = await Auth.refreshToken();
            if (!success) window.location.href = '/login';
        }
    }
});

window.Auth = Auth;