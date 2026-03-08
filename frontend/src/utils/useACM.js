import { useState, useEffect, useCallback, useRef } from 'react'

const API = '/api'
const POLL_MS = 1500

export function useACM() {
  const [snapshot, setSnapshot]     = useState(null)
  const [conjunctions, setConj]     = useState([])
  const [fleetStats, setFleet]      = useState(null)
  const [maneuvers, setManeuvers]   = useState([])
  const [selectedSat, setSelected]  = useState(null)
  const [satDetail, setSatDetail]   = useState(null)
  const [error, setError]           = useState(null)
  const [simRunning, setSimRunning] = useState(false)
  const timerRef = useRef(null)

  const fetchAll = useCallback(async () => {
    try {
      const [snap, conj, fleet, man] = await Promise.all([
        fetch(`${API}/visualization/snapshot`).then(r => r.json()),
        fetch(`${API}/conjunctions`).then(r => r.json()),
        fetch(`${API}/fleet/stats`).then(r => r.json()),
        fetch(`${API}/maneuvers/queue`).then(r => r.json()),
      ])
      setSnapshot(snap)
      setConj(conj.cdms || [])
      setFleet(fleet)
      setManeuvers(man.queued || [])
      setError(null)
    } catch (e) {
      setError('API unreachable — is the backend running?')
    }
  }, [])

  const fetchSatDetail = useCallback(async (satId) => {
    if (!satId) { setSatDetail(null); return }
    try {
      const d = await fetch(`${API}/satellites/${satId}`).then(r => r.json())
      setSatDetail(d)
    } catch {}
  }, [])

  const stepSim = useCallback(async (seconds = 60) => {
    setSimRunning(true)
    try {
      await fetch(`${API}/simulate/step`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ step_seconds: seconds })
      })
      await fetchAll()
    } catch (e) { setError(e.message) }
    setSimRunning(false)
  }, [fetchAll])

  const autoStep = useCallback((on) => {
    if (on) {
      timerRef.current = setInterval(() => stepSim(60), 2000)
    } else {
      clearInterval(timerRef.current)
    }
  }, [stepSim])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, POLL_MS)
    return () => clearInterval(id)
  }, [fetchAll])

  useEffect(() => {
    fetchSatDetail(selectedSat)
  }, [selectedSat, fetchSatDetail])

  return {
    snapshot, conjunctions, fleetStats, maneuvers,
    selectedSat, setSelectedSat: setSelected,
    satDetail, error, simRunning,
    stepSim, autoStep, fetchAll
  }
}
