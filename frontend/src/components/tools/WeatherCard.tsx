import { makeAssistantToolUI } from '@assistant-ui/react'

interface WeatherData {
  success?: boolean
  location?: string
  temperature?: { value: number; unit: string } | { max: { value: number; unit: string }; min: { value: number; unit: string } }
  humidity?: { value: number; unit: string }
  wind?: { speed: { value: number; unit: string }; direction?: number }
  precipitation?: { value?: number; probability?: number; unit: string }
  conditions?: string
  date?: string
  timestamp?: string
}

const WEATHER_ICONS: Record<string, string> = {
  'Clear sky': '☀️', 'Mainly clear': '🌤️', 'Partly cloudy': '⛅', 'Overcast': '☁️',
  'Foggy': '🌫️', 'Light drizzle': '🌦️', 'Moderate drizzle': '🌧️', 'Slight rain': '🌧️',
  'Moderate rain': '🌧️', 'Heavy rain': '🌧️', 'Slight snow': '🌨️', 'Moderate snow': '🌨️',
  'Heavy snow': '❄️', 'Thunderstorm': '⛈️',
}

export const WeatherToolUI = makeAssistantToolUI<Record<string, string>, WeatherData>({
  toolName: 'get_weather',
  render: ({ result }) => {
    if (!result || !result.success) return null
    const w = result
    const icon = WEATHER_ICONS[w.conditions ?? ''] ?? '🌡️'
    const isCurrentWeather = 'value' in (w.temperature ?? {})

    return (
      <div className="weather-card">
        <div className="weather-card-header">
          <span className="weather-card-icon">{icon}</span>
          <span className="weather-card-location">{w.location}</span>
        </div>
        <div className="weather-card-body">
          {isCurrentWeather ? (
            <div className="weather-card-temp">
              {(w.temperature as any)?.value}°C
            </div>
          ) : (
            <div className="weather-card-temp">
              {(w.temperature as any)?.max?.value}° / {(w.temperature as any)?.min?.value}°C
            </div>
          )}
          <div className="weather-card-condition">{w.conditions}</div>
          <div className="weather-card-details">
            {w.humidity && <span>💧 {w.humidity.value}%</span>}
            {w.wind && <span>💨 {w.wind.speed.value} km/h</span>}
            {w.precipitation?.value != null && <span>🌧️ {w.precipitation.value} mm</span>}
            {w.precipitation?.probability != null && <span>🌧️ {w.precipitation.probability}%</span>}
          </div>
        </div>
        {(w.timestamp || w.date) && (
          <div className="weather-card-footer">{w.date ?? w.timestamp}</div>
        )}
      </div>
    )
  },
})
