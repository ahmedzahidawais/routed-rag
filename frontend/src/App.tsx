// frontend/src/App.tsx
import { useState, useEffect, useRef } from 'react';
import { FiSend } from 'react-icons/fi';

// --- Configuration ---
// Make sure this matches your deployed backend URL
const API_BASE_URL = 'http://localhost:8000';
interface Message {
  id: string; // Add unique ID for key prop
  text: string;
  isUser: boolean;
  citationMap?: { [key: string]: string };
}

// --- Text Formatting (Simplified) ---

// Citations disabled in simplified app

// Citations disabled in simplified app
const extractCitationMap = (_text: string): { [key: string]: string } => ({})

// Function to format plain text
const formatText = (text: string) => {
  const paragraphs = text
    .split(/\n+/)
    .map(p => p.trim())
    .filter(p => p.length > 0);

  return (
    <div className="space-y-3">
      {paragraphs.map((paragraph, i) => <p key={i}>{paragraph}</p>)}
    </div>
  );
};

// --- Main App Component ---
function App() {
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null); // Ref for scrolling
  const textareaRef = useRef<HTMLTextAreaElement>(null); // Ref for auto-resize

  // Scroll to bottom effect
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]); // Trigger effect when messages change

  // Add mouse position tracking
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      document.documentElement.style.setProperty('--mouse-x', `${e.clientX}`);
      document.documentElement.style.setProperty('--mouse-y', `${window.innerHeight - e.clientY}`);
    };

    document.addEventListener('mousemove', handleMouseMove);
    return () => document.removeEventListener('mousemove', handleMouseMove);
  }, []);

  // Auto-resize textarea when inputMessage changes
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputMessage]);

  const handleSendMessage = async () => {
    const trimmedMessage = inputMessage.trim();
    if (!trimmedMessage || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      text: trimmedMessage,
      isUser: true,
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError('');

    const botMessageId = `bot-${Date.now()}`;
    setMessages(prev => [...prev, { id: botMessageId, text: '', isUser: false }]);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: trimmedMessage }),
      });

      if (!response.ok || !response.body) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to parse error response.' }));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedResponse = '';
      let citationMap: { [key: string]: string } = {};

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        accumulatedResponse += chunk;
        // Try to extract the citation map if present
        citationMap = extractCitationMap(accumulatedResponse);

        setMessages(prev =>
          prev.map(msg =>
            msg.id === botMessageId
              ? { ...msg, text: accumulatedResponse, citationMap }
              : msg
          )
        );
      }

    } catch (err) {
      console.error('Error fetching chat response:', err);
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
      setMessages(prev =>
        prev.map(msg =>
          msg.id === botMessageId
            ? { ...msg, text: `Error: ${errorMessage}` }
            : msg
        )
      );
      setError(`Failed to get response: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Render Logic ---

  // Chat Interface
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-100 to-gray-200 flex flex-col">
      <header className="bg-white shadow-md sticky top-0 z-10">
        <div className="max-w-4xl mx-auto py-3 px-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-semibold text-gray-800">RAG Chatbot</h1>
        </div>
      </header>

      <main className="flex-1 max-w-4xl mx-auto w-full p-4 flex flex-col">
        {/* Chat Messages Area */}
        <div className="bg-white rounded-lg shadow-xl flex-1 overflow-y-auto mb-4 p-4 sm:p-6 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id} // Use unique ID for key
              className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                // Apply different classes for user and bot
                // ADD THE CSS RULE FOR .bot-message-class in your global CSS:
                // .bot-message-class { white-space: pre-wrap; }
                className={`max-w-[85%] rounded-xl px-4 py-3 shadow-sm ${
                  message.isUser
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-800 bot-message-class' // Added bot-message-class
                } overflow-hidden`} // Keep overflow-hidden
                 style={{ wordBreak: 'break-word' }} // Keep word-break as safety
              >
                {message.isUser ? (
                  <p style={{ whiteSpace: 'pre-wrap' }}>{message.text}</p> // Preserve newlines for user messages
                ) : (
                  message.text ? (
                    formatText(message.text)
                  ) : (
                    <span className="italic text-gray-500">Generiere Antwort...</span>
                  )
                )}
              </div>
            </div>
          ))}
          {/* Element to scroll to */}
          <div ref={chatEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-white rounded-lg shadow-lg p-3 sm:p-4 sticky bottom-4 "> {/* Made input sticky */}
          <div className="flex items-center gap-2 sm:gap-3">
            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
                // Shift+Enter will insert a newline by default
              }}
              placeholder="Ask something..."
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent text-sm sm:text-base"
              disabled={isLoading} // Disable input while loading
              rows={1}
              style={{ overflow: 'hidden', resize: 'none', maxHeight: 200 }} // Auto-resize, limit max height
            />
            <button
              onClick={handleSendMessage}
              disabled={isLoading || !inputMessage.trim()} // Disable if loading or input is empty
              className="bg-blue-500 text-white rounded-full p-2 sm:p-3 hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 transition duration-150 ease-in-out"
              aria-label="Send message" // Accessibility
            >
              <FiSend className="h-4 w-4 sm:h-5 sm:w-5" />
            </button>
          </div>
           {/* Display API errors near input */}
           {error && !isLoading && (
             <p className="text-red-600 text-xs mt-2 text-center">{error}</p>
           )}
        </div>
      </main>
    </div>
  );
}

export default App;