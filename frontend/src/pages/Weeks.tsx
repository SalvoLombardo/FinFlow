import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { format, parseISO, getISOWeek } from 'date-fns'
import { it } from 'date-fns/locale'
import { api } from '../api/client'
import { RangeSelector } from '../components/analytics/RangeSelector'
import { WeeklyBarChart } from '../components/analytics/WeeklyBarChart'
import type { WeekBarData } from '../components/analytics/WeeklyBarChart'
import { BalanceTrendChart } from '../components/analytics/BalanceTrendChart'
import type { BalanceData } from '../components/analytics/BalanceTrendChart'
import { CategoryDonutChart } from '../components/analytics/CategoryDonutChart'
import type { CategoryData } from '../components/analytics/CategoryDonutChart'
import { AddTransactionModal } from '../components/AddTransactionModal'

interface Week {
  week_id: string | null
  week_start: string
  week_end: string
  opening_balance: number
  closing_balance: number
  total_income: number
  total_expense: number
  net: number
  is_projected: boolean
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

export function Weeks() {
  const [params, setParams] = useSearchParams()
  const [addModalDate, setAddModalDate] = useState<string | null>(null)
  const [isCurrentVisible, setIsCurrentVisible] = useState(true)
  const currentWeekRef = useRef<HTMLDivElement | null>(null)

  const view     = params.get('view')     ?? 'list'
  const range    = parseInt(params.get('range') ?? '12', 10)
  const category = params.get('category') ?? null

  const { data: weeks = [], isLoading } = useQuery<Week[]>({
    queryKey: ['weeks', range],
    queryFn: () => api.get('/weeks', { params: { range } }).then((r) => r.data),
  })

  // Track whether the current week card is in the viewport
  useEffect(() => {
    const el = currentWeekRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => setIsCurrentVisible(entry.isIntersecting),
      { threshold: 0.1 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [weeks])

  const scrollToCurrent = () =>
    currentWeekRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })

  const setView = (v: string) =>
    setParams((p) => { p.set('view', v); return p })

  const setRange = (r: number) =>
    setParams((p) => { p.set('range', String(r)); return p })

  const setCategory = (cat: string | null) =>
    setParams((p) => { cat === null ? p.delete('category') : p.set('category', cat); return p })

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold">Settimane</h1>
        <div className="flex bg-surface rounded-lg p-0.5 gap-0.5 border border-white/5">
          <ViewTab active={view === 'list'}      onClick={() => setView('list')}>Lista</ViewTab>
          <ViewTab active={view === 'analytics'} onClick={() => setView('analytics')}>Analytics</ViewTab>
        </div>
      </div>

      {/* Range selector — visible in both views */}
      <div className="flex justify-end mb-5">
        <RangeSelector value={range} onChange={setRange} />
      </div>

      {/* Modal for adding transactions from projected week cards (no week_id yet) */}
      <AddTransactionModal
        defaultDate={addModalDate ?? undefined}
        open={addModalDate !== null}
        onOpenChange={(open) => { if (!open) setAddModalDate(null) }}
      />

      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => <div key={i} className="h-40 bg-surface rounded-2xl" />)}
        </div>
      ) : view === 'list' ? (
        <GridView weeks={weeks} onAddTransaction={setAddModalDate} currentWeekRef={currentWeekRef} />
      ) : (
        <AnalyticsView
          weeks={weeks}
          activeCategory={category}
          onCategoryChange={setCategory}
        />
      )}

      {/* Scroll-to-current button — visible only when current week is off-screen */}
      {view === 'list' && !isCurrentVisible && (
        <button
          onClick={scrollToCurrent}
          className="fixed bottom-6 right-6 flex items-center gap-2 px-3 py-2 bg-surface border border-primary/40 text-primary text-xs font-medium rounded-xl shadow-lg hover:bg-primary/10 transition-colors z-20"
        >
          <span className="text-base leading-none">◎</span>
          Settimana corrente
        </button>
      )}
    </div>
  )
}

