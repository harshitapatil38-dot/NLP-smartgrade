import React from 'react';
import { Navigate, Outlet, NavLink, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export const AdminLayout = () => {
  const { user, isAdmin, loading, logout } = useAuth();
  const navigate = useNavigate();

  if (loading) return <div className="loading">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return (
    <div className="error-container" style={{ padding: '3rem', textAlign: 'center' }}>
      <h2>403 Forbidden</h2>
      <p>You do not have administrative privileges.</p>
      <button className="btn-primary" onClick={() => { logout(); navigate('/login'); }}>Sign Out</button>
    </div>
  );

  return (
    <div className="admin-layout">
      <nav className="admin-sidebar">
        <Link to="/admin/dashboard" style={{textDecoration: 'none'}}>
          <h2>PCCOE Admin</h2>
        </Link>
        <ul>
          <li><NavLink to="/admin/dashboard" className={({isActive}) => isActive ? "active" : ""}>Dashboard</NavLink></li>
          <li><NavLink to="/admin/documents" className={({isActive}) => isActive ? "active" : ""}>Knowledge Management</NavLink></li>
          <li><Link to="/">View Student Chatbot</Link></li>
        </ul>
        <div className="sidebar-footer">
          <p style={{marginBottom: '0.5rem', opacity: 0.9}}>User: <strong>{user.email || 'Admin'}</strong></p>
          <p style={{marginBottom: '0.5rem', opacity: 0.9}}>Role: <strong>{user.role}</strong></p>
          <button className="btn-logout" onClick={() => { logout(); navigate('/login'); }}>Logout</button>
        </div>
      </nav>
      <main className="admin-content">
        <Outlet />
      </main>
    </div>
  );
};
