import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

export const DocumentListPage = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [filters, setFilters] = useState({
    status: '',
    department_id: '',
    source: ''
  });

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      // Clean up empty filters
      const activeFilters = Object.fromEntries(
        Object.entries(filters).filter(([_, v]) => v !== '')
      );
      const data = await api.listDocuments(activeFilters);
      setDocuments(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [filters]);

  const handleFilterChange = (e) => {
    setFilters(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Knowledge Management</h1>
        <Link to="/admin/documents/new" className="btn-primary">+ New Document</Link>
      </div>

      <div className="filters-card">
        <div className="form-group">
          <label>Status</label>
          <select name="status" value={filters.status} onChange={handleFilterChange}>
            <option value="">All</option>
            <option value="DRAFT">DRAFT</option>
            <option value="PENDING_REVIEW">PENDING REVIEW</option>
            <option value="APPROVED">APPROVED</option>
            <option value="PUBLISHED">PUBLISHED</option>
            <option value="REJECTED">REJECTED</option>
            <option value="ARCHIVED">ARCHIVED</option>
          </select>
        </div>
        <div className="form-group">
          <label>Department ID</label>
          <input 
            type="number" 
            name="department_id" 
            value={filters.department_id} 
            onChange={handleFilterChange} 
            placeholder="e.g. 1" 
          />
        </div>
        <div className="form-group">
          <label>Source</label>
          <input 
            type="text" 
            name="source" 
            value={filters.source} 
            onChange={handleFilterChange} 
            placeholder="e.g. Website" 
          />
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="table-container">
        {loading ? (
          <p>Loading documents...</p>
        ) : documents.length === 0 ? (
          <p>No documents found.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Category</th>
                <th>Department</th>
                <th>Status</th>
                <th>Created At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map(doc => (
                <tr key={doc.id}>
                  <td>{doc.id}</td>
                  <td>{doc.title}</td>
                  <td>{doc.category || '-'}</td>
                  <td>{doc.department_id || '-'}</td>
                  <td><span className={`badge status-${doc.status.toLowerCase()}`}>{doc.status}</span></td>
                  <td>{new Date(doc.created_at).toLocaleDateString()}</td>
                  <td>
                    <Link to={`/admin/documents/${doc.id}`} className="btn-secondary btn-sm">View Details</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
