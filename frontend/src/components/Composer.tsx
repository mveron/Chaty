import { useEffect, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import type { FormEvent } from "react";
import type { KeyboardEvent } from "react";

interface ComposerProps {
  onSend: (value: string) => Promise<void>;
  onUploadFiles: (files: File[]) => Promise<void>;
  disabled: boolean;
  uploading: boolean;
}

export function Composer({ onSend, onUploadFiles, disabled, uploading }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  const handleUploadClick = () => {
    if (uploading) {
      return;
    }
    fileInputRef.current?.click();
  };

  const handleFilesSelected = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!selectedFiles.length || uploading) {
      return;
    }
    void onUploadFiles(selectedFiles);
  };

  return (
    <form className="composer-bar" onSubmit={handleSubmit}>
      <button
        aria-label="Upload files for ingest"
        className="upload-btn"
        disabled={uploading}
        onClick={handleUploadClick}
        title={uploading ? "Uploading..." : "Upload .txt/.pdf files"}
        type="button"
      >
        {uploading ? "Uploading..." : "Upload"}
      </button>
      <input
        ref={fileInputRef}
        accept=".txt,.pdf,text/plain,application/pdf"
        hidden
        multiple
        onChange={handleFilesSelected}
        type="file"
      />
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
