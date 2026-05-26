import styles from './Sidebar.module.css'

const SUGGESTIONS = [
  { label: 'Recent emails',       q: 'What are the most recent emails I received?' },
  { label: 'This week',           q: 'Any emails I received this week?' },
  { label: 'Orders & deliveries', q: 'Do I have any order confirmations or delivery updates?' },
  { label: 'Payments & invoices', q: 'Any emails about payments, invoices or billing?' },
  { label: 'Job applications',    q: 'Show me job application updates' },
  { label: 'Google / Microsoft',  q: 'Any emails from Google or Microsoft?' },
  { label: 'Newsletters',         q: 'Summarise newsletter emails I received' },
  { label: 'Subscriptions',       q: 'Any subscription renewal or expiry notices?' },
]

export default function Sidebar({ status, vectorCount, onSuggestion }) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoIcon}>✦</span>
        <span className={styles.logoText}>Inbox Intel</span>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionLabel}>Suggested</div>
        <div className={styles.chips}>
          {SUGGESTIONS.map(({ label, q }) => (
            <button
              key={label}
              className={styles.chip}
              onClick={() => onSuggestion(q)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.footer}>
        <span className={`${styles.dot} ${styles[status]}`} />
        <span className={styles.statusText}>
          {status === 'online'
            ? `${vectorCount?.toLocaleString() ?? '—'} vectors indexed`
            : status === 'error'
            ? 'API offline'
            : 'Connecting…'}
        </span>
      </div>
    </aside>
  )
}