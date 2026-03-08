export default function ManeuverTimeline({ maneuvers, simTime }) {
  const now = simTime ? new Date(simTime) : new Date()
  const windowMs = 3600 * 1000 * 2  // 2 hour window
  const start = now.getTime()
  const end = start + windowMs

  const typeColor = {
    EVASION:   '#ef4444',
    RECOVERY:  '#f59e0b',
    GRAVEYARD: '#6b7280',
    MANUAL:    '#3b82f6',
  }

  const inWindow = maneuvers.filter(m => {
    const t = new Date(m.burn_time).getTime()
    return t >= start && t <= end
  })

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: '#0d9488', fontSize: 10, fontWeight: 'bold' }}>
          📅 MANEUVER TIMELINE (NEXT 2H)
        </span>
        <span style={{ color: '#475569', fontSize: 9 }}>
          {inWindow.length} pending burn{inWindow.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Timeline bar */}
      <div style={{ position: 'relative', height: 20, background: '#0d1b2a', borderRadius: 4, overflow: 'hidden' }}>
        {/* NOW marker */}
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: 2, background: '#0d9488', zIndex: 2
        }} />
        {inWindow.map((m, i) => {
          const t = new Date(m.burn_time).getTime()
          const pct = ((t - start) / windowMs) * 100
          const color = typeColor[m.burn_type] || '#3b82f6'
          return (
            <div key={i} title={`${m.satellite_id} | ${m.burn_type} | ΔV: ${m.dv_mag_ms} m/s`}
              style={{
                position: 'absolute',
                left: `${pct}%`, top: 2, bottom: 2, width: 6,
                background: color, borderRadius: 2,
                cursor: 'pointer', opacity: 0.85,
              }} />
          )
        })}
        {/* Cooldown zones */}
        {inWindow.map((m, i) => {
          const t = new Date(m.burn_time).getTime()
          const pct = ((t - start) / windowMs) * 100
          const cooldownPct = (600000 / windowMs) * 100
          return (
            <div key={`cd-${i}`}
              style={{
                position: 'absolute',
                left: `${pct}%`, top: 2, bottom: 2,
                width: `${cooldownPct}%`,
                background: 'rgba(100,100,100,0.15)',
                borderRadius: 2,
              }} />
          )
        })}
      </div>

      {/* Time labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 8, color: '#475569' }}>
        <span>NOW</span>
        <span>+30m</span>
        <span>+1h</span>
        <span>+1h30</span>
        <span>+2h</span>
      </div>

      {/* Burn list */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {inWindow.length === 0 ? (
          <div style={{ color: '#475569', fontSize: 10, textAlign: 'center', paddingTop: 20 }}>
            No burns scheduled in next 2 hours
          </div>
        ) : inWindow.map((m, i) => {
          const color = typeColor[m.burn_type] || '#3b82f6'
          const burnTime = new Date(m.burn_time)
          const minsFromNow = Math.round((burnTime - now) / 60000)
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '4px 6px', marginBottom: 3,
              background: '#0d1b2a', borderRadius: 4,
              borderLeft: `3px solid ${color}`,
            }}>
              <div style={{
                width: 60, color, fontSize: 8,
                fontWeight: 'bold', flexShrink: 0
              }}>
                {m.burn_type}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: '#e2e8f0', fontSize: 9, fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {m.satellite_id}
                </div>
                <div style={{ color: '#475569', fontSize: 8 }}>
                  T+{minsFromNow}m | ΔV {m.dv_mag_ms} m/s
                </div>
              </div>
              <div style={{ color: '#475569', fontSize: 8, flexShrink: 0 }}>
                {burnTime.toISOString().slice(11, 19)}Z
              </div>
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        {Object.entries(typeColor).map(([type, color]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 8, height: 8, background: color, borderRadius: 2 }} />
            <span style={{ color: '#64748b', fontSize: 8 }}>{type}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
