export default function SatPanel({ satDetail, selectedSat }) {
  if (!selectedSat) return (
    <div style={{ color: '#475569', fontSize: 10, textAlign: 'center', paddingTop: 40 }}>
      Click a satellite on the map to inspect
    </div>
  )
  if (!satDetail) return (
    <div style={{ color: '#475569', fontSize: 10, textAlign: 'center', paddingTop: 40 }}>
      Loading...
    </div>
  )

  const statusColor = {
    NOMINAL: '#0d9488', EVADING: '#ef4444',
    RECOVERING: '#f59e0b', EOL: '#6b7280'
  }[satDetail.status] || '#3b82f6'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>
      {/* Header */}
      <div style={{
        background: '#0d1b2a', borderRadius: 6, padding: '8px 10px',
        borderLeft: `3px solid ${statusColor}`
      }}>
        <div style={{ color: '#e2e8f0', fontWeight: 'bold', fontSize: 12 }}>{satDetail.id}</div>
        <div style={{ color: statusColor, fontSize: 10, fontWeight: 'bold' }}>{satDetail.status}</div>
      </div>

      {/* Key metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        {[
          { label: 'LAT', val: satDetail.lat?.toFixed(2) + '°' },
          { label: 'LON', val: satDetail.lon?.toFixed(2) + '°' },
          { label: 'ALT', val: satDetail.alt_km?.toFixed(1) + ' km' },
          { label: 'DRIFT', val: satDetail.drift_km?.toFixed(2) + ' km' },
          { label: 'FUEL', val: satDetail.fuel_pct?.toFixed(1) + '%' },
          { label: 'ΔV USED', val: (satDetail.dv_used * 1000)?.toFixed(1) + ' m/s' },
        ].map(({ label, val }) => (
          <div key={label} style={{
            background: '#0d1b2a', borderRadius: 4,
            padding: '5px 8px', border: '1px solid #1e3a5f'
          }}>
            <div style={{ color: '#475569', fontSize: 8 }}>{label}</div>
            <div style={{ color: '#e2e8f0', fontSize: 11, fontWeight: 'bold' }}>{val}</div>
          </div>
        ))}
      </div>

      {/* Fuel bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#64748b', marginBottom: 3 }}>
          <span>FUEL REMAINING</span>
          <span>{satDetail.fuel_kg?.toFixed(1)} kg</span>
        </div>
        <div style={{ height: 8, background: '#1e293b', borderRadius: 4 }}>
          <div style={{
            width: `${satDetail.fuel_pct}%`, height: '100%',
            background: satDetail.fuel_pct > 40 ? '#0d9488' : satDetail.fuel_pct > 15 ? '#f59e0b' : '#ef4444',
            borderRadius: 4, transition: 'width 0.5s'
          }} />
        </div>
      </div>

      {/* In station-keeping box */}
      <div style={{
        fontSize: 9, padding: '4px 8px', borderRadius: 4,
        background: satDetail.in_box ? '#052e2e' : '#2d1515',
        color: satDetail.in_box ? '#0d9488' : '#ef4444',
        border: `1px solid ${satDetail.in_box ? '#0d9488' : '#ef4444'}44`
      }}>
        {satDetail.in_box ? '✓ Within 10km station-keeping box' : '⚠ OUTSIDE station-keeping box'}
      </div>

      {/* Maneuver log */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{ color: '#64748b', fontSize: 9, marginBottom: 4 }}>MANEUVER LOG</div>
        <div style={{ maxHeight: 120, overflowY: 'auto' }}>
          {(satDetail.maneuver_log || []).length === 0
            ? <div style={{ color: '#334155', fontSize: 9 }}>No maneuvers executed</div>
            : [...(satDetail.maneuver_log || [])].reverse().map((m, i) => (
              <div key={i} style={{
                fontSize: 8, color: '#64748b', padding: '2px 0',
                borderBottom: '1px solid #0d1b2a'
              }}>
                <span style={{
                  color: m.type === 'EVASION' ? '#ef4444' : m.type === 'RECOVERY' ? '#f59e0b' : '#3b82f6',
                  fontWeight: 'bold'
                }}>{m.type}</span>
                {' '}{m.burn_id.slice(-12)} | ΔV {m.dv_mag} m/s | ⛽ {m.fuel_remaining_kg} kg
              </div>
            ))
          }
        </div>
      </div>
    </div>
  )
}
