import { useMemo, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { LoginPanel } from './components/auth/LoginPanel'
import { ChatTab } from './components/chat/ChatTab'
import { DocumentsTab } from './components/documents/DocumentsTab'
import { DriveTab } from './components/drive/DriveTab'
import { VisionTab } from './components/vision/VisionTab'
import { TabBar } from './components/layout/TabBar'
import { AuthProvider, useAuth } from './context/AuthContext'

const queryClient = new QueryClient()

const FEATURE_VISION = String(import.meta.env.VITE_FEATURE_VISION ?? '').toLowerCase() === 'true'

function AppInner() {
  const { session } = useAuth()
  const [activeTab, setActiveTab] = useState('chat')

  const tabs = useMemo(() => {
    const base = [
      { id: 'chat', label: 'Ask' },
      { id: 'documents', label: 'Documents' },
      { id: 'drive', label: 'Google Drive' },
    ]
    if (FEATURE_VISION) base.push({ id: 'vision', label: 'Photo analysis (preview)' })
    return base
  }, [])

  if (!session) {
    return (
      <div style={{ maxWidth: 560, margin: '0 auto', padding: '32px 20px', fontFamily: 'system-ui, sans-serif' }}>
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 24, fontWeight: 650, margin: '0 0 6px', color: '#0969da' }}>
            TrueAI
          </h1>
          <p style={{ margin: 0, color: '#57606a', fontSize: 14 }}>Document RAG workspace — sign in to continue.</p>
        </header>
        <LoginPanel />
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 920, margin: '0 auto', padding: '20px 24px', fontFamily: 'system-ui, sans-serif' }}>
      <header
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '16px 24px',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#0969da', margin: '0 0 6px 0' }}>TrueAI</h1>
          <p style={{ margin: 0, color: '#57606a', fontSize: 13 }}>RAG on your ingested reports</p>
        </div>
        <LoginPanel />
      </header>

      <TabBar tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === 'chat' && <ChatTab />}
      {activeTab === 'documents' && <DocumentsTab />}
      {activeTab === 'drive' && <DriveTab />}
      {FEATURE_VISION && activeTab === 'vision' && <VisionTab />}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppInner />
      </AuthProvider>
    </QueryClientProvider>
  )
}
