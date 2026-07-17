import React from 'react';

/**
 * Themed loading modal — a centered box with an animated spinner, a title, and optional subtext.
 * Use it for long-running operations (parsing a repo, loading an integration) so the user gets a
 * clear "working…" overlay instead of only a disabled button.
 *
 * Props:
 *   open     — whether the modal is shown
 *   title    — main line (e.g. "Parsing repository…")
 *   subtext  — secondary line (e.g. the repo name / URL)
 *   step,total — optional progress counter; when total > 1 shows "step of total"
 */
export default function LoadingModal({ open, title = 'Working…', subtext, step, total }) {
  if (!open) return null;
  const showCount = !!total && total > 1 && !!step;
  return (
    <div className="loading-modal-overlay" role="alertdialog" aria-busy="true" aria-live="polite">
      <div className="loading-modal">
        <div className="loading-modal-spinner" aria-hidden />
        <h3 className="loading-modal-title">{title}</h3>
        {subtext && <p className="loading-modal-subtext">{subtext}</p>}
        {showCount && <span className="loading-modal-count">{step} of {total}</span>}
      </div>
    </div>
  );
}
