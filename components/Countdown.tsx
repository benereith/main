"use client";

import { useEffect, useState } from "react";

export default function Countdown({ zielISO }: { zielISO: string }) {
  const [rest, setRest] = useState<null | {
    tage: number;
    stunden: number;
    minuten: number;
  }>(null);

  useEffect(() => {
    const rechne = () => {
      const ms = new Date(zielISO).getTime() - Date.now();
      if (ms <= 0) return setRest({ tage: 0, stunden: 0, minuten: 0 });
      setRest({
        tage: Math.floor(ms / 86400000),
        stunden: Math.floor((ms / 3600000) % 24),
        minuten: Math.floor((ms / 60000) % 60),
      });
    };
    rechne();
    const id = setInterval(rechne, 30000);
    return () => clearInterval(id);
  }, [zielISO]);

  // Vor der Hydration nichts rendern, damit Server und Client übereinstimmen.
  if (!rest) return <div className="h-[76px]" aria-hidden />;

  const felder = [
    { wert: rest.tage, label: rest.tage === 1 ? "Tag" : "Tage" },
    { wert: rest.stunden, label: "Stunden" },
    { wert: rest.minuten, label: "Minuten" },
  ];

  return (
    <div className="flex items-start justify-center gap-8 sm:gap-12">
      {felder.map((f) => (
        <div key={f.label} className="text-center">
          <div className="font-display text-4xl sm:text-5xl">{f.wert}</div>
          <div className="mt-1 text-xs tracking-widest text-grau uppercase">
            {f.label}
          </div>
        </div>
      ))}
    </div>
  );
}
