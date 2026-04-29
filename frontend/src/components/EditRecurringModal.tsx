import { useEffect, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { format, parseISO } from 'date-fns'
import { it } from 'date-fns/locale'
import { api } from '../api/client'

export interface RecurringTx {
  id: string
  name: string
  amount: number
  type: 'income' | 'expense'
  category: string | null
  recurrence_rule: string | null
  recurrence_end_date: string | null
}

interface Props {
  transaction: RecurringTx | null
  /** Used as cache key to invalidate the projected-week query on success. */
  weekStart: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

const FIELD =
  'w-full bg-bg border border-white/10 rounded-xl px-3 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-primary transition-colors'

export function EditRecurringModal({ transaction, weekStart, open, onOpenChange }: Props) {
  const qc = useQueryClient()

  const [name, setName]                       = useState('')
  const [amount, setAmount]                   = useState('')
  const [recurrenceRule, setRecurrenceRule]   = useState('W:1')
  const [recurrenceEndDate, setRecurrenceEndDate] = useState('')
  const [error, setError]                     = useState<string | null>(null)

  useEffect(() => {
    if (transaction && open) {
      setName(transaction.name)
      setAmount(String(transaction.amount))
      setRecurrenceRule(transaction.recurrence_rule ?? 'W:1')
      setRecurrenceEndDate(transaction.recurrence_end_date ?? '')
      setError(null)
    }
  }, [transaction, open])

  const handleOpenChange = (next: boolean) => {
    if (!next) setError(null)
    onOpenChange(next)
  }

  const mutation = useMutation({
    mutationFn: (patch: {
      name: string
      amount: number
      recurrence_rule: string
      recurrence_end_date: string | null
    }) => api.put(`/transactions/${transaction!.id}`, patch).then((r) => r.data),

    onError: () => setError('Errore durante il salvataggio. Riprova.'),

    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['projected-week', weekStart] })
      qc.invalidateQueries({ queryKey: ['weeks'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
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
      recurrence_rule: recurrenceRule,
      recurrence_end_date: recurrenceEndDate || null,
    })
  }

  if (!transaction) return null

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed z-50 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100%-2rem)] max-w-md bg-surface border border-white/10 rounded-2xl p-6 shadow-2xl focus:outline-none">
          <Dialog.Title className="text-base font-semibold mb-1">
            Modifica ricorrente
          </Dialog.Title>
          <p className="text-xs text-muted mb-5">
            Le modifiche si rifletteranno su tutte le proiezioni future.
          </p>

          {/* Type badge — read-only */}
          <div className="flex items-center gap-2 mb-4">
            <span
              className={[
                'text-xs font-medium px-2 py-0.5 rounded-full',
                transaction.type === 'income'
                  ? 'bg-income/10 text-income'
                  : 'bg-expense/10 text-expense',
              ].join(' ')}
            >
              {transaction.type === 'income' ? 'Entrata' : 'Uscita'}
            </span>
            {transaction.category && (
              <span className="text-xs text-muted">{transaction.category}</span>
            )}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-muted block mb-1">Descrizione *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
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
                className={`${FIELD} tabular-nums`}
              />
            </div>

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

            <div>
              <label className="text-xs text-muted block mb-1">Fine ricorrenza (opz.)</label>
              <input
                type="date"
                value={recurrenceEndDate}
                onChange={(e) => setRecurrenceEndDate(e.target.value)}
                className={`${FIELD} [color-scheme:dark]`}
              />
              {recurrenceEndDate && (
                <p className="text-xs text-muted mt-1">
                  Ultima occorrenza entro la settimana del{' '}
                  <span className="text-text tabular-nums">
                    {format(parseISO(recurrenceEndDate), 'd MMM yyyy', { locale: it })}
                  </span>
                  {' '}·{' '}
                  <button
                    type="button"
                    onClick={() => setRecurrenceEndDate('')}
                    className="text-primary hover:text-primary/80 transition-colors"
                  >
                    Rimuovi data
                  </button>
                </p>
              )}
            </div>

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
                {mutation.isPending ? 'Salvo…' : 'Salva modifiche'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
