import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { BalanceTrendChart } from '../components/analytics/BalanceTrendChart'
import type { BalanceData } from '../components/analytics/BalanceTrendChart'

interface WeekSummary {
  week_id: string | null
  week_start: string
  week_end: string
  opening_balance: number
  closing_balance: number
  total_income: number
  total_expense: number
  net: number
  is_projected: boolean
}

interface GoalDelta {
  id: string
  name: string
  target_amount: number
  current_amount: number
  remaining: number
  progress_pct: number
  target_date: string
  goal_type: 'liquidity' | 'savings'
  status: string
}

interface DashboardSummary {
  current_balance: number
  projection: WeekSummary[]
  goals: GoalDelta[]
}

interface Transaction {
  id: string
  name: string
  amount: number
  type: 'income' | 'expense'
  category: string | null
  is_recurring: boolean
}

function fmt(n: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
}

export function Dashboard() {
  const { data, isLoading, isError } = useQuery<DashboardSummary>({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/dashboard/summary').then((r) => r.data),
  })

  // projection[0] is always the current week (backend: n_weeks_back=0)
  const currentWeek = data?.projection[0] ?? null

  const { data: currentTxns = [] } = useQuery<Transaction[]>({
    queryKey: ['transactions', currentWeek?.week_id],
    queryFn: () =>
      api.get('/transactions', { params: { week_id: currentWeek!.week_id } }).then((r) => r.data),
    enabled: !!currentWeek?.week_id,
  })

  if (isLoading) return <PageShell><Skeleton /></PageShell>
  if (isError)   return <PageShell><ErrorBanner /></PageShell>

  const balance = data!.current_balance

  // Projection chart — closing_balance for each week in the horizon
  const projectionData: BalanceData[] = data!.projection.map((w, i) => ({
    label: `S${i + 1}`,
    balance: w.closing_balance,
  }))
  const goalTarget = data!.goals[0]?.target_amount

  // Current week totals from real transactions (0 if week has no DB record yet)
  const totalIn  = currentTxns.filter((t) => t.type === 'income').reduce((s, t) => s + t.amount, 0)
  const totalOut = currentTxns.filter((t) => t.type === 'expense').reduce((s, t) => s + t.amount, 0)

  return (
    <PageShell>
      {/* Hero row — saldo + primi 2 obiettivi */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-surface rounded-2xl p-5 border border-white/5">
          <p className="text-muted text-xs mb-1">Saldo attuale</p>
          <p className={`tabular-nums text-2xl font-semibold ${balance >= 0 ? 'text-income' : 'text-expense'}`}>
            {fmt(balance)}
          </p>
        </div>

        {data!.goals.slice(0, 2).map((g) => (
          <div key={g.id} className="bg-surface rounded-2xl p-5 border border-white/5">
            <p className="text-muted text-xs mb-1 truncate">{g.name}</p>
            <div className="flex items-end gap-2">
              <p className="tabular-nums text-lg font-semibold">{g.progress_pct}%</p>
              <p className="text-muted text-xs mb-0.5">di {fmt(g.target_amount)}</p>
            </div>
            <div className="mt-2 h-1.5 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-500"
                style={{ width: `${g.progress_pct}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Projection chart */}
      <div className="bg-surface rounded-2xl p-5 border border-white/5 mb-6">
        <p className="text-sm font-medium mb-1">Proiezione 8 settimane</p>
        <p className="text-muted text-xs mb-4">
          Saldo proiettato basato sulle transazioni ricorrenti
        </p>
        <BalanceTrendChart data={projectionData} goalTarget={goalTarget} />
      </div>

      {/* Transazioni settimana corrente */}
      {currentWeek && (
        <div className="bg-surface rounded-2xl p-5 border border-white/5">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-medium">Settimana in corso</p>
            {currentWeek.week_id && (
              <Link
                to={`/weeks/${currentWeek.week_id}`}
                className="text-xs text-primary hover:text-primary/80 transition-colors"
              >
                Vedi tutto →
              </Link>
            )}
          </div>

          {currentTxns.length === 0 ? (
            <p className="text-muted text-sm text-center py-4">
              Nessuna transazione questa settimana.
            </p>
          ) : (
            <>
              <div className="space-y-2 mb-4">
                {currentTxns.slice(0, 5).map((t) => (
                  <div key={t.id} className="flex items-center justify-between text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{t.name}</p>
                      {t.category && (
                        <p className="text-muted text-xs">{t.category}</p>
                      )}
                    </div>
                    <p className={`tabular-nums font-semibold flex-shrink-0 ml-3 ${t.type === 'income' ? 'text-income' : 'text-expense'}`}>
                      {t.type === 'income' ? '+' : '-'}{fmt(t.amount)}
                    </p>
                  </div>
                ))}
              </div>

              <div className="flex gap-4 pt-3 border-t border-white/5">
                <div>
                  <p className="text-muted text-xs">Entrate</p>
                  <p className="tabular-nums text-sm font-semibold text-income">{fmt(totalIn)}</p>
                </div>
                <div>
                  <p className="text-muted text-xs">Uscite</p>
                  <p className="tabular-nums text-sm font-semibold text-expense">{fmt(totalOut)}</p>
                </div>
                <div>
                  <p className="text-muted text-xs">Netto</p>
                  <p className={`tabular-nums text-sm font-semibold ${totalIn - totalOut >= 0 ? 'text-income' : 'text-expense'}`}>
                    {fmt(totalIn - totalOut)}
                  </p>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </PageShell>
  )
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <h1 className="text-lg font-semibold mb-6">Dashboard</h1>
      {children}
    </div>
  )
}

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-24 bg-surface rounded-2xl" />
      <div className="h-56 bg-surface rounded-2xl" />
      <div className="h-48 bg-surface rounded-2xl" />
    </div>
  )
}

function ErrorBanner() {
  return (
    <div className="bg-expense/10 border border-expense/20 rounded-xl px-4 py-3 text-expense text-sm">
      Impossibile caricare i dati. Verifica che il backend sia raggiungibile.
    </div>
  )
}
