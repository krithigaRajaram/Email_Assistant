import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Chat from './components/Chat'
import useApi from './hooks/useApi'
import './styles/index.css'
import './styles/App.css'

export default function App() {
  const { status, vectorCount } = useApi()
  const [messages, setMessages] = useState([])

  const handleSuggestion = (q) => {
    // Bubble up to Chat via a shared state trick
    setMessages(prev => [...prev, { role: 'user', text: q, id: Date.now() }])
  }

  const clearChat = () => setMessages([])

  return (
    <div className="app">
      <div className="noise" />
      <Sidebar
        status={status}
        vectorCount={vectorCount}
        onSuggestion={handleSuggestion}
      />
      <Chat
        messages={messages}
        setMessages={setMessages}
        onClear={clearChat}
        apiStatus={status}
      />
    </div>
  )
}