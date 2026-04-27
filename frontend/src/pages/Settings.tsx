import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect, type FormEvent } from 'react'
import { api } from '../api/client'

interface AISettings {
  ai_enabled: boolean
  ai_mode: 'ollama' | 'api_key'
  ai_provider: string | null
  ai_model: string | null
  ollama_url: string
  ollama_model: string
}

export function Settings() {
  const qc = useQueryClient()

  const { data } = useQuery<AISettings>({
    queryKey: ['ai-settings'],
    queryFn: () => api.get('/settings/ai').then((r) => r.data),
  })

  const [form, setForm] = useState<Partial<AISettings>>({})
  useEffect(() => { if (data) setForm(data) }, [data])

  const mutation = useMutation({
    mutationFn: (body: Partial<AISettings>) => api.put('/settings/ai', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-settings'] }),
  })

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    mutation.mutate(form)
  }

  const f = { ...data, ...form }

  return (
    <div className="p-4 sm:p-6 max-w-lg mx-auto">
      <h1 className="text-lg font-semibold mb-6">Impostazioni</h1>

      <form onSubmit={handleSubmit} className="bg-surface border border-white/5 rounded-2xl p-6 space-y-6">
        <p className="text-sm font-medium">Configurazione AI</p>

        {/* Enable toggle */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm">Abilita suggerimenti AI</p>
            <p className="text-muted text-xs mt-0.5">Analisi settimanali automatiche</p>
          </div>
          <button
            type="button"
            onClick={() => setForm((s) => ({ ...s, ai_enabled: !s.ai_enabled }))}
            className={[
              'relative w-11 h-6 rounded-full transition-colors',
              f.ai_enabled ? 'bg-primary' : 'bg-white/10',
            ].join(' ')}
          >
            <span
              className={[
                'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform',
                f.ai_enabled ? 'translate-x-5' : 'translate-x-0',
              ].join(' ')}
            />
          </button>
        </div>

        {f.ai_enabled && (
          <>
            {/* Mode radio */}
            <div className="space-y-2">
              <p className="text-sm text-muted">Modalità</p>
              <div className="flex gap-3">
                {(['ollama', 'api_key'] as const).map((mode) => (
                  <label key={mode} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="ai_mode"
                      checked={f.ai_mode === mode}
                      onChange={() => setForm((s) => ({ ...s, ai_mode: mode }))}
                      className="accent-primary"
                    />
                    <span className="text-sm">{mode === 'ollama' ? 'Ollama (locale)' : 'API Key'}</span>
                  </label>
                ))}
              </div>
            </div>

            {f.ai_mode === 'api_key' && (
              <div className="space-y-3">
                <Field label="Provider" placeholder="openai / anthropic / gemini"
                  value={f.ai_provider ?? ''}
                  onChange={(v) => setForm((s) => ({ ...s, ai_provider: v }))} />
                <Field label="Modello" placeholder="gpt-4o / claude-opus-4-7 / gemini-pro"
                  value={f.ai_model ?? ''}
                  onChange={(v) => setForm((s) => ({ ...s, ai_model: v }))} />
                <Field label="API Key" placeholder="sk-…" type="password"
                  value=""
                  onChange={(v) => setForm((s) => ({ ...s, api_key: v } as Partial<AISettings> & { api_key?: string }))} />
              </div>
            )}

            {f.ai_mode === 'ollama' && (
              <div className="space-y-3">
                <Field label="URL Ollama" placeholder="http://localhost:11434"
                  value={f.ollama_url ?? ''}
                  onChange={(v) => setForm((s) => ({ ...s, ollama_url: v }))} />
                <Field label="Modello" placeholder="llama3.2"
                  value={f.ollama_model ?? ''}
                  onChange={(v) => setForm((s) => ({ ...s, ollama_model: v }))} />
              </div>
            )}
          </>
        )}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="bg-primary hover:bg-primary/90 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {mutation.isPending ? 'Salvataggio…' : 'Salva'}
          </button>
          {mutation.isSuccess && <p className="text-income text-sm self-center">Salvato!</p>}
          {mutation.isError   && <p className="text-expense text-sm self-center">Errore nel salvataggio.</p>}
        </div>
      </form>
    </div>
  )
}

function Field({
  label, value, onChange, placeholder, type = 'text',
}: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs text-muted">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-bg border border-white/10 rounded-lg px-3 py-2 text-sm text-text placeholder:text-muted focus:outline-none focus:border-primary transition-colors"
      />
    </div>
  )
}
