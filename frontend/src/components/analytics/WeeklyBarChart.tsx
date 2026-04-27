import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'

export interface WeekBarData {
  label: string
  income: number
  expense: number
}

function shortFmt(n: number) {
  if (Math.abs(n) >= 1000) return `€${(n / 1000).toFixed(1)}k`
  return `€${n.toFixed(0)}`
}

function fmt(n: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
}

function CustomTooltip({ active, payload, label }: {
  active?: boolean
  payload?: { dataKey: string; value: number }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  const income  = payload.find((p) => p.dataKey === 'income')?.value  ?? 0
  const expense = payload.find((p) => p.dataKey === 'expense')?.value ?? 0
  const delta   = income - expense
  return (
    <div className="bg-surface border border-white/10 rounded-xl p-3 text-xs space-y-1 shadow-lg">
      <p className="font-medium text-text mb-1.5">{label}</p>
      <p style={{ color: '#22C55E' }}>Entrate: {fmt(income)}</p>
      <p style={{ color: '#EF4444' }}>Uscite: {fmt(expense)}</p>
      <p className={`font-semibold border-t border-white/10 pt-1.5 ${delta >= 0 ? '' : ''}`}
        style={{ color: delta >= 0 ? '#22C55E' : '#EF4444' }}
      >
        Delta: {delta >= 0 ? '+' : ''}{fmt(delta)}
      </p>
    </div>
  )
}

export function WeeklyBarChart({ data }: { data: WeekBarData[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} barGap={3} barCategoryGap="35%">
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: '#64748B', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={shortFmt}
          tick={{ fill: '#64748B', fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={52}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
        <Bar dataKey="income"  fill="#22C55E" radius={[3, 3, 0, 0]} name="Entrate" maxBarSize={20} />
        <Bar dataKey="expense" fill="#EF4444" radius={[3, 3, 0, 0]} name="Uscite"  maxBarSize={20} />
      </BarChart>
    </ResponsiveContainer>
  )
}
