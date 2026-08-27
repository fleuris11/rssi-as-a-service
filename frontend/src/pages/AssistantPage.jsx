import { Bot, ChevronDown, ChevronUp, Send, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi } from '../api/endpoints'
import FeatureGate from '../components/FeatureGate'
import Card from '../components/ui/Card'
import { useToast } from '../components/ui/Toast'

const SUGGESTIONS = [
  'Suis-je en conformité RGPD ?',
  'Quelles sont mes actions prioritaires ?',
  'Mon site est-il bien sécurisé ?',
]

function usePolling() {
  const timeoutRef = useRef(null)

  useEffect(() => () => clearTimeout(timeoutRef.current), [])

  const poll = useCallback((jobId, onSettled) => {
    async function tick() {
      try {
        const response = await aiApi.getJob(jobId)
        if (response.data.status === 'done' || response.data.status === 'failed') {
          onSettled(response.data)
          return
        }
      } catch {
        // Hiccup réseau ponctuel — le job existe toujours côté serveur, on continue.
      }
      timeoutRef.current = setTimeout(tick, 2000)
    }
    tick()
  }, [])

  return poll
}

function PreviewPanel() {
  const { showToast } = useToast()
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  async function handleToggle() {
    if (!open && !preview) {
      setLoading(true)
      try {
        const response = await aiApi.previewAssistant()
        setPreview(response.data)
      } catch {
        showToast({ type: 'error', message: 'Impossible de charger l’aperçu.' })
      } finally {
        setLoading(false)
      }
    }
    setOpen((o) => !o)
  }

  return (
    <Card padding="p-4">
      <button
        type="button"
        onClick={handleToggle}
        className="transition-smooth flex items-center gap-1 text-xs font-medium text-ink-600 hover:text-brand-700"
      >
        {open ? <ChevronUp className="size-3.5" aria-hidden="true" /> : <ChevronDown className="size-3.5" aria-hidden="true" />}
        {open ? 'Masquer' : 'Voir'} les données qui seraient transmises à l’IA
      </button>
      {open && (
        <div className="mt-2">
          {loading && <p className="text-xs text-ink-500">Chargement…</p>}
          {preview && (
            <pre className="max-h-64 overflow-auto rounded bg-ink-50 p-3 text-xs text-ink-700">
              {JSON.stringify(preview, null, 2)}
            </pre>
          )}
        </div>
      )}
    </Card>
  )
}

function AssistantAvatar() {
  return (
    <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white">
      <Bot className="size-4" aria-hidden="true" />
    </div>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex items-end gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && <AssistantAvatar />}
      <div
        className={`max-w-[75%] whitespace-pre-wrap rounded-lg px-3.5 py-2.5 text-sm ${
          isUser ? 'bg-brand-700 text-white' : 'bg-ink-100 text-ink-800'
        }`}
      >
        {message.content}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2">
      <AssistantAvatar />
      <div className="flex items-center gap-1 rounded-lg bg-ink-100 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 animate-bounce rounded-full bg-ink-400"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  )
}

export default function AssistantPage() {
  const { showToast } = useToast()
  const [aiEnabled, setAiEnabled] = useState(null)
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const scrollRef = useRef(null)
  const poll = usePolling()

  const init = useCallback(async () => {
    setLoading(true)
    try {
      const settingsRes = await aiApi.getSettings()
      setAiEnabled(settingsRes.data.ai_enabled)
      if (!settingsRes.data.ai_enabled) {
        setLoading(false)
        return
      }

      const conversationsRes = await aiApi.listConversations()
      let conversation = conversationsRes.data.results[0]
      if (!conversation) {
        const created = await aiApi.createConversation()
        conversation = created.data
      }
      setConversationId(conversation.id)

      const messagesRes = await aiApi.listMessages(conversation.id)
      setMessages(messagesRes.data.results)
    } catch {
      showToast({ type: 'error', message: 'Impossible de charger l’assistant.' })
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    init()
  }, [init])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, sending])

  async function sendText(text) {
    if (!text || sending) return
    setSending(true)
    try {
      const response = await aiApi.sendMessage(conversationId, text)
      const { message: userMessage, job } = response.data
      setMessages((prev) => [...prev, userMessage])
      setInput('')

      poll(job.id, async (finishedJob) => {
        if (finishedJob.status === 'done') {
          const messagesRes = await aiApi.listMessages(conversationId)
          setMessages(messagesRes.data.results)
        } else {
          showToast({ type: 'error', message: 'L’assistant n’a pas pu répondre — réessayez dans un instant.' })
        }
        setSending(false)
      })
    } catch (err) {
      showToast({ type: 'error', message: err.response?.data?.detail || 'Impossible d’envoyer ce message.' })
      setSending(false)
    }
  }

  function handleSend(event) {
    event.preventDefault()
    sendText(input.trim())
  }

  if (loading) {
    return (
      <div className="h-96 animate-pulse rounded-lg bg-ink-100" />
    )
  }

  if (!aiEnabled) {
    return (
      <div className="space-y-2">
        <h1 className="font-display text-2xl font-semibold text-ink-900">Assistant</h1>
        <p className="text-ink-600">
          L’IA est désactivée pour cette entreprise. Un administrateur peut l’activer depuis la
          page Documents.
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-8.5rem)] flex-col gap-4">
      <div>
        <h1 className="font-display text-2xl font-semibold text-ink-900">Assistant</h1>
        <p className="mt-1 text-sm text-ink-500">
          Posez vos questions sur votre conformité — l’assistant s’appuie sur vos scores, écarts et
          alertes, et vous oriente vers un professionnel pour ce qui dépasse son périmètre.
        </p>
      </div>

      <PreviewPanel />

      <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-ink-200 bg-surface shadow-soft">
        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="flex size-11 items-center justify-center rounded-full bg-brand-100 text-brand-700">
                <Sparkles className="size-5" aria-hidden="true" />
              </div>
              <p className="mt-3 text-sm text-ink-500">
                Posez votre première question à l’assistant.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => sendText(suggestion)}
                    className="transition-smooth rounded-full border border-ink-200 px-3 py-1.5 text-xs font-medium text-ink-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}
          {sending && <TypingIndicator />}
        </div>

        {/* La zone de saisie est désactivée hors offre, jamais retirée :
            l'historique des échanges reste lisible, et le client voit que
            l'assistant existe. */}
        <FeatureGate feature="assistant">
        <form onSubmit={handleSend} className="flex gap-2 border-t border-ink-200 p-3">
          <input
            aria-label="Votre question pour l’assistant"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            placeholder="Écrivez votre question…"
            className="transition-smooth flex-1 rounded-md border border-ink-200 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-brand-600 disabled:bg-ink-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            aria-label="Envoyer"
            className="transition-smooth flex items-center justify-center rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-brand-600/45"
          >
            <Send className="size-4" aria-hidden="true" />
          </button>
        </form>
        </FeatureGate>
      </div>
    </div>
  )
}
