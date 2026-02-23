import { createContext, forwardRef, useCallback, useContext, useImperativeHandle } from 'react'
import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  MessagePrimitive,
  ComposerPrimitive,
  ActionBarPrimitive,
  AttachmentPrimitive,
  useThreadRuntime,
} from '@assistant-ui/react'
import { MarkdownTextPrimitive } from '@assistant-ui/react-markdown'
import remarkGfm from 'remark-gfm'
import { useAGUIRuntime } from '../hooks/useAGUIRuntime'
import { WeatherToolUI } from './tools/WeatherCard'

export interface ChatWindowHandle {
  getMessages: () => Array<{ role: string; content: unknown }>
}

interface ChatWindowProps {
  threadId: string
  initialHistory: Array<{ role: 'user' | 'assistant'; content: unknown }>
  url?: string
}

const RetractContext = createContext<(() => string) | null>(null)

/* ── Icons ───────────────────────────────────────────────────────────────── */
function IconCopy() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="5" y="5" width="9" height="9" rx="1.5" />
      <path d="M10 5V3.5A1.5 1.5 0 008.5 2h-5A1.5 1.5 0 002 3.5v5A1.5 1.5 0 003.5 10H5" />
    </svg>
  )
}

function IconCopied() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 8l3.5 3.5L13 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/* ── Retract button — only on last assistant message ─────────────────────── */
function RetractButton() {
  const retractLast = useContext(RetractContext)
  const threadRuntime = useThreadRuntime()

  const handleRetract = useCallback(() => {
    if (!retractLast) return
    const userText = retractLast()
    if (userText) threadRuntime.composer.setText(userText)
  }, [retractLast, threadRuntime])

  return (
    <button className="aui-action-bar-button" onClick={handleRetract} title="Retract">
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M2 6h8a4 4 0 010 8H6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M5 3L2 6l3 3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  )
}

/* ── User message ─────────────────────────────────────────────────────────── */
function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-user-message-root">
      <div className="aui-user-message-content-wrapper">
        <div className="aui-user-message-content">
          <MessagePrimitive.Parts components={{ Image: UserImage, File: UserFile }} />
        </div>
        <ActionBarPrimitive.Root
          hideWhenRunning
          autohide="never"
          className="aui-user-action-bar-root"
        >
          <ActionBarPrimitive.Copy className="aui-action-bar-button" title="Copy">
            <MessagePrimitive.If copied><IconCopied /></MessagePrimitive.If>
            <MessagePrimitive.If copied={false}><IconCopy /></MessagePrimitive.If>
          </ActionBarPrimitive.Copy>
        </ActionBarPrimitive.Root>
      </div>
    </MessagePrimitive.Root>
  )
}

function UserImage({ image }: { image: string }) {
  return <img src={image} alt="attachment" className="user-attachment-img" />
}

function UserFile({ filename, mimeType }: { filename?: string; data: string; mimeType: string }) {
  const icon = mimeType?.startsWith('text/') || mimeType === 'application/pdf' ? '📄'
    : mimeType === 'application/json' ? '📋'
    : mimeType?.startsWith('audio/') ? '🎵'
    : mimeType?.startsWith('video/') ? '🎬'
    : '📎'
  return <span className="user-attachment-file">{icon} {filename || 'file'}</span>
}

/* ── Chain-of-thought ────────────────────────────────────────────────────── */
function ReasoningText({ text }: { text: string }) {
  return <div className="thinking-text">{text}</div>
}

