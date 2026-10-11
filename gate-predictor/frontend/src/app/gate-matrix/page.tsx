'use client'

import { useEffect, useState } from 'react'

interface TopicItem {
  topic_id: string
  topic_name: string
  topic_code: string
  weighted_marks: number
  consistency: number
  trend: number
  gap: number
  priority_score: number
  bucket: string
  rationale: string
  confidence: string
  total_historical_appearances: number
  avg_marks_per_year: number
  last_appeared_year: number | null
}

interface PriorityResponse {
  subject_id: string
  subject_name: string
  disclaimer: string
  must_do_topics: TopicItem[]
  should_do_topics: TopicItem[]
  skip_if_short_topics: TopicItem[]
  all_topics: TopicItem[]
}

export default function GateMatrixPage() {
  const [data, setData] = useState<PriorityResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'all' | 'must' | 'should' | 'skip'>('all')

  useEffect(() => {
    fetch('/api/v1/subjects/operating_systems/topics/priority')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch topic priorities')
        return res.json()
      })
      .then((data) => {
        setData(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: '#a1a1aa' }}>
        <div style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ffffff', marginBottom: '8px' }}>
          ⌛ Analyzing 10 Years of Official GATE PYQs...
        </div>
        <p style={{ fontSize: '0.9rem', color: '#71717a' }}>Computing recency-decay priority scores, consistency indices, and topic yield buckets.</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="card-panel" style={{ padding: '32px', textAlign: 'center', borderColor: '#3f3f46', background: '#121215' }}>
        <h3 style={{ color: '#ffffff', margin: '0 0 8px 0' }}>⚠️ Connection Error</h3>
        <p style={{ color: '#a1a1aa', margin: '0 0 16px 0' }}>Could not fetch topic priority dataset: {error}</p>
        <p style={{ fontSize: '0.85rem', color: '#71717a' }}>Please verify the backend API server is running on port 8000.</p>
      </div>
    )
  }

  const filterTopics = (topics: TopicItem[]) => {
    return topics.filter((t) =>
      t.topic_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.topic_code.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }

  const mustDoFiltered = filterTopics(data.must_do_topics)
  const shouldDoFiltered = filterTopics(data.should_do_topics)
  const skipFiltered = filterTopics(data.skip_if_short_topics)
  const totalTopicsCount = data.all_topics?.length || (data.must_do_topics.length + data.should_do_topics.length + data.skip_if_short_topics.length)

  return (
    <div>
      <div style={{ marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
          <div>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, margin: '0 0 6px 0', color: '#ffffff' }}>
              GATE CS Topic Yield & Priority Matrix
            </h1>
            <p style={{ color: '#a1a1aa', margin: 0, fontSize: '0.95rem', maxWidth: '750px' }}>
              Statistical priority rankings computed from official GATE PYQ data (recency weighting, linear trend extrapolation, and appearance gap analysis).
            </p>
          </div>

          <a href="/mock-paper" className="btn-primary" style={{ textDecoration: 'none', padding: '10px 18px', borderRadius: '8px' }}>
            🚀 Launch Mock Exam Attempt
          </a>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <div className="card-panel" style={{ padding: '16px 20px', background: '#121215' }}>
          <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500, marginBottom: '4px' }}>Total Topics Analyzed</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#ffffff' }}>{totalTopicsCount} Topics</div>
          <div style={{ fontSize: '0.75rem', color: '#71717a', marginTop: '2px' }}>Subject: Operating Systems</div>
        </div>

        <div className="card-panel" style={{ padding: '16px 20px', background: '#121215', borderLeft: '4px solid #ffffff' }}>
          <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500, marginBottom: '4px' }}>Must-Do Yield Target</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#ffffff' }}>~60% Marks</div>
          <div style={{ fontSize: '0.75rem', color: '#a1a1aa', marginTop: '2px' }}>{data.must_do_topics.length} High-Yield Topics</div>
        </div>

        <div className="card-panel" style={{ padding: '16px 20px', background: '#121215', borderLeft: '4px solid #a1a1aa' }}>
          <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500, marginBottom: '4px' }}>Should-Do Yield Target</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#e4e4e7' }}>~25% Marks</div>
          <div style={{ fontSize: '0.75rem', color: '#a1a1aa', marginTop: '2px' }}>{data.should_do_topics.length} Medium-Yield Topics</div>
        </div>

        <div className="card-panel" style={{ padding: '16px 20px', background: '#121215', borderLeft: '4px solid #3f3f46' }}>
          <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500, marginBottom: '4px' }}>Skip-If-Short Target</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#a1a1aa' }}>~15% Marks</div>
          <div style={{ fontSize: '0.75rem', color: '#71717a', marginTop: '2px' }}>{data.skip_if_short_topics.length} Low-Yield Topics</div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '6px', background: '#121215', padding: '4px', borderRadius: '8px', border: '1px solid #27272a' }}>
          <button onClick={() => setActiveTab('all')} style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: activeTab === 'all' ? '#ffffff' : 'transparent', color: activeTab === 'all' ? '#09090b' : '#a1a1aa', cursor: 'pointer', fontWeight: 700 }}>All Topics ({totalTopicsCount})</button>
          <button onClick={() => setActiveTab('must')} style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: activeTab === 'must' ? '#ffffff' : 'transparent', color: activeTab === 'must' ? '#09090b' : '#a1a1aa', cursor: 'pointer', fontWeight: 700 }}>Must-Do ({mustDoFiltered.length})</button>
          <button onClick={() => setActiveTab('should')} style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: activeTab === 'should' ? '#ffffff' : 'transparent', color: activeTab === 'should' ? '#09090b' : '#a1a1aa', cursor: 'pointer', fontWeight: 700 }}>Should-Do ({shouldDoFiltered.length})</button>
          <button onClick={() => setActiveTab('skip')} style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: activeTab === 'skip' ? '#ffffff' : 'transparent', color: activeTab === 'skip' ? '#09090b' : '#a1a1aa', cursor: 'pointer', fontWeight: 700 }}>Skip ({skipFiltered.length})</button>
        </div>

        <input
          type="text"
          placeholder="🔍 Search topic or code..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ padding: '10px 16px', borderRadius: '8px', background: '#09090b', border: '1px solid #27272a', color: '#ffffff', outline: 'none', width: '280px', fontFamily: 'inherit' }}
        />
      </div>

      <div style={{ display: 'grid', gap: '16px' }}>
        {(activeTab === 'all' || activeTab === 'must') && mustDoFiltered.map((t) => (
          <div key={t.topic_id} className="card-panel" style={{ padding: '20px', borderLeft: '4px solid #ffffff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
              <div>
                <span className="badge-must-do" style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', marginRight: '8px' }}>Must-Do</span>
                <span style={{ fontSize: '0.85rem', color: '#a1a1aa', fontFamily: 'monospace' }}>{t.topic_code}</span>
                <h3 style={{ fontSize: '1.15rem', margin: '4px 0 6px 0', color: '#ffffff' }}>{t.topic_name}</h3>
                <p style={{ fontSize: '0.9rem', color: '#a1a1aa', margin: 0 }}>{t.rationale}</p>
              </div>
              <div style={{ textAlign: 'right', minWidth: '100px' }}>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#ffffff' }}>{(t.priority_score * 100).toFixed(1)}</div>
                <div style={{ fontSize: '0.75rem', color: '#71717a' }}>Priority Score</div>
              </div>
            </div>
          </div>
        ))}

        {(activeTab === 'all' || activeTab === 'should') && shouldDoFiltered.map((t) => (
          <div key={t.topic_id} className="card-panel" style={{ padding: '20px', borderLeft: '4px solid #a1a1aa' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
              <div>
                <span className="badge-should-do" style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', marginRight: '8px' }}>Should-Do</span>
                <span style={{ fontSize: '0.85rem', color: '#a1a1aa', fontFamily: 'monospace' }}>{t.topic_code}</span>
                <h3 style={{ fontSize: '1.15rem', margin: '4px 0 6px 0', color: '#ffffff' }}>{t.topic_name}</h3>
                <p style={{ fontSize: '0.9rem', color: '#a1a1aa', margin: 0 }}>{t.rationale}</p>
              </div>
              <div style={{ textAlign: 'right', minWidth: '100px' }}>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#e4e4e7' }}>{(t.priority_score * 100).toFixed(1)}</div>
                <div style={{ fontSize: '0.75rem', color: '#71717a' }}>Priority Score</div>
              </div>
            </div>
          </div>
        ))}

        {(activeTab === 'all' || activeTab === 'skip') && skipFiltered.map((t) => (
          <div key={t.topic_id} className="card-panel" style={{ padding: '20px', borderLeft: '4px solid #3f3f46' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
              <div>
                <span className="badge-skip" style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', marginRight: '8px' }}>Skip-If-Short</span>
                <span style={{ fontSize: '0.85rem', color: '#71717a', fontFamily: 'monospace' }}>{t.topic_code}</span>
                <h3 style={{ fontSize: '1.15rem', margin: '4px 0 6px 0', color: '#d4d4d8' }}>{t.topic_name}</h3>
                <p style={{ fontSize: '0.9rem', color: '#71717a', margin: 0 }}>{t.rationale}</p>
              </div>
              <div style={{ textAlign: 'right', minWidth: '100px' }}>
                <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#a1a1aa' }}>{(t.priority_score * 100).toFixed(1)}</div>
                <div style={{ fontSize: '0.75rem', color: '#71717a' }}>Priority Score</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

