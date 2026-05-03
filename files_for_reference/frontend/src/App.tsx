import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TabBar } from './components/layout/TabBar'
import { ChatTab } from './components/chat/ChatTab'
import { DocumentsTab } from './components/documents/DocumentsTab'
import { DriveTab } from './components/drive/DriveTab'
import { VisionTab } from './components/vision/VisionTab'

const queryClient = new QueryClient()

function AppInner() {
  const [activeTab, setActiveTab] = useState('chat')

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '20px 24px', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1976D2', marginBottom: 4, marginTop: 0 }}>
        TrueAI
      </h1>
      <p style={{ color: '#888', fontSize: 13, marginTop: 0, marginBottom: 20 }}>
        RAG-powered Q&amp;A on your engineering reports
      </p>

      <TabBar active={activeTab} onChange={setActiveTab} />

      {activeTab === 'chat' && <ChatTab />}
      {activeTab === 'documents' && <DocumentsTab />}
      {activeTab === 'drive' && <DriveTab />}
      {activeTab === 'vision' && <VisionTab />}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInner />
    </QueryClientProvider>
  )
}
