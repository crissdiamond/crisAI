import React, { useEffect, useRef, useState } from "react";
import type { UiSharePointAuthStart } from "@crisai/contracts";
import { runtime } from "../lib/runtime.js";
import { humanizeError } from "../lib/format.js";

type Phase = "starting" | "pending" | "connected" | "failed";

// Device-code login popup. On mount it starts the flow (server-side), shows the
// user code + verification link, and polls status every few seconds. It closes
// itself shortly after the login completes, so the user never copies a code
// from a log file again.
export function SharePointAuthDialog({ onClose }: { onClose: () => void }) {
  const [phase, setPhase] = useState<Phase>("starting");
  const [details, setDetails] = useState<UiSharePointAuthStart | null>(null);
  const [account, setAccount] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Check status first — if already connected, show that without forcing a new
  // device flow. Otherwise start the flow and poll until a terminal state.
  useEffect(() => {
    let active = true;
    let timer: number | undefined;

    async function poll() {
      try {
        const status = await runtime.getSharePointLoginStatus();
        if (!active) return;
        if (status.status === "connected") {
          setAccount(status.account);
          setPhase("connected");
          return;
        }
        if (status.status === "failed") {
          setPhase("failed");
          setError(status.error ?? "Sign-in failed.");
          return;
        }
        timer = window.setTimeout(() => void poll(), 3000);
      } catch (reason: unknown) {
        if (!active) return;
        setPhase("failed");
        setError(humanizeError(reason));
      }
    }

    runtime
      .getSharePointLoginStatus()
      .then((status) => {
        if (!active) return undefined;
        if (status.status === "connected") {
          setAccount(status.account);
          setPhase("connected");
          return undefined;
        }
        return runtime.startSharePointLogin().then((start) => {
          if (!active) return;
          setDetails(start);
          setPhase("pending");
          timer = window.setTimeout(() => void poll(), 3000);
        });
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setPhase("failed");
        setError(humanizeError(reason));
      });

    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  // Auto-close shortly after a successful connection.
  useEffect(() => {
    if (phase !== "connected") return undefined;
    const timer = window.setTimeout(onClose, 1600);
    return () => window.clearTimeout(timer);
  }, [phase, onClose]);

  // Focus management + Escape to dismiss.
  useEffect(() => {
    closeRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const link = details?.verification_uri_complete || details?.verification_uri || "";

  function copyCode() {
    if (!details) return;
    void navigator.clipboard?.writeText(details.user_code);
    setCopied(true);
  }

  return (
    <div className="modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="modal sharepoint-auth"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sp-auth-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="sp-auth-title">Connect SharePoint</h2>
          <button type="button" className="btn-ghost" ref={closeRef} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {phase === "starting" ? <p className="sp-auth-status" role="status">Starting sign-in…</p> : null}

        {phase === "pending" && details ? (
          <div className="sp-auth-body">
            <ol className="sp-auth-steps">
              <li>
                Open{" "}
                <a href={details.verification_uri} target="_blank" rel="noreferrer">
                  {details.verification_uri}
                </a>
              </li>
              <li className="sp-auth-code-step">
                <span>Enter this code:</span>
                <span className="sp-auth-code">{details.user_code}</span>
                <button type="button" className="btn-secondary" onClick={copyCode}>
                  {copied ? "Copied" : "Copy"}
                </button>
              </li>
              <li>Approve the sign-in. This window closes automatically when you’re connected.</li>
            </ol>
            {link ? (
              <a className="sp-auth-open" href={link} target="_blank" rel="noreferrer">
                Open Microsoft sign-in ↗
              </a>
            ) : null}
            <p className="sp-auth-status" role="status">
              Waiting for you to finish signing in…
            </p>
          </div>
        ) : null}

        {phase === "connected" ? (
          <p className="sp-auth-success" role="status">
            ✓ Connected{account ? ` as ${account}` : ""}. You can now search SharePoint and OneDrive.
          </p>
        ) : null}

        {phase === "failed" ? (
          <div className="sp-auth-failed">
            <p role="alert">Sign-in didn’t complete: {error}</p>
            <button type="button" onClick={onClose}>
              Close
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
