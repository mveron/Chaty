import { fetchEventSource } from "@microsoft/fetch-event-source";

export interface SourceItem {
  source: string;
  score: number;
  preview: string;
}

export interface IngestResult {
  indexed_files: string[];
  skipped_files: string[];
  total_chunks_added: number;
  collection_name: string;
  persist_dir: string;
}

const PROVIDER_HOST_SUFFIXES = ["ollama.com", "openai.com", "openai.vocareum.com"];

function normalizeBackendUrl(rawBaseUrl: string): string {
  const input = rawBaseUrl.trim();
  if (!input) {
    throw new Error("Backend URL is empty. Use your FastAPI backend URL, e.g. http://localhost:8000.");
  }

  const withScheme = /^https?:\/\//i.test(input) ? input : `http://${input}`;
  let parsed: URL;
  try {
    parsed = new URL(withScheme);
  } catch {
    throw new Error("Backend URL is invalid. Example: http://localhost:8000");
  }

  const hostname = parsed.hostname.toLowerCase();
  const pointsToProvider = PROVIDER_HOST_SUFFIXES.some(
    (suffix) => hostname === suffix || hostname.endsWith(`.${suffix}`)
  );
  if (pointsToProvider) {
    throw new Error(
      "Backend URL points to provider API directly. Use your FastAPI backend URL (for local dev: http://localhost:8000)."
    );
  }

  const path = parsed.pathname.replace(/\/+$/, "");
  return `${parsed.origin}${path}`;
}

export interface ChatOptions {
  baseUrl: string;
  sessionId: string;
  message: string;
  topK: number;
  model?: string;
  temperature: number;
  onToken: (token: string) => void;
  onSources: (sources: SourceItem[]) => void;
}

export const streamChat = async ({
  baseUrl,
  sessionId,
  message,
  topK,
  model,
  temperature,
  onToken,
  onSources,
}: ChatOptions): Promise<void> => {
  const backendBaseUrl = normalizeBackendUrl(baseUrl);
  const controller = new AbortController();
  await fetchEventSource(`${backendBaseUrl}/chat`, {
    signal: controller.signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      top_k: topK,
      chat_model: model || undefined,
      temperature,
    }),
    async onopen(response) {
      if (!response.ok) {
        let detail = `Chat request failed with status ${response.status}`;
        try {
          const payload = (await response.json()) as { detail?: string };
          if (payload.detail) {
            detail = payload.detail;
          }
        } catch {
          // Keep status-based fallback message.
        }
        throw new Error(detail);
      }
    },
    onmessage(event) {
      if (!event.data) {
        return;
      }
      const payload = JSON.parse(event.data) as Record<string, unknown>;
      if (event.event === "token") {
        onToken(String(payload.text ?? ""));
      }
      if (event.event === "sources") {
        onSources((payload.sources as SourceItem[]) ?? []);
      }
      if (event.event === "done") {
        controller.abort();
      }
    },
  }).catch((error: Error) => {
    if (error.name === "AbortError") {
      return;
    }
    throw error;
  });
};

export const triggerIngest = async (baseUrl: string, force = false): Promise<IngestResult> => {
  const backendBaseUrl = normalizeBackendUrl(baseUrl);
  const response = await fetch(`${backendBaseUrl}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force }),
  });
  if (!response.ok) {
    let detail = "Ingest failed";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Ignore parse failures and keep default message.
    }
    throw new Error(detail);
  }
  return (await response.json()) as IngestResult;
};
