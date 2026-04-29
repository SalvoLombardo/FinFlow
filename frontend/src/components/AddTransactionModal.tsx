import { useEffect, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

interface TransactionCreate {
  name: string
  amount: number
  type: 'income' | 'expense'
  category?: string
  transaction_date?: string
  is_recurring: boolean
  recurrence_rule?: string
  recurrence_end_date?: string
}

interface Transaction {
  id: string
  week_id: string
  name: string
  amount: number
  type: 'income' | 'expense'
  category: string | null
  transaction_date: string | null
  is_recurring: boolean
}

interface Props {
  /** Provided by WeekDetail for optimistic cache updates keyed by week. */
  weekId?: string
  /** Pre-fills the date field (used when opening from a projected week card). */
  defaultDate?: string
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Called after the transaction is successfully saved (after modal closes). */
  onSuccess?: () => void
}

const FIELD =
  'w-full bg-bg border border-white/10 rounded-xl px-3 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-primary transition-colors'

export function AddTransactionModal({ weekId, defaultDate, open, onOpenChange, onSuccess }: Props) {
  const qc = useQueryClient()

  // Compute slot once per render (stable within the same hour)
  const now        = new Date()
  const currentDow  = now.getDay()   // 0=Sunday … 6=Saturday — matches PostgreSQL EXTRACT(DOW)
  const currentHour = now.getHours()

  const { data: suggestions = [] } = useQuery<string[]>({
    queryKey: ['suggest-category', currentDow, currentHour],
    queryFn: () =>
      api
        .get('/transactions/suggest-category', { params: { dow: currentDow, hour: currentHour } })
        .then((r) => r.data.suggestions),
    enabled: open,
    staleTime: 60 * 60 * 1000, // cache for the current hour slot
  })

  const { data: allCategories = [] } = useQuery<string[]>({
    queryKey: ['categories'],
    queryFn: () => api.get('/transactions/categories').then((r) => r.data.categories),
    enabled: open,
    staleTime: 5 * 60 * 1000,
  })

  const [name, setName]           = useState('')
  const [amount, setAmount]       = useState('')
  const [type, setType]           = useState<'income' | 'expense'>('expense')
  const [category, setCategory]   = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const [date, setDate]           = useState('')
  const [recurring, setRecurring]               = useState(false)
  const [recurrenceRule, setRecurrenceRule]     = useState<string>('M:1')
  const [recurrenceEndDate, setRecurrenceEndDate] = useState<string>('')
  const [installments, setInstallments]         = useState<string>('')
  const [error, setError]                       = useState<string | null>(null)

  // Pre-fill date when modal opens (supports projected-week cards)
  useEffect(() => {
    if (open) setDate(defaultDate ?? '')
  }, [open, defaultDate])

  const reset = () => {
    setName(''); setAmount(''); setType('expense')
    setCategory(''); setDate(''); setRecurring(false)
    setRecurrenceRule('M:1'); setRecurrenceEndDate(''); setInstallments('')
    setError(null)
  }

  // Given a start date, recurrence rule and number of occurrences, returns the end date.
  const calcEndDate = (start: string, rule: string, count: number): string => {
    if (!start || count < 2) return ''
    const [unit, intervalStr] = rule.split(':')
    const interval = parseInt(intervalStr, 10) || 1
    const d = new Date(start + 'T12:00:00')
    if (unit === 'W') d.setDate(d.getDate() + (count - 1) * interval * 7)
    else if (unit === 'M') d.setMonth(d.getMonth() + (count - 1) * interval)
    else if (unit === 'Y') d.setFullYear(d.getFullYear() + (count - 1) * interval)
    return d.toISOString().split('T')[0]
  }

  const handleInstallmentsChange = (val: string) => {
    setInstallments(val)
    const n = parseInt(val, 10)
    if (!isNaN(n) && n >= 2) {
      setRecurrenceEndDate(calcEndDate(date, recurrenceRule, n))
    } else {
      setRecurrenceEndDate('')
    }
  }

  const handleEndDateChange = (val: string) => {
    setRecurrenceEndDate(val)
    setInstallments('') // manual date overrides installments helper
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) reset()
    onOpenChange(next)
  }

  const mutation = useMutation({
    mutationFn: (data: TransactionCreate) =>
      api.post('/transactions', data).then((r) => r.data),

    onMutate: async (newTx) => {
      if (!weekId) return {}
      await qc.cancelQueries({ queryKey: ['transactions', weekId] })
      const previous = qc.getQueryData<Transaction[]>(['transactions', weekId])
      qc.setQueryData(['transactions', weekId], (old: Transaction[] = []) => [
        ...old,
        {
          id: `optimistic-${Date.now()}`,
          week_id: weekId,
          name: newTx.name,
          amount: newTx.amount,
          type: newTx.type,
          category: newTx.category ?? null,
          transaction_date: newTx.transaction_date ?? null,
          is_recurring: newTx.is_recurring,
        },
      ])
      return { previous }
    },

    onError: (_err, _vars, ctx) => {
      if (weekId && ctx?.previous) {
        qc.setQueryData(['transactions', weekId], ctx.previous)
      }
      setError('Errore durante il salvataggio. Riprova.')
    },

    onSettled: () => {
      if (weekId) {
        qc.invalidateQueries({ queryKey: ['transactions', weekId] })
      }
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      // Always refresh weeks so projected cards update after a transaction is created
      qc.invalidateQueries({ queryKey: ['weeks'] })
    },

    onSuccess: () => { handleOpenChange(false); onSuccess?.() },
  })

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const parsed = parseFloat(amount)
    if (!name.trim() || isNaN(parsed) || parsed <= 0) {
      setError('Nome e importo (> 0) sono obbligatori.')
      return
    }
    setError(null)
    mutation.mutate({
      name: name.trim(),
      amount: parsed,
      type,
      category: category.trim() || undefined,
      transaction_date: date || undefined,
      is_recurring: recurring,
      recurrence_rule: recurring ? recurrenceRule : undefined,
      recurrence_end_date: recurring && recurrenceEndDate ? recurrenceEndDate : undefined,
    })
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed z-50 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100%-2rem)] max-w-md bg-surface border border-white/10 rounded-2xl p-6 shadow-2xl focus:outline-none">
          <Dialog.Title className="text-base font-semibold mb-5">
            Nuova transazione
          </Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Type toggle */}
            <div className="flex rounded-xl overflow-hidden border border-white/10">
              {(['expense', 'income'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  className={[
                    'flex-1 py-2 text-sm font-medium transition-colors',
                    type === t
                      ? t === 'expense' ? 'bg-expense text-white' : 'bg-income text-white'
                      : 'text-muted hover:text-text',
                  ].join(' ')}
                >
                  {t === 'expense' ? 'Uscita' : 'Entrata'}
                </button>
              ))}
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Descrizione *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="es. Spesa supermercato"
                className={FIELD}
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Importo (€) *</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className={`${FIELD} tabular-nums`}
              />
            </div>

            <div className="grid grid-cols-2 gap-3 items-start">
              <div>
                <label className="text-xs text-muted block mb-1">Categoria</label>
                {/* Contextual chips — visible only before the user starts typing */}
                {category === '' && suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {suggestions.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setCategory(s)}
                        className="px-2 py-0.5 rounded-full text-[11px] bg-primary/15 text-primary border border-primary/20 hover:bg-primary/25 transition-colors"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
                {/* Input + contains-match dropdown for previously used categories */}
                <div className="relative">
                  <input
                    value={category}
                    onChange={(e) => { setCategory(e.target.value); setShowDropdown(true) }}
                    onFocus={() => { if (category.length >= 2) setShowDropdown(true) }}
                    onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
                    placeholder="es. Alimentari"
                    className={FIELD}
                  />
                  {showDropdown && category.length >= 2 && (() => {
                    const matches = allCategories.filter((c) =>
                      c.toLowerCase().includes(category.toLowerCase())
                    )
                    return matches.length > 0 ? (
                      <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-surface border border-white/10 rounded-xl overflow-hidden shadow-lg">
                        {matches.slice(0, 6).map((c) => (
                          <button
                            key={c}
                            type="button"
                            onMouseDown={() => { setCategory(c); setShowDropdown(false) }}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 transition-colors"
                          >
                            {c}
                          </button>
                        ))}
                      </div>
                    ) : null
                  })()}
                </div>
              </div>
              <div>
                <label className="text-xs text-muted block mb-1">Data</label>
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className={`${FIELD} [color-scheme:dark]`}
                />
              </div>
            </div>

            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={recurring}
                onChange={(e) => setRecurring(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-text">Transazione ricorrente</span>
            </label>

            {recurring && (
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-muted block mb-1">Frequenza</label>
                  <select
                    value={recurrenceRule}
                    onChange={(e) => {
                      setRecurrenceRule(e.target.value)
                      // Recalculate end date if installments are set
                      const n = parseInt(installments, 10)
                      if (!isNaN(n) && n >= 2) {
                        setRecurrenceEndDate(calcEndDate(date, e.target.value, n))
                      }
                    }}
                    className={`${FIELD} cursor-pointer`}
                  >
                    <option value="W:1">Ogni settimana</option>
                    <option value="W:2">Ogni 2 settimane</option>
                    <option value="M:1">Ogni mese</option>
                    <option value="M:2">Ogni 2 mesi</option>
                    <option value="M:3">Ogni 3 mesi (trimestrale)</option>
                    <option value="M:6">Ogni 6 mesi (semestrale)</option>
                    <option value="Y:1">Ogni anno</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted block mb-1">Fine ricorrenza (opz.)</label>
                    <input
                      type="date"
                      value={recurrenceEndDate}
                      onChange={(e) => handleEndDateChange(e.target.value)}
                      className={`${FIELD} [color-scheme:dark]`}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted block mb-1">oppure quante rate?</label>
                    <input
                      type="number"
                      min="2"
                      step="1"
                      value={installments}
                      onChange={(e) => handleInstallmentsChange(e.target.value)}
                      placeholder="es. 24"
                      className={`${FIELD} tabular-nums`}
                    />
                  </div>
                </div>
                {recurrenceEndDate && (
                  <p className="text-xs text-muted">
                    Ultima occorrenza entro la settimana del{' '}
                    <span className="text-text tabular-nums">
                      {new Date(recurrenceEndDate + 'T12:00:00').toLocaleDateString('it-IT', {
                        day: 'numeric', month: 'long', year: 'numeric',
                      })}
                    </span>
                  </p>
                )}
              </div>
            )}

            {error && <p className="text-expense text-xs">{error}</p>}

            <div className="flex gap-2 pt-1">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="flex-1 py-2 rounded-xl border border-white/10 text-sm text-muted hover:text-text transition-colors"
                >
                  Annulla
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="flex-1 py-2 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {mutation.isPending ? 'Salvo…' : 'Aggiungi'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
