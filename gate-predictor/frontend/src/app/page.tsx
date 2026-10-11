'use client'

import React, { useState, useEffect, useRef } from 'react'
import {
  Zap,
  ChevronDown,
  Moon,
  Sun,
  User,
  BookOpen,
  FileText,
  History as HistoryIcon,
  BarChart3,
  Flame,
  Clock,
  Send,
  Paperclip,
  Download,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Sparkles,
  Play,
  Plus,
  ArrowUpRight,
  HelpCircle,
  Check,
  ChevronRight,
  X
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ExamOption {
  id: string
  name: string
  shortName: string
  category: string
  subjects: string[]
  icon: string
  totalMarks: number
  weightages: Array<{ name: string; pct: number; marks: number; color: string }>
  weakTopics: Array<{ name: string; tag: string; risk: 'High' | 'Medium'; gap: string }>
  nextMock: { name: string; time: string; duration: string; target: string }
  quickPrompts: Array<{ label: string; prompt: string }>
}

interface TopicPriority {
  topic: string
  code: string
  yield: 'Must-Do' | 'Should-Do' | 'Skip-If-Short'
  marks: number
  trend: string
  reason: string
}

interface QuestionItem {
  id: string
  text: string
  type: string
  options: Record<string, string> | null
  correct_option: string
  explanation: string
  topic: string
  difficulty: string
}

interface AIResponseData {
  exam_id: string
  exam_name: string
  prompt_text: string
  insights: string
  topics: TopicPriority[]
  questions: QuestionItem[]
  filename?: string
}

interface ChatMessage {
  id: string
  sender: 'user' | 'assistant'
  timestamp: string
  text: string
  data?: AIResponseData
}

// ── Built-in Exam Metadata Catalog ────────────────────────────────────────────

const EXAM_PRESETS: Record<string, ExamOption> = {
  neet_ug: {
    id: 'neet_ug',
    name: 'NEET UG (Medical Entrance)',
    shortName: 'NEET',
    category: 'Medical UG',
    subjects: ['Biology (Botany & Zoology)', 'Physics', 'Chemistry'],
    icon: '🧬',
    totalMarks: 720,
    weightages: [
      { name: 'Biology (Botany & Zoology)', pct: 50, marks: 360, color: '#10b981' },
      { name: 'Chemistry', pct: 25, marks: 180, color: '#8b5cf6' },
      { name: 'Physics', pct: 25, marks: 180, color: '#f59e0b' },
    ],
    weakTopics: [
      { name: 'Genetics & Molecular Biology', tag: 'High-Yield (18%)', risk: 'High', gap: 'Gap: 2 yrs' },
      { name: 'Rotational Dynamics & Torque', tag: 'Error Rate 58%', risk: 'High', gap: 'Recency: Recent' },
      { name: 'Chemical Kinetics & Equilibrium', tag: 'Consistent Yield', risk: 'Medium', gap: 'Gap: 1 yr' },
    ],
    nextMock: {
      name: 'NEET All-India Simulation #4',
      time: 'Tomorrow, 10:00 AM',
      duration: '180 mins',
      target: '≥ 640 / 720',
    },
    quickPrompts: [
      { label: 'Mock Test', prompt: 'Create a 10-question high-yield mock test for NEET Biology & Chemistry with full step-by-step solution keys.' },
      { label: 'Must-Do Topics', prompt: 'List the Must-Do, Should-Do, and Skip-If-Short topic breakdown for NEET Botany, Zoology, and Physics.' },
      { label: '30-Day Plan', prompt: 'Formulate an evidence-based 30-day revision schedule targeting 650+ score in NEET UG.' },
    ],
  },
  jee_main: {
    id: 'jee_main',
    name: 'JEE Main (Engineering UG)',
    shortName: 'JEE',
    category: 'Engineering UG',
    subjects: ['Mathematics', 'Physics', 'Chemistry'],
    icon: '🚀',
    totalMarks: 300,
    weightages: [
      { name: 'Mathematics', pct: 34, marks: 100, color: '#3b82f6' },
      { name: 'Physics', pct: 33, marks: 100, color: '#f59e0b' },
      { name: 'Chemistry', pct: 33, marks: 100, color: '#10b981' },
    ],
    weakTopics: [
      { name: 'Electromagnetic Induction & AC', tag: 'High Marks Yield', risk: 'High', gap: 'Gap: 1 yr' },
      { name: 'Definite Integrals & Areas', tag: 'NAT Trap Pattern', risk: 'High', gap: 'Recency: Constant' },
      { name: 'Coordination Compounds & Bonding', tag: 'Accuracy 52%', risk: 'Medium', gap: 'Recency: High' },
    ],
    nextMock: {
      name: 'JEE Main All-India Mock #6',
      time: 'Tomorrow, 09:00 AM',
      duration: '180 mins',
      target: '≥ 210 / 300',
    },
    quickPrompts: [
      { label: 'Mock Test', prompt: 'Generate a 10-question high-yield JEE Physics and Mathematics mock test with numerical NAT questions.' },
      { label: 'Must-Do Topics', prompt: 'Breakdown JEE Main topics into Must-Do, Should-Do, and Skip chapters based on past 5 years trend.' },
      { label: 'Formula Drill', prompt: 'Provide a high-speed formula and concept check for Electromagnetism and Calculus.' },
    ],
  },
  gate_cs: {
    id: 'gate_cs',
    name: 'GATE (Computer Science & IT)',
    shortName: 'GATE',
    category: 'Engineering PG',
    subjects: ['Core CS', 'Engineering Math', 'General Aptitude'],
    icon: '⚡',
    totalMarks: 100,
    weightages: [
      { name: 'Core CS Subjects', pct: 70, marks: 70, color: '#8b5cf6' },
      { name: 'General Aptitude', pct: 15, marks: 15, color: '#f59e0b' },
      { name: 'Engineering Mathematics', pct: 15, marks: 15, color: '#3b82f6' },
    ],
    weakTopics: [
      { name: 'Virtual Memory & TLB Paging', tag: 'Must-Do (~6.5 Marks)', risk: 'High', gap: 'Recency: 2024' },
      { name: 'Dynamic Programming & Graphs', tag: 'Yield: 5.0 Marks', risk: 'High', gap: 'Recency: Constant' },
      { name: 'B-Trees & Indexing (DBMS)', tag: 'Accuracy 49%', risk: 'Medium', gap: 'Gap: 1 yr' },
    ],
    nextMock: {
      name: 'GATE CS Blueprint Mock #2',
      time: 'Tomorrow, 02:00 PM',
      duration: '180 mins',
      target: '≥ 68 / 100',
    },
    quickPrompts: [
      { label: 'Mock Test', prompt: 'Assemble a 15-question GATE CS mock paper covering Operating Systems, DBMS, and Algorithms.' },
      { label: 'Must-Do Topics', prompt: 'Show topic priority scores and buckets (Must-Do ~60%, Should-Do ~25%, Skip ~15%) for GATE CS.' },
      { label: 'Scoring Rules', prompt: 'Explain official GATE negative marking strategy (+1/-1/3, +2/-2/3, MSQ/NAT zero penalty).' },
    ],
  },
  upsc_csat: {
    id: 'upsc_csat',
    name: 'UPSC Civil Services (CSAT / GS)',
    shortName: 'UPSC',
    category: 'Civil Services',
    subjects: ['Reading Comprehension', 'Quantitative Aptitude', 'Logical Reasoning'],
    icon: '🏛️',
    totalMarks: 200,
    weightages: [
      { name: 'Reading Comprehension', pct: 40, marks: 80, color: '#6366f1' },
      { name: 'Quantitative Aptitude', pct: 35, marks: 70, color: '#10b981' },
      { name: 'Logical Reasoning & DI', pct: 25, marks: 50, color: '#f59e0b' },
    ],
    weakTopics: [
      { name: 'Number Systems & Permutations', tag: 'CSAT Qualifying Trap', risk: 'High', gap: 'Recency: High' },
      { name: 'Passage Inference & Assumptions', tag: 'Time Trap Pattern', risk: 'High', gap: 'Constant' },
      { name: 'Syllogisms & Analytical Puzzles', tag: 'Accuracy 60%', risk: 'Medium', gap: 'Gap: 1 yr' },
    ],
    nextMock: {
      name: 'CSAT Paper II Simulation #3',
      time: 'Sunday, 10:30 AM',
      duration: '120 mins',
      target: '≥ 80 / 200 (Qualifying)',
    },
    quickPrompts: [
      { label: 'Mock Test', prompt: 'Create an 8-question UPSC CSAT test focusing on reading comprehension inferences and number puzzles.' },
      { label: 'Must-Do Topics', prompt: 'Identify the highest-yield chapters needed to safely clear UPSC CSAT 66.7 marks cutoff.' },
      { label: 'Strategy Plan', prompt: 'Provide a time-allocation blueprint for 80 questions in 120 minutes with negative marking control.' },
    ],
  },
  custom_exam: {
    id: 'custom_exam',
    name: 'Custom Exam / Syllabus Upload',
    shortName: 'Custom',
    category: 'General Competitive',
    subjects: ['Domain Knowledge', 'Analytical Reasoning', 'Quantitative & Verbal'],
    icon: '✨',
    totalMarks: 100,
    weightages: [
      { name: 'Core Domain', pct: 50, marks: 50, color: '#06b6d4' },
      { name: 'Analytical & Problem Solving', pct: 30, marks: 30, color: '#8b5cf6' },
      { name: 'General Aptitude', pct: 20, marks: 20, color: '#f43f5e' },
    ],
    weakTopics: [
      { name: 'Uploaded Syllabus Core Concepts', tag: 'Analyze via PDF', risk: 'High', gap: 'Custom' },
      { name: 'High-Weightage Domain Questions', tag: 'RAG Extraction', risk: 'Medium', gap: 'Recent' },
    ],
    nextMock: {
      name: 'Custom Diagnostic Mock #1',
      time: 'On-Demand',
      duration: '60 mins',
      target: '≥ 75%',
    },
    quickPrompts: [
      { label: 'Mock Test', prompt: 'Generate a diagnostic 10-question practice test from my uploaded syllabus topics.' },
      { label: 'Must-Do Topics', prompt: 'Breakdown the core topics into High, Medium, and Low yield based on standard exam patterns.' },
      { label: 'Plan', prompt: 'Design a structured 4-week preparation timeline tailored for this custom syllabus.' },
    ],
  },
}

// ── Lightweight Markdown Renderer ─────────────────────────────────────────────

function RenderMarkdown({ content }: { content: string }) {
  if (!content) return null

  // Split lines
  const lines = content.split('\n')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', lineHeight: 1.6 }}>
      {lines.map((line, idx) => {
        const trimmed = line.trim()
        if (!trimmed) {
          return <div key={idx} style={{ height: '4px' }} />
        }

        // Headers
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={idx} style={{ fontSize: '0.95rem', fontWeight: 700, margin: '6px 0 2px', color: 'var(--text-main)' }}>
              {formatInlineText(trimmed.replace('### ', ''))}
            </h4>
          )
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={idx} style={{ fontSize: '1.05rem', fontWeight: 800, margin: '8px 0 3px', color: 'var(--text-main)' }}>
              {formatInlineText(trimmed.replace('## ', ''))}
            </h3>
          )
        }
        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={idx} style={{ fontSize: '1.15rem', fontWeight: 800, margin: '10px 0 4px', color: 'var(--text-main)' }}>
              {formatInlineText(trimmed.replace('# ', ''))}
            </h2>
          )
        }

        // Bullet points
        if (trimmed.startsWith('- ') || trimmed.startsWith('• ') || trimmed.startsWith('* ')) {
          const text = trimmed.substring(2)
          return (
            <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', paddingLeft: '4px' }}>
              <span style={{ color: 'var(--accent-dim)', fontSize: '0.9rem', lineHeight: '1.6' }}>•</span>
              <span style={{ fontSize: '0.92rem', color: 'var(--text-main)' }}>{formatInlineText(text)}</span>
            </div>
          )
        }

        // Regular paragraph
        return (
          <p key={idx} style={{ margin: 0, fontSize: '0.92rem', color: 'var(--text-main)' }}>
            {formatInlineText(trimmed)}
          </p>
        )
      })}
    </div>
  )
}

