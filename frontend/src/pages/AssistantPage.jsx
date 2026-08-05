import { useCallback, useEffect, useRef, useState } from 'react'
import { aiApi } from '../api/endpoints'

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
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  async function handleToggle() {
    if (!open && !preview) {
      setLoading(true)
      setError('')
      try {
        const response = await aiApi.previewAssistant()
        setPreview(response.data)
      } catch {
        setError('Impossible de charger l’aperçu.')
      } finally {
        setLoading(false)
      }
    }
    setOpen((o) => !o)
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
      <button
        type="button"
        onClick={handleToggle}
        className="text-xs font-medium text-slate-600 underline decoration-dotted underline-offset-2"
      >
        {open ? 'Masquer' : 'Voir'} les données qui seraient transmises à l’IA
      </button>
      {open && (
        <div className="mt-2">
          {loading && <p className="text-xs text-slate-500">Chargement…</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}
          {preview && (
            <pre className="max-h-64 overflow-auto rounded bg-slate-50 p-3 text-xs text-slate-700">
              {JSON.stringify(preview, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
          isUser ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-800'
        }`}
      >
        {message.content}
      </div>
    </div>
  )
}

export default function AssistantPage() {
  const [aiEnabled, setAiEnabled] = useState(null)
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const poll = usePolling()

  const init = useCallback(async () => {
    setLoading(true)
    setError('')
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
      setError('Impossible de charger l’assistant.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    init()
  }, [init])

  async function handleSend(event) {
    event.preventDefault()
    const text = input.trim()
    if (!text || sending) return

    setSending(true)
    setError('')
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
          setError("L'assistant n'a pas pu répondre — réessayez dans un instant.")
        }
        setSending(false)
      })
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(detail || "Impossible d'envoyer ce message.")
      setSending(false)
    }
  }

  if (loading) {
    return <p className="text-slate-500">Chargement…</p>
  }

  if (!aiEnabled) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900">Assistant</h1>
        <p className="text-slate-600">
          L’IA est désactivée pour cette entreprise. Un administrateur peut l’activer depuis la
          page Documents.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Assistant</h1>
        <p className="mt-1 text-sm text-slate-500">
          Posez vos questions sur votre conformité — l’assistant s’appuie sur vos scores, écarts et
          alertes, et vous oriente vers un professionnel pour ce qui dépasse son périmètre.
        </p>
      </div>

      <PreviewPanel />

      <div className="flex min-h-[400px] flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <p className="text-sm text-slate-500">
              Posez votre première question, par exemple « Suis-je en conformité RGPD ? ».
            </p>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}
          {sending && <p className="text-xs text-slate-500">L’assistant réfléchit…</p>}
        </div>

        <form onSubmit={handleSend} className="flex gap-2 border-t border-slate-200 p-3">
          <input
            aria-label="Votre question pour l’assistant"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            placeholder="Écrivez votre question…"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Envoyer
          </button>
        </form>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
