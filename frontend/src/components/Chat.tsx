import { useEffect, useMemo, useState } from "react";

import { streamChat, triggerIngest } from "../api/chat";
import type { SourceItem } from "../api/chat";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";
import type { ChatMessage } from "./MessageList";
import { SettingsDrawer } from "./SettingsDrawer";
import { SourcesPanel } from "./SourcesPanel";

type ThemeMode = "light" | "dark";

function getLocal<T>(key: string, fallback: T): T {
  const raw = localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function setLocal<T>(key: string, value: T): void {
  localStorage.setItem(key, JSON.stringify(value));
}

function sanitizeInitialBackendUrl(value: string): string {
  const trimmed = value.trim().toLowerCase();
  if (
    trimmed.includes("ollama.com") ||
    trimmed.includes("openai.com") ||
    trimmed.includes("openai.vocareum.com")
  ) {
    return "http://localhost:8000";
  }
  return value;
}

function sanitizeInitialModel(value: string): string {
  const trimmed = value.trim().toLowerCase();
  if (!trimmed || trimmed.includes("gpt-oss")) {
    return "gpt-4o-mini";
  }
  return value;
}

function getInitialTheme(): ThemeMode {
  const stored = getLocal<ThemeMode | null>("chaty.theme", null);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [lastReindexAt, setLastReindexAt] = useState<string | null>(null);

  const [apiBaseUrl, setApiBaseUrl] = useState(() =>
    sanitizeInitialBackendUrl(getLocal("chaty.apiBaseUrl", "http://localhost:8000"))
  );
  const [model, setModel] = useState(() => sanitizeInitialModel(getLocal("chaty.model", "gpt-4o-mini")));
  const [topK, setTopK] = useState(() => getLocal("chaty.topK", 4));
  const [temperature, setTemperature] = useState(() => getLocal("chaty.temperature", 0.2));
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);

  const sessionId = useMemo(() => crypto.randomUUID(), []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    setLocal("chaty.theme", theme);
  }, [theme]);

  const handleSend = async (value: string) => {
    setBusy(true);
    setError(null);
    setStatus(null);
    setSources([]);
    const nowLabel = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const initialMessages: ChatMessage[] = [
      ...messages,
      { role: "user", content: value, createdAt: nowLabel },
      { role: "assistant", content: "", createdAt: nowLabel },
    ];
    setMessages(initialMessages);

    try {
      await streamChat({
        baseUrl: apiBaseUrl,
        sessionId,
        message: value,
        topK,
        model,
        temperature,
        onToken: (token) => {
          setMessages((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            if (!last || last.role !== "assistant") {
              return next;
            }
            next[next.length - 1] = { ...last, content: `${last.content}${token}` };
            return next;
          });
        },
        onSources: (nextSources) => setSources(nextSources),
      });
    } catch (streamError) {
      setError((streamError as Error).message);
      setMessages((current) => {
        const next = [...current];
        const last = next[next.length - 1];
        if (last?.role === "assistant" && !last.content) {
          next[next.length - 1] = {
            role: "assistant",
            content: "Request failed. Verify backend connectivity and OpenAI API configuration.",
            createdAt: nowLabel,
          };
        }
        return next;
      });
    } finally {
      setBusy(false);
    }
  };

  const handleReindex = async () => {
    setIngesting(true);
    setError(null);
    setStatus(null);
    try {
      const result = await triggerIngest(apiBaseUrl, true);
      setStatus(
        `Indexed ${result.indexed_files.length} file(s), skipped ${result.skipped_files.length}, chunks ${result.total_chunks_added}.`
      );
      setLastReindexAt(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (ingestError) {
      setError((ingestError as Error).message);
    } finally {
      setIngesting(false);
    }
  };

  const handleChangeApiBaseUrl = (value: string) => {
    setApiBaseUrl(value);
    setLocal("chaty.apiBaseUrl", value);
  };

  const handleChangeModel = (value: string) => {
    setModel(value);
    setLocal("chaty.model", value);
  };

  const handleChangeTopK = (value: number) => {
    const sanitized = Math.max(1, Math.min(20, Number.isFinite(value) ? value : 4));
    setTopK(sanitized);
    setLocal("chaty.topK", sanitized);
  };

  const handleChangeTemperature = (value: number) => {
    const sanitized = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0.2));
    setTemperature(sanitized);
    setLocal("chaty.temperature", sanitized);
  };

  const handleToggleTheme = () => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  };

  return (
    <div className="desktop-shell">
      <SettingsDrawer
        theme={theme}
        apiBaseUrl={apiBaseUrl}
        model={model}
        topK={topK}
        temperature={temperature}
        ingesting={ingesting}
        lastReindexAt={lastReindexAt}
        onChangeApiBaseUrl={handleChangeApiBaseUrl}
        onChangeModel={handleChangeModel}
        onChangeTopK={handleChangeTopK}
        onChangeTemperature={handleChangeTemperature}
        onToggleTheme={handleToggleTheme}
        onReindex={handleReindex}
      />
      <main className="chat-column">
        <header className="chat-header">
          <h1>Chaty RAG</h1>
          <p>Desktop web workspace. Backend is configured for OpenAI chat and embeddings.</p>
        </header>
        <div className="connection-banner">Connected backend: {apiBaseUrl}</div>
        {error && <div className="error">{error}</div>}
        {status && <div className="status">{status}</div>}
        <MessageList messages={messages} />
        <Composer onSend={handleSend} disabled={busy} />
      </main>
      <SourcesPanel sources={sources} />
    </div>
  );
}