/* ── Assistant message ───────────────────────────────────────────────────── */
function ToolFallback({ toolName, args }: { toolName: string; args: Record<string, unknown> }) {
  return (
    <details className="thinking-block">
      <summary className="thinking-summary">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" className="thinking-chevron">
          <path d="M2.5 4.5L6 8l3.5-3.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        🔧 {toolName}
      </summary>
      <pre style={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', opacity: 0.7 }}>
        {JSON.stringify(args, null, 2)}
      </pre>
    </details>
  )
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="aui-assistant-message-root">
      <div className="aui-assistant-message-content">
        <MessagePrimitive.Parts
          components={{
            Text: () => <MarkdownTextPrimitive className="aui-md" remarkPlugins={[remarkGfm]} />,
            Reasoning: ReasoningText,
            ReasoningGroup: ({ children }) => (
              <details className="thinking-block">
                <summary className="thinking-summary">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" className="thinking-chevron">
                    <path d="M2.5 4.5L6 8l3.5-3.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Thinking
                </summary>
                {children}
              </details>
            ),
            tools: { Fallback: ToolFallback },
          }}
        />
      </div>
      <div className="aui-assistant-message-footer">
        {/* Copy + Retract — both hover-visible; Retract guards itself to last message only */}
        <ActionBarPrimitive.Root
          hideWhenRunning
          autohide="never"
          className="aui-assistant-action-bar-root"
        >
          <ActionBarPrimitive.Copy className="aui-action-bar-button" title="Copy">
            <MessagePrimitive.If copied><IconCopied /></MessagePrimitive.If>
            <MessagePrimitive.If copied={false}><IconCopy /></MessagePrimitive.If>
          </ActionBarPrimitive.Copy>
          <MessagePrimitive.If last>
            <RetractButton />
          </MessagePrimitive.If>
        </ActionBarPrimitive.Root>
      </div>
    </MessagePrimitive.Root>
  )
}

/* ── Thread ──────────────────────────────────────────────────────────────── */
function Thread() {
  return (
    <ThreadPrimitive.Root className="aui-thread-root">
      <ThreadPrimitive.Viewport className="aui-thread-viewport">
        <ThreadPrimitive.Empty>
          <div className="aui-thread-welcome-root">
            <div className="aui-thread-welcome-center">
              <p className="aui-thread-welcome-message">Start a conversation…</p>
            </div>
          </div>
        </ThreadPrimitive.Empty>

        <ThreadPrimitive.Messages
          components={{ UserMessage, AssistantMessage }}
        />

        <ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer">
          <ThreadPrimitive.ScrollToBottom className="aui-thread-scroll-to-bottom" />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>

      <ComposerPrimitive.Root className="aui-composer-root">
        <ComposerPrimitive.Attachments
          components={{
            Attachment: () => (
              <div className="composer-attachment-chip">
                <span className="composer-attachment-name">📎 <AttachmentPrimitive.Name /></span>
                <AttachmentPrimitive.Remove className="composer-attachment-remove">✕</AttachmentPrimitive.Remove>
              </div>
            ),
          }}
        />
        <ComposerPrimitive.AttachmentDropzone className="aui-composer-attachment-dropzone">
          <ComposerPrimitive.AddAttachment className="composer-add-attachment" title="Attach file">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3.5 13V4.5a3 3 0 016 0V12a1.5 1.5 0 01-3 0V5.5a.75.75 0 011.5 0v5" strokeLinecap="round" />
            </svg>
          </ComposerPrimitive.AddAttachment>
          <ComposerPrimitive.Input
            className="aui-composer-input"
            placeholder="Type a message…"
          />
          <div className="aui-composer-action-wrapper">
            <ComposerPrimitive.Cancel className="aui-composer-cancel">
              <span className="aui-composer-cancel-icon">■</span>
            </ComposerPrimitive.Cancel>
            <ComposerPrimitive.Send className="aui-composer-send">
              <svg className="aui-composer-send-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M13 8L3 3l2 5-2 5 10-5z" strokeLinejoin="round" />
              </svg>
            </ComposerPrimitive.Send>
          </div>
        </ComposerPrimitive.AttachmentDropzone>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  )
}

/* ── ChatWindow ──────────────────────────────────────────────────────────── */
const ChatWindow = forwardRef<ChatWindowHandle, ChatWindowProps>(function ChatWindow(
  { threadId, initialHistory, url = '/api/persona/chat' },
  ref
) {
  const { runtime, getMessages, retractLast } = useAGUIRuntime({
    url,
    threadId,
    initialMessages: initialHistory,
  })

  useImperativeHandle(ref, () => ({ getMessages }), [getMessages])

  return (
    <RetractContext.Provider value={retractLast}>
      <AssistantRuntimeProvider runtime={runtime}>
        <WeatherToolUI />
        <Thread />
      </AssistantRuntimeProvider>
    </RetractContext.Provider>
  )
})

export default ChatWindow
