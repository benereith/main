"use client";

import { useState } from "react";

export default function Faq({
  eintraege,
}: {
  eintraege: { frage: string; antwort: string }[];
}) {
  const [offen, setOffen] = useState<number | null>(0);

  return (
    <div className="mx-auto max-w-2xl divide-y divide-sand border-y border-sand">
      {eintraege.map((e, i) => (
        <div key={e.frage}>
          <button
            onClick={() => setOffen(offen === i ? null : i)}
            className="flex w-full items-center justify-between gap-4 py-5 text-left"
            aria-expanded={offen === i}
          >
            <span className="font-medium">{e.frage}</span>
            <span
              className={`shrink-0 text-gold transition-transform ${
                offen === i ? "rotate-45" : ""
              }`}
              aria-hidden
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 5v14M5 12h14"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
              </svg>
            </span>
          </button>
          {offen === i && (
            <p className="pb-5 leading-relaxed text-grau">{e.antwort}</p>
          )}
        </div>
      ))}
    </div>
  );
}
