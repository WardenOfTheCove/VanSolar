import io
import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

MODEL_FILENAME = 'solar_radiation_model.joblib'
LEGACY_MODEL_FILENAME = 'solar_radiation_model (1).joblib'


def _find_model_path() -> Path:
    candidate_roots = [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    candidate_names = [MODEL_FILENAME, LEGACY_MODEL_FILENAME]

    for root in candidate_roots:
        for candidate_name in candidate_names:
            candidate = root / candidate_name
            if candidate.exists() and candidate.is_file():
                return candidate

    for root in candidate_roots:
        for candidate_name in candidate_names:
            for match in root.rglob(candidate_name):
                if match.is_file():
                    return match

    return candidate_roots[0] / MODEL_FILENAME


MODEL_PATH = _find_model_path()
NASA_POWER_URL = 'https://power.larc.nasa.gov/api/temporal/daily/point'
VANCOUVER_LATITUDE = 49.2827
VANCOUVER_LONGITUDE = -123.1207
NASA_POWER_PARAMETER = 'ALLSKY_SFC_SW_DWN'
SOLAR_THRESHOLD_KWH_PER_M2_DAY = 5.0
TARGET_LIKE = {
    'solar_rad',
    'solar_radiation',
    'solar radiation',
    'radiation',
    'ghi',
    'irradiance',
    'target',
    'y',
    'output',
    'label',
}
DATE_LIKE = {
    'year', 'mo', 'month', 'dy', 'day', 'date', 'datetime', 'time', 'timestamp', 'dayofyear'
}
NASA_POWER_REQUIRED_DATE_COLUMNS = {'year', 'mo', 'dy'}
NASA_POWER_REQUIRED_SOLAR_COLUMNS = {
    'allsky_sfc_sw_dwn',
    'allsky_sfc_shortwave_downward_irradiance',
    'allsky',
    'solar_rad',
    'solar_radiation',
    'ghi',
    'irradiance',
}

app = FastAPI(title='VanSolar API', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def _load_model():
    try:
        return joblib.load(MODEL_PATH)
    except Exception as exc:  # pragma: no cover - runtime error path
        raise RuntimeError(f'Could not load model file: {exc}') from exc


def _normalize_column_name(name):
    return str(name).strip().lower().replace(' ', '_').replace('-', '_')


def _fetch_nasa_power_vancouver_dataframe(days_back: int = 365) -> pd.DataFrame:
    end_date = pd.Timestamp.utcnow().normalize()
    start_date = end_date - pd.Timedelta(days=max(days_back - 1, 0))
    params = {
        'parameters': NASA_POWER_PARAMETER,
        'community': 'RE',
        'latitude': str(VANCOUVER_LATITUDE),
        'longitude': str(VANCOUVER_LONGITUDE),
        'start': start_date.strftime('%Y%m%d'),
        'end': end_date.strftime('%Y%m%d'),
        'format': 'JSON',
    }
    request_url = f'{NASA_POWER_URL}?{urllib.parse.urlencode(params)}'
    request = urllib.request.Request(request_url, headers={'User-Agent': 'VanSolar/1.0'})
    with urllib.request.urlopen(request, context=ssl._create_unverified_context(), timeout=30) as response:
        payload = json.loads(response.read().decode('utf-8'))

    parameter_map = payload.get('properties', {}).get('parameter', {})
    values = parameter_map.get(NASA_POWER_PARAMETER, {})
    if not values:
        raise ValueError('NASA POWER did not return the ALLSKY_SFC_SW_DWN parameter for Vancouver.')

    records = []
    for date_key, raw_value in values.items():
        if raw_value in (None, '', 'null', 'NaN'):
            continue

        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError):
            continue

        if pd.isna(numeric_value) or numeric_value <= -900:
            continue

        date_obj = pd.to_datetime(str(date_key), format='%Y%m%d')
        records.append({
            'date': date_obj,
            'year': int(date_obj.year),
            'mo': int(date_obj.month),
            'dy': int(date_obj.day),
            'allsky_sfc_sw_dwn': float(numeric_value),
        })

    if not records:
        raise ValueError('No valid All Sky Surface Shortwave Downward Radiance data was returned for Vancouver.')

    df = pd.DataFrame(records).sort_values('date').reset_index(drop=True)
    return df


def _validate_nasa_power_dataset(df: pd.DataFrame, source_text: str = '') -> None:
    normalized_columns = {_normalize_column_name(col) for col in df.columns}
    date_matches = NASA_POWER_REQUIRED_DATE_COLUMNS.issubset(normalized_columns) or {'year', 'month', 'day'} <= normalized_columns
    solar_matches = any(
        solar_key in normalized_columns
        for solar_key in NASA_POWER_REQUIRED_SOLAR_COLUMNS
    )

    nasa_signature = 'nasa/power' in source_text.lower() or 'power source native resolution daily data' in source_text.lower()

    if not nasa_signature:
        raise ValueError(
            'Only NASA POWER datasets are supported. Please upload a CSV exported directly from NASA POWER.'
        )

    if not date_matches:
        raise ValueError(
            'This dataset does not look like a NASA POWER file because the required YEAR, MO, and DY columns are missing.'
        )

    if not solar_matches:
        raise ValueError(
            'This file is not a valid NASA POWER solar dataset. The required solar irradiance column is missing.'
        )


def _to_kwh_per_m2_day(value):
    numeric_value = float(value)
    if abs(numeric_value) > 100:
        return numeric_value / 1000.0
    return numeric_value


def _build_threshold_summary(predicted_solar_val):
    predicted_kwh = _to_kwh_per_m2_day(predicted_solar_val)
    threshold_met = predicted_kwh >= SOLAR_THRESHOLD_KWH_PER_M2_DAY
    return {
        'predicted_solar_kwh_per_m2_day': round(predicted_kwh, 4),
        'threshold_kwh_per_m2_day': float(SOLAR_THRESHOLD_KWH_PER_M2_DAY),
        'threshold_met': threshold_met,
        'threshold_status': 'Above threshold' if threshold_met else 'Below threshold',
        'recommendation': 'Good solar potential for the next day.' if threshold_met else 'Solar production is below the 5 kWh/m²/day threshold.',
    }


def _build_vancouver_next_day_forecast():
    df = _fetch_nasa_power_vancouver_dataframe(365)
    if df.empty:
        raise ValueError('The NASA POWER response was empty.')

    clean_df = df.dropna(subset=['allsky_sfc_sw_dwn']).sort_values('date').reset_index(drop=True)
    if clean_df.empty:
        raise ValueError('No valid solar data was found in the NASA POWER response.')

    today = pd.Timestamp.now().normalize()
    relevant_df = clean_df[clean_df['date'] <= today]
    if relevant_df.empty:
        relevant_df = clean_df

    latest_date = relevant_df['date'].iloc[-1]
    current_solar_val = float(relevant_df['allsky_sfc_sw_dwn'].iloc[-1])
    target_date = today + pd.Timedelta(days=1)

    model = _load_model()
    predicted_solar_val = float(model.predict(np.array([[current_solar_val]]))[0])
    coefficient = float(getattr(model, 'coef_', [0.0])[0]) if hasattr(model, 'coef_') else 0.0
    intercept = float(getattr(model, 'intercept_', 0.0)) if hasattr(model, 'intercept_') else 0.0
    threshold_summary = _build_threshold_summary(predicted_solar_val)

    return {
        'status': 'success',
        'message': 'Live NASA POWER solar data retrieved for Vancouver, Canada.',
        'source': 'NASA POWER API',
        'city': 'Vancouver, Canada',
        'parameter': NASA_POWER_PARAMETER,
        'feature': 'allsky_sfc_sw_dwn',
        'rows': int(len(clean_df)),
        'coefficient': round(coefficient, 6),
        'intercept': round(intercept, 6),
        'matched_date': latest_date.strftime('%Y-%m-%d'),
        'current_solar_val': round(current_solar_val, 4),
        'tomorrow_date': target_date.strftime('%Y-%m-%d'),
        'tomorrow_val': round(current_solar_val, 4),
        'predicted_solar_val': round(predicted_solar_val, 4),
        'predicted_solar_kwh_per_m2_day': threshold_summary['predicted_solar_kwh_per_m2_day'],
        'threshold_kwh_per_m2_day': threshold_summary['threshold_kwh_per_m2_day'],
        'threshold_met': threshold_summary['threshold_met'],
        'threshold_status': threshold_summary['threshold_status'],
        'recommendation': threshold_summary['recommendation'],
        'predictions': [round(float(value), 4) for value in model.predict(clean_df['allsky_sfc_sw_dwn'].tail(10).to_numpy().reshape(-1, 1))[:10]],
    }


def _read_csv_dataset(contents: bytes) -> pd.DataFrame:
    content_text = contents.decode('utf-8-sig', errors='replace')
    lines = content_text.splitlines()
    csv_start = None

    for i, line in enumerate(lines):
        cleaned = line.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered.startswith('year,') or lowered.startswith('year,mo'):
            csv_start = i
            break

    if csv_start is not None:
        try:
            df = pd.read_csv(io.StringIO('\n'.join(lines[csv_start:])))
            if df is not None and not df.empty and not df.select_dtypes(include=[np.number]).empty:
                return df
        except Exception:
            pass

    candidates = []
    for header in (0, None):
        try:
            df = pd.read_csv(io.BytesIO(contents), header=header)
        except Exception:
            continue

        if df is None or df.empty:
            continue

        candidates.append(df)

    if not candidates:
        raise ValueError('The uploaded file could not be parsed as a CSV dataset.')

    def score_frame(frame: pd.DataFrame) -> tuple:
        cols = [str(col).strip() for col in frame.columns]
        alpha_cols = sum(1 for col in cols if any(ch.isalpha() for ch in col))
        target_penalty = sum(1 for col in cols if _normalize_column_name(col) in TARGET_LIKE)
        date_penalty = sum(1 for col in cols if _normalize_column_name(col) in DATE_LIKE)
        numeric_cols = frame.select_dtypes(include=[np.number]).shape[1]
        return (alpha_cols > 0, -target_penalty, -date_penalty, numeric_cols, len(frame))

    best_df = max(candidates, key=score_frame)

    if best_df.select_dtypes(include=[np.number]).empty:
        raise ValueError(
            'No numeric columns were found in the upload. Please provide a CSV with at least one numeric feature column.'
        )

    _validate_nasa_power_dataset(best_df, content_text)
    return best_df


def _choose_feature_columns(df, expected_features):
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        raise ValueError('No numeric columns were found in the uploaded dataset.')

    def is_date_like(col):
        norm = _normalize_column_name(col)
        return norm in DATE_LIKE or norm.endswith('_year') or norm.endswith('_month') or norm.endswith('_day')

    preferred = [
        col for col in numeric_df.columns
        if _normalize_column_name(col) not in TARGET_LIKE and not is_date_like(col)
        and any(token in _normalize_column_name(col) for token in ('allsky', 'solar', 'radiation', 'irradiance', 'ghi', 'temperature', 'wind', 'pressure', 'dew', 'humidity'))
    ]
    candidates = preferred or [
        col for col in numeric_df.columns
        if _normalize_column_name(col) not in TARGET_LIKE and not is_date_like(col)
    ]

    if not candidates:
        if expected_features == 1:
            raise ValueError(
                'No usable feature column was found. Please upload a CSV with a numeric input column such as value, irradiation, or temperature, and avoid target columns like solar_radiation.'
            )
        raise ValueError('No feature columns were found in the uploaded dataset. Please provide numeric input columns only.')

    if expected_features == 1:
        return [candidates[0]]

    selected = candidates[:expected_features]
    if len(selected) < expected_features:
        selected = list(numeric_df.columns[:expected_features])
    return selected


def predictionSet_updated(df):
    clean_df = df.copy()
    normalized_cols = {str(col).lower() for col in clean_df.columns}

    if {'year', 'mo', 'dy'} <= normalized_cols or {'year', 'month', 'day'} <= normalized_cols:
        year_col = next((col for col in clean_df.columns if str(col).lower() == 'year'), None)
        mo_col = next((col for col in clean_df.columns if str(col).lower() in {'mo', 'month'}), None)
        dy_col = next((col for col in clean_df.columns if str(col).lower() in {'dy', 'day'}), None)

        if year_col is None or mo_col is None or dy_col is None:
            raise ValueError('The uploaded dataset is missing date columns required for solar analysis.')

        clean_df['_date'] = pd.to_datetime(
            clean_df[year_col].astype(str) + '-' + clean_df[mo_col].astype(str) + '-' + clean_df[dy_col].astype(str),
            errors='coerce',
        )
    elif 'date' in normalized_cols:
        date_col = next(col for col in clean_df.columns if str(col).lower() == 'date')
        clean_df['_date'] = pd.to_datetime(clean_df[date_col], errors='coerce')
    else:
        clean_df['_date'] = pd.Series(pd.date_range(start='2000-01-01', periods=len(clean_df), freq='D'))

    clean_df = clean_df.dropna(subset=['_date']).sort_values('_date').reset_index(drop=True)
    solar_feature = _choose_feature_columns(clean_df, 1)[0]
    solar_values = pd.to_numeric(clean_df[solar_feature], errors='coerce')
    solar_values = solar_values.replace(-999, np.nan)
    solar_values = solar_values[solar_values > -900].dropna()
    if solar_values.empty:
        raise ValueError('No solar values were found in the uploaded dataset.')

    matched_date = clean_df['_date'].iloc[-1].strftime('%Y-%m-%d')
    current_solar_val = float(solar_values.iloc[-1])
    tomorrow_idx = -2 if len(solar_values) > 1 else -1
    tomorrow_date = clean_df['_date'].iloc[tomorrow_idx].strftime('%Y-%m-%d')
    tomorrow_val = float(solar_values.iloc[tomorrow_idx])
    return matched_date, current_solar_val, tomorrow_date, tomorrow_val


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'VanSolar API'}


