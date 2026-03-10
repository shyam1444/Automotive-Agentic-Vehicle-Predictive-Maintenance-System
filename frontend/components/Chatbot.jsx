import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Bot, User, Loader2, MessageSquare, Plus, Clock, Trash2 } from 'lucide-react';

export default function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [history, setHistory] = useState([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Scroll to bottom on new message
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    // Generate simple local storage key for session
    const savedSession = localStorage.getItem('current_chat_session');
    if (savedSession) {
      setSessionId(savedSession);
      fetchHistory(savedSession);
    } else {
      startNewChat();
    }
    fetchSessionsList();
  }, []);

  const fetchHistory = async (sid) => {
    try {
      const response = await fetch(`http://localhost:8000/api/chat/history/${sid}`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data);
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    }
  };

  const fetchSessionsList = () => {
    const sessions = JSON.parse(localStorage.getItem('chat_sessions_list') || '[]');
    setHistory(sessions);
  };

  const saveToSessionsList = (sid, preview) => {
    const sessions = JSON.parse(localStorage.getItem('chat_sessions_list') || '[]');
    const existing = sessions.find(s => s.id === sid);
    if (!existing) {
      const newSessions = [{ id: sid, preview, date: new Date().toISOString() }, ...sessions].slice(0, 10);
      localStorage.setItem('chat_sessions_list', JSON.stringify(newSessions));
      setHistory(newSessions);
    }
  };

  const startNewChat = () => {
    setSessionId('');
    setMessages([]);
    localStorage.removeItem('current_chat_session');
    setIsSidebarOpen(false);
  };

  const clearAllHistory = () => {
    if (window.confirm("Are you sure you want to clear all chat history?")) {
      localStorage.removeItem('chat_sessions_list');
      localStorage.removeItem('current_chat_session');
      setHistory([]);
      setSessionId('');
      setMessages([]);
    }
  };

  const loadChat = (sid) => {
    setSessionId(sid);
    localStorage.setItem('current_chat_session', sid);
    fetchHistory(sid);
    setIsSidebarOpen(false);
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage.content, session_id: sessionId || null })
      });

      if (!response.ok) {
        throw new Error('Network error');
      }

      const data = await response.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);

      if (!sessionId || data.session_id !== sessionId) {
        setSessionId(data.session_id);
        localStorage.setItem('current_chat_session', data.session_id);
        saveToSessionsList(data.session_id, userMessage.content);
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I couldn't reach the backend service. Make sure Ollama and the API are running." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card w-full h-[600px] flex overflow-hidden p-0 border border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-md">
      {/* Sidebar / History */}
      <AnimatePresence>
        {(isSidebarOpen || window.innerWidth > 768) && (
          <motion.div
            initial={{ x: -300 }}
            animate={{ x: 0 }}
            exit={{ x: -300 }}
            className={`w-64 border-r border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/80 flex flex-col absolute md:relative z-10 h-full`}
          >
            <div className="p-4 border-b border-slate-200 dark:border-slate-700">
              <button
                onClick={startNewChat}
                className="w-full btn btn-primary flex items-center justify-center gap-2 py-2"
              >
                <Plus size={18} /> New Chat
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              <div className="text-xs text-slate-500 font-semibold mb-2 px-2 uppercase tracking-wider">Recent</div>
              {history.map((session) => (
                <button
                  key={session.id}
                  onClick={() => loadChat(session.id)}
                  className={`w-full text-left p-3 rounded-xl mb-2 flex items-start gap-3 transition-all duration-200 ${sessionId === session.id ? 'bg-primary-500 text-white shadow-md shadow-primary-500/20' : 'hover:bg-slate-100 dark:hover:bg-slate-700/50 text-slate-700 dark:text-slate-300'}`}
                >
                  <MessageSquare size={16} className={`mt-1 flex-shrink-0 ${sessionId === session.id ? 'text-primary-100' : 'text-slate-400'}`} />
                  <div className="overflow-hidden">
                    <div className="text-sm truncate font-medium">{session.preview}</div>
                    <div className={`text-xs flex items-center gap-1 mt-1 ${sessionId === session.id ? 'text-primary-100 opacity-90' : 'opacity-60'}`}>
                      <Clock size={12} />
                      {new Date(session.date).toLocaleDateString()}
                    </div>
                  </div>
                </button>
              ))}
              {history.length === 0 && (
                <div className="text-sm text-slate-500 text-center p-6 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl mt-4">No recent chats</div>
              )}
            </div>

            <div className="p-4 border-t border-slate-200 dark:border-slate-700 mt-auto bg-slate-50 dark:bg-slate-800/80">
              <button
                onClick={clearAllHistory}
                disabled={history.length === 0}
                className="w-full px-4 py-2.5 rounded-xl border border-red-200 dark:border-red-900/50 hover:bg-red-50 dark:hover:bg-red-900/20 text-red-600 dark:text-red-400 flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm"
              >
                <Trash2 size={16} /> Delete All History
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full bg-slate-50/50 dark:bg-slate-900/50 relative">
        {/* Header */}
        <div className="h-16 border-b border-slate-200 dark:border-slate-800 flex items-center px-4 md:px-6 justify-between shrink-0 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <button
              className="md:hidden p-2 -ml-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            >
              <MessageSquare size={20} className="text-slate-600 dark:text-slate-300" />
            </button>
            <div className="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center text-primary-600 dark:text-primary-400">
              <Bot size={24} />
            </div>
            <div>
              <h3 className="font-semibold text-slate-800 dark:text-slate-100">Automotive AI Assistant</h3>
              <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                Gemma 2B • Local & Private
              </p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scroll-smooth">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-50">
              <Bot size={48} className="text-primary-500" />
              <div>
                <h4 className="text-lg font-medium text-slate-800 dark:text-slate-200">How can I help you today?</h4>
                <p className="text-sm text-slate-500 max-w-sm mt-2">
                  Ask me about vehicle status, anomalies, or historical alerts. Try "Why is VEHICLE_1 marked as critical?"
                </p>
              </div>
            </div>
          )}

          {messages.map((msg, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex items-start gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user'
                  ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/50 dark:text-blue-400'
                  : 'bg-primary-100 text-primary-600 dark:bg-primary-900/50 dark:text-primary-400'
                }`}>
                {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className={`px-5 py-3.5 rounded-2xl max-w-[85%] text-sm leading-relaxed ${msg.role === 'user'
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-tr-none shadow-md shadow-blue-500/20 font-medium'
                  : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-100 dark:border-slate-700 rounded-tl-none shadow-sm'
                }`}>
                {msg.content.split('\n').map((line, i) => {
                  // Basic rudimentary formatting for bold Markdown text
                  const boldRegex = /\*\*(.*?)\*\*/g;
                  if (line.trim() === '') return <br key={i} />;

                  const formattedLine = line.split(boldRegex).map((part, j) => {
                    if (j % 2 === 1) return <strong key={j} className="font-semibold">{part}</strong>;
                    return part;
                  });

                  return (
                    <span key={i} className="block mb-1">
                      {formattedLine}
                    </span>
                  );
                })}
              </div>
            </motion.div>
          ))}

          {isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-4"
            >
              <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center text-primary-600 shrink-0">
                <Bot size={16} />
              </div>
              <div className="px-4 py-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-tl-none flex items-center gap-2">
                <Loader2 size={16} className="animate-spin text-primary-500" />
                <span className="text-sm text-slate-500 font-medium">Analyzing telemetry...</span>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 shrink-0">
          <form onSubmit={sendMessage} className="relative max-w-4xl mx-auto">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about vehicle telemetry..."
              className="w-full bg-slate-100 dark:bg-slate-800 border border-transparent focus:border-primary-500 rounded-full px-6 py-4 pr-14 text-sm outline-none transition-all shadow-inner text-slate-800 dark:text-slate-100"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="absolute right-2 top-2 p-2 rounded-full bg-primary-600 hover:bg-primary-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send size={18} />
            </button>
          </form>
          <div className="text-center mt-2">
            <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold flex items-center justify-center gap-2">
              <span className="w-1 h-1 rounded-full bg-primary-500"></span>
              Secure Local Intelligence
              <span className="w-1 h-1 rounded-full bg-primary-500"></span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