function ViewTab({
  active, onClick, children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={[
        'px-3 py-1.5 rounded-md text-sm transition-colors',
        active ? 'bg-primary text-white' : 'text-muted hover:text-text',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

// ---- Grid view ----

function GridView({
  weeks,
  onAddTransaction,
  currentWeekRef,
}: {
  weeks: Week[]
  onAddTransaction: (weekStart: string) => void
  currentWeekRef: React.RefObject<HTMLDivElement | null>
}) {
  if (weeks.length === 0) {
    return <p className="text-muted text-sm text-center py-12">Nessuna settimana trovata.</p>
  }
  const today = new Date().toISOString().slice(0, 10)
  return (
    <div className="space-y-3">
      {weeks.map((w, idx) => {
        const isCur = w.week_start <= today && today <= w.week_end
        const month = format(parseISO(w.week_start), 'MMMM yyyy', { locale: it })
        const prevMonth = idx > 0
          ? format(parseISO(weeks[idx - 1].week_start), 'MMMM yyyy', { locale: it })
          : null
        const showMonthHeader = month !== prevMonth
        return (
          <div key={w.week_start}>
            {showMonthHeader && (
              <div className={`flex items-center gap-3 mb-1 ${idx > 0 ? 'mt-5' : ''}`}>
                <span className="text-xs font-medium text-muted capitalize">{month}</span>
                <div className="flex-1 h-px bg-white/10" />
              </div>
            )}
            <div ref={isCur ? currentWeekRef : undefined}>
              <WeekCard week={w} onAddTransaction={onAddTransaction} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function WeekCard({
  week,
  onAddTransaction,
}: {
  week: Week
  onAddTransaction: (weekStart: string) => void
}) {
  const today      = new Date().toISOString().slice(0, 10)
  const isCurrent  = week.week_start <= today && today <= week.week_end
  const isProjected = week.is_projected
  const hasId      = week.week_id !== null

  const weekNum  = getISOWeek(parseISO(week.week_start))
  const startFmt = format(parseISO(week.week_start), 'd MMM', { locale: it })
  const endFmt   = format(parseISO(week.week_end), 'd MMM yyyy', { locale: it })

  // Label/button shown at the bottom of every card
  const addButton = hasId ? (
    <span className="text-xs text-primary">+ Aggiungi transazione</span>
  ) : isProjected ? (
    <span className="text-xs text-muted">→ Vedi previsione dettagliata</span>
  ) : (
    <button
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        onAddTransaction(week.week_start)
      }}
      className="text-xs text-primary hover:text-primary/80 transition-colors"
    >
      + Aggiungi transazione
    </button>
  )

  const content = (
    <div
      className={[
        'rounded-2xl p-4 border transition-colors',
        isProjected
          ? 'bg-surface border-dashed border-white/20 hover:bg-white/[0.03] cursor-pointer'
          : isCurrent
            ? 'bg-primary/[0.08] border-primary shadow-[0_0_24px_rgba(99,102,241,0.18)] hover:bg-primary/[0.11] cursor-pointer'
            : 'bg-surface border-white/5 hover:bg-white/5',
        hasId ? 'cursor-pointer' : '',
      ].join(' ')}
    >
      {/* Header row */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <p className="text-sm font-medium">
          Sett.&nbsp;{weekNum}&nbsp;·&nbsp;{startFmt}&nbsp;–&nbsp;{endFmt}
        </p>
        {isCurrent && (
          <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded-full font-medium leading-none">
            CORRENTE
          </span>
        )}
        {isProjected && (
          <span className="text-[10px] bg-white/5 text-muted px-1.5 py-0.5 rounded-full leading-none">
            Proiezione
          </span>
        )}
      </div>

      {/* Opening / Closing balances */}
      <div className="grid grid-cols-2 gap-x-6 mb-3">
        <div>
          <p className="text-[10px] text-muted uppercase tracking-wide">Apertura</p>
          <p className="tabular-nums text-sm">{fmt(week.opening_balance)}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted uppercase tracking-wide">
            Chiusura{isProjected ? ' *' : ''}
          </p>
          <p className="tabular-nums text-sm">{fmt(week.closing_balance)}</p>
        </div>
      </div>

      {/* Income / Expense / Net */}
      <div className="flex items-end gap-5 mb-3">
        <div>
          <p className="text-[10px] text-muted">Entrate</p>
          <p className="tabular-nums text-sm text-income">+{fmt(week.total_income)}</p>
        </div>
        <div>
          <p className="text-[10px] text-muted">Uscite</p>
          <p className="tabular-nums text-sm text-expense">-{fmt(week.total_expense)}</p>
        </div>
        <div className="ml-auto text-right">
          <p className="text-[10px] text-muted">Netto</p>
          <p className={`tabular-nums text-sm font-semibold ${week.net >= 0 ? 'text-income' : 'text-expense'}`}>
            {week.net >= 0 ? '+' : ''}{fmt(week.net)}
          </p>
        </div>
      </div>

      {addButton}
    </div>
  )

  if (hasId) {
    return <Link to={`/weeks/${week.week_id}`}>{content}</Link>
  }
  if (isProjected) {
    return <Link to={`/weeks/projected?week_start=${week.week_start}`}>{content}</Link>
  }
  return content
}

// ---- Analytics view ----

interface AnalyticsProps {
  weeks: Week[]
  activeCategory: string | null
  onCategoryChange: (cat: string | null) => void
}

function AnalyticsView({ weeks, activeCategory, onCategoryChange }: AnalyticsProps) {
  // Only weeks with a real DB record have transactions
  const weekIds = new Set(
    weeks.filter((w) => w.week_id !== null).map((w) => w.week_id!)
  )

  const { data: allTransactions = [] } = useQuery<Transaction[]>({
    queryKey: ['transactions'],
    queryFn: () => api.get('/transactions').then((r) => r.data),
  })

  const txns = allTransactions.filter((t) => weekIds.has(t.week_id))

  // Grafico 1 — barre grouped per settimana
  const weekBarData: WeekBarData[] = weeks.map((w) => {
    const wTxns  = w.week_id ? txns.filter((t) => t.week_id === w.week_id) : []
    const income  = wTxns.filter((t) => t.type === 'income').reduce((s, t) => s + t.amount, 0)
    const expense = wTxns.filter((t) => t.type === 'expense').reduce((s, t) => s + t.amount, 0)
    return { label: format(parseISO(w.week_start), 'd/M'), income, expense }
  })

  // Grafico 2 — andamento saldo di chiusura
  const balanceData: BalanceData[] = weeks.map((w) => ({
    label: format(parseISO(w.week_start), 'd/M'),
    balance: w.closing_balance,
  }))

  // Grafico 3 — breakdown categorie spese (tutte le categorie aggregate)
  const catMap: Record<string, number> = {}
  txns
    .filter((t) => t.type === 'expense')
    .forEach((t) => {
      const cat = t.category ?? 'Altro'
      catMap[cat] = (catMap[cat] ?? 0) + t.amount
    })
  const categoryData: CategoryData[] = Object.entries(catMap)
    .map(([category, amount]) => ({ category, amount }))
    .sort((a, b) => b.amount - a.amount)

  // Lista transazioni filtrate per categoria attiva
  const filteredTxns = activeCategory
    ? txns
        .filter((t) => (t.category ?? 'Altro') === activeCategory && t.type === 'expense')
        .sort((a, b) => (b.transaction_date ?? '').localeCompare(a.transaction_date ?? ''))
    : []

  return (
    <div className="space-y-6">
      {/* Grafico 1 — barre grouped */}
      <section className="bg-surface rounded-2xl p-4 border border-white/5">
        <p className="text-xs text-muted uppercase tracking-wide mb-3">Entrate vs Uscite</p>
        <WeeklyBarChart data={weekBarData} />
      </section>

      {/* Grafici 2 + 3 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="bg-surface rounded-2xl p-4 border border-white/5">
          <p className="text-xs text-muted uppercase tracking-wide mb-3">Andamento saldo</p>
          <BalanceTrendChart data={balanceData} />
        </section>

        <section className="bg-surface rounded-2xl p-4 border border-white/5">
          <p className="text-xs text-muted uppercase tracking-wide mb-3">Breakdown categorie spese</p>
          <CategoryDonutChart
            data={categoryData}
            activeCategory={activeCategory}
            onCategoryClick={onCategoryChange}
          />
        </section>
      </div>

      {/* Transazioni filtrate per categoria */}
      {activeCategory && filteredTxns.length > 0 && (
        <section className="bg-surface rounded-2xl p-4 border border-white/5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-muted uppercase tracking-wide">
              Transazioni — {activeCategory}
            </p>
            <button
              onClick={() => onCategoryChange(null)}
              className="text-xs text-primary hover:text-primary/80 transition-colors"
            >
              Rimuovi filtro
            </button>
          </div>
          <div className="space-y-2">
            {filteredTxns.map((t) => (
              <div key={t.id} className="flex items-center justify-between text-sm py-1">
                <div className="min-w-0">
                  <p className="font-medium truncate">{t.name}</p>
                  {t.transaction_date && (
                    <p className="text-muted text-xs">
                      {format(parseISO(t.transaction_date), 'd MMM yyyy', { locale: it })}
                    </p>
                  )}
                </div>
                <p className="tabular-nums text-expense font-semibold">-{fmt(t.amount)}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
