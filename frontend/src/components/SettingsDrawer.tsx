interface SettingsDrawerProps {
  theme: "light" | "dark";
  apiBaseUrl: string;
  model: string;
  topK: number;
  temperature: number;
  ingesting: boolean;
  lastReindexAt: string | null;
  onChangeApiBaseUrl: (value: string) => void;
  onChangeModel: (value: string) => void;
  onChangeTopK: (value: number) => void;
  onChangeTemperature: (value: number) => void;
  onToggleTheme: () => void;
  onReindex: () => Promise<void>;
}

export function SettingsDrawer({
  theme,
  apiBaseUrl,
  model,
  topK,
  temperature,
  ingesting,
  lastReindexAt,
  onChangeApiBaseUrl,
  onChangeModel,
  onChangeTopK,
  onChangeTemperature,
  onToggleTheme,
  onReindex,
}: SettingsDrawerProps) {
  return (
    <aside className="settings-column">
      <div className="brand-row">
        <div className="brand-icon">C</div>
        <h1>Chaty</h1>
      </div>
      <h2>Configuration</h2>
      <button className="theme-toggle-btn" onClick={onToggleTheme} type="button">
        {theme === "dark" ? "☀️ Light mode" : "🌙 Dark mode"}
      </button>

      <label className="field-group">
        <span>Backend URL</span>
        <input value={apiBaseUrl} onChange={(event) => onChangeApiBaseUrl(event.target.value)} />
      </label>
      <label className="field-group">
        <span>Chat model</span>
        <input value={model} onChange={(event) => onChangeModel(event.target.value)} placeholder="gpt-4o-mini" />
      </label>
      <label className="field-group">
        <div className="field-row">
          <span>Top-K retrieval</span>
          <strong>{topK}</strong>
        </div>
        <input
          className="range-input"
          type="range"
          min={1}
          max={20}
          step={1}
          value={topK}
          onChange={(event) => onChangeTopK(Number(event.target.value))}
        />
      </label>
      <label className="field-group">
        <div className="field-row">
          <span>Temperature</span>
          <strong>{temperature.toFixed(2)}</strong>
        </div>
        <input
          className="range-input"
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={temperature}
          onChange={(event) => onChangeTemperature(Number(event.target.value))}
        />
      </label>

      <div className="settings-footer">
        <button className="primary-btn" disabled={ingesting} onClick={() => void onReindex()}>
          {ingesting ? "INDEXING..." : "REINDEX INGEST/"}
        </button>
        <p>{lastReindexAt ? `Last reindex: ${lastReindexAt}` : "No reindex run yet"}</p>
        <small>Backend uses OpenAI API credentials from server `.env`.</small>
      </div>
    </aside>
  );
}
