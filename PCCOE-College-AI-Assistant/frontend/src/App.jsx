import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { AdminLayout } from './components/AdminLayout';
import { LoginPage } from './pages/LoginPage';
import { DocumentListPage } from './pages/DocumentListPage';
import { DocumentCreatePage } from './pages/DocumentCreatePage';
import { DocumentDetailsPage } from './pages/DocumentDetailsPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import ChatbotPage from './pages/ChatbotPage';
import './index.css';

const App = () => {
  const { user, loading } = useAuth();

  if (loading) return <div className="loading-screen">Loading Application...</div>;

  return (
    <Routes>
      <Route path="/" element={<ChatbotPage />} />
      <Route path="/login" element={user ? <Navigate to="/admin/dashboard" replace /> : <LoginPage />} />
      
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<AdminDashboardPage />} />
        <Route path="documents" element={<DocumentListPage />} />
        <Route path="documents/new" element={<DocumentCreatePage />} />
        <Route path="documents/:id" element={<DocumentDetailsPage />} />
      </Route>
      
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
