import { Component, ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: '100vh', background: '#0c0a08', color: '#e8ddd0',
          fontFamily: 'monospace', flexDirection: 'column', gap: '16px', padding: '32px',
        }}>
          <div style={{ color: '#e07070', fontSize: '16px', fontWeight: 600 }}>
            Runtime Error
          </div>
          <pre style={{
            background: '#1a1714', border: '1px solid #2a2520', borderRadius: '4px',
            padding: '16px', fontSize: '12px', maxWidth: '700px', overflow: 'auto',
            color: '#d4c9bc', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {this.state.error.message}
            {'\n\n'}
            {this.state.error.stack}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '8px 16px', background: '#c8882a', border: 'none',
              borderRadius: '3px', color: '#0c0a08', cursor: 'pointer',
              fontWeight: 600, fontSize: '12px',
            }}
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
