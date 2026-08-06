"use client";

import { Fragment, useMemo, useState } from "react";

export type RsvpZeile = {
  id: string;
  vorname: string;
  nachname: string;
  email: string;
  telefon: string | null;
  teilnahme: "ja" | "nein";
  begleitung: boolean;
  begleitung_name: string | null;
  kinder_anzahl: number;
  kinder_namen: string | null;
  dabei_freitag: boolean;
  dabei_samstag: boolean;
  dabei_sonntag: boolean;
  uebernachtung: "hotel" | "woanders" | "keine";
  uebernachtung_details: string | null;
  naechte: string | null;
  essen: "alles" | "vegetarisch" | "vegan";
  allergien: string | null;
  shuttle: boolean;
  lied_wunsch: string | null;
  nachricht: string | null;
  created_at: string;
};

type Filter = "alle" | "ja" | "nein" | "hotel" | "woanders";

const filterLabel: Record<Filter, string> = {
  alle: "Alle",
  ja: "Zusagen",
  nein: "Absagen",
  hotel: "Schläft im Hotel",
  woanders: "Schläft woanders",
};

const uebernachtungLabel: Record<RsvpZeile["uebernachtung"], string> = {
  hotel: "Kloster Haydau",
  woanders: "Woanders",
  keine: "—",
};

const essenLabel: Record<RsvpZeile["essen"], string> = {
  alles: "Alles",
  vegetarisch: "Vegetarisch",
  vegan: "Vegan",
};

