import { useState } from 'react'
import styles from './Message.module.css'

export default function Message({ role, text, sources = [] }) {
  const [copied,       setCopied]       = useState(false)
  const [showSources,  setShowSources]  = useState(false)

  function copyText() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className={`${styles.message} ${styles[role]}`}>
      <div className={styles.bubble}>
        {text}
      </div>

      {role === 'bot' && (
        <div className={styles.meta}>
          {/* Copy button */}
          <button
            className={`${styles.actionBtn} ${copied ? styles.copied : ''}`}
            onClick={copyText}
          >
            {copied ? (
              <>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                Copied
              </>
            ) : (
              <>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                Copy
              </>
            )}
          </button>

          {/* Sources toggle */}
          {sources.length > 0 && (
            <button
              className={`${styles.actionBtn} ${showSources ? styles.active : ''}`}
              onClick={() => setShowSources(s => !s)}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              {showSources ? 'Hide' : `${sources.length} source${sources.length > 1 ? 's' : ''}`}
            </button>
          )}
        </div>
      )}

      {/* Sources panel */}
      {role === 'bot' && showSources && sources.length > 0 && (
        <div className={styles.sourcesPanel}>
          {sources.slice(0, 3).map((src, i) => (
            <div key={i} className={styles.sourceCard}>
              <div className={styles.sourceSubject}>{src.subject || 'No subject'}</div>
              <div className={styles.sourceMeta}>
                <span>{src.from || 'Unknown'}</span>
                <span className={styles.dot}>·</span>
                <span>{src.date || ''}</span>
              </div>
              {src.snippet && (
                <div className={styles.sourceSnippet}>{src.snippet}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}