import { useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format, parseISO, getISOWeek } from 'date-fns'
import { it } from 'date-fns/locale'
import { api } from '../api/client'
import { AddTransactionModal } from '../components/AddTransactionModal'
import { EditRecurringModal } from '../components/EditRecurringModal'
import type { RecurringTx } from '../components/EditRecurringModal'

interface ProjectedTransaction {
  id: string
  name: string
  amount: number
  type: 'income' | 'expense'
  category: string | null
  recurrence_rule: string | null
  recurrence_end_date: string | null
}

interface ProjectedWeekDetail {
  week_start: string
  week_end: string
  opening_balance: number
  closing_balance: number
  total_income: number
  total_expense: number
  transactions: ProjectedTransaction[]
}

function fmt(n: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
}

function ruleLabel(rule: string | null): string {
  if (!rule) return 'Ogni settimana'
  const map: Record<string, string> = {
    'W:1': 'Ogni settimana',
    'W:2': 'Ogni 2 settimane',
    'M:1': 'Ogni mese',
    'M:2': 'Ogni 2 mesi',
    'M:3': 'Ogni 3 mesi',
    'M:6': 'Ogni 6 mesi',
    'Y:1': 'Ogni anno',
  }
  return map[rule] ?? rule
}

export function ProjectedWeekDetail() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const weekStart = searchParams.get('week_start') ?? ''

  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editingTx, setEditingTx]       = useState<RecurringTx | null>(null)

  const { data, isLoading, isError } = useQuery<ProjectedWeekDetail>({
    queryKey: ['projected-week', weekStart],
    queryFn: () =>
      api.get('/weeks/projected', { params: { week_start: weekStart } }).then((r) => r.data),
    enabled: !!weekStart,
  })

  if (!weekStart) return <Navigate to="/weeks" replace />

  const weekNum  = weekStart ? getISOWeek(parseISO(weekStart)) : ''
  const startFmt = weekStart ? format(parseISO(weekStart), 'd MMM', { locale: it }) : ''
  const endFmt   = data ? format(parseISO(data.week_end), 'd MMM yyyy', { locale: it }) : ''

  return (
    <div className="p-4 sm:p-6 max-w-2xl mx-auto">
      {/* Back link */}
      <button
        onClick={() => navigate('/weeks')}
        className="text-sm text-muted hover:text-text transition-colors mb-5 flex items-center gap-1"
      >
        ← Tutte le settimane
      </button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6 flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-lg font-semibold">
              Sett.&nbsp;{weekNum}&nbsp;·&nbsp;{startFmt}{endFmt ? ` – ${endFmt}` : ''}
            </h1>
            <span className="text-[10px] bg-white/5 text-muted px-2 py-0.5 rounded-full leading-none border border-white/10">
              Previsione
            </span>
          </div>
          <p className="text-xs text-muted mt-1">
            Settimana proiettata — nessun dato reale nel database.
          </p>
        </div>
        <button
          onClick={() => setAddModalOpen(true)}
          className="px-3 py-2 bg-primary text-white text-sm font-medium rounded-xl hover:bg-primary/90 transition-colors"
        >
          + Aggiungi transazione
        </button>
      </div>

      {/* Balance summary */}
      {data && (
        <div className="bg-surface rounded-2xl p-4 border border-white/5 mb-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide">Apertura</p>
            <p className="tabular-nums text-sm mt-0.5">{fmt(data.opening_balance)}</p>
          </div>
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide">Chiusura *</p>
            <p className="tabular-nums text-sm mt-0.5">{fmt(data.closing_balance)}</p>
          </div>
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide">Entrate</p>
            <p className="tabular-nums text-sm mt-0.5 text-income">+{fmt(data.total_income)}</p>
          </div>
          <div>
            <p className="text-[10px] text-muted uppercase tracking-wide">Uscite</p>
            <p className="tabular-nums text-sm mt-0.5 text-expense">-{fmt(data.total_expense)}</p>
          </div>
        </div>
      )}

      {/* Transaction list */}
      <section className="bg-surface rounded-2xl border border-white/5 overflow-hidden">
        <div className="px-4 py-3 border-b border-white/5">
          <p className="text-xs text-muted uppercase tracking-wide">
            Transazioni ricorrenti previste
            {data ? ` (${data.transactions.length})` : ''}
          </p>
        </div>

        {isLoading && (
          <div className="space-y-3 p-4 animate-pulse">
            {[1, 2, 3].map((i) => <div key={i} className="h-14 bg-white/5 rounded-xl" />)}
          </div>
        )}

        {isError && (
          <p className="text-sm text-expense p-4">
            Impossibile caricare la previsione. Verifica che la data sia valida e nel futuro.
          </p>
        )}

        {data && data.transactions.length === 0 && (
          <p className="text-sm text-muted p-4 text-center py-8">
            Nessuna transazione ricorrente prevista per questa settimana.
          </p>
        )}

        {data && data.transactions.length > 0 && (
          <ul className="divide-y divide-white/5">
            {data.transactions.map((tx) => (
              <li key={tx.id} className="flex items-center gap-3 px-4 py-3">
                {/* Amount badge */}
                <span
                  className={[
                    'tabular-nums text-sm font-semibold min-w-[80px] text-right',
                    tx.type === 'income' ? 'text-income' : 'text-expense',
                  ].join(' ')}
                >
                  {tx.type === 'income' ? '+' : '-'}{fmt(tx.amount)}
                </span>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <p className="text-sm font-medium truncate">{tx.name}</p>
                    <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded-full leading-none flex-shrink-0">
                      Ricorrente
                    </span>
                  </div>
                  <p className="text-xs text-muted truncate">
                    {tx.category ?? 'Nessuna categoria'}
                    {' · '}
                    {ruleLabel(tx.recurrence_rule)}
                    {tx.recurrence_end_date && (
                      <> · fino al{' '}
                        {format(parseISO(tx.recurrence_end_date), 'd MMM yyyy', { locale: it })}
                      </>
                    )}
                  </p>
                </div>

                <button
                  onClick={() => setEditingTx({
                    id: tx.id,
                    name: tx.name,
                    amount: tx.amount,
                    type: tx.type,
                    category: tx.category,
                    recurrence_rule: tx.recurrence_rule,
                    recurrence_end_date: tx.recurrence_end_date,
                  })}
                  className="text-xs text-primary hover:text-primary/80 transition-colors flex-shrink-0"
                >
                  Modifica
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-[10px] text-muted mt-3">
        * I valori sono stime basate sulle ricorrenze attive. Aggiungendo una transazione
        la settimana viene creata nel database.
      </p>

      {/* AddTransactionModal — materialises the week when used */}
      <AddTransactionModal
        defaultDate={weekStart}
        open={addModalOpen}
        onOpenChange={setAddModalOpen}
        onSuccess={() => navigate('/weeks')}
      />

      {/* EditRecurringModal — edits the source recurring transaction */}
      <EditRecurringModal
        transaction={editingTx}
        weekStart={weekStart}
        open={editingTx !== null}
        onOpenChange={(open) => { if (!open) setEditingTx(null) }}
      />
    </div>
  )
}
