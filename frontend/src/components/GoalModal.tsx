import { useState, useEffect } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export type GoalType = 'savings' | 'liquidity'

export interface GoalData {
  id: string
  name: string
  target_amount: number
  current_amount: number
  target_date: string
  goal_type: GoalType
  status: 'active' | 'achieved' | 'abandoned'
  progress_pct: number
  remaining: number
}

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  goal?: GoalData
}

const FIELD =
  'w-full bg-bg border border-white/10 rounded-xl px-3 py-2 text-sm text-text placeholder-muted focus:outline-none focus:border-primary transition-colors'

const TYPE_DESCRIPTIONS: Record<GoalType, string> = {
  savings:   'Vuoi mettere da parte un importo a partire da oggi',
  liquidity: 'Vuoi avere almeno questo saldo totale sul conto',
}

export function GoalModal({ open, onOpenChange, goal }: Props) {
  const qc = useQueryClient()
  const isEdit = !!goal

  const [name, setName]               = useState('')
  const [targetAmount, setTargetAmount] = useState('')
  const [targetDate, setTargetDate]   = useState('')
  const [goalType, setGoalType]       = useState<GoalType>('savings')
  const [error, setError]             = useState<string | null>(null)

  useEffect(() => {
    if (open && goal) {
      setName(goal.name)
      setTargetAmount(String(goal.target_amount))
      setTargetDate(goal.target_date)
      setGoalType(goal.goal_type)
    }
  }, [open, goal])

  const reset = () => {
    setName(''); setTargetAmount(''); setTargetDate('')
    setGoalType('savings'); setError(null)
  }

  const handleOpenChange = (next: boolean) => {
    if (!next) reset()
    onOpenChange(next)
  }

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['goals'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const createMutation = useMutation({
    mutationFn: (data: { name: string; target_amount: number; target_date: string; goal_type: GoalType }) =>
      api.post('/goals', data).then((r) => r.data),
    onSuccess: () => { invalidate(); handleOpenChange(false) },
    onError: () => setError('Errore durante il salvataggio. Riprova.'),
  })

  const updateMutation = useMutation({
    mutationFn: (data: { name?: string; target_amount?: number; target_date?: string; goal_type?: GoalType }) =>
      api.put(`/goals/${goal!.id}`, data).then((r) => r.data),
    onSuccess: () => { invalidate(); handleOpenChange(false) },
    onError: () => setError('Errore durante il salvataggio. Riprova.'),
  })

  const isPending = createMutation.isPending || updateMutation.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const target = parseFloat(targetAmount)
    if (!name.trim() || isNaN(target) || target <= 0) {
      setError('Nome e importo obiettivo (> 0) sono obbligatori.')
      return
    }
    if (!targetDate) { setError('La data obiettivo è obbligatoria.'); return }
    setError(null)
    const payload = {
      name: name.trim(),
      target_amount: target,
      target_date: targetDate,
      goal_type: goalType,
    }
    if (isEdit) updateMutation.mutate(payload)
    else createMutation.mutate(payload)
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 z-40" />
        <Dialog.Content className="fixed z-50 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[calc(100%-2rem)] max-w-md bg-surface border border-white/10 rounded-2xl p-6 shadow-2xl focus:outline-none">
          <Dialog.Title className="text-base font-semibold mb-5">
            {isEdit ? 'Modifica obiettivo' : 'Nuovo obiettivo'}
          </Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Goal type toggle */}
            <div>
              <div className="flex rounded-xl overflow-hidden border border-white/10">
                {(['savings', 'liquidity'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setGoalType(t)}
                    className={[
                      'flex-1 py-2 text-sm font-medium transition-colors',
                      goalType === t ? 'bg-primary text-white' : 'text-muted hover:text-text',
                    ].join(' ')}
                  >
                    {t === 'savings' ? 'Risparmio' : 'Liquidità'}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-muted mt-1.5 px-0.5">
                {TYPE_DESCRIPTIONS[goalType]}
              </p>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">Nome *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={goalType === 'savings' ? 'es. Fondo emergenza' : 'es. Saldo minimo dicembre'}
                className={FIELD}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">
                  {goalType === 'savings' ? 'Da risparmiare (€) *' : 'Saldo target (€) *'}
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={targetAmount}
                  onChange={(e) => setTargetAmount(e.target.value)}
                  placeholder="0.00"
                  className={`${FIELD} tabular-nums`}
                />
              </div>
              <div>
                <label className="text-xs text-muted block mb-1">Data obiettivo *</label>
                <input
                  type="date"
                  value={targetDate}
                  onChange={(e) => setTargetDate(e.target.value)}
                  className={`${FIELD} [color-scheme:dark]`}
                />
              </div>
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
                disabled={isPending}
                className="flex-1 py-2 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {isPending ? 'Salvo…' : isEdit ? 'Aggiorna' : 'Crea'}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
