import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'

export interface CategoryData {
  category: string
  amount: number
}

const COLORS = [
  '#6366F1', '#F59E0B', '#3B82F6', '#EC4899',
  '#14B8A6', '#F97316', '#8B5CF6', '#06B6D4',
  '#84CC16', '#A3E635',
]

function fmt(n: number) {
  return new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface border border-white/10 rounded-xl p-3 text-xs shadow-lg">
      <p className="font-medium text-text mb-1">{payload[0].name}</p>
      <p className="tabular-nums text-muted">{fmt(payload[0].value)}</p>
    </div>
  )
}

interface Props {
  data: CategoryData[]
  onCategoryClick?: (category: string | null) => void
  activeCategory?: string | null
}

export function CategoryDonutChart({ data, onCategoryClick, activeCategory }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-44 text-muted text-sm">
        Nessuna spesa nel periodo
      </div>
    )
  }

  const total = data.reduce((s, d) => s + d.amount, 0)

  const handleClick = (entry: CategoryData) => {
    onCategoryClick?.(activeCategory === entry.category ? null : entry.category)
  }

  return (
    <div className="flex flex-col sm:flex-row gap-4 items-start">
      {/* Donut */}
      <div className="w-full sm:w-44 h-44 flex-shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="amount"
              nameKey="category"
              innerRadius="55%"
              outerRadius="80%"
              paddingAngle={2}
              onClick={(data) => handleClick(data as unknown as CategoryData)}
              style={{ cursor: 'pointer' }}
            >
              {data.map((entry, i) => (
                <Cell
                  key={entry.category}
                  fill={COLORS[i % COLORS.length]}
                  opacity={!activeCategory || activeCategory === entry.category ? 1 : 0.3}
                  stroke="transparent"
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex-1 space-y-1 max-h-44 overflow-y-auto">
        {data.map((entry, i) => {
          const pct = total > 0 ? ((entry.amount / total) * 100).toFixed(1) : '0.0'
          const isActive = activeCategory === entry.category
          return (
            <button
              key={entry.category}
              onClick={() => handleClick(entry)}
              className={[
                'w-full flex items-center gap-2 text-left px-2 py-1 rounded-lg transition-colors text-xs',
                isActive ? 'bg-white/10' : 'hover:bg-white/5',
                !activeCategory || isActive ? 'opacity-100' : 'opacity-40',
              ].join(' ')}
            >
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ background: COLORS[i % COLORS.length] }}
              />
              <span className="flex-1 truncate text-text">{entry.category}</span>
              <span className="tabular-nums text-muted">{fmt(entry.amount)}</span>
              <span className="tabular-nums text-muted w-10 text-right">{pct}%</span>
            </button>
          )
        })}
        {activeCategory && (
          <button
            onClick={() => onCategoryClick?.(null)}
            className="w-full text-center text-xs text-primary hover:text-primary/80 py-1"
          >
            Rimuovi filtro
          </button>
        )}
      </div>
    </div>
  )
}
