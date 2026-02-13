import { useEffect, useRef } from "react";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const listRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const node = listRef.current;
    if (!node) {
      return;
    }
    node.scrollTop = node.scrollHeight;
  }, [messages]);

  return (
    <section className="message-list" ref={listRef}>
      {messages.map((message, index) => (
        <article key={`${message.role}-${index}`} className={`message-card message-${message.role}`}>
          <header>
            <span>{message.role === "user" ? "You" : "Chaty Assistant"}</span>
            <time>{message.createdAt}</time>
          </header>
          <p>{message.content}</p>
        </article>
      ))}
      {messages.length === 0 && (
        <div className="chat-placeholder">
          <h2>Chaty RAG</h2>
          <p>Drop `.txt` or `.pdf` files into `ingest/`, run reindex, then ask document questions.</p>
        </div>
      )}
    </section>
  );
}
