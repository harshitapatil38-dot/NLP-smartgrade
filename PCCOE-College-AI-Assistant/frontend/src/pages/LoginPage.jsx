import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

export const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api.login(email, password);
      login(data.access_token);
      navigate('/admin/documents');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <img src="https://www.pccoepune.com/images/pccoe-logo-new.webp" alt="PCCOE Logo" className="login-logo-img" style={{height: '60px', marginBottom: '1rem'}} />
          <h2>Admin Login</h2>
          <p>PCCOE College AI Assistant</p>
        </div>
        
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input 
              id="email"
              type="email" 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              placeholder="admin@example.com"
              required 
              aria-required="true"
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input 
              id="password"
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              placeholder="••••••••"
              required 
              aria-required="true"
            />
          </div>
          <button type="submit" disabled={loading} className="btn-primary" aria-busy={loading}>
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>
        
        <Link to="/" className="login-back-link">
          &larr; Back to Student Assistant
        </Link>
      </div>
    </div>
  );
};
