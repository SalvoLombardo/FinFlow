import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { format, parseISO } from 'date-fns'
import { it } from 'date-fns/locale'
import { api } from '../api/client'
import { RangeSelector } from '../components/analytics/RangeSelector'
import { WeeklyBarChart } from '../components/analytics/WeeklyBarChart'
import type { WeekBarData } from '../components/analytics/WeeklyBarChart'
import { BalanceTrendChart } from '../components/analytics/BalanceTrendChart'
import type { BalanceData } from '../components/analytics/BalanceTrendChart'
import { CategoryDonutChart } from '../components/analytics/CategoryDonutChart'
import type { CategoryData } from '../components/analytics/CategoryDonutChart'
import { CreateWeekModal } from '../components/CreateWeekModal'

interface Week {
  id: string
  week_start: string
  week_end: string
  opening_balance: number
  closing_balance: number | null
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
  const [params, setParams]       = useSearchParams()
  const [createOpen, setCreateOpen] = useState(false)

  const view     = params.get('view')     ?? 'list'
  const range    = parseInt(params.get('range') ?? '12', 10)
  const category = params.get('category') ?? null

  const { data: weeks = [], isLoading } = useQuery<Week[]>({
    queryKey: ['weeks'],
    queryFn: () => api.get('/weeks').then((r) => r.data),
  })

  const setView = (v: string) =>
    setParams((p) => { p.set('view', v); return p })

  const setRange = (r: number) =>
    setParams((p) => { p.set('range', String(r)); return p })

  const setCategory = (cat: string | null) =>
    setParams((p) => { cat === null ? p.delete('category') : p.set('category', cat); return p })

  // Use last closed week's closing_balance as default opening for new week
  const sorted = [...weeks].sort((a, b) => b.week_start.localeCompare(a.week_start))
  const lastClosed = sorted.find((w) => w.closing_balance !== null)
  const defaultOpening = lastClosed?.closing_balance ?? 0

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-lg font-semibold">Settimane</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <span className="text-lg leading-none">+</span>
            Nuova
          </button>
          <div className="flex bg-surface rounded-lg p-0.5 gap-0.5 border border-white/5">
            <ViewTab active={view === 'list'}      onClick={() => setView('list')}>Lista</ViewTab>
            <ViewTab active={view === 'analytics'} onClick={() => setView('analytics')}>Analytics</ViewTab>
          </div>
        </div>
      </div>

      <CreateWeekModal
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultOpeningBalance={defaultOpening}
      />

      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-surface rounded-xl" />)}
        </div>
      ) : view === 'list' ? (
        <ListView weeks={weeks} />
      ) : (
        <AnalyticsView
          weeks={weeks}
          range={range}
          activeCategory={category}
          onRangeChange={setRange}
          onCategoryChange={setCategory}
        />
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

// ---- Analytics view ----

interface AnalyticsProps {
  weeks: Week[]
  range: number
  activeCategory: string | null
  onRangeChange: (r: number) => void
  onCategoryChange: (cat: string | null) => void
}

function AnalyticsView({ weeks, range, activeCategory, onRangeChange, onCategoryChange }: AnalyticsProps) {
  const sorted     = [...weeks].sort((a, b) => a.week_start.localeCompare(b.week_start))
  const rangeWeeks = sorted.slice(-range)
  const weekIds    = new Set(rangeWeeks.map((w) => w.id))

  const { data: allTransactions = [] } = useQuery<Transaction[]>({
    queryKey: ['transactions'],
    queryFn: () => api.get('/transactions').then((r) => r.data),
  })

  const txns = allTransactions.filter((t) => weekIds.has(t.week_id))

  // Grafico 1 — barre grouped
  const weekBarData: WeekBarData[] = rangeWeeks.map((w) => {
    const wTxns  = txns.filter((t) => t.week_id === w.id)
    const income  = wTxns.filter((t) => t.type === 'income').reduce((s, t) => s + t.amount, 0)
    const expense = wTxns.filter((t) => t.type === 'expense').reduce((s, t) => s + t.amount, 0)
    return { label: format(parseISO(w.week_start), 'd/M'), income, expense }
  })

  // Grafico 2 — andamento saldo
  const balanceData: BalanceData[] = rangeWeeks.map((w) => ({
    label: format(parseISO(w.week_start), 'd/M'),
    balance: w.closing_balance,
  }))

  // Grafico 3 — breakdown categorie spese (sempre tutte le categorie)
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

  // Lista transazioni filtrata per categoria attiva
  const filteredTxns = activeCategory
    ? txns
        .filter((t) => (t.category ?? 'Altro') === activeCategory && t.type === 'expense')
        .sort((a, b) => (b.transaction_date ?? '').localeCompare(a.transaction_date ?? ''))
    : []

  return (
    <div className="space-y-6">
      {/* Range selector */}
      <div className="flex justify-end">
        <RangeSelector value={range} onChange={onRangeChange} />
      </div>

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

// ---- List view ----

function ListView({ weeks }: { weeks: Week[] }) {
  if (weeks.length === 0) {
    return <p className="text-muted text-sm text-center py-12">Nessuna settimana trovata.</p>
  }

  const grouped: Record<string, Week[]> = {}
  for (const w of weeks) {
    const month = format(parseISO(w.week_start), 'MMMM yyyy', { locale: it })
    ;(grouped[month] ??= []).push(w)
  }

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([month, mWeeks]) => (
        <div key={month}>
          <p className="text-muted text-xs uppercase tracking-wide mb-2">{month}</p>
          <div className="space-y-2">
            {mWeeks.map((w) => <WeekSummaryBar key={w.id} week={w} />)}
          </div>
        </div>
      ))}
    </div>
  )
}

function WeekSummaryBar({ week }: { week: Week }) {
  const start  = format(parseISO(week.week_start), 'd MMM', { locale: it })
  const end    = format(parseISO(week.week_end),   'd MMM', { locale: it })
  const closed = week.closing_balance !== null
  const delta  = closed ? week.closing_balance! - week.opening_balance : null

  return (
    <Link
      to={`/weeks/${week.id}`}
      className="flex items-center justify-between bg-surface hover:bg-white/5 border border-white/5 rounded-xl px-4 py-3 transition-colors"
    >
      <div>
        <p className="text-sm font-medium">{start} – {end}</p>
        <p className="text-muted text-xs mt-0.5">
          Apertura: <span className="tabular-nums">{fmt(week.opening_balance)}</span>
        </p>
      </div>
      <div className="text-right">
        {closed ? (
          <>
            <p className={`tabular-nums text-sm font-semibold ${delta! >= 0 ? 'text-income' : 'text-expense'}`}>
              {delta! >= 0 ? '+' : ''}{fmt(delta!)}
            </p>
            <p className="text-muted text-xs tabular-nums">{fmt(week.closing_balance!)}</p>
          </>
        ) : (
          <span className="text-xs text-muted bg-white/5 px-2 py-0.5 rounded-full">In corso</span>
        )}
      </div>
    </Link>
  )
}
