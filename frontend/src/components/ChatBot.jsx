import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, Bot, User, FileText, BarChart2 } from 'lucide-react';

export default function ChatBot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'ai',
      text: "Hello Control Room. I am SentriX AI. I can generate incident reports, summarize monthly surveillance data, or locate specific threats. How can I assist you today?"
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = { id: Date.now(), sender: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Simulate AI response logic
    setTimeout(() => {
      let aiText = "I have logged your request.";
      const lowerInput = userMsg.text.toLowerCase();
      
      if (lowerInput.includes('report') || lowerInput.includes('monthly')) {
        aiText = "Generating the Monthly Surveillance Operations Report... I have compiled data across all 12 cameras. There were 84 total incidents this month, primarily Trailing and Zone Intrusions. Would you like me to export this as a PDF dossier?";
      } else if (lowerInput.includes('camera') || lowerInput.includes('cam')) {
        aiText = "Camera CAM-01 at the Main Entrance has the highest anomaly rate this week. I recommend reviewing the patrol schedule for that zone.";
      } else if (lowerInput.includes('vehicle') || lowerInput.includes('anpr')) {
        aiText = "I can scan the ANPR logs. Please provide the license plate number or the timeframe you are interested in.";
      } else {
        aiText = "I can analyze threat patterns, generate shift reports, and cross-reference watchlist data. What specific intelligence do you need?";
      }

      setMessages(prev => [...prev, { id: Date.now(), sender: 'ai', text: aiText }]);
      setIsTyping(false);
    }, 1500);
  };

  return (
    <>
      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          width: 56,
          height: 56,
          borderRadius: '50%',
          background: 'var(--brand-blue)',
          color: 'white',
          border: 'none',
          boxShadow: '0 4px 20px rgba(29, 78, 216, 0.4)',
          display: isOpen ? 'none' : 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          zIndex: 999,
          transition: 'transform 0.2s',
        }}
        onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.05)'}
        onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
      >
        <MessageSquare size={24} />
      </button>

      {/* Chat Window */}
      {isOpen && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          width: 380,
          height: 550,
          background: 'var(--bg-primary)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 1000,
          overflow: 'hidden',
          animation: 'slide-up 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)'
        }}>
          {/* Header */}
          <div style={{
            background: 'var(--brand-navy)',
            color: 'white',
            padding: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 32, height: 32, background: 'rgba(29, 78, 216, 0.4)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Bot size={18} color="#93c5fd" />
              </div>
              <div>
                <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>SentriX AI Agent</div>
                <div style={{ fontSize: '0.65rem', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span className="ws-dot" style={{ width: 6, height: 6 }} /> ONLINE
                </div>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              style={{ background: 'transparent', border: 'none', color: '#cbd5e1', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Quick Actions */}
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)', display: 'flex', gap: 8, overflowX: 'auto' }}>
            <button className="btn btn-ghost" style={{ fontSize: '0.65rem', padding: '4px 10px', whiteSpace: 'nowrap' }} onClick={() => setInput('Generate Monthly Report')}>
              <FileText size={12} /> Monthly Report
            </button>
            <button className="btn btn-ghost" style={{ fontSize: '0.65rem', padding: '4px 10px', whiteSpace: 'nowrap' }} onClick={() => setInput('Show Threat Analytics')}>
              <BarChart2 size={12} /> Threat Analytics
            </button>
          </div>

          {/* Messages Area */}
          <div style={{ flex: 1, padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16, background: 'var(--bg-void)' }}>
            {messages.map((msg) => (
              <div key={msg.id} style={{ display: 'flex', gap: 12, flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row' }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: msg.sender === 'user' ? 'var(--brand-blue)' : 'var(--bg-secondary)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: msg.sender === 'user' ? 'white' : 'var(--brand-navy)'
                }}>
                  {msg.sender === 'user' ? <User size={14} /> : <Bot size={14} />}
                </div>
                <div style={{
                  background: msg.sender === 'user' ? 'var(--brand-blue)' : 'var(--bg-primary)',
                  color: msg.sender === 'user' ? 'white' : 'var(--text-primary)',
                  padding: '10px 14px',
                  borderRadius: '12px',
                  borderTopRightRadius: msg.sender === 'user' ? 0 : '12px',
                  borderTopLeftRadius: msg.sender === 'user' ? '12px' : 0,
                  fontSize: '0.85rem',
                  maxWidth: '85%',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                  border: msg.sender === 'ai' ? '1px solid var(--border)' : 'none',
                  lineHeight: 1.5
                }}>
                  {msg.text}
                </div>
              </div>
            ))}
            {isTyping && (
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--brand-navy)' }}>
                  <Bot size={14} />
                </div>
                <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', padding: '12px 14px', borderRadius: '12px', borderTopLeftRadius: 0, display: 'flex', gap: 4, alignItems: 'center' }}>
                  <span className="dot-pulse" style={{ width: 6, height: 6, background: 'var(--text-muted)', borderRadius: '50%', animation: 'pulse-dot 1s infinite' }} />
                  <span className="dot-pulse" style={{ width: 6, height: 6, background: 'var(--text-muted)', borderRadius: '50%', animation: 'pulse-dot 1s infinite 0.2s' }} />
                  <span className="dot-pulse" style={{ width: 6, height: 6, background: 'var(--text-muted)', borderRadius: '50%', animation: 'pulse-dot 1s infinite 0.4s' }} />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form onSubmit={handleSend} style={{ padding: '16px', background: 'var(--bg-primary)', borderTop: '1px solid var(--border)', display: 'flex', gap: 12 }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask SentriX AI..."
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: '8px',
                border: '1px solid var(--border)',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
            <button
              type="submit"
              disabled={!input.trim()}
              style={{
                background: input.trim() ? 'var(--brand-blue)' : 'var(--bg-secondary)',
                color: input.trim() ? 'white' : 'var(--text-muted)',
                border: 'none',
                borderRadius: '8px',
                padding: '0 16px',
                cursor: input.trim() ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s'
              }}
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
