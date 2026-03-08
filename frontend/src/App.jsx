import { useState, useEffect } from 'react'
import { useACM } from './utils/useACM'
import GroundTrack from './components/GroundTrack'
import BullseyePlot from './components/BullseyePlot'
import FleetHealth from './components/FleetHealth'
import ManeuverTimeline from './components/ManeuverTimeline'
import SatPanel from './components/SatPanel'

const C = {
  bg:      '#050d1a',
  panel:   '#0a1628',
  border:  '#1e3a5f',
  teal:    '#0d9488',
  tealLt:  '#5eead4',
  muted:   '#475569',
  text:    '#e2e8f0',
  red:     '#ef4444',
  amber:   '#f59e0b',
}

function Panel({ title, children, style = {} }) {
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: 10, display: 'flex',
      flexDirection: 'column', gap: 8, overflow: 'hidden',
      ...style
    }}>
      {title && (
        <div style={{
          color: C.teal, fontSize: 10, fontWeight: 'bold',
          letterSpacing: '0.08em', borderBottom: `1px solid ${C.border}`,
          paddingBottom: 6, flexShrink: 0
        }}>
          {title}
        </div>
      )}
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        {children}
      </div>
    </div>
  )
}

function StatusBar({ fleetStats, error, simRunning, stepSim, autoStep, simTime }) {
  const [auto, setAuto] = useState(false)

  const toggleAuto = () => {
    const next = !auto
    setAuto(next)
    autoStep(next)
  }

  return (
    <div style={{
      height: 44, background: '#030810',
      borderBottom: `1px solid ${C.border}`,
      display: 'flex', alignItems: 'center',
      padding: '0 16px', gap: 20, flexShrink: 0
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 16 }}>🛰️</span>
        <div>
          <div style={{ color: C.tealLt, fontSize: 12, fontWeight: 'bold', lineHeight: 1 }}>
            PROJECT AETHER
          </div>
          <div style={{ color: C.muted, fontSize: 8, lineHeight: 1 }}>
            AUTONOMOUS CONSTELLATION MANAGER
          </div>
        </div>
      </div>

      <div style={{ width: 1, height: 24, background: C.border }} />

      {/* Sim time */}
      <div>
        <div style={{ color: C.muted, fontSize: 7 }}>SIM TIME (UTC)</div>
        <div style={{ color: C.tealLt, fontSize: 10, fontFamily: 'monospace' }}>
          {simTime ? new Date(simTime).toISOString().slice(0, 19) + 'Z' : '—'}
        </div>
      </div>

      {/* Stats */}
      {fleetStats && [
        { label: 'SATS', val: fleetStats.total_satellites, color: C.text },
        { label: 'NOMINAL', val: fleetStats.nominal, color: C.teal },
        { label: 'ACTIVE CDMs', val: fleetStats.active_cdms, color: fleetStats.active_cdms > 0 ? C.red : C.muted },
        { label: 'AVOIDED', val: fleetStats.collisions_avoided, color: C.amber },
        { label: 'UPTIME', val: fleetStats.uptime_pct + '%', color: fleetStats.uptime_pct > 90 ? C.teal : C.amber },
      ].map(({ label, val, color }) => (
        <div key={label}>
          <div style={{ color: C.muted, fontSize: 7 }}>{label}</div>
          <div style={{ color, fontSize: 11, fontWeight: 'bold' }}>{val}</div>
        </div>
      ))}

      <div style={{ flex: 1 }} />

      {/* Error */}
      {error && (
        <div style={{ color: C.red, fontSize: 9, background: '#2d1515', padding: '3px 8px', borderRadius: 4 }}>
          ⚠ {error}
        </div>
      )}

      {/* Controls */}
      <button onClick={() => stepSim(60)}
        disabled={simRunning}
        style={{
          background: simRunning ? '#1e293b' : C.teal,
          color: simRunning ? C.muted : '#000',
          border: 'none', borderRadius: 4, padding: '4px 10px',
          fontSize: 9, fontWeight: 'bold', cursor: simRunning ? 'not-allowed' : 'pointer'
        }}>
        {simRunning ? '⟳ STEPPING...' : '▶ STEP +1min'}
      </button>
      <button onClick={toggleAuto}
        style={{
          background: auto ? '#7f1d1d' : '#1e293b',
          color: auto ? C.red : C.muted,
          border: `1px solid ${auto ? C.red : C.border}`,
          borderRadius: 4, padding: '4px 10px',
          fontSize: 9, fontWeight: 'bold', cursor: 'pointer'
        }}>
        {auto ? '⏹ STOP AUTO' : '⚡ AUTO SIM'}
      </button>

      {/* Team */}
      <div style={{ borderLeft: `1px solid ${C.border}`, paddingLeft: 12 }}>
        <div style={{ color: C.muted, fontSize: 7 }}>TEAM</div>
        <div style={{ color: C.tealLt, fontSize: 9, fontWeight: 'bold' }}>DEBUG THUGS</div>
        <div style={{ color: C.muted, fontSize: 7 }}>C.V. RAMAN GLOBAL UNIVERSITY</div>
      </div>
    </div>
  )
}

export default function App() {
  const {
    snapshot, conjunctions, fleetStats, maneuvers,
    selectedSat, setSelectedSat, satDetail,
    error, simRunning, stepSim, autoStep
  } = useACM()

  return (
    <div style={{
      width: '100vw', height: '100vh',
      background: C.bg, display: 'flex', flexDirection: 'column',
      fontFamily: "'Courier New', monospace", overflow: 'hidden'
    }}>
      {/* Top status bar */}
      <StatusBar
        fleetStats={fleetStats}
        error={error}
        simRunning={simRunning}
        stepSim={stepSim}
        autoStep={autoStep}
        simTime={snapshot?.timestamp}
      />

      {/* Main grid */}
      <div style={{
        flex: 1, display: 'grid', minHeight: 0,
        gridTemplateColumns: '1fr 260px',
        gridTemplateRows: '1fr 220px',
        gap: 6, padding: 6,
      }}>

        {/* Ground Track Map — large top left */}
        <Panel title="🌍 GROUND TRACK — MERCATOR PROJECTION">
          <GroundTrack
            snapshot={snapshot}
            selectedSat={selectedSat}
            onSelectSat={setSelectedSat}
            satDetail={satDetail}
          />
        </Panel>

        {/* Right column: Bullseye + Sat detail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Panel title="🎯 CONJUNCTION BULLSEYE PLOT" style={{ flex: '0 0 auto' }}>
            <BullseyePlot conjunctions={conjunctions} selectedSat={selectedSat} />
          </Panel>
          <Panel title="📡 SATELLITE INSPECTOR" style={{ flex: 1 }}>
            <SatPanel satDetail={satDetail} selectedSat={selectedSat} />
          </Panel>
        </div>

        {/* Bottom left: Fleet health */}
        <Panel title="⛽ FLEET HEALTH & FUEL MONITOR" style={{ overflow: 'auto' }}>
          <FleetHealth snapshot={snapshot} fleetStats={fleetStats} />
        </Panel>

        {/* Bottom right: Maneuver timeline */}
        <Panel title="📅 MANEUVER GANTT SCHEDULER">
          <ManeuverTimeline
            maneuvers={maneuvers}
            simTime={snapshot?.timestamp}
          />
        </Panel>
      </div>
    </div>
  )
}