function formatInlineText(text: string): React.ReactNode {
  // Regex to match **bold** and `code`
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)

  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} style={{ color: 'var(--accent-primary)', fontWeight: 700 }}>
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          style={{
            background: 'var(--bg-elevated)',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '0.85em',
            fontFamily: 'monospace',
            color: 'var(--accent-secondary)',
          }}
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}

// ── SVG Donut Chart Component ─────────────────────────────────────────────────

function DonutChart({
  weightages,
  totalMarks,
}: {
  weightages: Array<{ name: string; pct: number; marks: number; color: string }>
  totalMarks: number
}) {
  const size = 160
  const strokeWidth = 22
  const radius = (size - strokeWidth) / 2
  const center = size / 2
  const circumference = 2 * Math.PI * radius

  let accumulatedPct = 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px', width: '100%' }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
          {/* Background Track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="transparent"
            stroke="var(--bg-elevated)"
            strokeWidth={strokeWidth}
          />
          {/* Segments */}
          {weightages.map((item, idx) => {
            const strokeDasharray = `${(item.pct / 100) * circumference} ${circumference}`
            const strokeDashoffset = -((accumulatedPct / 100) * circumference)
            accumulatedPct += item.pct

            return (
              <circle
                key={idx}
                cx={center}
                cy={center}
                r={radius}
                fill="transparent"
                stroke={item.color}
                strokeWidth={strokeWidth}
                strokeDasharray={strokeDasharray}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{
                  transition: 'stroke-dasharray 0.4s ease, stroke-dashoffset 0.4s ease',
                }}
              />
            )
          })}
        </svg>

        {/* Center Marks Metric */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            textAlign: 'center',
          }}
        >
          <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
            {totalMarks}
          </span>
          <span style={{ fontSize: '0.65rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Total Marks
          </span>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
        {weightages.map((item, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.78rem',
              color: 'var(--text-muted)',
              padding: '4px 6px',
              borderRadius: '6px',
              background: 'rgba(255, 255, 255, 0.02)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: item.color,
                  display: 'inline-block',
                }}
              />
              <span style={{ color: 'var(--text-main)', fontWeight: 500 }}>{item.name}</span>
            </div>
            <span style={{ fontWeight: 700, color: 'var(--text-main)' }}>
              {item.pct}% <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>({item.marks}m)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main 3-Column Page Component ──────────────────────────────────────────────

export default function AIDashboardPage() {
  // Theme State
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')

  // Exam Selection
  const [selectedExamKey, setSelectedExamKey] = useState<string>('neet_ug')
  const [dropdownOpen, setDropdownOpen] = useState(false)

  // Current Exam Configuration
  const currentExam = EXAM_PRESETS[selectedExamKey] || EXAM_PRESETS.neet_ug

  // Prompt & Chat State
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [pdfUploading, setPdfUploading] = useState(false)
  const [pdfExporting, setPdfExporting] = useState<string | null>(null)

  // Question Interaction State
  const [selectedOptions, setSelectedOptions] = useState<Record<string, string>>({})
  const [revealedSolutions, setRevealedSolutions] = useState<Record<string, boolean>>({})

  // Modals / Drawers
  const [historyOpen, setHistoryOpen] = useState(false)
  const [customExamModalOpen, setCustomExamModalOpen] = useState(false)
  const [customExamName, setCustomExamName] = useState('')
  const [customExamSubjects, setCustomExamSubjects] = useState('')

  // Mock Tests History Store
  const [mockHistory, setMockHistory] = useState<Array<{ id: string; exam: string; score: string; date: string }>>([
    { id: '1', exam: 'NEET UG Full Mock #3', score: '612 / 720 (85%)', date: 'Yesterday' },
    { id: '2', exam: 'JEE Main Physics Drill', score: '78 / 100 (78%)', date: '2 days ago' },
    { id: '3', exam: 'GATE CS OS & DBMS Mock', score: '56 / 70 (80%)', date: '3 days ago' },
  ])

  // Chat Feed Messages
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-welcome',
      sender: 'assistant',
      timestamp: 'Just now',
      text: `Hello! I am your **AI Exam Predictor & Study Assistant**. I am currently calibrated for **${currentExam.name}**.\n\nYou can ask me to:\n- 🎯 Generate a realistic **Mock Test** with verification keys\n- 📊 Calculate **Must-Do High-Yield Topics** using appearance gap analysis\n- 📑 Upload a **Syllabus / PYQ PDF** for instant RAG extraction\n- 💡 Formulate an evidence-based **Revision Plan**`,
    },
  ])

  const chatEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Toggle Theme
  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(nextTheme)
    document.documentElement.setAttribute('data-theme', nextTheme)
  }

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // When active exam changes, add context note to chat
  const handleSelectExam = (key: string) => {
    setSelectedExamKey(key)
    setDropdownOpen(false)
    const target = EXAM_PRESETS[key]
    if (target) {
      setMessages((prev) => [
        ...prev,
        {
          id: `switch-${Date.now()}`,
          sender: 'assistant',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `Switched target focus to **${target.name}** (${target.category}). Study stats, weightage breakdown, and quick prompts have been recalibrated.`,
        },
      ])
    }
  }

  // Execute AI Prompt Request
  const handlePromptSubmit = async (customPrompt?: string) => {
    const activePrompt = customPrompt || prompt
    if (!activePrompt.trim() || loading) return

    const userMsgId = `user-${Date.now()}`
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: activePrompt,
    }

    setMessages((prev) => [...prev, userMsg])
    setPrompt('')
    setLoading(true)

    try {
      const res = await fetch('/api/v1/ai/prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: activePrompt,
          exam_id: selectedExamKey,
          generate_pdf: false,
        }),
      })

      if (!res.ok) throw new Error('Failed to generate AI response')
      const json = await res.json()
      const aiData: AIResponseData = json.data

      const assistantMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: aiData.insights,
        data: aiData,
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `⚠️ **Error encountered**: ${err.message || 'Unable to connect to AI study pipeline'}. Please verify backend status on port 8000.`,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  // Handle PDF Upload & Analysis
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const uploadMsg: ChatMessage = {
      id: `up-${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: `📄 Uploaded PDF Document: **${file.name}**`,
    }

    setMessages((prev) => [...prev, uploadMsg])
    setPdfUploading(true)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('exam_id', selectedExamKey)

    try {
      const res = await fetch('/api/v1/ai/analyze-pdf', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) throw new Error('Failed to analyze uploaded PDF document')
      const json = await res.json()
      const aiData: AIResponseData = json.data

      const assistantMsg: ChatMessage = {
        id: `ai-pdf-${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `Successfully parsed and performed OCR analysis on **${file.name}**. Key topics extracted and predicted weightages computed below:`,
        data: aiData,
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `⚠️ **PDF Extraction Error**: ${err.message || 'Failed to parse PDF document'}`,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setPdfUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // Handle PDF Export & Download
  const handleExportPDF = async (aiData: AIResponseData, msgId: string) => {
    setPdfExporting(msgId)

    try {
      const res = await fetch('/api/v1/ai/export-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `AI Trend Analysis & Question Paper - ${aiData.exam_name}`,
          exam_name: aiData.exam_name,
          prompt_text: aiData.prompt_text,
          insights: aiData.insights,
          topics: aiData.topics,
          questions: aiData.questions,
        }),
      })

      if (!res.ok) throw new Error('Failed to generate PDF document')
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${aiData.exam_name.replace(/\s+/g, '_')}_Paper_Analysis.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      alert('Error downloading PDF: ' + err.message)
    } finally {
      setPdfExporting(null)
    }
  }

  // Handle Option Select in Question Cards
  const handleSelectOption = (questionId: string, optKey: string) => {
    setSelectedOptions((prev) => ({
      ...prev,
      [questionId]: optKey,
    }))
  }

  // Toggle Solution Reveal
  const toggleRevealSolution = (questionId: string) => {
    setRevealedSolutions((prev) => ({
      ...prev,
      [questionId]: !prev[questionId],
    }))
  }

  // Save Custom Exam
  const handleSaveCustomExam = () => {
    if (!customExamName.trim()) return
    const customSubjectsList = customExamSubjects.split(',').map((s) => s.trim()).filter(Boolean)

    EXAM_PRESETS.custom_exam.name = customExamName
    EXAM_PRESETS.custom_exam.shortName = customExamName.split(' ')[0] || 'Custom'
    if (customSubjectsList.length > 0) {
      EXAM_PRESETS.custom_exam.subjects = customSubjectsList
    }

    setSelectedExamKey('custom_exam')
    setCustomExamModalOpen(false)
    handleSelectExam('custom_exam')
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-primary)',
        color: 'var(--text-main)',
      }}
    >
      {/* ──────────────────────────────────────────────────────────────────────────
          1. SLIM TOP BAR
          ⚡ Logo   [NEET UG ▾]                 Theme 🌙   Profile
      ────────────────────────────────────────────────────────────────────────── */}
      <header
        style={{
          height: '56px',
          borderBottom: '1px solid var(--border-color)',
          background: 'var(--bg-card)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          zIndex: 40,
          flexShrink: 0,
        }}
      >
        {/* Left: Logo & Exam Dropdown Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
          {/* ⚡ Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <span
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-color)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.1rem',
              }}
            >
              ⚡
            </span>
            <span style={{ fontSize: '1.05rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--accent-primary)' }}>
              PaperPilot AI
            </span>
            <span
              style={{
                fontSize: '0.65rem',
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'var(--bg-elevated)',
                color: 'var(--accent-muted)',
                border: '1px solid var(--border-color)',
              }}
            >
              PRO
            </span>
          </div>

          {/* [NEET UG ▾] Exam Dropdown */}
          <div ref={dropdownRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                padding: '6px 14px',
                borderRadius: '8px',
                color: 'var(--text-main)',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <span>{currentExam.icon}</span>
              <span>{currentExam.shortName}</span>
              <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>UG</span>
              <ChevronDown size={14} style={{ color: 'var(--text-dim)' }} />
            </button>

            {/* Dropdown Menu */}
            {dropdownOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 6px)',
                  left: 0,
                  width: '260px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '10px',
                  boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                  padding: '6px',
                  zIndex: 100,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <div style={{ padding: '6px 10px', fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>
                  Select Target Exam
                </div>
                {Object.values(EXAM_PRESETS).map((e) => {
                  const isSelected = selectedExamKey === e.id
                  return (
                    <button
                      key={e.id}
                      onClick={() => handleSelectExam(e.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 10px',
                        borderRadius: '6px',
                        border: 'none',
                        background: isSelected ? 'var(--bg-elevated)' : 'transparent',
                        color: isSelected ? 'var(--accent-primary)' : 'var(--text-muted)',
                        cursor: 'pointer',
                        textAlign: 'left',
                        fontSize: '0.83rem',
                        fontWeight: isSelected ? 700 : 500,
                        transition: 'background 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>{e.icon}</span>
                        <div>
                          <div>{e.name}</div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>{e.category}</div>
                        </div>
                      </div>
                      {isSelected && <Check size={14} color="var(--accent-primary)" />}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Center: Status indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
          <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
          <span>Gemini 3.5 Flash RAG Active</span>
        </div>

        {/* Right: Theme Toggle & Profile */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Theme 🌙 */}
          <button
            onClick={toggleTheme}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-secondary)',
              color: 'var(--text-main)',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {theme === 'dark' ? <Moon size={15} /> : <Sun size={15} />}
            <span>Theme {theme === 'dark' ? '🌙' : '☀️'}</span>
          </button>

          {/* Profile */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 10px',
              borderRadius: '20px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              cursor: 'pointer',
            }}
          >
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
                color: '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 700,
              }}
            >
              NM
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-main)' }}>Naman</span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>Pro Prep</span>
            </div>
          </div>
        </div>
      </header>

      {/* ──────────────────────────────────────────────────────────────────────────
          2. MAIN 3-COLUMN WORKSPACE
          SIDEBAR  |  MAIN AREA (CHAT + PROMPTS + INPUT)  |  RIGHT PANEL (STATS)
      ────────────────────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* ── LEFT PANEL: SIDEBAR ────────────────────────────────────────────── */}
        <aside
          style={{
            width: '240px',
            borderRight: '1px solid var(--border-color)',
            background: 'var(--bg-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            padding: '20px 14px',
            flexShrink: 0,
            overflowY: 'auto',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
            {/* Exam Section */}
            <div>
              <div
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  color: 'var(--text-dim)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: '10px',
                  paddingLeft: '6px',
                }}
              >
                Exam:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {Object.values(EXAM_PRESETS).map((e) => {
                  const isSelected = selectedExamKey === e.id
                  return (
                    <button
                      key={e.id}
                      onClick={() => handleSelectExam(e.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        border: isSelected ? '1px solid var(--accent-primary)' : '1px solid transparent',
                        background: isSelected ? 'var(--bg-elevated)' : 'transparent',
                        color: isSelected ? 'var(--accent-primary)' : 'var(--text-muted)',
                        fontSize: '0.85rem',
                        fontWeight: isSelected ? 700 : 500,
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span style={{ fontSize: '0.95rem' }}>{e.icon}</span>
                      <span>• {e.shortName}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Tools Section */}
            <div>
              <div
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  color: 'var(--text-dim)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  marginBottom: '10px',
                  paddingLeft: '6px',
                }}
              >
                Tools:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {/* • Mock */}
                <a
                  href="/mock-paper"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    textDecoration: 'none',
                    color: 'var(--text-muted)',
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                >
                  <BookOpen size={15} />
                  <span>• Mock Test</span>
                </a>

                {/* • PDF Ingestion */}
                <button
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                >
                  <FileText size={15} />
                  <span>• PDF Analyzer</span>
                </button>

                {/* • History */}
                <button
                  onClick={() => setHistoryOpen(true)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--text-muted)',
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                >
                  <HistoryIcon size={15} />
                  <span>• History</span>
                </button>

                {/* • GATE Priority Matrix */}
                <a
                  href="/gate-matrix"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '8px 12px',
                    borderRadius: '8px',
                    textDecoration: 'none',
                    color: 'var(--text-muted)',
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-primary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                >
                  <BarChart3 size={15} />
                  <span>• GATE Matrix</span>
                </a>
              </div>
            </div>
          </div>

          {/* Bottom Sidebar Card */}
          <div
            style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              fontSize: '0.75rem',
              color: 'var(--text-dim)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--text-main)', marginBottom: '4px' }}>
              ⚡ RAG & Scoring Active
            </div>
            <div>Official GATE / NTA negative marking rules enforced.</div>
          </div>
        </aside>

        {/* ── CENTER PANEL: MAIN AREA (CHAT + PROMPTS + INPUT) ───────────────── */}
        <main
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            background: 'var(--bg-primary)',
          }}
        >
          {/* Main Area Sub-header: Current Focus */}
          <div
            style={{
              padding: '10px 20px',
              borderBottom: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.82rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>{currentExam.icon}</span>
              <strong style={{ color: 'var(--text-main)' }}>{currentExam.name}</strong>
              <span style={{ color: 'var(--text-dim)' }}>•</span>
              <span style={{ color: 'var(--text-muted)' }}>{currentExam.subjects.join(' • ')}</span>
            </div>
            <span
              style={{
                fontSize: '0.72rem',
                color: 'var(--accent-muted)',
                background: 'var(--bg-elevated)',
                padding: '2px 8px',
                borderRadius: '4px',
                border: '1px solid var(--border-color)',
              }}
            >
              Recency $\lambda=0.15$
            </span>
          </div>

          {/* ┌─ Chat Feed ──────────────────────────────────────────────────┐ */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '20px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
            }}
          >
            {messages.map((msg) => {
              const isUser = msg.sender === 'user'
              return (
                <div
                  key={msg.id}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isUser ? 'flex-end' : 'flex-start',
                    gap: '4px',
                  }}
                >
                  {/* Sender Header */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '0.75rem',
                      color: 'var(--text-dim)',
                    }}
                  >
                    <span style={{ fontWeight: 700, color: isUser ? 'var(--accent-primary)' : 'var(--text-muted)' }}>
                      {isUser ? '👤 You' : '🤖 AI Study Assistant'}
                    </span>
                    <span>• {msg.timestamp}</span>
                  </div>

                  {/* Message Card */}
                  <div
                    style={{
                      maxWidth: isUser ? '85%' : '100%',
                      padding: '16px 20px',
                      borderRadius: '12px',
                      background: isUser ? 'var(--bg-elevated)' : 'var(--bg-card)',
                      border: isUser ? '1px solid var(--border-hover)' : '1px solid var(--border-color)',
                      color: 'var(--text-main)',
                      fontSize: '0.92rem',
                      boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
                    }}
                  >
                    <RenderMarkdown content={msg.text} />

                    {/* Rich Response Output: Topic Matrix, Questions, PDF Action */}
                    {msg.data && (
                      <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                        {/* 1. High-Yield Topic Priority Matrix */}
                        {msg.data.topics && msg.data.topics.length > 0 && (
                          <div>
                            <div
                              style={{
                                fontSize: '0.88rem',
                                fontWeight: 700,
                                color: 'var(--accent-primary)',
                                marginBottom: '10px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                              }}
                            >
                              <BarChart3 size={15} />
                              <span>Topic Priorities & Yield Breakdown</span>
                            </div>

                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                                gap: '10px',
                              }}
                            >
                              {msg.data.topics.map((t, idx) => {
                                const isMust = t.yield === 'Must-Do'
                                const isShould = t.yield === 'Should-Do'
                                const borderCol = isMust ? '#10b981' : isShould ? '#3b82f6' : '#71717a'
                                const badgeBg = isMust ? 'rgba(16, 185, 129, 0.15)' : isShould ? 'rgba(59, 130, 246, 0.15)' : 'rgba(113, 113, 122, 0.15)'
                                const badgeCol = isMust ? '#10b981' : isShould ? '#60a5fa' : '#a1a1aa'

                                return (
                                  <div
                                    key={idx}
                                    style={{
                                      padding: '12px 14px',
                                      borderRadius: '8px',
                                      background: 'var(--bg-secondary)',
                                      border: '1px solid var(--border-color)',
                                      borderLeft: `4px solid ${borderCol}`,
                                    }}
                                  >
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                      <span
                                        style={{
                                          fontSize: '0.7rem',
                                          background: badgeBg,
                                          color: badgeCol,
                                          padding: '2px 6px',
                                          borderRadius: '4px',
                                          fontWeight: 700,
                                        }}
                                      >
                                        {t.yield}
                                      </span>
                                      <span style={{ fontSize: '0.75rem', color: 'var(--text-main)', fontWeight: 600 }}>
                                        {t.trend}
                                      </span>
                                    </div>
                                    <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)' }}>
                                      {t.topic}
                                    </div>
                                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                                      {t.reason}
                                    </div>
                                    <div
                                      style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        fontSize: '0.72rem',
                                        color: 'var(--text-dim)',
                                        marginTop: '8px',
                                      }}
                                    >
                                      <span>
                                        Code: <strong style={{ color: 'var(--text-main)' }}>{t.code}</strong>
                                      </span>
                                      <span>
                                        Est: <strong style={{ color: 'var(--text-main)' }}>{t.marks} Marks</strong>
                                      </span>
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}

                        {/* 2. Interactive Question Bank Cards */}
                        {msg.data.questions && msg.data.questions.length > 0 && (
                          <div>
                            <div
                              style={{
                                fontSize: '0.88rem',
                                fontWeight: 700,
                                color: 'var(--accent-primary)',
                                marginBottom: '10px',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                              }}
                            >
                              <BookOpen size={15} />
                              <span>Practice Question Bank ({msg.data.questions.length} Items)</span>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                              {msg.data.questions.map((q, qIdx) => {
                                const selected = selectedOptions[q.id]
                                const isRevealed = revealedSolutions[q.id]
                                const isCorrect = selected === q.correct_option

                                return (
                                  <div
                                    key={qIdx}
                                    style={{
                                      padding: '14px 16px',
                                      borderRadius: '8px',
                                      background: 'var(--bg-secondary)',
                                      border: '1px solid var(--border-color)',
                                    }}
                                  >
                                    <div
                                      style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        marginBottom: '8px',
                                      }}
                                    >
                                      <span
                                        style={{
                                          fontSize: '0.72rem',
                                          background: 'var(--bg-elevated)',
                                          color: 'var(--text-main)',
                                          padding: '2px 8px',
                                          borderRadius: '4px',
                                          fontWeight: 600,
                                        }}
                                      >
                                        Q{qIdx + 1} • {q.type} • {q.topic}
                                      </span>
                                      <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                                        Difficulty: {q.difficulty}
                                      </span>
                                    </div>

                                    <div
                                      style={{
                                        fontSize: '0.92rem',
                                        fontWeight: 600,
                                        color: 'var(--text-main)',
                                        marginBottom: '10px',
                                      }}
                                    >
                                      {q.text}
                                    </div>

                                    {/* Options Matrix */}
                                    {q.options && (
                                      <div
                                        style={{
                                          display: 'grid',
                                          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                                          gap: '8px',
                                          marginBottom: '10px',
                                        }}
                                      >
                                        {Object.entries(q.options).map(([k, v]) => {
                                          const isChosen = selected === k
                                          const showSuccess = selected && k === q.correct_option
                                          const showWrong = isChosen && !isCorrect

                                          let optBorder = 'var(--border-color)'
                                          let optBg = 'var(--bg-card)'
                                          if (showSuccess) {
                                            optBorder = '#10b981'
                                            optBg = 'rgba(16, 185, 129, 0.1)'
                                          } else if (showWrong) {
                                            optBorder = '#ef4444'
                                            optBg = 'rgba(239, 68, 68, 0.1)'
                                          } else if (isChosen) {
                                            optBorder = 'var(--accent-primary)'
                                            optBg = 'var(--bg-elevated)'
                                          }

                                          return (
                                            <button
                                              key={k}
                                              onClick={() => handleSelectOption(q.id, k)}
                                              style={{
                                                padding: '8px 12px',
                                                borderRadius: '6px',
                                                background: optBg,
                                                border: `1px solid ${optBorder}`,
                                                color: 'var(--text-main)',
                                                fontSize: '0.83rem',
                                                textAlign: 'left',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                                transition: 'all 0.15s ease',
                                              }}
                                            >
                                              <span>
                                                <strong>({k})</strong> {v}
                                              </span>
                                              {showSuccess && <CheckCircle2 size={14} color="#10b981" />}
                                              {showWrong && <XCircle size={14} color="#ef4444" />}
                                            </button>
                                          )
                                        })}
                                      </div>
                                    )}

                                    {/* Reveal Solution Button & Content */}
                                    <div style={{ marginTop: '8px' }}>
                                      <button
                                        onClick={() => toggleRevealSolution(q.id)}
                                        style={{
                                          background: 'transparent',
                                          border: 'none',
                                          color: 'var(--accent-muted)',
                                          fontSize: '0.78rem',
                                          fontWeight: 600,
                                          cursor: 'pointer',
                                          padding: '2px 0',
                                          display: 'flex',
                                          alignItems: 'center',
                                          gap: '4px',
                                        }}
                                      >
                                        <span>{isRevealed ? 'Hide Solution' : 'Reveal Solution & Traps'}</span>
                                        <ChevronDown
                                          size={13}
                                          style={{
                                            transform: isRevealed ? 'rotate(180deg)' : 'none',
                                            transition: 'transform 0.15s ease',
                                          }}
                                        />
                                      </button>

                                      {isRevealed && (
                                        <div
                                          style={{
                                            marginTop: '8px',
                                            padding: '10px 14px',
                                            borderRadius: '6px',
                                            background: 'var(--bg-card)',
                                            borderLeft: '3px solid #10b981',
                                            fontSize: '0.8rem',
                                          }}
                                        >
                                          <div style={{ fontWeight: 700, color: '#10b981', marginBottom: '2px' }}>
                                            Correct Option: ({q.correct_option})
                                          </div>
                                          <div style={{ color: 'var(--text-muted)' }}>{q.explanation}</div>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}

                        {/* 3. PDF Export Action Button */}
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'flex-end',
                            paddingTop: '10px',
                            borderTop: '1px solid var(--border-color)',
                          }}
                        >
                          <button
                            onClick={() => handleExportPDF(msg.data!, msg.id)}
                            disabled={pdfExporting === msg.id}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '8px 16px',
                              borderRadius: '6px',
                              background: 'var(--accent-primary)',
                              color: 'var(--bg-primary)',
                              fontWeight: 700,
                              fontSize: '0.82rem',
                              border: 'none',
                              cursor: pdfExporting === msg.id ? 'wait' : 'pointer',
                            }}
                          >
                            <Download size={14} />
                            <span>{pdfExporting === msg.id ? 'Generating PDF...' : 'Download Report as PDF'}</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {loading && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  color: 'var(--text-muted)',
                  fontSize: '0.85rem',
                  padding: '10px',
                }}
              >
                <Clock size={16} className="animate-spin" />
                <span>Generating AI trend analysis, question bank, and weightage priorities...</span>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Quick prompts (exam-specific) & Input Bar */}
          <div
            style={{
              padding: '14px 20px',
              borderTop: '1px solid var(--border-color)',
              background: 'var(--bg-card)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
          >
            {/* Quick Prompts: [Mock Test] [Must-Do] [Plan] */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>
                Quick Prompts:
              </span>
              {currentExam.quickPrompts.map((qp, idx) => (
                <button
                  key={idx}
                  onClick={() => handlePromptSubmit(qp.prompt)}
                  style={{
                    fontSize: '0.78rem',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-main)',
                    padding: '4px 10px',
                    borderRadius: '14px',
                    cursor: 'pointer',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-hover)'
                    e.currentTarget.style.background = 'var(--bg-elevated)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-color)'
                    e.currentTarget.style.background = 'var(--bg-secondary)'
                  }}
                >
                  <Sparkles size={11} color="var(--accent-muted)" />
                  <span>[{qp.label}]</span>
                </button>
              ))}
            </div>

            {/* Input Bar: [ Upload PDF | Type here | ➤ ] */}
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileUpload}
                disabled={pdfUploading}
                style={{ display: 'none' }}
              />

              {/* Upload PDF button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={pdfUploading}
                title="Upload Syllabus or PYQ PDF for instant RAG extraction"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-main)',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: pdfUploading ? 'wait' : 'pointer',
                  flexShrink: 0,
                  transition: 'all 0.15s ease',
                }}
              >
                <Paperclip size={15} />
                <span>{pdfUploading ? 'Reading...' : 'Upload PDF'}</span>
              </button>

              {/* Text Input Prompt */}
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handlePromptSubmit()
                  }
                }}
                placeholder={`Type your prompt for ${currentExam.shortName}... e.g. 'Generate 10-question mock' or 'Show high-yield topics'`}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-main)',
                  fontSize: '0.88rem',
                  outline: 'none',
                  fontFamily: 'inherit',
                  transition: 'border-color 0.15s ease',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--border-focus)')}
                onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-color)')}
              />

              {/* Send Button ➤ */}
              <button
                onClick={() => handlePromptSubmit()}
                disabled={loading || !prompt.trim()}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '42px',
                  height: '42px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'var(--accent-primary)',
                  color: 'var(--bg-primary)',
                  cursor: loading || !prompt.trim() ? 'not-allowed' : 'pointer',
                  opacity: loading || !prompt.trim() ? 0.5 : 1,
                  flexShrink: 0,
                  transition: 'all 0.15s ease',
                }}
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </main>

        {/* ── RIGHT PANEL: STUDY STATS ───────────────────────────────────────── */}
        <aside
          style={{
            width: '300px',
            borderLeft: '1px solid var(--border-color)',
            background: 'var(--bg-card)',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
            padding: '20px 16px',
            overflowY: 'auto',
            flexShrink: 0,
          }}
        >
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: '0.9rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.01em' }}>
              Study Stats
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                color: 'var(--accent-muted)',
                background: 'var(--bg-secondary)',
                padding: '2px 8px',
                borderRadius: '10px',
                border: '1px solid var(--border-color)',
                fontWeight: 600,
              }}
            >
              {currentExam.shortName} Live
            </span>
          </div>

          <div style={{ height: '1px', background: 'var(--border-color)', margin: '0' }} />

          {/* 1. Subject Weightage (Donut Chart) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: 'var(--text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              Subject Weightage
            </div>
            <DonutChart weightages={currentExam.weightages} totalMarks={currentExam.totalMarks} />
          </div>

          <div style={{ height: '1px', background: 'var(--border-color)' }} />

          {/* 2. Weak Topics */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: 'var(--text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span>Weak Topics</span>
              <span style={{ color: '#ef4444' }}>Priority Focus</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {currentExam.weakTopics.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.83rem', fontWeight: 700, color: 'var(--text-main)' }}>
                      {item.name}
                    </span>
                    <span
                      style={{
                        fontSize: '0.65rem',
                        padding: '1px 5px',
                        borderRadius: '3px',
                        background: item.risk === 'High' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                        color: item.risk === 'High' ? '#ef4444' : '#f59e0b',
                        fontWeight: 700,
                      }}
                    >
                      {item.risk} Risk
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                      {item.tag} • {item.gap}
                    </span>
                    <button
                      onClick={() => handlePromptSubmit(`Generate a 5-question high-yield practice drill for ${item.name} with step-by-step traps and solutions.`)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--accent-brand)',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        padding: 0,
                      }}
                    >
                      Drill ⚡
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ height: '1px', background: 'var(--border-color)' }} />

          {/* 3. Streak 🔥 */}
          <div
            style={{
              padding: '12px',
              borderRadius: '10px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Flame size={17} color="#f97316" />
                <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  5-Day Streak 🔥
                </span>
              </div>
              <span style={{ fontSize: '0.72rem', color: '#10b981', fontWeight: 700 }}>
                Top 5%
              </span>
            </div>

            {/* Day Dots */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2px' }}>
              {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((day, idx) => {
                const isCompleted = idx < 5
                const isToday = idx === 5
                return (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <div
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: isCompleted ? '#f97316' : isToday ? 'var(--bg-elevated)' : 'var(--bg-card)',
                        border: isToday ? '1px solid #f97316' : '1px solid var(--border-color)',
                        color: isCompleted ? '#ffffff' : 'var(--text-dim)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                      }}
                    >
                      {isCompleted ? '✓' : day}
                    </div>
                    <span style={{ fontSize: '0.62rem', color: 'var(--text-dim)' }}>{day}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 4. Next Mock */}
          <div
            style={{
              padding: '14px',
              borderRadius: '10px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <div
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: 'var(--text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              Next Mock
            </div>

            <div style={{ fontSize: '0.88rem', fontWeight: 800, color: 'var(--text-main)' }}>
              {currentExam.nextMock.name}
            </div>

            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              ⏰ {currentExam.nextMock.time} ({currentExam.nextMock.duration})
            </div>

            <div style={{ fontSize: '0.72rem', color: 'var(--accent-muted)' }}>
              Target: <strong style={{ color: 'var(--text-main)' }}>{currentExam.nextMock.target}</strong>
            </div>

            <a
              href="/mock-paper"
              style={{
                marginTop: '4px',
                padding: '8px 12px',
                borderRadius: '6px',
                background: 'var(--accent-primary)',
                color: 'var(--bg-primary)',
                fontWeight: 700,
                fontSize: '0.8rem',
                textDecoration: 'none',
                textAlign: 'center',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
              }}
            >
              <Play size={13} fill="currentColor" />
              <span>Start Mock Test</span>
            </a>
          </div>
        </aside>
      </div>

      {/* ──────────────────────────────────────────────────────────────────────────
          3. HISTORY DRAWER / MODAL
      ────────────────────────────────────────────────────────────────────────── */}
      {historyOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(4px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '520px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-main)' }}>
                📜 Study History & Attempts
              </div>
              <button
                onClick={() => setHistoryOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Recent mock exam attempts and AI verified evaluations across your active subjects.
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {mockHistory.map((h) => (
                <div
                  key={h.id}
                  style={{
                    padding: '12px 14px',
                    borderRadius: '8px',
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-main)' }}>{h.exam}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Completed {h.date}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#10b981' }}>{h.score}</div>
                    <a
                      href="/mock-paper"
                      style={{ fontSize: '0.72rem', color: 'var(--accent-muted)', textDecoration: 'none' }}
                    >
                      Review →
                    </a>
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={() => setHistoryOpen(false)}
              style={{
                padding: '10px',
                borderRadius: '6px',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-main)',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: 'pointer',
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
