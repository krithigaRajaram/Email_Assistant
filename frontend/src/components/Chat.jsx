import { useState, useEffect, useRef } from 'react'
import useApi from '../hooks/useApi'
import Message from './Message'
import styles from './Chat.module.css'

export default function Chat({ messages, setMessages, onClear, apiStatus }) {
  const { query } = useApi()
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef             = useRef(null)
  const textareaRef           = useRef(null)

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }, [input])

  // When App pushes a suggestion as a user message, fire the query
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (last?.role === 'user' && last?.pending) {
      fireQuery(last.text, last.id)
    }
  }, [messages])

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    const id = Date.now()
    setMessages(prev => [...prev, { role: 'user', text, id, pending: true }])
    await fireQuery(text, id)
  }

  async function fireQuery(text, id) {
    // Mark user message as no longer pending
    setMessages(prev => prev.map(m => m.id === id ? { ...m, pending: false } : m))
    setLoading(true)
    try {
      const data = await query(text)
      setMessages(prev => [...prev, {
        role: 'bot', text: data.answer,
        sources: data.sources, id: Date.now()
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'bot',
        text: '⚠ Could not reach the API. Is uvicorn running on port 8000?',
        id: Date.now()
      }])
    }
    setLoading(false)
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <main className={styles.main}>
      <header className={styles.topbar}>
        <button className={styles.clearBtn} onClick={onClear}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/>
          </svg>
          Clear chat
        </button>
      </header>

      <div className={styles.chatArea}>
        {isEmpty && !loading ? (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>✦</div>
            <h2>What do you want to know<br />about your inbox?</h2>
            <p>3,000 emails indexed and ready.</p>
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <Message key={msg.id} {...msg} />
            ))}
            {loading && (
              <div className={styles.typingWrap}>
                <div className={styles.typingIndicator}>
                  <span /><span /><span />
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      <div className={styles.inputWrap}>
        <div className={styles.inputBox}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask anything about your emails…"
            rows={1}
            disabled={loading || apiStatus === 'error'}
          />
          <button
            className={styles.sendBtn}
            onClick={send}
            disabled={loading || !input.trim() || apiStatus === 'error'}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
        <div className={styles.hint}>Enter to send · Shift+Enter for new line</div>
      </div>
    </main>
  )
}