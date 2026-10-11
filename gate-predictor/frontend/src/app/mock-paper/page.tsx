'use client'

import { useState } from 'react'

interface QuestionItem {
  id: string
  topic_id: string
  qtype: 'MCQ' | 'MSQ' | 'NAT'
  marks: number
  difficulty: string
  text: string
  options: Record<string, string> | null
  source: string
}

interface ScoreReport {
  attempt_id: string
  mock_paper_id: string
  total_score: number
  max_score: number
  accuracy_pct: number
  correct_count: number
  incorrect_count: number
  unattempted_count: number
  total_time_seconds: number
  question_details: Array<{
    question_id: string
    qtype: string
    marks_allocated: number
    marks_obtained: number
    is_correct: boolean
    user_answer: any
    correct_answer: any
    explanation: string
  }>
  weak_topics: Array<{
    topic_id: string
    topic_name: string
    accuracy_pct: number
    priority_bucket: string
  }>
}

export default function MockPaperPage() {
  const [paper, setPaper] = useState<{ id: string; questions: QuestionItem[]; duration_minutes: number } | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [userAnswers, setUserAnswers] = useState<Record<string, any>>({})
  const [report, setReport] = useState<ScoreReport | null>(null)
  const [assembling, setAssembling] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleAssemble = async () => {
    setAssembling(true)
    setReport(null)
    setUserAnswers({})
    try {
      const res = await fetch('/api/v1/mock-papers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ total_questions: 15, total_marks: 25.0 }),
      })
      const data = await res.json()
      
      // Fetch full paper details
      const paperRes = await fetch(`/api/v1/mock-papers/${data.paper_id}`)
      const paperData = await paperRes.json()
      
      setPaper(paperData)
      setCurrentIndex(0)
    } catch (err) {
      alert('Failed to assemble paper: ' + err)
    } finally {
      setAssembling(false)
    }
  }

  const handleSelectOption = (qId: string, qtype: string, key: string) => {
    if (qtype === 'MCQ') {
      setUserAnswers((prev) => ({ ...prev, [qId]: [key] }))
    } else if (qtype === 'MSQ') {
      const current = userAnswers[qId] || []
      const updated = current.includes(key)
        ? current.filter((k: string) => k !== key)
        : [...current, key]
      setUserAnswers((prev) => ({ ...prev, [qId]: updated }))
    }
  }

  const handleNATChange = (qId: string, val: string) => {
    setUserAnswers((prev) => ({ ...prev, [qId]: val ? parseFloat(val) : null }))
  }

  const handleSubmit = async () => {
    if (!paper) return
    setSubmitting(true)

    const answerPayloads = Object.entries(userAnswers).map(([qId, val]) => ({
      question_id: qId,
      user_answer: val,
      time_taken_seconds: 30.0,
    }))

    try {
      const res = await fetch(`/api/v1/mock-papers/${paper.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mock_paper_id: paper.id,
          user_id: 'student_123',
          answers: answerPayloads,
        }),
      })
      const scoreReport = await res.json()
      setReport(scoreReport)
    } catch (err) {
      alert('Failed to score paper: ' + err)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, margin: '0 0 6px 0', color: '#ffffff' }}>
            GATE CS Mock Examination
          </h1>
          <p style={{ color: '#a1a1aa', margin: 0, fontSize: '0.95rem' }}>
            Simulated exam environment adhering strictly to official GATE CS marking rules (MCQ negative marking, MSQ exact matching, NAT range checking).
          </p>
        </div>
        <button
          onClick={handleAssemble}
          disabled={assembling}
          className="btn-primary"
          style={{ padding: '12px 24px', fontSize: '0.95rem' }}
        >
          {assembling ? '⌛ Assembling Blueprint...' : '✨ Generate New Mock Paper'}
        </button>
      </div>

      {/* Start Banner (when no paper active) */}
      {!paper && !report && (
        <div className="card-panel" style={{ padding: '48px 32px', textAlign: 'center', background: '#121215', border: '1px solid #27272a' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '16px' }}>📝</div>
          <h2 style={{ color: '#ffffff', fontSize: '1.4rem', fontWeight: 800, margin: '0 0 8px 0' }}>
            Ready to Attempt a Realistic GATE Mock Paper?
          </h2>
          <p style={{ color: '#a1a1aa', maxWidth: '640px', margin: '0 auto 24px auto', fontSize: '0.95rem', lineHeight: 1.6 }}>
            Click <strong>"Generate New Mock Paper"</strong> above to assemble a 15-question sample exam generated from official GATE Computer Science topic weightage distributions.
          </p>
          <div style={{ display: 'inline-flex', gap: '24px', background: '#09090b', padding: '12px 24px', borderRadius: '8px', border: '1px solid #27272a', fontSize: '0.85rem', color: '#e4e4e7' }}>
            <span>• 1-Mark MCQ (+1 / -0.33)</span>
            <span>• 2-Mark MCQ (+2 / -0.67)</span>
            <span>• MSQ & NAT (No Negative)</span>
          </div>
        </div>
      )}

      {/* Performance Scorecard View */}
      {report && (
        <div style={{ marginBottom: '36px' }}>
          <div className="card-panel" style={{ padding: '32px', marginBottom: '28px', background: '#121215', borderLeft: '6px solid #ffffff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div>
                <h2 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0, color: '#ffffff' }}>🎉 Attempt Performance Scorecard</h2>
                <p style={{ color: '#a1a1aa', fontSize: '0.85rem', margin: '4px 0 0 0' }}>Attempt ID: <code style={{ color: '#ffffff' }}>{report.attempt_id}</code></p>
              </div>
              <button
                onClick={handleAssemble}
                className="btn-primary"
                style={{ padding: '8px 16px', fontSize: '0.85rem' }}
              >
                🔄 Attempt Another Paper
              </button>
            </div>

            {/* Score Stats Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
              <div className="card-panel" style={{ padding: '16px', textAlign: 'center', background: '#09090b' }}>
                <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500 }}>Total Score</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#ffffff', marginTop: '4px' }}>
                  {report.total_score} <span style={{ fontSize: '1rem', color: '#71717a', fontWeight: 500 }}>/ {report.max_score}</span>
                </div>
              </div>

              <div className="card-panel" style={{ padding: '16px', textAlign: 'center', background: '#09090b' }}>
                <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500 }}>Accuracy Rate</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#ffffff', marginTop: '4px' }}>
                  {report.accuracy_pct.toFixed(1)}%
                </div>
              </div>

              <div className="card-panel" style={{ padding: '16px', textAlign: 'center', background: '#09090b' }}>
                <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500 }}>Correct / Incorrect</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#ffffff', marginTop: '4px' }}>
                  <span style={{ color: '#ffffff' }}>{report.correct_count}</span> / <span style={{ color: '#a1a1aa' }}>{report.incorrect_count}</span>
                </div>
              </div>

              <div className="card-panel" style={{ padding: '16px', textAlign: 'center', background: '#09090b' }}>
                <div style={{ fontSize: '0.8rem', color: '#a1a1aa', fontWeight: 500 }}>Unattempted</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#71717a', marginTop: '4px' }}>
                  {report.unattempted_count}
                </div>
              </div>
            </div>

            {/* Recommended Review Topics */}
            {report.weak_topics.length > 0 && (
              <div style={{ background: '#18181b', border: '1px solid #27272a', padding: '16px', borderRadius: '8px' }}>
                <h3 style={{ fontSize: '1rem', color: '#ffffff', margin: '0 0 10px 0', fontWeight: 700 }}>
                  ⚠️ Recommended Priority Review Topics
                </h3>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {report.weak_topics.map((wt) => (
                    <span key={wt.topic_id} className="badge-must-do" style={{ padding: '4px 12px', borderRadius: '14px', fontSize: '0.8rem' }}>
                      {wt.topic_name} ({wt.accuracy_pct.toFixed(0)}% Accuracy)
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Detailed Question Performance Table */}
          <div className="card-panel" style={{ padding: '24px', background: '#121215' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: '0 0 16px 0', color: '#ffffff' }}>
              Detailed Question Analysis
            </h3>
            
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Type</th>
                  <th>Allocated</th>
                  <th>Obtained</th>
                  <th>Status</th>
                  <th>Your Answer</th>
                  <th>Correct Answer</th>
                  <th>Explanation</th>
                </tr>
              </thead>
              <tbody>
                {report.question_details.map((q, idx) => (
                  <tr key={q.question_id}>
                    <td><strong>Q{idx + 1}</strong></td>
                    <td><span style={{ fontSize: '0.75rem', background: '#27272a', color: '#ffffff', padding: '2px 6px', borderRadius: '4px' }}>{q.qtype}</span></td>
                    <td>{q.marks_allocated} M</td>
                    <td style={{ fontWeight: 700, color: q.marks_obtained > 0 ? '#ffffff' : q.marks_obtained < 0 ? '#a1a1aa' : '#71717a' }}>
                      {q.marks_obtained > 0 ? `+${q.marks_obtained}` : q.marks_obtained}
                    </td>
                    <td>
                      {q.is_correct ? (
                        <span style={{ color: '#ffffff', fontWeight: 700 }}>✓ Correct</span>
                      ) : q.user_answer == null ? (
                        <span style={{ color: '#71717a' }}>— Skipped</span>
                      ) : (
                        <span style={{ color: '#a1a1aa', fontWeight: 600 }}>✗ Incorrect</span>
                      )}
                    </td>
                    <td><code>{JSON.stringify(q.user_answer) ?? 'None'}</code></td>
                    <td><code>{JSON.stringify(q.correct_answer)}</code></td>
                    <td style={{ fontSize: '0.8rem', color: '#a1a1aa', maxWidth: '300px' }}>{q.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Exam Interface View */}
      {paper && !report && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px' }}>
          {/* Main Question Workspace */}
          <div className="card-panel" style={{ padding: '32px', background: '#121215' }}>
            {(() => {
              const q = paper.questions[currentIndex]
              const userAns = userAnswers[q.id]
              return (
                <div>
                  {/* Question Header Bar */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', paddingBottom: '14px', borderBottom: '1px solid #27272a' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#ffffff' }}>
                        Question {currentIndex + 1} of {paper.questions.length}
                      </span>
                      <span style={{ background: '#27272a', border: '1px solid #3f3f46', color: '#f4f4f5', padding: '2px 8px', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 600 }}>
                        {q.qtype}
                      </span>
                      <span style={{ background: '#18181b', border: '1px solid #27272a', color: '#ffffff', padding: '2px 8px', borderRadius: '4px', fontSize: '0.8rem', fontWeight: 600 }}>
                        {q.marks} Mark{q.marks > 1 ? 's' : ''}
                      </span>
                    </div>

                    <span style={{ fontSize: '0.8rem', color: '#a1a1aa', background: '#09090b', padding: '4px 10px', borderRadius: '6px', border: '1px solid #27272a' }}>
                      Source: <strong>{q.source.toUpperCase()}</strong>
                    </span>
                  </div>

                  {/* Question Prompt Text */}
                  <p style={{ fontSize: '1.1rem', lineHeight: 1.65, marginBottom: '28px', color: '#ffffff', fontWeight: 400 }}>
                    {q.text}
                  </p>

                  {/* MCQ / MSQ Options */}
                  {q.qtype !== 'NAT' && q.options && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '32px' }}>
                      {Object.entries(q.options).map(([optKey, optText]) => {
                        const isSelected = Array.isArray(userAns) && userAns.includes(optKey)
                        return (
                          <div
                            key={optKey}
                            onClick={() => handleSelectOption(q.id, q.qtype, optKey)}
                            style={{
                              padding: '16px 20px',
                              borderRadius: '8px',
                              border: isSelected ? '2px solid #ffffff' : '1px solid #27272a',
                              background: isSelected ? '#1e1e24' : '#09090b',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '14px',
                              transition: 'all 0.15s ease',
                            }}
                          >
                            <span
                              style={{
                                width: '28px',
                                height: '28px',
                                borderRadius: q.qtype === 'MCQ' ? '50%' : '4px',
                                background: isSelected ? '#ffffff' : '#27272a',
                                color: isSelected ? '#09090b' : '#a1a1aa',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 800,
                                fontSize: '0.85rem',
                              }}
                            >
                              {optKey}
                            </span>
                            <span style={{ color: isSelected ? '#ffffff' : '#e4e4e7', fontSize: '1rem', fontWeight: isSelected ? 600 : 400 }}>{optText}</span>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* NAT Input */}
                  {q.qtype === 'NAT' && (
                    <div style={{ marginBottom: '32px', background: '#09090b', padding: '20px', borderRadius: '8px', border: '1px solid #27272a' }}>
                      <label style={{ display: 'block', fontSize: '0.9rem', color: '#a1a1aa', marginBottom: '10px', fontWeight: 500 }}>
                        Enter Numerical Answer (Numerical Answer Type):
                      </label>
                      <input
                        type="number"
                        step="any"
                        value={userAns ?? ''}
                        onChange={(e) => handleNATChange(q.id, e.target.value)}
                        placeholder="e.g. 4.5"
                        style={{
                          background: '#121215',
                          border: '1px solid #3f3f46',
                          color: '#ffffff',
                          padding: '12px 16px',
                          borderRadius: '6px',
                          fontSize: '1.1rem',
                          width: '220px',
                          outline: 'none',
                          fontFamily: 'inherit',
                        }}
                      />
                    </div>
                  )}

                  {/* Navigation Footer */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #27272a', paddingTop: '20px' }}>
                    <button
                      disabled={currentIndex === 0}
                      onClick={() => setCurrentIndex((prev) => prev - 1)}
                      className="btn-secondary"
                      style={{ opacity: currentIndex === 0 ? 0.5 : 1 }}
                    >
                      ← Previous Question
                    </button>
                    
                    <button
                      disabled={currentIndex === paper.questions.length - 1}
                      onClick={() => setCurrentIndex((prev) => prev + 1)}
                      className="btn-secondary"
                      style={{ opacity: currentIndex === paper.questions.length - 1 ? 0.5 : 1 }}
                    >
                      Next Question →
                    </button>
                  </div>
                </div>
              )
            })()}
          </div>

          {/* Question Palette Sidebar */}
          <div className="card-panel" style={{ padding: '24px', height: 'fit-content', background: '#121215' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, margin: '0 0 16px 0', borderBottom: '1px solid #27272a', paddingBottom: '12px', color: '#ffffff' }}>
              Question Palette
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '20px' }}>
              {paper.questions.map((q, idx) => {
                const isAttempted = userAnswers[q.id] != null
                const isCurrent = idx === currentIndex
                return (
                  <button
                    key={q.id}
                    onClick={() => setCurrentIndex(idx)}
                    style={{
                      padding: '10px 0',
                      borderRadius: '6px',
                      border: isCurrent ? '2px solid #ffffff' : '1px solid #27272a',
                      background: isAttempted ? '#ffffff' : '#09090b',
                      color: isAttempted ? '#09090b' : '#ffffff',
                      fontWeight: 800,
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                    }}
                  >
                    {idx + 1}
                  </button>
                )
              })}
            </div>

            {/* Palette Legend */}
            <div style={{ fontSize: '0.75rem', color: '#a1a1aa', display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '24px', background: '#09090b', padding: '12px', borderRadius: '6px', border: '1px solid #27272a' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#ffffff' }}></span>
                <span>Answered</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#09090b', border: '2px solid #ffffff' }}></span>
                <span>Current Question</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#09090b', border: '1px solid #27272a' }}></span>
                <span>Unanswered</span>
              </div>
            </div>

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="btn-primary"
              style={{
                width: '100%',
                padding: '14px 0',
                justifyContent: 'center',
              }}
            >
              {submitting ? '⌛ Scoring Exam...' : 'Submit & Score Paper'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

