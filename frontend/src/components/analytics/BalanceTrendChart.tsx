import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine,
} from 'recharts'

export interface BalanceData {
  label: string
  balance: number | null
}

function shortFmt(n: number) {
  if (Math.abs(n) >= 1000) return `€${(n / 1000).toFixed(1)}k`
  return `€${n.toFixed(0)}`
}

function fmt(n: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
}

interface Props {
  data: BalanceData[]
  goalTarget?: number
}

export function BalanceTrendChart({ data, goalTarget }: Props) {
  const valid = data.filter((d) => d.balance !== null)
  const first = valid[0]?.balance ?? 0
  const last  = valid[valid.length - 1]?.balance ?? 0
  const isRising   = last >= first
  const strokeColor = isRising ? '#22C55E' : '#EF4444'
  const gradId = 'balanceAreaGrad'

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={strokeColor} stopOpacity={0.2} />
            <stop offset="95%" stopColor={strokeColor} stopOpacity={0} />
          </linearGradient>
        </defs>

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
        <Tooltip
          formatter={(v) => [fmt(v as number), 'Saldo']}
          labelStyle={{ color: '#F1F5F9', marginBottom: 4 }}
          contentStyle={{
            background: '#1A1D27',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 12,
            fontSize: 12,
          }}
        />

        <Area
          dataKey="balance"
          stroke={strokeColor}
          strokeWidth={2}
          fill={`url(#${gradId})`}
          connectNulls
          dot={false}
          activeDot={{ r: 4, fill: strokeColor, strokeWidth: 0 }}
        />

        {goalTarget !== undefined && (
          <ReferenceLine
            y={goalTarget}
            stroke="#6366F1"
            strokeDasharray="6 3"
            strokeWidth={1.5}
            label={{
              value: `Obiettivo ${fmt(goalTarget)}`,
              fill: '#6366F1',
              fontSize: 10,
              position: 'insideTopRight',
            }}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  )
}
