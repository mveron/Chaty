import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { KeyboardEvent } from "react";

interface ComposerProps {
  onSend: (value: string) => Promise<void>;
  disabled: boolean;
}

export function Composer({ onSend, disabled }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!disabled) {
      textareaRef.current?.focus();
    }
  }, [disabled]);

  const submitMessage = async () => {
    if (disabled) {
      return;
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    setValue("");
    await onSend(trimmed);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await submitMessage();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (disabled) {
      return;
    }
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    void submitMessage();
  };

  return (
    <form className="composer-bar" onSubmit={handleSubmit}>
      <button aria-label="Attach file" className="icon-btn" type="button">
        +
      </button>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => {
          if (!disabled) {
            requestAnimationFrame(() => textareaRef.current?.focus());
          }
        }}
        placeholder="Ask about your ingested documents..."
        rows={1}
      />
      <button className="send-btn" disabled={disabled || !value.trim()} type="submit">
        {disabled ? "..." : ">"}
      </button>
    </form>
  );
}
