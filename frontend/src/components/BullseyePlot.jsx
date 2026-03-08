import { useEffect, useRef } from 'react'

const SIZE = 260
const CX = SIZE / 2, CY = SIZE / 2
const MAX_R = 110

function riskColor(risk) {
  if (risk === 'CRITICAL') return '#ef4444'
  if (risk === 'RED')      return '#f97316'
  if (risk === 'YELLOW')   return '#eab308'
  return '#22c55e'
}

export default function BullseyePlot({ conjunctions, selectedSat }) {
  const canvasRef = useRef(null)

  const cdms = selectedSat
    ? conjunctions.filter(c => c.sat_id === selectedSat)
    : conjunctions.slice(0, 20)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, SIZE, SIZE)

    // Background
    ctx.fillStyle = '#050d1a'
    ctx.fillRect(0, 0, SIZE, SIZE)

    // Rings: 1km, 5km, 50km
    const rings = [
      { r: MAX_R * 0.1, label: '0.1km', color: '#ef4444' },
      { r: MAX_R * 0.3, label: '1km',   color: '#f97316' },
      { r: MAX_R * 0.7, label: '5km',   color: '#eab308' },
      { r: MAX_R,       label: '50km',  color: '#1e3a5f' },
    ]
    rings.forEach(({ r, label, color }) => {
      ctx.beginPath()
      ctx.arc(CX, CY, r, 0, Math.PI * 2)
      ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.globalAlpha = 0.5
      ctx.stroke(); ctx.globalAlpha = 1
      ctx.fillStyle = '#475569'; ctx.font = '8px monospace'
      ctx.fillText(label, CX + r + 2, CY - 2)
    })

    // Crosshairs
    ctx.strokeStyle = '#1e3a5f'; ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.moveTo(CX, 0); ctx.lineTo(CX, SIZE); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(0, CY); ctx.lineTo(SIZE, CY); ctx.stroke()

    // Center = our satellite
    ctx.beginPath(); ctx.arc(CX, CY, 5, 0, Math.PI * 2)
    ctx.fillStyle = '#0d9488'; ctx.fill()
    ctx.fillStyle = '#5eead4'; ctx.font = '8px monospace'
    ctx.fillText('SAT', CX + 6, CY - 4)

    // Plot debris
    cdms.forEach((c, i) => {
      const dist = Math.min(c.miss_km, 50)
      const r = (dist / 50) * MAX_R
      const angle = (i / Math.max(cdms.length, 1)) * Math.PI * 2 - Math.PI / 2
      const x = CX + r * Math.cos(angle)
      const y = CY + r * Math.sin(angle)

      ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2)
      ctx.fillStyle = riskColor(c.risk); ctx.fill()

      // Tooltip label
      ctx.fillStyle = '#94a3b8'; ctx.font = '7px monospace'
      ctx.fillText(c.deb_id.slice(-5), x + 6, y + 3)
    })

    // TCA rings label
    ctx.fillStyle = '#64748b'; ctx.font = '8px monospace'
    ctx.fillText('Miss Distance (km)', 4, SIZE - 4)

  }, [cdms])

  return (
    <div style={{ textAlign: 'center' }}>
      <canvas ref={canvasRef} width={SIZE} height={SIZE}
        style={{ width: SIZE, height: SIZE }} />
      <div style={{ color: '#64748b', fontSize: 9, marginTop: 4 }}>
        {cdms.length} conjunction{cdms.length !== 1 ? 's' : ''} shown
        {selectedSat ? ` for ${selectedSat}` : ' (all fleet)'}
      </div>
    </div>
  )
}
