import { useEffect, useState } from 'react';
import './App.css';

const API_URL = 'http://localhost:8000/api/vancouver-solar';

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

  const cards = data
    ? [
        {
          label: 'Current solar value',
          value: formatValue(data.current_solar_val, ' W/m²'),
          sublabel: `Matched date: ${data.matched_date || '—'}`,
        },
        {
          label: 'Next-day prediction',
          value: formatValue(data.predicted_solar_val, ' W/m²'),
          sublabel: `Target date: ${data.tomorrow_date || '—'}`,
        },
        {
          label: 'Model intercept',
          value: formatValue(data.intercept),
          sublabel: 'Local linear regression output',
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
                <h2>{data ? `${formatValue(data.predicted_solar_val, ' W/m²')} predicted` : '—'}</h2>
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
                <ul>
                  <li>Current observed value: {formatValue(data?.current_solar_val, ' W/m²')}</li>
                  <li>Next-day target date: {data?.tomorrow_date || '—'}</li>
                  <li>Predicted next-day value: {formatValue(data?.predicted_solar_val, ' W/m²')}</li>
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
          </>
        )}
      </div>
    </div>
  );
}

export default App;
