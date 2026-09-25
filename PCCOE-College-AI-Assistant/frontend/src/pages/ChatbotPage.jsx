import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../services/api';
import './ChatbotPage.css';

const QUICK_QUESTIONS = [
  "What documents are required for admission?",
  "What courses does PCCOE offer?",
  "What departments are available?",
  "What scholarships are available?",
  "What facilities does PCCOE provide?",
  "How can I contact PCCOE?"
];

const ChatbotPage = () => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleClearChat = () => {
    setMessages([]);
    setSessionId(crypto.randomUUID());
  };

  const handleSubmit = async (overrideQuestion = null) => {
    const question = (typeof overrideQuestion === 'string' ? overrideQuestion : inputValue).trim();
    if (!question || loading) return;

    const userMsg = { role: 'user', content: question, sources: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setLoading(true);

    try {
      const response = await api.sendChatMessage(question, sessionId);
      
      if (response.session_id && response.session_id !== sessionId) {
        setSessionId(response.session_id);
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.answer,
          sources: response.sources || []
        }
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${error.message || 'Something went wrong while processing your request.'}`,
          sources: [],
          isError: true
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const renderSourceCard = (src, idx) => {
    const isUrl = src.source && src.source.startsWith('http');
    // Extract a display friendly URL
    const displayUrl = isUrl ? src.source.replace(/^https?:\/\/(www\.)?/, '') : src.source;

    return (
      <div key={idx} className="chatbot-source-card">
        <div className="source-card-header">
          <span className="source-icon">📄</span>
          <span className="source-title">PCCOE Official Source</span>
        </div>
        <div className="source-card-url">
          {displayUrl}
        </div>
        {isUrl ? (
          <a href={src.source} target="_blank" rel="noopener noreferrer" className="source-card-link">
            View source →
          </a>
        ) : (
          <span className="source-card-link-disabled">Local source</span>
        )}
      </div>
    );
  };

  return (
    <div className="chatbot-container">
      <header className="chatbot-header">
        <div className="header-brand">
          <div className="header-logo">
            {/* PCCOE Initial or Logo placeholder */}
            <span>P</span>
          </div>
          <div className="chatbot-header-title">
            <h1>PCCOE College AI Assistant</h1>
            <p>Official Information Portal</p>
          </div>
        </div>
        <nav className="header-nav">
          <a href="/login" className="nav-login-btn">Admin Login</a>
          <button className="chatbot-clear-btn" onClick={handleClearChat} disabled={loading || messages.length === 0}>
            New Chat
          </button>
        </nav>
      </header>
      
      <div className="chatbot-messages-container">
        {messages.length === 0 && !loading ? (
          <div className="chatbot-welcome-area">
            <h2>Welcome to PCCOE AI Assistant</h2>
            <p className="welcome-subtitle">How can I help you today?</p>
            <p className="welcome-desc">
              Ask about admissions, academics, departments, examinations, scholarships, facilities, campus information and more.
            </p>
            
            <div className="quick-questions-grid">
              {QUICK_QUESTIONS.map((q, idx) => (
                <button key={idx} className="quick-question-card" onClick={() => handleSubmit(q)}>
                  <span>{q}</span>
                  <span className="arrow">→</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`chatbot-message-row ${msg.role === 'user' ? 'row-user' : 'row-assistant'}`}>
              <div className={`chatbot-message-bubble ${msg.role === 'user' ? 'bubble-user' : 'bubble-assistant'} ${msg.isError ? 'bubble-error' : ''}`}>
                <div className="chatbot-message-content">
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
                
                {msg.sources && msg.sources.length > 0 && (
                  <div className="chatbot-sources">
                    <h4 className="chatbot-sources-heading">Sources</h4>
                    <div className="chatbot-sources-list">
                      {msg.sources.map((src, sIdx) => renderSourceCard(src, sIdx))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        
        {loading && (
          <div className="chatbot-message-row row-assistant">
            <div className="chatbot-message-bubble bubble-assistant bubble-loading">
              <span className="dot-typing"></span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="chatbot-footer-wrapper">
        <div className="chatbot-input-area">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about PCCOE..."
            disabled={loading}
            rows={1}
          />
          <button className="chatbot-send-btn" onClick={() => handleSubmit()} disabled={!inputValue.trim() || loading} aria-label="Send message">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
        <div className="chatbot-disclaimer">
          AI Assistant can make mistakes. Please verify important information on the official PCCOE website.
        </div>
      </div>
    </div>
  );
};

export default ChatbotPage;
