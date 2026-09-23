const API_BASE_URL = 'http://localhost:8000/api/v1';

export const fetchApi = async (endpoint, options = {}) => {
  const token = localStorage.getItem('token');
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem('token');
    window.dispatchEvent(new Event('auth-error'));
    throw new Error('Unauthorized');
  }

  if (response.status === 403) {
    throw new Error('Forbidden: You do not have permission.');
  }

  if (response.status === 204) {
    return null;
  }

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error?.message || 'API request failed');
  }

  return response.json();
};

export const api = {
  login: (email, password) => 
    fetchApi('/auth/login', { 
      method: 'POST', 
      body: JSON.stringify({ email, password }) 
    }),
    
  listDocuments: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchApi(`/documents/${query ? '?' + query : ''}`);
  },
  
  getDocument: (id) => fetchApi(`/documents/${id}`),
  
  createDocument: (data) => 
    fetchApi('/documents/', { method: 'POST', body: JSON.stringify(data) }),

  uploadDocument: async (formData) => {
    const token = localStorage.getItem('token');
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(`http://localhost:8000/api/v1/documents/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });
    
    if (response.status === 401) {
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('auth-error'));
      throw new Error('Unauthorized');
    }
    if (response.status === 403) {
      throw new Error('Forbidden: You do not have permission.');
    }
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || errData.error?.message || 'API request failed');
    }
    return response.json();
  },
    
  updateDocument: (id, data) => 
    fetchApi(`/documents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    
  deleteDocument: (id) => 
    fetchApi(`/documents/${id}`, { method: 'DELETE' }),

  submitForReview: (versionId, comment = null) =>
    fetchApi(`/workflow/documents/versions/${versionId}/submit`, { method: 'POST', body: JSON.stringify({ comment }) }),

  approveDocument: (versionId, comment = null) =>
    fetchApi(`/workflow/documents/versions/${versionId}/approve`, { method: 'POST', body: JSON.stringify({ comment }) }),

  rejectDocument: (versionId, comment = null) =>
    fetchApi(`/workflow/documents/versions/${versionId}/reject`, { method: 'POST', body: JSON.stringify({ comment }) }),

  publishDocument: (versionId, comment = null) =>
    fetchApi(`/workflow/documents/versions/${versionId}/publish`, { method: 'POST', body: JSON.stringify({ comment }) }),

  archiveDocument: (versionId, comment = null) =>
    fetchApi(`/workflow/documents/versions/${versionId}/archive`, { method: 'POST', body: JSON.stringify({ comment }) }),

  retryProcessing: (versionId) =>
    fetchApi(`/workflow/documents/versions/${versionId}/retry-processing`, { method: 'POST' }),

  sendChatMessage: (question, session_id) => 
    fetchApi('/chat', {
      method: 'POST',
      body: JSON.stringify({ question, session_id })
    }),
};
