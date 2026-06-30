import { useMemo, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { LoginPanel } from './components/auth/LoginPanel'
import { ChatTab } from './components/chat/ChatTab'
import { DocumentsTab } from './components/documents/DocumentsTab'
import { DriveTab } from './components/drive/DriveTab'
import { DemoGate } from './components/layout/DemoGate'
import { PreferencesTab } from './components/preferences/PreferencesTab'
import { ReportWriterTab } from './components/report-writer/ReportWriterTab'
import { VisionTab } from './components/vision/VisionTab'
import { TabBar } from './components/layout/TabBar'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'

const queryClient = new QueryClient()

const FEATURE_VISION = String(import.meta.env.VITE_FEATURE_VISION ?? '').toLowerCase() === 'true'

const TAB_FEATURE_LABELS: Record<string, string> = {
  'report-writer': 'Report Writer',
  documents: 'Documents',
  drive: 'Google Drive',
  vision: 'Photo analysis',
}

function AppInner() {
  const { session, passwordRecovery, publicConfig } = useAuth()
  const [activeTab, setActiveTab] = useState('chat')

  const demoMode = !!publicConfig?.demo_mode
  const enabledTabs = publicConfig?.enabled_tabs
  const demoGateMessage =
    publicConfig?.demo_gate_message ??
    '{feature} is available in the full version. Contact us for details.'

  const tabs = useMemo(() => {
    const base = [
      { id: 'chat', label: 'Search' },
      { id: 'report-writer', label: 'Report Writer' },
      { id: 'documents', label: 'Documents' },
      { id: 'drive', label: 'Google Drive' },
    ]
    if (FEATURE_VISION) base.push({ id: 'vision', label: 'Photo analysis (preview)' })
    base.push({ id: 'preferences', label: 'Preferences' })
    return base
  }, [])

  const tabEnabled = (tabId: string) => {
    if (!demoMode) return true
    if (!enabledTabs) return tabId === 'chat' || tabId === 'preferences'
    return enabledTabs.includes(tabId)
  }

  const renderTab = (tabId: string, featureLabel: string, content: React.ReactNode) => {
    if (!tabEnabled(tabId)) {
      return <DemoGate featureName={featureLabel} messageTemplate={demoGateMessage} />
    }
    return content
  }

  if (!session) {
    return (
      <div style={{ maxWidth: 560, margin: '0 auto', padding: '32px 20px', fontFamily: 'system-ui, sans-serif' }}>
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 24, fontWeight: 650, margin: '0 0 6px', color: 'var(--app-primary)' }}>
            TrueAI
          </h1>
          <p style={{ margin: 0, color: 'var(--app-text-muted)', fontSize: 14 }}>
            {demoMode
              ? 'Demo — sign up to search sample inspection reports.'
              : 'Document RAG workspace — sign in to continue.'}
          </p>
        </header>
        <LoginPanel />
      </div>
    )
  }

  if (passwordRecovery) {
    return (
      <div style={{ maxWidth: 560, margin: '0 auto', padding: '32px 20px', fontFamily: 'system-ui, sans-serif' }}>
        <header style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 24, fontWeight: 650, margin: '0 0 6px', color: 'var(--app-primary)' }}>
            Set a new password
          </h1>
          <p style={{ margin: 0, color: 'var(--app-text-muted)', fontSize: 14 }}>
            Signed in as <span style={{ color: 'var(--app-text)' }}>{session.user.email}</span>. Choose a new password to
            finish resetting your account.
          </p>
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
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--app-primary)', margin: '0 0 6px 0' }}>TrueAI</h1>
          <p style={{ margin: 0, color: 'var(--app-text-muted)', fontSize: 13 }}>
            {demoMode ? 'Demo on sample inspection reports' : 'RAG on the shared report library'}
          </p>
        </div>
        <LoginPanel />
      </header>

      {demoMode && (
        <p
          style={{
            margin: '0 0 12px',
            padding: '8px 12px',
            borderRadius: 6,
            fontSize: 12,
            color: 'var(--app-text-muted)',
            background: 'var(--app-surface)',
            border: '1px solid var(--app-border)',
          }}
        >
          Demo — synthetic report library. Search is limited to 10 queries per hour per account.
        </p>
      )}

      <TabBar tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === 'chat' && renderTab('chat', 'Search', <ChatTab />)}
      {activeTab === 'report-writer' &&
        renderTab('report-writer', TAB_FEATURE_LABELS['report-writer'], <ReportWriterTab />)}
      {activeTab === 'documents' &&
        renderTab('documents', TAB_FEATURE_LABELS.documents, <DocumentsTab />)}
      {activeTab === 'drive' && renderTab('drive', TAB_FEATURE_LABELS.drive, <DriveTab />)}
      {FEATURE_VISION &&
        activeTab === 'vision' &&
        renderTab('vision', TAB_FEATURE_LABELS.vision, <VisionTab />)}
      {activeTab === 'preferences' && renderTab('preferences', 'Preferences', <PreferencesTab />)}
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AppInner />
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
