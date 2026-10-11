import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Multi-Exam Paper Predictor & Study Assistant (JEE, NEET, GATE, UPSC)',
  description: 'AI-powered trend analyzer, prompt question generator, syllabus PDF parser, and priority matrix for competitive exams.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" data-theme="dark">
      <body>
        {children}
      </body>
    </html>
  )
}

