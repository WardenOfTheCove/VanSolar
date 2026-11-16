import { useEffect, useState } from 'react'
import './App.css'

function App() {
  const [summary, setSummary] = useState(null)
  const [predictionSamples, setPredictionSamples] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const threshold = 5.0
  const predictedValue = summary?.predictedSolar ?? null

  const weatherIcon =
    predictedValue == null
      ? '☀️'
      : predictedValue >= 5
        ? '☀️'
        : predictedValue >= 2
          ? '☁️'
          : '🌧️'

  const decisionMode = predictedValue != null && predictedValue >= threshold ? 'Use your own solar energy' : 'Buy from the grid'

  const decisionCards = [
    {
      title: 'Homes',
      description:
        predictedValue != null && predictedValue >= threshold
          ? 'Use your own solar energy for daytime appliances, water heating, and EV charging. Grid purchases should be limited to backup periods or low-sun conditions.'
          : 'Buy from the grid for the shortfall, because solar generation is below the 5.0 kWh/m²/day threshold needed to cover most routine household demand.',
    },
    {
      title: 'Solar Farms',
      description:
        predictedValue != null && predictedValue >= threshold
          ? 'Use your own solar energy for operation, storage charging, and export planning. This is a strong generation day and internal use is efficient.'
          : 'Buy from the grid only as a balancing measure, because generation is not high enough to support heavy loads without relying on external power.',
    },
    {
      title: 'Facilities',
      description:
        predictedValue != null && predictedValue >= threshold
          ? 'Use your own solar energy for HVAC, lighting, and production loads while reserving grid supply as backup for contingency or peak demand.'
          : 'Buy from the grid to cover the deficit and reduce operational risk. Solar alone is not enough to support full facility demand at this production level.',
    },
  ]

  const riskCards = [
    {
      title: 'False positive',
      value: '$50 penalty',
      description: 'Overpredicting solar can trigger heavy loads, causing emergency grid use or service disruption.',
    },
    {
      title: 'False negative',
      value: '$20 lost savings',
      description: 'Underpredicting solar can mean missing low-cost free solar energy and paying more for grid power.',
    },
    {
      title: 'Operational risk',
      value: 'Decision accuracy',
      description: 'If model decisions differ from actual solar conditions, the cost of error increases even when predictions look useful.',
    },
  ]

  const applySummary = (data) => {
    setSummary({
      feature: data.feature,
      coefficient: data.coefficient,
      intercept: data.intercept,
      rows: data.rows,
      message: data.message,
      matchedDate: data.matched_date,
      currentSolar: data.current_solar_val,
      tomorrowDate: data.tomorrow_date,
      tomorrowValue: data.tomorrow_val,
      predictedSolar: data.predicted_solar_val,
    })
    setPredictionSamples(data.predictions || [])
  }

  const loadVancouverSolar = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/vancouver-solar')
      const data = await response.json()

      if (!response.ok || data.status === 'error') {
        throw new Error(data.message || 'NASA POWER data could not be loaded.')
      }

      applySummary(data)
    } catch (err) {
      setError(err.message)
      setSummary(null)
      setPredictionSamples([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadVancouverSolar()
  }, [])

  return (
    <div className="app-shell shadcn-shell">
      <header className="topbar shadcn-header">
        <div className="brand-wrap">
          <div>
            <p className="eyebrow">Solar Intelligence for Vancouver, Canada</p>
            <h1>VanSolar</h1>
          </div>
        </div>
      </header>

      <main className="dashboard single-panel-layout">
        <section className="shadcn-card panel weather-panel">
          <div className="panel-head">
            <div>
              <p className="section-label">Forecast</p>
              <h2>All Sky Surface Shortwave Downward Radiance</h2>
            </div>
            <button type="button" className="shadcn-badge pill action-button" onClick={loadVancouverSolar}>
              Refresh data
            </button>
          </div>

          {loading && <p className="status-text">Loading Vancouver solar data…</p>}
          {error && <div className="error-box">{error}</div>}

          <div className="metric-grid">
            <div className="summary-box accent-box">
              <span>Latest date</span>
              <strong>{summary?.matchedDate || '—'}</strong>
              <small>Available observation</small>
            </div>
            <div className="summary-box accent-box">
              <span>Current irradiance</span>
              <strong>{summary?.currentSolar != null ? `${Number(summary.currentSolar).toFixed(4)} kWh/m²/day` : '—'}</strong>
              <small>Latest solar input</small>
            </div>
            <div className="summary-box">
              <span>Next forecast date</span>
              <strong>{summary?.tomorrowDate || '—'}</strong>
              <small>Next-day target</small>
            </div>
            <div className="summary-box">
              <span>Tomorrow value</span>
              <strong>{summary?.tomorrowValue != null ? `${Number(summary.tomorrowValue).toFixed(4)} kWh/m²/day` : '—'}</strong>
              <small>Observed next value</small>
            </div>
            <div className="summary-box highlight-box">
              <span>Predicted next day</span>
              <strong>{summary?.predictedSolar != null ? `${Number(summary.predictedSolar).toFixed(4)} kWh/m²/day` : '—'}</strong>
              <small>Linear-regression forecast</small>
            </div>
            <div className="summary-box">
              <span>Feature used</span>
              <strong>{summary?.feature || '—'}</strong>
              <small>Selected model input</small>
            </div>
          </div>

          <div className="info-grid">
            <div className="info-box">
              <span>Dataset rows</span>
              <strong>{summary?.rows ?? '—'}</strong>
            </div>
            <div className="info-box">
              <span>Model coefficient</span>
              <strong>{summary?.coefficient ?? '—'}</strong>
            </div>
            <div className="info-box">
              <span>Model intercept</span>
              <strong>{summary?.intercept ?? '—'}</strong>
            </div>
          </div>

          <div className="decision-panel">
            <div className="decision-header-row">
              <div>
                <p className="section-label">Decision logic</p>
                <h3>What You Can Do</h3>
              </div>
              <span className="decision-threshold">Threshold: {threshold.toFixed(1)} kWh/m²/day</span>
            </div>

            <div className="decision-summary">
              <span className="decision-label">Current recommendation</span>
              <strong>
                <span className="weather-indicator" aria-label="Weather condition">{weatherIcon}</span>
                {decisionMode}
              </strong>
            </div>

            <div className="decision-grid">
              {decisionCards.map((card) => (
                <div key={card.title} className="decision-card">
                  <h4>{card.title}</h4>
                  <p>{card.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="risk-panel">
            <div className="risk-header-row">
              <div>
                <p className="section-label">Model risk</p>
                <h3>Forecast errors and cost of being wrong</h3>
              </div>
            </div>

            <div className="risk-grid">
              {riskCards.map((card) => (
                <div key={card.title} className="risk-card">
                  <span>{card.title}</span>
                  <strong>{card.value}</strong>
                  <p>{card.description}</p>
                </div>
              ))}
            </div>

            <div className="disclaimer-box">
              Any financial decisions made using these predictions are for informational purposes only and are not our liability.
              Final operational and financial choices remain the sole responsibility of the user, site operator, or decision-maker.
            </div>
          </div>

        </section>
      </main>
    </div>
  )
}

export default App
