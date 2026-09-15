import { ArrowRight, Bot, ChevronDown, ChevronUp, Send, ShieldCheck, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { aiApi } from '../api/endpoints'
import FeatureGate from '../components/FeatureGate'
import { useToast } from '../components/ui/Toast'

/**
 * L'assistant (lot C, C4).
 *
 * Trois changements, trois constats :
 *
 * - une zone de saisie vide devant un dirigeant reste vide : les questions de
 *   départ viennent de SA situation (« Que faire de mes 2 compromissions
 *   critiques ? »), calculées par le serveur sans appel d'IA ;
 * - une réponse qui parle de fuites doit mener à l'écran des fuites : les
 *   liens sont déduits côté serveur, d'une liste fermée d'écrans ;
 * - la pseudonymisation est un argument, pas un avertissement : elle est dite
 *   une fois, en début de conversation, en une ligne.
 */

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

/** La ligne dite une fois : ce qui est protégé, et comment le vérifier. */
function RappelPseudonymisation() {
  const { showToast } = useToast()
  const [donnees, setDonnees] = useState(null)
  const [ouvert, setOuvert] = useState(false)

  async function basculer() {
    if (!ouvert && !donnees) {
      try {
        const reponse = await aiApi.previewAssistant()
        setDonnees(reponse.data)
      } catch {
        showToast({ type: 'error', message: 'Impossible de charger les données transmises.' })
        return
      }
    }
    setOuvert((v) => !v)
  }

  return (
    <div className="mt-4 max-w-md text-left">
      <p className="flex items-start gap-1.5 text-xs text-ink-500">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-ok-strong" aria-hidden="true" />
        <span>
          Vos données sont pseudonymisées avant tout traitement externe : les noms, domaines et
          adresses sont remplacés par des marqueurs, puis restaurés dans la réponse.{' '}
          <button
            type="button"
            onClick={basculer}
            aria-expanded={ouvert}
            className="inline-flex items-center gap-0.5 font-medium text-brand-600 hover:text-brand-700"
          >
            Voir ce qui est transmis
            {ouvert ? (
              <ChevronUp className="size-3" aria-hidden="true" />
            ) : (
              <ChevronDown className="size-3" aria-hidden="true" />
            )}
          </button>
        </span>
      </p>
      {ouvert && donnees && (
        <pre className="mt-2 max-h-48 overflow-auto rounded bg-ink-50 p-3 text-xs text-ink-700">
          {JSON.stringify(donnees, null, 2)}
        </pre>
      )}
    </div>
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
      <div className="max-w-[75%]">
        <div
          className={`whitespace-pre-wrap rounded-lg px-3.5 py-2.5 text-sm ${
            isUser ? 'bg-brand-700 text-white' : 'bg-ink-100 text-ink-800'
          }`}
        >
          {message.content}
        </div>
        {/* Lot C, point 18 : la réponse mène à l'écran où l'on agit. */}
        {!isUser && message.links?.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {message.links.map((lien) => (
              <Link
                key={lien.to}
                to={lien.to}
                className="transition-smooth inline-flex items-center gap-1 rounded-full border border-brand-200 bg-surface px-2.5 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50"
              >
                {lien.label}
                <ArrowRight className="size-3" aria-hidden="true" />
              </Link>
            ))}
          </div>
        )}
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
  const [suggestions, setSuggestions] = useState([])
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

      const [conversationsRes, suggestionsRes] = await Promise.all([
        aiApi.listConversations(),
        // Les suggestions ne doivent jamais emporter la page : sans elles,
        // l'assistant reste utilisable.
        aiApi.assistantSuggestions().catch(() => ({ data: { results: [] } })),
      ])
      setSuggestions(suggestionsRes.data.results)

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
    scrollRef.current?.scrollTo?.({ top: scrollRef.current.scrollHeight })
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
    return <div className="h-96 animate-pulse rounded-lg bg-ink-100" />
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
          Posez vos questions sur votre sécurité — l’assistant s’appuie sur vos scores, votre plan
          d’action, vos alertes et vos compromissions, et vous oriente vers un professionnel pour ce
          qui dépasse son périmètre.
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-ink-200 bg-surface shadow-soft">
        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="flex size-11 items-center justify-center rounded-full bg-brand-100 text-brand-700">
                <Sparkles className="size-5" aria-hidden="true" />
              </div>
              <p className="mt-3 text-sm text-ink-700">
                {suggestions.length > 0
                  ? 'Voici ce que la plateforme voit chez vous. Par quoi voulez-vous commencer ?'
                  : 'Posez votre première question à l’assistant.'}
              </p>
              {suggestions.length > 0 && (
                <ul className="mt-4 flex max-w-2xl flex-wrap justify-center gap-2">
                  {suggestions.map((suggestion) => (
                    <li key={suggestion.question}>
                      <button
                        type="button"
                        onClick={() => sendText(suggestion.question)}
                        title={suggestion.reason}
                        className="transition-smooth rounded-full border border-ink-200 px-3 py-1.5 text-sm font-medium text-ink-700 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                      >
                        {suggestion.question}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {/* Point 19 : dit une fois, au début — pas un bandeau répété. */}
              <RappelPseudonymisation />
            </div>
          ) : (
            messages.map((m) => <MessageBubble key={m.id} message={m} />)
          )}
          {sending && <TypingIndicator />}
        </div>

        {/* La zone de saisie est désactivée hors offre, jamais retirée. */}
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
