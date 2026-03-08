import { useEffect, useRef } from 'react'

const W = 860, H = 430

function latLonToXY(lat, lon) {
  const x = ((lon + 180) / 360) * W
  const y = ((90 - lat) / 180) * H
  return [x, y]
}

// Approximate terminator line
function terminatorPoints() {
  const pts = []
  const now = new Date()
  const dayOfYear = Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 86400000)
  const declination = -23.45 * Math.cos((360 / 365) * (dayOfYear + 10) * Math.PI / 180)
  for (let lon = -180; lon <= 180; lon += 2) {
    const lat = -Math.atan2(
      Math.cos((lon + now.getUTCHours() * 15) * Math.PI / 180),
      Math.tan(declination * Math.PI / 180)
    ) * 180 / Math.PI
    pts.push([lat, lon])
  }
  return pts
}

export default function GroundTrack({ snapshot, selectedSat, onSelectSat, satDetail }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, W, H)

    // Background
    ctx.fillStyle = '#050d1a'
    ctx.fillRect(0, 0, W, H)

    // Grid lines
    ctx.strokeStyle = '#0d2040'
    ctx.lineWidth = 0.5
    for (let lat = -90; lat <= 90; lat += 30) {
      const y = ((90 - lat) / 180) * H
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
    }
    for (let lon = -180; lon <= 180; lon += 30) {
      const x = ((lon + 180) / 360) * W
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
    }

    // Equator
    ctx.strokeStyle = '#1e3a5f'
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(0, H/2); ctx.lineTo(W, H/2); ctx.stroke()

    // Terminator
    const term = terminatorPoints()
    ctx.strokeStyle = 'rgba(255,200,0,0.25)'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    term.forEach(([lat, lon], i) => {
      const [x, y] = latLonToXY(lat, lon)
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Night shadow (simple fill below terminator)
    ctx.fillStyle = 'rgba(0,0,0,0.3)'
    ctx.beginPath()
    term.forEach(([lat, lon], i) => {
      const [x, y] = latLonToXY(lat, lon)
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    })
    ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath(); ctx.fill()

    if (!snapshot) return

    // Debris (tiny dots, max 2000 for perf)
    ctx.fillStyle = 'rgba(255,100,50,0.5)'
    for (const deb of snapshot.debris_cloud || []) {
      const [, lat, lon] = deb
      const [x, y] = latLonToXY(lat, lon)
      ctx.beginPath(); ctx.arc(x, y, 1.2, 0, Math.PI * 2); ctx.fill()
    }

    // Ground stations
    const GS = [
      { name: 'ISTRAC', lat: 13.03, lon: 77.52 },
      { name: 'Svalbard', lat: 78.23, lon: 15.41 },
      { name: 'Goldstone', lat: 35.43, lon: -116.89 },
      { name: 'Punta Arenas', lat: -53.15, lon: -70.92 },
      { name: 'IIT Delhi', lat: 28.55, lon: 77.19 },
      { name: 'McMurdo', lat: -77.85, lon: 166.67 },
    ]
    GS.forEach(gs => {
      const [x, y] = latLonToXY(gs.lat, gs.lon)
      ctx.strokeStyle = '#0d9488'; ctx.lineWidth = 1.5
      ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.stroke()
      ctx.fillStyle = '#5eead4'; ctx.font = '9px monospace'
      ctx.fillText(gs.name, x + 6, y - 3)
    })

    // Satellite trajectory
    if (satDetail?.trajectory) {
      ctx.strokeStyle = 'rgba(250,204,21,0.6)'
      ctx.lineWidth = 1.5; ctx.setLineDash([4, 3])
      ctx.beginPath()
      satDetail.trajectory.forEach(({ lat, lon }, i) => {
        const [x, y] = latLonToXY(lat, lon)
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      })
      ctx.stroke(); ctx.setLineDash([])
    }

    // Satellites
    for (const sat of snapshot.satellites || []) {
      const [x, y] = latLonToXY(sat.lat, sat.lon)
      const isSelected = sat.id === selectedSat
      const color = sat.status === 'NOMINAL' ? '#0d9488'
                  : sat.status === 'EVADING' ? '#ef4444'
                  : sat.status === 'RECOVERING' ? '#f59e0b'
                  : sat.status === 'EOL' ? '#6b7280' : '#3b82f6'

      // Outer glow for selected
      if (isSelected) {
        ctx.beginPath()
        ctx.arc(x, y, 9, 0, Math.PI * 2)
        ctx.fillStyle = 'rgba(250,204,21,0.3)'
        ctx.fill()
      }

      ctx.beginPath()
      ctx.arc(x, y, isSelected ? 6 : 4, 0, Math.PI * 2)
      ctx.fillStyle = color; ctx.fill()
      ctx.strokeStyle = isSelected ? '#fbbf24' : 'rgba(255,255,255,0.3)'
      ctx.lineWidth = isSelected ? 2 : 0.5; ctx.stroke()

      if (isSelected) {
        ctx.fillStyle = '#fbbf24'; ctx.font = 'bold 9px monospace'
        ctx.fillText(sat.id, x + 7, y - 5)
      }
    }

    // Legend
    ctx.font = '9px monospace'
    const legend = [
      { color: '#0d9488', label: 'NOMINAL' },
      { color: '#ef4444', label: 'EVADING' },
      { color: '#f59e0b', label: 'RECOVERING' },
      { color: '#6b7280', label: 'EOL' },
      { color: 'rgba(255,100,50,0.5)', label: 'DEBRIS' },
    ]
    legend.forEach(({ color, label }, i) => {
      ctx.fillStyle = color
      ctx.fillRect(8, 8 + i * 14, 8, 8)
      ctx.fillStyle = '#94a3b8'
      ctx.fillText(label, 20, 16 + i * 14)
    })

  }, [snapshot, selectedSat, satDetail])

  const handleClick = (e) => {
    if (!snapshot?.satellites) return
    const rect = canvasRef.current.getBoundingClientRect()
    const mx = (e.clientX - rect.left) * (W / rect.width)
    const my = (e.clientY - rect.top) * (H / rect.height)
    for (const sat of snapshot.satellites) {
      const [x, y] = latLonToXY(sat.lat, sat.lon)
      if (Math.hypot(mx - x, my - y) < 10) {
        onSelectSat(sat.id === selectedSat ? null : sat.id)
        return
      }
    }
    onSelectSat(null)
  }

  return (
    <canvas
      ref={canvasRef} width={W} height={H}
      style={{ width: '100%', height: '100%', cursor: 'crosshair', display: 'block' }}
      onClick={handleClick}
    />
  )
}