export default function AdminTabelle({ zeilen }: { zeilen: RsvpZeile[] }) {
  const [filter, setFilter] = useState<Filter>("alle");
  const [suche, setSuche] = useState("");
  const [offen, setOffen] = useState<string | null>(null);

  const gefiltert = useMemo(() => {
    const s = suche.trim().toLowerCase();
    return zeilen.filter((r) => {
      if (filter === "ja" && r.teilnahme !== "ja") return false;
      if (filter === "nein" && r.teilnahme !== "nein") return false;
      if (filter === "hotel" && r.uebernachtung !== "hotel") return false;
      if (filter === "woanders" && r.uebernachtung !== "woanders") return false;
      if (!s) return true;
      return `${r.vorname} ${r.nachname} ${r.email} ${r.begleitung_name ?? ""}`
        .toLowerCase()
        .includes(s);
    });
  }, [zeilen, filter, suche]);

  const csvExport = () => {
    const spalten: (keyof RsvpZeile)[] = [
      "vorname",
      "nachname",
      "email",
      "telefon",
      "teilnahme",
      "begleitung",
      "begleitung_name",
      "kinder_anzahl",
      "kinder_namen",
      "dabei_freitag",
      "dabei_samstag",
      "dabei_sonntag",
      "uebernachtung",
      "uebernachtung_details",
      "naechte",
      "essen",
      "allergien",
      "shuttle",
      "lied_wunsch",
      "nachricht",
      "created_at",
    ];

    const escape = (v: unknown) => {
      const s = v === null || v === undefined ? "" : String(v);
      // Formeln in Excel/Numbers neutralisieren
      const sicher = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
      return `"${sicher.replace(/"/g, '""')}"`;
    };

    const csv = [
      spalten.join(";"),
      ...gefiltert.map((r) => spalten.map((c) => escape(r[c])).join(";")),
    ].join("\r\n");

    // BOM, damit Excel Umlaute korrekt anzeigt
    const blob = new Blob(["﻿" + csv], {
      type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gaesteliste-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl">Gästeliste</h2>
        <button onClick={csvExport} className="btn btn-rand !py-2 !text-sm">
          Als CSV exportieren ({gefiltert.length})
        </button>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {(Object.keys(filterLabel) as Filter[]).map((k) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
              filter === k
                ? "bg-salbei-dunkel text-white"
                : "border border-sand bg-white text-grau hover:border-salbei"
            }`}
          >
            {filterLabel[k]}
          </button>
        ))}
        <input
          className="feld ml-auto max-w-56"
          placeholder="Name oder E-Mail suchen"
          value={suche}
          onChange={(e) => setSuche(e.target.value)}
        />
      </div>

      {gefiltert.length === 0 ? (
        <p className="karte mt-5 text-center text-grau">
          Noch keine Rückmeldungen in dieser Ansicht.
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto rounded-xl border border-sand bg-white">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="border-b border-sand bg-sand/30 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Pers.</th>
                <th className="px-4 py-3 font-medium">Übernachtung</th>
                <th className="px-4 py-3 font-medium">Tage</th>
                <th className="px-4 py-3 font-medium">Essen</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-sand">
              {gefiltert.map((r) => {
                const anzahl = 1 + (r.begleitung ? 1 : 0) + r.kinder_anzahl;
                const tage = [
                  r.dabei_freitag && "Fr",
                  r.dabei_samstag && "Sa",
                  r.dabei_sonntag && "So",
                ]
                  .filter(Boolean)
                  .join(" · ");

                return (
                  <Fragment key={r.id}>
                    <tr className="align-top">
                      <td className="px-4 py-3">
                        <div className="font-medium">
                          {r.vorname} {r.nachname}
                        </div>
                        <a
                          href={`mailto:${r.email}`}
                          className="text-xs text-grau underline underline-offset-2"
                        >
                          {r.email}
                        </a>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            r.teilnahme === "ja"
                              ? "bg-salbei/25 text-salbei-dunkel"
                              : "bg-altrosa/25 text-tinte"
                          }`}
                        >
                          {r.teilnahme === "ja" ? "Zusage" : "Absage"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {r.teilnahme === "ja" ? anzahl : "—"}
                      </td>
                      <td className="px-4 py-3 text-grau">
                        {r.teilnahme === "ja"
                          ? uebernachtungLabel[r.uebernachtung]
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-grau">{tage || "—"}</td>
                      <td className="px-4 py-3 text-grau">
                        {r.teilnahme === "ja" ? essenLabel[r.essen] : "—"}
                        {r.allergien?.trim() && (
                          <span className="ml-1 text-gold" title={r.allergien}>
                            ⚠
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setOffen(offen === r.id ? null : r.id)}
                          className="text-xs text-grau underline underline-offset-2"
                        >
                          {offen === r.id ? "Weniger" : "Details"}
                        </button>
                      </td>
                    </tr>

                    {offen === r.id && (
                      <tr className="bg-creme/60">
                        <td colSpan={7} className="px-4 py-4">
                          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
                            <Detail label="Telefon" wert={r.telefon} />
                            <Detail
                              label="Begleitung"
                              wert={
                                r.begleitung ? r.begleitung_name || "ja" : "nein"
                              }
                            />
                            <Detail
                              label="Kinder"
                              wert={
                                r.kinder_anzahl > 0
                                  ? `${r.kinder_anzahl} — ${r.kinder_namen || "keine Namen angegeben"}`
                                  : "keine"
                              }
                            />
                            <Detail label="Nächte" wert={r.naechte} />
                            <Detail
                              label="Unterkunft"
                              wert={r.uebernachtung_details}
                            />
                            <Detail label="Allergien" wert={r.allergien} />
                            <Detail
                              label="Shuttle"
                              wert={r.shuttle ? "ja" : "nein"}
                            />
                            <Detail label="Liedwunsch" wert={r.lied_wunsch} />
                            <Detail
                              label="Eingetragen am"
                              wert={new Date(r.created_at).toLocaleDateString(
                                "de-DE",
                                {
                                  day: "2-digit",
                                  month: "2-digit",
                                  year: "numeric",
                                },
                              )}
                            />
                            {r.nachricht?.trim() && (
                              <div className="sm:col-span-2 lg:col-span-3">
                                <dt className="text-xs tracking-wide text-grau uppercase">
                                  Nachricht
                                </dt>
                                <dd className="mt-1 whitespace-pre-wrap">
                                  {r.nachricht}
                                </dd>
                              </div>
                            )}
                          </dl>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Detail({ label, wert }: { label: string; wert: string | null }) {
  return (
    <div>
      <dt className="text-xs tracking-wide text-grau uppercase">{label}</dt>
      <dd className="mt-0.5">{wert?.trim() ? wert : "—"}</dd>
    </div>
  );
}
