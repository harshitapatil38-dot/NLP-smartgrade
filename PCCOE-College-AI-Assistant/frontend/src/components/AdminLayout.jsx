import React from 'react';
import { Navigate, Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export const AdminLayout = () => {
  const { user, isAdmin, loading, logout } = useAuth();
  const navigate = useNavigate();

  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return (
    <div className="error-container">
      <h2>403 Forbidden</h2>
      <p>You do not have administrative privileges.</p>
      <button onClick={() => { logout(); navigate('/login'); }}>Sign Out</button>
    </div>
  );

  return (
    <div className="admin-layout">
      <nav className="admin-sidebar">
        <h2>PCCOE Admin</h2>
        <ul>
          <li><Link to="/admin/dashboard">Dashboard</Link></li>
          <li><Link to="/admin/documents">Knowledge Management</Link></li>
        </ul>
        <div className="sidebar-footer">
          <p>Logged in as: <strong>{user.role}</strong></p>
          <button className="btn-logout" onClick={() => { logout(); navigate('/login'); }}>Logout</button>
        </div>
      </nav>
      <main className="admin-content">
        <Outlet />
      </main>
    </div>
  );
};
