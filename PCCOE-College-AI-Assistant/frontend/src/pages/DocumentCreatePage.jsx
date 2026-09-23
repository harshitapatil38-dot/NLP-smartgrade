import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../services/api';

export const DocumentCreatePage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    department_id: '',
    source: ''
  });

  const [file, setFile] = useState(null);

  const handleChange = (e) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a file to upload.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = new FormData();
      payload.append("title", formData.title);
      if (formData.description) payload.append("description", formData.description);
      if (formData.category) payload.append("category", formData.category);
      if (formData.department_id) payload.append("department_id", parseInt(formData.department_id, 10));
      if (formData.source) payload.append("source", formData.source);
      payload.append("file", file);

      const result = await api.uploadDocument(payload);
      navigate(`/admin/documents/${result.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Create New Document</h1>
        <Link to="/admin/documents" className="btn-secondary">Back to List</Link>
      </div>

      <div className="form-card">
        {error && <div className="alert alert-error">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Title *</label>
            <input 
              type="text" 
              name="title" 
              value={formData.title} 
              onChange={handleChange} 
              required 
            />
          </div>
          
          <div className="form-group">
            <label>Description</label>
            <textarea 
              name="description" 
              value={formData.description} 
              onChange={handleChange} 
              rows="4"
            />
          </div>
          
          <div className="form-group row">
            <div className="col">
              <label>Category</label>
              <input 
                type="text" 
                name="category" 
                value={formData.category} 
                onChange={handleChange} 
              />
            </div>
            <div className="col">
              <label>Department ID</label>
              <input 
                type="number" 
                name="department_id" 
                value={formData.department_id} 
                onChange={handleChange} 
              />
            </div>
            <div className="col">
              <label>Source URL</label>
              <input 
                type="url" 
                name="source" 
                value={formData.source} 
                onChange={handleChange} 
                placeholder="https://..."
              />
            </div>
          </div>

          <div className="form-group">
            <label>Upload Document File *</label>
            <input 
              type="file" 
              name="file" 
              onChange={handleFileChange} 
              accept=".pdf,.docx,.txt,.html"
              required 
            />
            <small>Supported formats: PDF, DOCX, TXT, HTML (Max 10MB)</small>
          </div>
          
          <div className="form-actions mt-3">
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Uploading...' : 'Upload & Create Draft'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
