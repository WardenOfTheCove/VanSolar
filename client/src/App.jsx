import { useEffect, useState } from 'react';
import './App.css';

const API_URL = '/api/vancouver-solar';

function formatValue(value, suffix = '') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }

  return `${Number(value).toFixed(4)}${suffix}`;
}

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadForecast = async () => {
    try {
      setLoading(true);
      setError('');

      const response = await fetch(API_URL);
      const payload = await response.json();

      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Unable to fetch forecast data.');
      }

      setData(payload);
    } catch (err) {
      setError(err.message || 'Could not load the forecast.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadForecast();
  }, []);

  const predictiveValue = data?.predicted_solar_kwh_per_m2_day ?? data?.predicted_solar_val ?? 0;
  const thresholdStatus = data?.threshold_met === true ? 'Above 5 kWh/m²/day threshold' : 'Below 5 kWh/m²/day threshold';

  const weatherIcon =
    Number(predictiveValue) >= 5
      ? '☀️'
      : Number(predictiveValue) >= 2
        ? '☁️'
        : '🌧️';

  const weatherLabel =
    Number(predictiveValue) >= 5
      ? 'High solar potential'
      : Number(predictiveValue) >= 2
        ? 'Moderate solar potential'
        : 'Low solar potential';

  const cards = data
    ? [
        {
          label: 'Current solar value',
          value: formatValue(data.current_solar_val, ' W/m²'),
          sublabel: `Matched date: ${data.matched_date || '—'}`,
        },
        {
          label: 'Next-day prediction',
          value: `${weatherIcon} ${formatValue(predictiveValue, ' kWh/m²/day')}`,
          sublabel: `Target date: ${data.tomorrow_date || '—'}`,
        },
        {
          label: 'Threshold check',
          value: `${weatherIcon} ${thresholdStatus}`,
          sublabel: `Limit: ${data.threshold_kwh_per_m2_day ?? 5} kWh/m²/day`,
        },
        {
          label: 'Model coefficient',
          value: formatValue(data.coefficient),
          sublabel: 'Estimated trend weight',
        },
      ]
    : [];

  return (
    <div className="app-shell">
      <div className="dashboard">
        <header className="topbar">
          <div>
            <p className="eyebrow">NASA POWER forecast</p>
            <h1>VanSolar</h1>
          </div>
          <button className="primary-button" onClick={loadForecast} disabled={loading}>
            {loading ? 'Loading…' : 'Refresh forecast'}
          </button>
        </header>

        {error ? (
          <div className="alert-box" role="alert">
            {error}
          </div>
        ) : null}

        {loading && !data ? (
          <div className="loading-box">Loading Vancouver solar forecast…</div>
        ) : (
          <>
            <section className="hero-panel">
              <div>
                <p className="hero-label">Forecast</p>
                <h2>{data ? `${formatValue(predictiveValue, ' kWh/m²/day')} predicted` : '—'}</h2>
              </div>
              <div className="hero-meta">
                <span>{data?.city || 'Vancouver, Canada'}</span>
                <span>{data?.source || 'NASA POWER API'}</span>
                <span>{data?.parameter || 'ALLSKY_SFC_SW_DWN'}</span>
              </div>
            </section>

            <section className="stats-grid">
              {cards.map((card) => (
                <article className="summary-box" key={card.label}>
                  <p>{card.label}</p>
                  <strong>{card.value}</strong>
                  <span>{card.sublabel}</span>
                </article>
              ))}
            </section>

            <section className="bottom-grid">
              <article className="detail-card">
                <h3>Prediction summary</h3>
                <p>
                  The model compares the most recently observed Vancouver solar value with the next-day target date
                  and estimates the expected irradiance using the trained linear regression model.
                </p>
                <div className="weather-badge" aria-label={`Forecast weather indicator: ${weatherLabel}`}>
                  <span className="weather-icon">{weatherIcon}</span>
                  <span>{weatherLabel}</span>
                </div>
                <ul>
                  <li>Current observed value: {formatValue(data?.current_solar_val, ' W/m²')}</li>
                  <li>Next-day target date: {data?.tomorrow_date || '—'}</li>
                  <li>Predicted next-day value: {formatValue(data?.predicted_solar_kwh_per_m2_day ?? data?.predicted_solar_val, ' kWh/m²/day')}</li>
                  <li>Threshold comparison: {data?.threshold_met === true ? 'Meets' : 'Below'} the 5 kWh/m²/day threshold</li>
                </ul>
              </article>

              <article className="detail-card">
                <h3>Data source</h3>
                <p>
                  This dashboard pulls daily All Sky Surface Shortwave Downward Radiance values from the NASA POWER API
                  for Vancouver, Canada and feeds that latest reading into the local regression model.
                </p>
                <div className="meta-list">
                  <span>Rows: {data?.rows ?? '—'}</span>
                  <span>City: {data?.city || 'Vancouver, Canada'}</span>
                  <span>Feature: {data?.feature || 'allsky_sfc_sw_dwn'}</span>
                </div>
              </article>
            </section>

            <section className="risk-grid">
              <article className="detail-card risk-card">
                <h3>Model error estimate</h3>
                <p>
                  This forecast is a statistical estimate and not a guarantee of actual daylight output. Weather,
                  cloud cover, seasonal variation, and sensor differences can cause the model to under- or overstate
                  solar performance. If the prediction is wrong, expected operational costs may include missed energy
                  generation, lower battery efficiency, oversupply or undersupply planning errors, and extra dispatch
                  or balancing costs.
                </p>
              </article>

              <article className="detail-card risk-card">
                <h3>Liability notice</h3>
                <p>
                  Any financial, operational, or investment decisions made using these predictions are made at the user’s
                  own risk. VanSolar provides informational estimates only and is not liable for losses, damages,
                  missed revenue, poor investment choices, or any downstream financial consequences resulting from the
                  use of these predictions.
                </p>
              </article>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
