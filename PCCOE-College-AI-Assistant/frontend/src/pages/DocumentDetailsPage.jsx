import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../services/api';

export const DocumentDetailsPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState({});

  const fetchDocument = async () => {
    setLoading(true);
    try {
      const data = await api.getDocument(id);
      setDoc(data);
      setEditData({
        title: data.title,
        description: data.description || '',
        category: data.category || '',
        source: data.source || ''
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocument();
  }, [id]);

  const handleEditChange = (e) => {
    setEditData(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    try {
      await api.updateDocument(id, editData);
      setIsEditing(false);
      fetchDocument();
    } catch (err) {
      alert(`Update failed: ${err.message}`);
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to permanently delete this document and all its versions?')) {
      try {
        await api.deleteDocument(id);
        navigate('/admin/documents');
      } catch (err) {
        alert(`Delete failed: ${err.message}`);
      }
    }
  };

  const handleWorkflow = async (action, versionId) => {
    setLoading(true);
    try {
      if (action === 'submit') await api.submitForReview(versionId);
      if (action === 'approve') await api.approveDocument(versionId);
      if (action === 'reject') await api.rejectDocument(versionId);
      if (action === 'publish') await api.publishDocument(versionId);
      if (action === 'archive') await api.archiveDocument(versionId);
      fetchDocument();
    } catch (err) {
      alert(`Action failed: ${err.message}`);
      setLoading(false);
    }
  };

  if (loading) return <div className="page-container"><p>Loading document details...</p></div>;
  if (error) return <div className="page-container"><div className="alert alert-error">{error}</div></div>;
  if (!doc) return <div className="page-container"><p>Document not found.</p></div>;

  const latestVersion = doc.versions?.find(v => v.version_number === doc.latest_version);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Document #{doc.id}: {doc.title}</h1>
        <div className="header-actions">
          {latestVersion?.status === 'DRAFT' && (
            <button className="btn-primary" onClick={() => handleWorkflow('submit', latestVersion.id)}>Submit for Review</button>
          )}
          {latestVersion?.status === 'PENDING_REVIEW' && (
            <>
              <button className="btn-primary" onClick={() => handleWorkflow('approve', latestVersion.id)}>Approve</button>
              <button className="btn-danger" onClick={() => handleWorkflow('reject', latestVersion.id)}>Reject</button>
            </>
          )}
          {latestVersion?.status === 'APPROVED' && (
            <button className="btn-primary" onClick={() => handleWorkflow('publish', latestVersion.id)}>Publish</button>
          )}
          {latestVersion?.status === 'PUBLISHED' && (
            <button className="btn-secondary" onClick={() => handleWorkflow('archive', latestVersion.id)}>Archive</button>
          )}

          <button className="btn-secondary" onClick={() => setIsEditing(!isEditing)}>
            {isEditing ? 'Cancel Edit' : 'Edit Metadata'}
          </button>
          <button className="btn-danger" onClick={handleDelete}>Delete</button>
          <Link to="/admin/documents" className="btn-secondary">Back to List</Link>
        </div>
      </div>

      <div className="content-grid">
        <div className="main-col">
          {isEditing ? (
            <div className="card edit-card">
              <h3>Edit Metadata</h3>
              <form onSubmit={handleUpdate}>
                <div className="form-group">
                  <label>Title</label>
                  <input type="text" name="title" value={editData.title} onChange={handleEditChange} required />
                </div>
                <div className="form-group">
                  <label>Description</label>
                  <textarea name="description" value={editData.description} onChange={handleEditChange} rows="3" />
                </div>
                <div className="form-group row">
                  <div className="col">
                    <label>Category</label>
                    <input type="text" name="category" value={editData.category} onChange={handleEditChange} />
                  </div>
                  <div className="col">
                    <label>Source</label>
                    <input type="text" name="source" value={editData.source} onChange={handleEditChange} />
                  </div>
                </div>
                <button type="submit" className="btn-primary">Save Changes</button>
              </form>
            </div>
          ) : (
            <div className="card details-card">
              <h3>Metadata</h3>
              <p><strong>Description:</strong> {doc.description || 'N/A'}</p>
              <p><strong>Category:</strong> {doc.category || 'N/A'}</p>
              <p><strong>Department ID:</strong> {doc.department_id || 'N/A'}</p>
              <p><strong>Source:</strong> {doc.source ? (
                <a href={doc.source} target="_blank" rel="noopener noreferrer">Open Source</a>
              ) : 'N/A'}</p>
              <p><strong>Created At:</strong> {new Date(doc.created_at).toLocaleString()}</p>
              <p><strong>Uploaded By (User ID):</strong> {doc.uploaded_by}</p>
            </div>
          )}

          <div className="card versions-card mt-4">
            <h3>Versions</h3>
            {doc.versions && doc.versions.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Version #</th>
                    <th>Status</th>
                    <th>Processing</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {doc.versions.map(v => (
                    <tr key={v.id}>
                      <td>v{v.version_number} {v.version_number === doc.latest_version && '(Latest)'}</td>
                      <td><span className={`badge status-${v.status.toLowerCase()}`}>{v.status}</span></td>
                      <td><span className={`badge proc-${v.processing_status.toLowerCase()}`}>{v.processing_status}</span></td>
                      <td>{new Date(v.created_at).toLocaleString()}</td>
                      <td>
                        {v.status === 'PUBLISHED' && v.processing_status === 'FAILED' && (
                          <button className="btn-secondary btn-sm" onClick={() => handleWorkflow('retry-processing', v.id)}>Retry</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p>No versions found.</p>
            )}
          </div>
        </div>

        <div className="side-col">
          <div className="card status-card">
            <h3>Status</h3>
            <div className="status-badge-lg">
              <span className={`badge status-${doc.status.toLowerCase()}`}>{doc.status}</span>
            </div>
            {doc.latest_version && <p className="mt-2">Latest Version: v{doc.latest_version}</p>}
          </div>
        </div>
      </div>
    </div>
  );
};
