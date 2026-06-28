type KeyValueListProps = {
  items: Array<{ label: string; value: string | number | undefined }>
}

export function KeyValueList({ items }: KeyValueListProps) {
  return (
    <div className="metric-grid">
      {items.map((item) => (
        <div className="metric" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value ?? '未记录'}</strong>
        </div>
      ))}
    </div>
  )
}
