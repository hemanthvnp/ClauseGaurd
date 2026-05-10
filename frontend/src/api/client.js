import axios from 'axios';

const _base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

const api = axios.create({
  baseURL: `${_base}/api/v1`,
});

api.interceptors.request.use((config) => {
  const token = window.localStorage.getItem('clauseguard_access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Automatic token refresh on 401
let isRefreshing = false;
let waitQueue = [];

function flushQueue(error, token = null) {
  waitQueue.forEach((cb) => (error ? cb.reject(error) : cb.resolve(token)));
  waitQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }

    const refreshToken = window.localStorage.getItem('clauseguard_refresh_token');
    if (!refreshToken) {
      window.localStorage.removeItem('clauseguard_access_token');
      window.location.href = '/login';
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        waitQueue.push({ resolve, reject });
      }).then((token) => {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      });
    }

    original._retry = true;
    isRefreshing = true;

    try {
      const { data } = await axios.post(`${_base}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      });
      window.localStorage.setItem('clauseguard_access_token', data.access_token);
      if (data.refresh_token) {
        window.localStorage.setItem('clauseguard_refresh_token', data.refresh_token);
      }
      api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
      flushQueue(null, data.access_token);
      original.headers.Authorization = `Bearer ${data.access_token}`;
      return api(original);
    } catch (refreshError) {
      flushQueue(refreshError);
      window.localStorage.removeItem('clauseguard_access_token');
      window.localStorage.removeItem('clauseguard_refresh_token');
      window.location.href = '/login';
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;
