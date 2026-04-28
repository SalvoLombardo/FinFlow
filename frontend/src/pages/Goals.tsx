import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format, parseISO, differenceInDays } from 'date-fns'
import { it } from 'date-fns/locale'
import { api } from '../api/client'
import { GoalModal } from '../components/GoalModal'
import type { GoalData } from '../components/GoalModal'

function fmt(n: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
}

export function Goals() {
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)
  const [editGoal, setEditGoal]   = useState<GoalData | undefined>(undefined)

  const { data: goals = [], isLoading } = useQuery<GoalData[]>({
    queryKey: ['goals'],
    queryFn: () => api.get('/goals').then((r) => r.data),
  })

  const abandonMutation = useMutation({
    mutationFn: (id: string) => api.put(`/goals/${id}`, { status: 'abandoned' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['goals'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  const handleEdit = (goal: GoalData) => {
    setEditGoal(goal)
    setModalOpen(true)
  }

  const handleAdd = () => {
    setEditGoal(undefined)
    setModalOpen(true)
  }

  const handleAbandon = (goal: GoalData) => {
    if (window.confirm(`Abbandonare l'obiettivo "${goal.name}"?`)) {
      abandonMutation.mutate(goal.id)
    }
  }

  const active    = goals.filter((g) => g.status === 'active')
  const achieved  = goals.filter((g) => g.status === 'achieved')
  const abandoned = goals.filter((g) => g.status === 'abandoned')

  return (
    <div className="p-4 sm:p-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-lg font-semibold">Obiettivi</h1>
        <button
          onClick={handleAdd}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <span className="text-lg leading-none">+</span>
          Aggiungi
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2].map((i) => <div key={i} className="h-28 bg-surface rounded-2xl" />)}
        </div>
      ) : goals.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-muted text-sm mb-3">Nessun obiettivo ancora.</p>
          <button
            onClick={handleAdd}
            className="text-primary text-sm hover:text-primary/80 transition-colors"
          >
            Crea il tuo primo obiettivo →
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {active.length > 0 && (
            <section>
              <p className="text-muted text-xs uppercase tracking-wide mb-3">Attivi</p>
              <div className="space-y-3">
                {active.map((g) => (
                  <GoalCard
                    key={g.id}
                    goal={g}
                    onEdit={() => handleEdit(g)}
                    onAbandon={() => handleAbandon(g)}
                    abandonPending={abandonMutation.isPending && abandonMutation.variables === g.id}
                  />
                ))}
              </div>
            </section>
          )}
          {achieved.length > 0 && (
            <section>
              <p className="text-muted text-xs uppercase tracking-wide mb-3">Raggiunti</p>
              <div className="space-y-3">
                {achieved.map((g) => <GoalCard key={g.id} goal={g} />)}
              </div>
            </section>
          )}
          {abandoned.length > 0 && (
            <section>
              <p className="text-muted text-xs uppercase tracking-wide mb-3">Abbandonati</p>
              <div className="space-y-3">
                {abandoned.map((g) => <GoalCard key={g.id} goal={g} />)}
              </div>
            </section>
          )}
        </div>
      )}

      <GoalModal
        open={modalOpen}
        onOpenChange={(v) => { setModalOpen(v); if (!v) setEditGoal(undefined) }}
        goal={editGoal}
      />
    </div>
  )
}

function GoalCard({
  goal,
  onEdit,
  onAbandon,
  abandonPending,
}: {
  goal: GoalData
  onEdit?: () => void
  onAbandon?: () => void
  abandonPending?: boolean
}) {
  const daysLeft  = differenceInDays(parseISO(goal.target_date), new Date())
  const achieved  = goal.status === 'achieved'
  const abandoned = goal.status === 'abandoned'

  const isSavings   = goal.goal_type === 'savings'
  const progressPct = goal.progress_pct  // already 0-100, computed by backend

  const progressLabel = isSavings
    ? `Risparmiati: ${fmt(goal.current_amount)} / ${fmt(goal.target_amount)}`
    : `Saldo: ${fmt(goal.current_amount)} / ${fmt(goal.target_amount)}`

  return (
    <div className={`bg-surface border border-white/5 rounded-2xl p-5 ${abandoned ? 'opacity-50' : ''}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-sm truncate">{goal.name}</p>
            {/* Goal type badge */}
            <span className={[
              'text-[10px] px-1.5 py-0.5 rounded-full leading-none shrink-0',
              isSavings
                ? 'bg-primary/10 text-primary'
                : 'bg-white/10 text-muted',
            ].join(' ')}>
              {isSavings ? 'Risparmio' : 'Liquidità'}
            </span>
          </div>
          <p className="text-muted text-xs mt-0.5">
            Entro {format(parseISO(goal.target_date), 'd MMM yyyy', { locale: it })}
            {!achieved && !abandoned && daysLeft >= 0 && (
              <span className={`ml-2 ${daysLeft <= 30 ? 'text-expense' : 'text-muted'}`}>
                ({daysLeft} giorni)
              </span>
            )}
            {!achieved && !abandoned && daysLeft < 0 && (
              <span className="ml-2 text-expense">(scaduto)</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
          {achieved && (
            <span className="text-xs bg-income/15 text-income px-2 py-0.5 rounded-full">Raggiunto</span>
          )}
          {abandoned && (
            <span className="text-xs bg-white/10 text-muted px-2 py-0.5 rounded-full">Abbandonato</span>
          )}
          {!achieved && !abandoned && onEdit && (
            <>
              <button
                onClick={onEdit}
                className="text-muted hover:text-text transition-colors text-xs px-2 py-0.5 rounded-lg hover:bg-white/5"
              >
                Modifica
              </button>
              <button
                onClick={onAbandon}
                disabled={abandonPending}
                className="text-muted hover:text-expense transition-colors text-xs px-2 py-0.5 rounded-lg hover:bg-white/5 disabled:opacity-40"
              >
                Abbandona
              </button>
            </>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              achieved ? 'bg-income' : abandoned ? 'bg-white/20' : 'bg-primary'
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <p className="tabular-nums text-xs text-muted shrink-0">{progressLabel}</p>
      </div>
    </div>
  )
}
