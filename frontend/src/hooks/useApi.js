import { useState, useEffect } from 'react'
import axios from 'axios'

const BASE = '/api'

export default function useApi() {
  const [status, setStatus]           = useState('connecting')
  const [vectorCount, setVectorCount] = useState(null)

  useEffect(() => {
    axios.get(`${BASE}/health`)
      .then(({ data }) => {
        setStatus('online')
        setVectorCount(data.vector_count ?? null)
      })
      .catch(() => setStatus('error'))
  }, [])

  async function query(question, k = 5) {
    const { data } = await axios.post(`${BASE}/query`, { question, k })
    return data // { question, answer, sources }
  }

  return { status, vectorCount, query }
}