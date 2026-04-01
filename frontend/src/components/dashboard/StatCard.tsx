import React from 'react'

interface StatCardProps {
  label: string
  value: string | number
  hint: string
}

export function StatCard({ label, value, hint }: StatCardProps) {
  return (
    <div className="panel stat-card">
      <p className="eyebrow">{label}</p>
      <h3>{value}</h3>
      <p className="muted">{hint}</p>
    </div>
  )
}
