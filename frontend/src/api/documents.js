import api from './client';

export const authApi = {
  register: (payload) => api.post('/auth/register', payload),
  login: (payload) => api.post('/auth/login', payload),
  refresh: (payload) => api.post('/auth/refresh', payload),
  me: () => api.get('/auth/me'),
};

export const demoApi = {
  bootstrap: () => api.get('/demo/bootstrap'),
};

export const documentsApi = {
  upload: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  list: (skip = 0, limit = 50) => api.get('/documents/', { params: { skip, limit } }),
  get: (id) => api.get(`/documents/${id}`),
  clauses: (id) => api.get(`/documents/${id}/clauses`),
  status: (id) => api.get(`/documents/${id}/status`),
  downloadBlob: (id) => api.get(`/documents/${id}/download`, { responseType: 'blob' }),
  remove: (id) => api.delete(`/documents/${id}`),
};

export const compareApi = {
  create: (payload) => api.post('/compare', payload),
  get: (id) => api.get(`/compare/${id}`),
};

export const signApi = {
  sign: (documentId, payload) => api.post(`/sign/${documentId}`, payload),
  downloadBlob: (documentId) => api.get(`/sign/${documentId}/download`, { responseType: 'blob' }),
};

export const extensionApi = {
  analyzeText: (payload) => api.post('/extension/analyze-text', payload),
};

export const chatApi = {
  ask: (documentId, payload) => api.post(`/chat/${documentId}`, payload),
};

export const negotiateApi = {
  suggest: (documentId, clauseId) =>
    api.post(`/negotiate/${documentId}`, { clause_id: clauseId }),
};

export const obligationsApi = {
  get: (documentId) => api.get(`/obligations/${documentId}`),
};