@app.get('/api/vancouver-solar')
async def vancouver_solar():
    try:
        return _build_vancouver_next_day_forecast()
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={'status': 'error', 'message': str(exc)},
        )


@app.post('/api/predict')
async def predict(file: UploadFile | None = File(default=None)):
    try:
        if file is None or not file.filename:
            return _build_vancouver_next_day_forecast()

        contents = await file.read()
        if not contents:
            raise ValueError('The uploaded file is empty.')

        name = file.filename.lower()
        if not name.endswith('.csv'):
            raise ValueError('Please upload a CSV dataset for the model.')

        source_text = contents.decode('utf-8-sig', errors='replace')
        if 'nasa/power' not in source_text.lower() and 'power source native resolution daily data' not in source_text.lower():
            raise ValueError('Only NASA POWER datasets are supported. Please upload a CSV exported directly from NASA POWER.')

        df = _read_csv_dataset(contents)
        if df.empty:
            raise ValueError('The uploaded dataset is empty.')

        model = _load_model()
        current_solar_val = float(df['allsky_sfc_sw_dwn'].iloc[-1]) if 'allsky_sfc_sw_dwn' in {str(col).lower() for col in df.columns} else float(df.select_dtypes(include=[np.number]).iloc[:, 0].iloc[-1])
        latest_date = pd.to_datetime(df['date']).iloc[-1] if 'date' in {str(col).lower() for col in df.columns} else pd.Timestamp.utcnow().normalize()
        predicted_solar_val = float(model.predict(np.array([[current_solar_val]]))[0])
        threshold_summary = _build_threshold_summary(predicted_solar_val)
        next_day_date = latest_date + pd.Timedelta(days=1)

        return {
            'status': 'success',
            'message': 'NASA POWER Vancouver data was used for the next-day forecast.',
            'source': 'NASA POWER API',
            'city': 'Vancouver, Canada',
            'feature': 'allsky_sfc_sw_dwn',
            'rows': int(len(df)),
            'coefficient': round(float(getattr(model, 'coef_', [0.0])[0]) if hasattr(model, 'coef_') else 0.0, 6),
            'intercept': round(float(getattr(model, 'intercept_', 0.0)) if hasattr(model, 'intercept_') else 0.0, 6),
            'matched_date': latest_date.strftime('%Y-%m-%d'),
            'current_solar_val': round(current_solar_val, 4),
            'tomorrow_date': next_day_date.strftime('%Y-%m-%d'),
            'tomorrow_val': round(current_solar_val, 4),
            'predicted_solar_val': round(predicted_solar_val, 4),
            'predicted_solar_kwh_per_m2_day': threshold_summary['predicted_solar_kwh_per_m2_day'],
            'threshold_kwh_per_m2_day': threshold_summary['threshold_kwh_per_m2_day'],
            'threshold_met': threshold_summary['threshold_met'],
            'threshold_status': threshold_summary['threshold_status'],
            'recommendation': threshold_summary['recommendation'],
            'predictions': [round(float(value), 4) for value in model.predict(df.select_dtypes(include=[np.number]).tail(10).to_numpy())[:10]],
        }
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={'status': 'error', 'message': str(exc)},
        )


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('backend.app:app', host='0.0.0.0', port=8000, reload=True)
