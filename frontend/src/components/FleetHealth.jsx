import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function FuelGauge({ sat }) {
  const pct = sat.fuel_pct
  const color = pct > 40 ? '#0d9488' : pct > 15 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#94a3b8', marginBottom: 2 }}>
        <span style={{ color: sat.status === 'EOL' ? '#6b7280' : '#e2e8f0', fontWeight: 'bold' }}>
          {sat.id.replace('SAT-', '')}
        </span>
        <span style={{ color }}>{pct.toFixed(0)}%</span>
      </div>
      <div style={{ height: 5, background: '#1e293b', borderRadius: 3 }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          background: color, borderRadius: 3,
          transition: 'width 0.5s ease'
        }} />
      </div>
    </div>
  )
}

export default function FleetHealth({ snapshot, fleetStats }) {
  const sats = snapshot?.satellites || []

  // DV vs collisions data for bar chart
  const dvData = sats
    .filter(s => s.dv_used > 0)
    .slice(0, 12)
    .map(s => ({
      name: s.id.replace('SAT-P', 'P').replace('-', '/'),
      dv: +(s.dv_used * 1000).toFixed(1),  // convert to m/s
      avoided: s.collisions_avoided,
    }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%' }}>

      {/* Fleet summary */}
      {fleetStats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 6 }}>
          {[
            { label: 'NOMINAL',    val: fleetStats.nominal,    color: '#0d9488' },
            { label: 'EVADING',    val: fleetStats.evading,    color: '#ef4444' },
            { label: 'RECOVERING', val: fleetStats.recovering, color: '#f59e0b' },
            { label: 'EOL',        val: fleetStats.eol,        color: '#6b7280' },
          ].map(({ label, val, color }) => (
            <div key={label} style={{
              background: '#0d1b2a', border: `1px solid ${color}33`,
              borderRadius: 6, padding: '6px 8px', textAlign: 'center'
            }}>
              <div style={{ color, fontSize: 18, fontWeight: 'bold' }}>{val}</div>
              <div style={{ color: '#64748b', fontSize: 9 }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Fuel gauges - scrollable */}
      <div>
        <div style={{ color: '#0d9488', fontSize: 10, fontWeight: 'bold', marginBottom: 6 }}>
          ⛽ FUEL STATUS — ALL SATELLITES
        </div>
        <div style={{ maxHeight: 140, overflowY: 'auto', paddingRight: 4 }}>
          {sats.map(s => <FuelGauge key={s.id} sat={s} />)}
        </div>
      </div>

      {/* ΔV vs Collisions Avoided */}
      {dvData.length > 0 && (
        <div style={{ flex: 1 }}>
          <div style={{ color: '#0d9488', fontSize: 10, fontWeight: 'bold', marginBottom: 4 }}>
            ΔV COST vs COLLISIONS AVOIDED
          </div>
          <ResponsiveContainer width="100%" height={100}>
            <BarChart data={dvData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fill: '#475569', fontSize: 8 }} />
              <YAxis tick={{ fill: '#475569', fontSize: 8 }} />
              <Tooltip
                contentStyle={{ background: '#0d1b2a', border: '1px solid #1e3a5f', fontSize: 10 }}
                labelStyle={{ color: '#5eead4' }}
              />
              <Bar dataKey="dv" name="ΔV (m/s)" radius={[2, 2, 0, 0]}>
                {dvData.map((entry, i) => (
                  <Cell key={i} fill={entry.avoided > 0 ? '#0d9488' : '#1e3a5f'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Uptime indicator */}
      {fleetStats && (
        <div style={{
          background: '#0d1b2a', border: '1px solid #1e3a5f',
          borderRadius: 6, padding: '8px 12px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center'
        }}>
          <span style={{ color: '#64748b', fontSize: 10 }}>CONSTELLATION UPTIME</span>
          <span style={{
            color: fleetStats.uptime_pct > 90 ? '#0d9488' : '#f59e0b',
            fontSize: 18, fontWeight: 'bold'
          }}>
            {fleetStats.uptime_pct}%
          </span>
        </div>
      )}
    </div>
  )
}
