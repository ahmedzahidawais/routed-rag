// frontend/src/App.tsx
import { useState, useEffect, useRef } from 'react';
import { FiSend } from 'react-icons/fi';

// --- Configuration ---
// Make sure this matches your deployed backend URL
const API_BASE_URL = 'https://rag-chatbot-api.azurewebsites.net/';
const PASSWORD = import.meta.env.VITE_APP_PASSWORD || 'default_password'; // Use environment variab
interface Message {
  id: string; // Add unique ID for key prop
  text: string;
  isUser: boolean;
  citationMap?: { [key: string]: string };
}

// --- Text Formatting (Simplified) ---

// Citation hover component with dynamic positioning
const CitationTooltip = ({ number, content }: { number: string; content: string }) => {
  const [show, setShow] = useState(false);
  const [position, setPosition] = useState<'top' | 'bottom'>('top');
  const [coords, setCoords] = useState({ left: 0, top: 0 });
  const ref = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (show && ref.current && tooltipRef.current) {
      const rect = ref.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();
      const spaceAbove = rect.top;
      const spaceBelow = window.innerHeight - rect.bottom;
      let newPosition: 'top' | 'bottom' = 'top';
      let top = rect.top - tooltipRect.height - 8; // 8px margin
      if (spaceBelow > tooltipRect.height + 16) {
        newPosition = 'bottom';
        top = rect.bottom + 8;
      } else if (spaceAbove > tooltipRect.height + 16) {
        newPosition = 'top';
        top = rect.top - tooltipRect.height - 8;
      } else {
        // Default to bottom, but clamp to viewport
        newPosition = 'bottom';
        top = Math.min(rect.bottom + 8, window.innerHeight - tooltipRect.height - 8);
      }
      setPosition(newPosition);
      setCoords({
        left: rect.left + rect.width / 2,
        top,
      });
    }
  }, [show]);

  return (
    <span
      ref={ref}
      className="text-blue-600 cursor-help hover:text-blue-800 relative"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      [{number}]
      {show && (
        <div
          ref={tooltipRef}
          className="fixed z-[1000] bg-white p-4 rounded-lg shadow-xl min-w-[300px] max-w-[500px] max-h-[400px] border border-gray-200 overflow-y-auto"
          style={{
            left: coords.left,
            top: coords.top,
            transform: 'translateX(-50%)',
          }}
        >
          <div className="text-sm text-gray-700 whitespace-pre-wrap break-words leading-relaxed">
            {content}
          </div>
          {/* Arrow */}
          <div
            className={`absolute left-1/2 ${position === 'top' ? 'top-full' : 'bottom-full'} transform -translate-x-1/2 ${position === 'top' ? '' : ''}`}
            style={{ width: 16, height: 16 }}
          >
            <div
              className="w-4 h-4 bg-white border-r border-b border-gray-200"
              style={{ transform: 'rotate(45deg)', marginTop: position === 'top' ? 0 : -8, marginBottom: position === 'top' ? -8 : 0 }}
            />
          </div>
        </div>
      )}
    </span>
  );
};

// Function to parse the citation map from the response
const extractCitationMap = (text: string): { [key: string]: string } => {
  const match = text.match(/\n\nCITATION_MAP: (\{[\s\S]*\})/);
  if (match) {
    try {
      return JSON.parse(match[1]);
    } catch {
      return {};
    }
  }
  return {};
};

// Function to format text with citations
const formatText = (text: string, citationMap?: { [key: string]: string }) => {
  // Remove the citation map marker from the text
  const cleanText = text.replace(/\n\nCITATION_MAP: (\{[\s\S]*\})/, '');
  const [mainContent, sources] = cleanText.split('\n\nQuellen:');
  const paragraphs = mainContent
    .split(/\n+/)
    .map(p => p.trim())
    .filter(p => p.length > 0);

  // Function to process text with citations
  const processTextWithCitations = (text: string) => {
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const citationMatch = part.match(/\[(\d+)\]/);
      if (citationMatch && citationMap && citationMap[citationMatch[1]]) {
        return (
          <CitationTooltip
            key={i}
            number={citationMatch[1]}
            content={citationMap[citationMatch[1]]}
          />
        );
      }
      return part;
    });
  };

  return (
    <div className="space-y-3">
      {paragraphs.map((paragraph, i) => (
        <p key={i}>{processTextWithCitations(paragraph)}</p>
      ))}
      {sources && (
        <div className="mt-4 pt-2 border-t border-gray-200">
          <p className="text-sm text-gray-600">
            <strong>Quellen:</strong> {sources.trim()}
          </p>
        </div>
      )}
    </div>
  );
};

// --- Main App Component ---
function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [inputMessage, setInputMessage] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null); // Ref for scrolling

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

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    // Basic password check (consider more secure methods for production)
    if (password === PASSWORD) {
      setIsAuthenticated(true);
      setError('');
      setPassword(''); // Clear password field after successful login
    } else {
      setError('Incorrect password');
    }
  };

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

  // Login Screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
        <div className="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
          <h2 className="text-2xl font-bold text-gray-800 mb-6 text-center">Chat Login</h2>
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label htmlFor="password" className="block text-gray-700 text-sm font-bold mb-2">
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter password"
                required // Make password required
              />
            </div>
            {error && (
              <p className="text-red-600 text-sm mb-4 text-center">{error}</p>
            )}
            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition duration-150 ease-in-out"
            >
              Login
            </button>
          </form>
        </div>
      </div>
    );
  }

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
                  <p>{message.text}</p> // Simple text for user
                ) : (
                  message.text ? (
                    formatText(message.text, message.citationMap)
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
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Ask something..."
              className="flex-1 rounded-full border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent text-sm sm:text-base"
              disabled={isLoading} // Disable input while loading
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