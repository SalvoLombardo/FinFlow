import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import { it } from 'date-fns/locale'
import { api } from '../api/client'
import { AddTransactionModal } from '../components/AddTransactionModal'

interface Week {
  id: string
  week_start: string
  week_end: string
  opening_balance: number
  closing_balance: number | null
  notes: string | null
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

function fmt(n: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
}

export function WeekDetail() {
  const { weekId } = useParams<{ weekId: string }>()
  const qc = useQueryClient()
  const [modalOpen, setModalOpen] = useState(false)

  const { data: week } = useQuery<Week>({
    queryKey: ['week', weekId],
    queryFn: () => api.get(`/weeks/${weekId}`).then((r) => r.data),
  })

  const { data: transactions = [], isLoading } = useQuery<Transaction[]>({
    queryKey: ['transactions', weekId],
    queryFn: () => api.get('/transactions', { params: { week_id: weekId } }).then((r) => r.data),
    enabled: !!weekId,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/transactions/${id}`),

    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['transactions', weekId] })
      const previous = qc.getQueryData<Transaction[]>(['transactions', weekId])
      qc.setQueryData(['transactions', weekId], (old: Transaction[] = []) =>
        old.filter((t) => t.id !== id)
      )
      return { previous }
    },

    onError: (_err, _id, ctx) => {
      if (ctx?.previous) {
        qc.setQueryData(['transactions', weekId], ctx.previous)
      }
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['transactions', weekId] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['weeks'] })
    },
  })

  const handleDelete = (id: string) => {
    if (window.confirm('Eliminare questa transazione?')) {
      deleteMutation.mutate(id)
    }
  }

  const incomes  = transactions.filter((t) => t.type === 'income')
  const expenses = transactions.filter((t) => t.type === 'expense')
  const totalIn  = incomes.reduce((s, t) => s + t.amount, 0)
  const totalOut = expenses.reduce((s, t) => s + t.amount, 0)

  return (
    <div className="p-4 sm:p-6 max-w-2xl mx-auto">
      <Link to="/weeks" className="text-muted text-sm hover:text-text transition-colors">
        ← Settimane
      </Link>

      {week && (
        <div className="mt-3 mb-6">
          <h1 className="text-lg font-semibold">
            {format(parseISO(week.week_start), 'd MMM', { locale: it })}
            {' – '}
            {format(parseISO(week.week_end), 'd MMM yyyy', { locale: it })}
          </h1>
          <div className="flex gap-4 mt-2">
            <Stat label="Entrate" value={fmt(totalIn)}  color="text-income" />
            <Stat label="Uscite"  value={fmt(totalOut)} color="text-expense" />
            <Stat
              label="Netto"
              value={fmt(totalIn - totalOut)}
              color={totalIn - totalOut >= 0 ? 'text-income' : 'text-expense'}
            />
          </div>
          {week.closing_balance !== null && (
            <p className="text-muted text-xs mt-2 tabular-nums">
              Saldo chiusura calcolato: <span className="text-text font-medium">{fmt(week.closing_balance)}</span>
            </p>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3].map((i) => <div key={i} className="h-14 bg-surface rounded-xl" />)}
        </div>
      ) : transactions.length === 0 ? (
        <p className="text-muted text-sm text-center py-12">
          Nessuna transazione questa settimana.
        </p>
      ) : (
        <div className="space-y-2">
          {transactions.map((t) => (
            <div
              key={t.id}
              className={[
                'flex items-center justify-between bg-surface border border-white/5 rounded-xl px-4 py-3',
                t.id.startsWith('optimistic-') ? 'opacity-60' : '',
              ].join(' ')}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium flex items-center gap-2 min-w-0">
                  <span className="truncate">{t.name}</span>
                  {t.is_recurring && (
                    <span className="flex-shrink-0 text-[10px] bg-primary/15 text-primary px-1.5 py-0.5 rounded-full">
                      Ricorrente
                    </span>
                  )}
                </p>
                {t.category && (
                  <p className="text-muted text-xs mt-0.5 truncate">{t.category}</p>
                )}
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <p className={`tabular-nums text-sm font-semibold ${t.type === 'income' ? 'text-income' : 'text-expense'}`}>
                  {t.type === 'income' ? '+' : '-'}{fmt(t.amount)}
                </p>
                {!t.id.startsWith('optimistic-') && (
                  <button
                    onClick={() => handleDelete(t.id)}
                    disabled={deleteMutation.isPending}
                    className="text-muted hover:text-expense transition-colors text-lg leading-none disabled:opacity-40"
                    title="Elimina"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* FAB */}
      {weekId && (
        <>
          <button
            onClick={() => setModalOpen(true)}
            className="fixed bottom-6 right-6 w-12 h-12 rounded-full bg-primary text-white text-2xl shadow-lg hover:bg-primary/90 transition-colors flex items-center justify-center z-30"
            title="Aggiungi transazione"
          >
            +
          </button>

          <AddTransactionModal
            weekId={weekId}
            open={modalOpen}
            onOpenChange={setModalOpen}
          />
        </>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <p className="text-muted text-xs">{label}</p>
      <p className={`tabular-nums text-sm font-semibold ${color}`}>{value}</p>
    </div>
  )
}
