import { useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultOpeningBalance?: number
}

const FIELD =
  'w-full bg-bg border border-white/10 rounded-xl px-3 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-primary transition-colors'

function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export function CreateWeekModal({ open, onOpenChange, defaultOpeningBalance = 0 }: Props) {
  const qc = useQueryClient()
  const [weekStart, setWeekStart]           = useState('')
  const [openingBalance, setOpeningBalance] = useState('')
  const [notes, setNotes]                   = useState('')
  const [error, setError]                   = useState<string | null>(null)

  const reset = () => {
    setWeekStart(''); setOpeningBalance(''); setNotes(''); setError(null)
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) reset()
    onOpenChange(next)
  }

  const mutation = useMutation({
    mutationFn: (data: { week_start: string; week_end: string; opening_balance: number; notes?: string }) =>
      api.post('/weeks', data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['weeks'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      handleOpenChange(false)
    },
    onError: () => setError('Errore durante il salvataggio. Riprova.'),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!weekStart) { setError('La data di inizio è obbligatoria.'); return }
    const balance = parseFloat(openingBalance || String(defaultOpeningBalance))
    if (isNaN(balance)) { setError('Saldo di apertura non valido.'); return }
    setError(null)
    mutation.mutate({
      week_start: weekStart,
      week_end: addDays(weekStart, 6),
      opening_balance: balance,
      notes: notes.trim() || undefined,
    })
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed z-50 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100%-2rem)] max-w-md bg-surface border border-white/10 rounded-2xl p-6 shadow-2xl focus:outline-none">
          <Dialog.Title className="text-base font-semibold mb-5">Nuova settimana</Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-muted block mb-1">Inizio settimana *</label>
              <input
                type="date"
                value={weekStart}
                onChange={(e) => setWeekStart(e.target.value)}
                className={`${FIELD} [color-scheme:dark]`}
              />
              {weekStart && (
                <p className="text-muted text-xs mt-1">Fine: {addDays(weekStart, 6)}</p>
              )}
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Saldo di apertura (€)</label>
              <input
                type="number"
                step="0.01"
                value={openingBalance}
                onChange={(e) => setOpeningBalance(e.target.value)}
                placeholder={defaultOpeningBalance.toFixed(2)}
                className={`${FIELD} tabular-nums`}
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Note</label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Opzionale"
                className={FIELD}
              />
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
                {mutation.isPending ? 'Salvo…' : 'Crea'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
