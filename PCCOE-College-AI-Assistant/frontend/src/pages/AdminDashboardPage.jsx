import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

export const AdminDashboardPage = () => {
  const [metrics, setMetrics] = useState({
    total: 0,
    draft: 0,
    pending: 0,
    approved: 0,
    published: 0,
    archived: 0
  });
  const [recentDocs, setRecentDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        const docs = await api.listDocuments({ limit: 1000 });
        
        const newMetrics = { total: docs.length, draft: 0, pending: 0, approved: 0, published: 0, archived: 0 };
        docs.forEach(doc => {
          if (doc.status === 'DRAFT') newMetrics.draft++;
          if (doc.status === 'PENDING_REVIEW') newMetrics.pending++;
          if (doc.status === 'APPROVED') newMetrics.approved++;
          if (doc.status === 'PUBLISHED') newMetrics.published++;
          if (doc.status === 'ARCHIVED') newMetrics.archived++;
        });
        
        setMetrics(newMetrics);
        
        // Sort by created_at desc
        const sorted = [...docs].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setRecentDocs(sorted.slice(0, 5));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  if (loading) return <div className="page-container"><p>Loading dashboard...</p></div>;
  if (error) return <div className="page-container"><div className="alert alert-error">{error}</div></div>;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Admin Dashboard</h1>
        <Link to="/admin/documents/new" className="btn-primary">+ New Document</Link>
      </div>

      <div className="metrics-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="card text-center">
          <h3>Total</h3>
          <h2>{metrics.total}</h2>
        </div>
        <div className="card text-center">
          <h3>Drafts</h3>
          <h2>{metrics.draft}</h2>
        </div>
        <div className="card text-center">
          <h3>Pending Review</h3>
          <h2>{metrics.pending}</h2>
        </div>
        <div className="card text-center">
          <h3>Approved</h3>
          <h2>{metrics.approved}</h2>
        </div>
        <div className="card text-center">
          <h3>Published</h3>
          <h2>{metrics.published}</h2>
        </div>
        <div className="card text-center">
          <h3>Archived</h3>
          <h2>{metrics.archived}</h2>
        </div>
      </div>

      <div className="card">
        <h3>Recent Documents</h3>
        {recentDocs.length === 0 ? (
          <p>No documents found.</p>
        ) : (
          <table className="data-table mt-2">
            <thead>
              <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Status</th>
                <th>Created At</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {recentDocs.map(doc => (
                <tr key={doc.id}>
                  <td>{doc.id}</td>
                  <td>{doc.title}</td>
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
