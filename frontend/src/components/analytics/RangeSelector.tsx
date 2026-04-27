const RANGES = [
  { label: '4W', value: 4 },
  { label: '8W', value: 8 },
  { label: '12W', value: 12 },
]

interface Props {
  value: number
  onChange: (v: number) => void
}

export function RangeSelector({ value, onChange }: Props) {
  return (
    <div className="flex bg-surface rounded-lg p-0.5 gap-0.5 border border-white/5">
      {RANGES.map((r) => (
        <button
          key={r.value}
          onClick={() => onChange(r.value)}
          className={[
            'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
            value === r.value ? 'bg-primary text-white' : 'text-muted hover:text-text',
          ].join(' ')}
        >
          {r.label}
        </button>
      ))}
    </div>
  )
}
