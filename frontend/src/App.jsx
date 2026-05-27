import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Chat from './components/Chat'
import useApi from './hooks/useApi'
import './styles/App.css'

export default function App() {
  const { status, vectorCount, query } = useApi()
  const [messages, setMessages] = useState([])

  function handleSuggestion(question) {
    // Add user message then immediately trigger query
    const id = Date.now()
    setMessages(prev => [...prev, { role: 'user', text: question, id }])
    fireQuery(question, query, setMessages)
  }

  function clearChat() {
    setMessages([])
  }

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
        query={query}
      />
    </div>
  )
}

export async function fireQuery(text, query, setMessages) {
  try {
    const data = await query(text)
    setMessages(prev => [...prev, {
      role: 'bot',
      text: data.answer,
      sources: data.sources,
      id: Date.now(),
    }])
  } catch {
    setMessages(prev => [...prev, {
      role: 'bot',
      text: '⚠ Could not reach the API. Is uvicorn running on port 8000?',
      id: Date.now(),
    }])
  }
}