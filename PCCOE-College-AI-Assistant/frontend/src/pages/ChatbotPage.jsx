import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../services/api';
import './ChatbotPage.css';

const ChatbotPage = () => {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Welcome to the PCCOE AI Assistant! How can I help you with college information today?',
      sources: []
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleClearChat = () => {
    setMessages([
      {
        role: 'assistant',
        content: 'Welcome to the PCCOE AI Assistant! How can I help you with college information today?',
        sources: []
      }
    ]);
    setSessionId(crypto.randomUUID());
  };

  const handleSubmit = async (overrideQuestion = null) => {
    const question = (typeof overrideQuestion === 'string' ? overrideQuestion : inputValue).trim();
    if (!question || loading) return;

    // Add user message
    const userMsg = { role: 'user', content: question, sources: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setLoading(true);

    try {
      const response = await api.sendChatMessage(question, sessionId);
      
      // Update session ID if backend gave us a new one
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
    return (
      <details key={idx} className="chatbot-source-card">
        <summary className="chatbot-source-summary">
          <span className="chatbot-source-icon">📄</span>
          <span className="chatbot-source-title">{src.title || 'Untitled Document'}</span>
          {src.similarity_score !== null && src.similarity_score !== undefined && (
            <span className="chatbot-source-badge">
              Relevance: {src.similarity_score.toFixed(2)}
            </span>
          )}
        </summary>
        <div className="chatbot-source-details">
          {src.department && (
            <div className="source-meta-row">
              <strong>Department:</strong> {src.department}
            </div>
          )}
          {src.document_version_id && (
            <div className="source-meta-row">
              <strong>Version ID:</strong> {src.document_version_id}
            </div>
          )}
          {src.page_number && (
            <div className="source-meta-row">
              <strong>Page:</strong> {src.page_number}
            </div>
          )}
          {src.source && (
            <div className="source-meta-row">
              <strong>Source:</strong>{' '}
              {isUrl ? (
                <a href={src.source} target="_blank" rel="noopener noreferrer">
                  {src.source}
                </a>
              ) : (
                <span>{src.source}</span>
              )}
            </div>
          )}
        </div>
      </details>
    );
  };

  return (
    <div className="chatbot-container">
      <header className="chatbot-header">
        <div className="chatbot-header-title">
          <h1>PCCOE College AI Assistant</h1>
          <p>Official student information and knowledge base</p>
        </div>
        <button className="chatbot-clear-btn" onClick={handleClearChat} disabled={loading}>
          Clear Chat
        </button>
      </header>
      
      <div className="chatbot-messages-container">
        {messages.map((msg, idx) => (
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
                  <h4 className="chatbot-sources-heading">Sources from the official college knowledge base</h4>
                  <div className="chatbot-sources-list">
                    {msg.sources.map((src, sIdx) => renderSourceCard(src, sIdx))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="chatbot-message-row row-assistant">
            <div className="chatbot-message-bubble bubble-assistant bubble-loading">
              <span className="dot-typing"></span>
            </div>
          </div>
        )}
        
        {messages.length === 1 && !loading && (
          <div className="chatbot-suggested-questions">
            <p className="suggested-heading">Suggested Questions:</p>
            <div className="suggested-chips">
              <button onClick={() => { setInputValue('How many departments does PCCOE have?'); handleSubmit('How many departments does PCCOE have?'); }}>Departments</button>
              <button onClick={() => { setInputValue('What clubs are available?'); handleSubmit('What clubs are available?'); }}>Clubs</button>
              <button onClick={() => { setInputValue('Tell me about the library.'); handleSubmit('Tell me about the library.'); }}>Library</button>
              <button onClick={() => { setInputValue('What facilities are available?'); handleSubmit('What facilities are available?'); }}>Facilities</button>
              <button onClick={() => { setInputValue('What scholarships are available?'); handleSubmit('What scholarships are available?'); }}>Scholarships</button>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div className="chatbot-footer-wrapper">
        <div className="chatbot-disclaimer">
          Answers are generated using information retrieved from the college knowledge base.
        </div>
        <div className="chatbot-input-area">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about PCCOE (Press Enter to send, Shift+Enter for new line)..."
            disabled={loading}
            rows={1}
          />
          <button className="chatbot-send-btn" onClick={handleSubmit} disabled={!inputValue.trim() || loading} aria-label="Send message">
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatbotPage;
