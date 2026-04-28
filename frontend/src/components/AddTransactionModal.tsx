import { useEffect, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

interface TransactionCreate {
  name: string
  amount: number
  type: 'income' | 'expense'
  category?: string
  transaction_date?: string
  is_recurring: boolean
  recurrence_rule?: string
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
}

const FIELD =
  'w-full bg-bg border border-white/10 rounded-xl px-3 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-primary transition-colors'

export function AddTransactionModal({ weekId, defaultDate, open, onOpenChange }: Props) {
  const qc = useQueryClient()

  const [name, setName]           = useState('')
  const [amount, setAmount]       = useState('')
  const [type, setType]           = useState<'income' | 'expense'>('expense')
  const [category, setCategory]   = useState('')
  const [date, setDate]           = useState('')
  const [recurring, setRecurring]         = useState(false)
  const [recurrenceRule, setRecurrenceRule] = useState<string>('M:1')
  const [error, setError]                 = useState<string | null>(null)

  // Pre-fill date when modal opens (supports projected-week cards)
  useEffect(() => {
    if (open) setDate(defaultDate ?? '')
  }, [open, defaultDate])

  const reset = () => {
    setName(''); setAmount(''); setType('expense')
    setCategory(''); setDate(''); setRecurring(false)
    setRecurrenceRule('M:1'); setError(null)
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

    onSuccess: () => handleOpenChange(false),
  })

  const handleSubmit = (e: React.FormEvent) => {
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

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">Categoria</label>
                <input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="es. Alimentari"
                  className={FIELD}
                />
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
              <div>
                <label className="text-xs text-muted block mb-1">Frequenza</label>
                <select
                  value={recurrenceRule}
                  onChange={(e) => setRecurrenceRule(e.target.value)}
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
