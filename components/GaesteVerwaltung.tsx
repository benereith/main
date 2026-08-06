"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export type Gast = {
  id: string;
  vorname: string;
  nachname: string;
  email: string | null;
  gruppe: string | null;
  seite: string | null;
  notiz: string | null;
  created_at: string;
};

export type RsvpKurz = {
  id: string;
  user_id: string;
  vorname: string;
  nachname: string;
  email: string;
  teilnahme: "ja" | "nein";
  gast_id: string | null;
  zuordnung_art: "email" | "name" | "manuell" | null;
  created_at: string;
};

type Reiter = "liste" | "offen" | "import";

/** Muss dieselbe Logik haben wie public.norm() in der Datenbank. */
function norm(t: string | null | undefined) {
  return (t ?? "")
    .replace(/ß/g, "ss")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

export default function GaesteVerwaltung({
  gaeste,
  rsvps,
}: {
  gaeste: Gast[];
  rsvps: RsvpKurz[];
}) {
  const router = useRouter();
  const [reiter, setReiter] = useState<Reiter>("liste");
  const [meldung, setMeldung] = useState<{
    art: "ok" | "fehler";
    text: string;
  } | null>(null);
  const [beschaeftigt, setBeschaeftigt] = useState(false);

  const rsvpProGast = useMemo(() => {
    const m = new Map<string, RsvpKurz>();
    rsvps.forEach((r) => r.gast_id && m.set(r.gast_id, r));
    return m;
  }, [rsvps]);

  const offeneRsvps = useMemo(
    () => rsvps.filter((r) => !r.gast_id),
    [rsvps],
  );

  const freieGaeste = useMemo(
    () => gaeste.filter((g) => !rsvpProGast.has(g.id)),
    [gaeste, rsvpProGast],
  );

  // ---- Kennzahlen ----
  const geantwortet = gaeste.filter((g) => rsvpProGast.has(g.id));
  const zugesagt = geantwortet.filter(
    (g) => rsvpProGast.get(g.id)!.teilnahme === "ja",
  ).length;
  const abgesagt = geantwortet.length - zugesagt;

  const kacheln = [
    { label: "Eingeladen", wert: gaeste.length, ton: "" },
    { label: "Zugesagt", wert: zugesagt, ton: "text-salbei-dunkel" },
    { label: "Abgesagt", wert: abgesagt, ton: "text-altrosa" },
    { label: "Noch keine Antwort", wert: freieGaeste.length, ton: "text-gold" },
  ];

  const zuordnungPruefen = async () => {
    setBeschaeftigt(true);
    setMeldung(null);
    const supabase = createClient();
    const { data, error } = await supabase.rpc("zuordnung_neu_pruefen");
    setBeschaeftigt(false);

    if (error) {
      return setMeldung({ art: "fehler", text: error.message });
    }
    setMeldung({
      art: "ok",
      text:
        (data ?? 0) === 0
          ? "Keine neuen Zuordnungen gefunden."
          : `${data} Anmeldung(en) neu zugeordnet.`,
    });
    router.refresh();
  };

  return (
    <div>
      {/* Kennzahlen */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kacheln.map((k) => (
          <div key={k.label} className="karte">
            <p className="text-sm text-grau">{k.label}</p>
            <p className={`mt-1 font-display text-4xl ${k.ton}`}>{k.wert}</p>
          </div>
        ))}
      </div>

      {offeneRsvps.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-gold/15 p-4">
          <p className="text-sm">
            <strong>{offeneRsvps.length}</strong> Anmeldung(en) konnten keinem
            Eintrag der Gästeliste zugeordnet werden.
          </p>
          <button
            onClick={() => setReiter("offen")}
            className="btn btn-rand !py-1.5 !text-sm"
          >
            Jetzt zuordnen
          </button>
        </div>
      )}

      {meldung && (
        <p
          className={`mt-6 rounded-lg p-3 text-sm ${
            meldung.art === "ok" ? "bg-salbei/20" : "bg-altrosa/20"
          }`}
        >
          {meldung.text}
        </p>
      )}

      {/* Reiter */}
      <div className="mt-8 flex flex-wrap items-center gap-2">
        {(
          [
            ["liste", `Gästeliste (${gaeste.length})`],
            ["offen", `Noch zuzuordnen (${offeneRsvps.length})`],
            ["import", "Liste importieren"],
          ] as const
        ).map(([k, text]) => (
          <button
            key={k}
            onClick={() => setReiter(k)}
            className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
              reiter === k
                ? "bg-salbei-dunkel text-white"
                : "border border-sand bg-white text-grau hover:border-salbei"
            }`}
          >
            {text}
          </button>
        ))}
        <button
          onClick={zuordnungPruefen}
          disabled={beschaeftigt}
          className="ml-auto text-sm text-grau underline underline-offset-4 disabled:opacity-50"
        >
          {beschaeftigt ? "Prüfe …" : "Zuordnung neu prüfen"}
        </button>
      </div>

      <div className="mt-6">
        {reiter === "liste" && (
          <Liste
            gaeste={gaeste}
            rsvpProGast={rsvpProGast}
            onMeldung={setMeldung}
          />
        )}
        {reiter === "offen" && (
          <Zuordnen
            offeneRsvps={offeneRsvps}
            freieGaeste={freieGaeste}
            onMeldung={setMeldung}
          />
        )}
        {reiter === "import" && (
          <Import vorhanden={gaeste} onMeldung={setMeldung} />
        )}
      </div>
    </div>
  );
}

/* ==========================================================================
 *  Reiter 1: Die Liste
 * ======================================================================== */
function Liste({
  gaeste,
  rsvpProGast,
  onMeldung,
}: {
  gaeste: Gast[];
  rsvpProGast: Map<string, RsvpKurz>;
  onMeldung: (m: { art: "ok" | "fehler"; text: string }) => void;
}) {
  const router = useRouter();
  const [suche, setSuche] = useState("");
  const [status, setStatus] = useState<"alle" | "offen" | "ja" | "nein">("alle");
  const [bearbeitet, setBearbeitet] = useState<string | null>(null);

  const gefiltert = useMemo(() => {
    const s = norm(suche);
    return gaeste.filter((g) => {
      const r = rsvpProGast.get(g.id);
      if (status === "offen" && r) return false;
      if (status === "ja" && r?.teilnahme !== "ja") return false;
      if (status === "nein" && r?.teilnahme !== "nein") return false;
      if (!s) return true;
      return norm(
        `${g.vorname} ${g.nachname} ${g.email ?? ""} ${g.gruppe ?? ""}`,
      ).includes(s);
    });
  }, [gaeste, rsvpProGast, suche, status]);

  const loeschen = async (g: Gast) => {
    if (
      !confirm(
        `${g.vorname} ${g.nachname} wirklich aus der Gästeliste entfernen?`,
      )
    )
      return;

    const supabase = createClient();
    const { error } = await supabase.from("gaeste").delete().eq("id", g.id);
    if (error) return onMeldung({ art: "fehler", text: error.message });
    onMeldung({ art: "ok", text: `${g.vorname} ${g.nachname} entfernt.` });
    router.refresh();
  };

  const nachfassenMailto = () => {
    const adressen = gefiltert
      .filter((g) => !rsvpProGast.has(g.id) && g.email?.trim())
      .map((g) => g.email!.trim());
    if (adressen.length === 0) {
      return onMeldung({
        art: "fehler",
        text: "In dieser Ansicht hat niemand ohne Antwort eine E-Mail-Adresse hinterlegt.",
      });
    }
    window.location.href = `mailto:?bcc=${encodeURIComponent(
      adressen.join(","),
    )}&subject=${encodeURIComponent("Kurze Erinnerung: unsere Hochzeit")}`;
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["alle", "Alle"],
            ["offen", "Ohne Antwort"],
            ["ja", "Zugesagt"],
            ["nein", "Abgesagt"],
          ] as const
        ).map(([k, text]) => (
          <button
            key={k}
            onClick={() => setStatus(k)}
            className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
              status === k
                ? "bg-salbei-dunkel text-white"
                : "border border-sand bg-white text-grau hover:border-salbei"
            }`}
          >
            {text}
          </button>
        ))}
        <input
          className="feld ml-auto max-w-56"
          placeholder="Name, Mail oder Gruppe"
          value={suche}
          onChange={(e) => setSuche(e.target.value)}
        />
        <button
          onClick={nachfassenMailto}
          className="btn btn-rand !py-2 !text-sm"
          title="Öffnet dein Mailprogramm mit allen Adressen im BCC"
        >
          Nachfassen
        </button>
      </div>

      <NeuerGast onMeldung={onMeldung} />

      {gefiltert.length === 0 ? (
        <p className="karte mt-5 text-center text-grau">
          {gaeste.length === 0
            ? "Noch niemand auf der Liste. Wechsel auf „Liste importieren“."
            : "Kein Treffer in dieser Ansicht."}
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto rounded-xl border border-sand bg-white">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-sand bg-sand/30 text-left">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">E-Mail (erwartet)</th>
                <th className="px-4 py-3 font-medium">Gruppe</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-sand">
              {gefiltert.map((g) => {
                const r = rsvpProGast.get(g.id);
                return bearbeitet === g.id ? (
                  <tr key={g.id}>
                    <td colSpan={5} className="bg-creme/60 px-4 py-4">
                      <GastBearbeiten
                        gast={g}
                        onFertig={() => setBearbeitet(null)}
                        onMeldung={onMeldung}
                      />
                    </td>
                  </tr>
                ) : (
                  <tr key={g.id} className="align-top">
                    <td className="px-4 py-3">
                      <div className="font-medium">
                        {g.vorname} {g.nachname}
                      </div>
                      {g.seite && (
                        <div className="text-xs text-grau">{g.seite}</div>
                      )}
                      {g.notiz && (
                        <div className="text-xs text-grau italic">{g.notiz}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-grau">{g.email || "—"}</td>
                    <td className="px-4 py-3 text-grau">{g.gruppe || "—"}</td>
                    <td className="px-4 py-3">
                      {r ? (
                        <>
                          <span
                            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              r.teilnahme === "ja"
                                ? "bg-salbei/25 text-salbei-dunkel"
                                : "bg-altrosa/25 text-tinte"
                            }`}
                          >
                            {r.teilnahme === "ja" ? "Zusage" : "Absage"}
                          </span>
                          <div className="mt-1 text-xs text-grau">
                            {r.email}
                            {r.zuordnung_art === "manuell" && " · von Hand"}
                          </div>
                        </>
                      ) : (
                        <span className="text-xs text-grau">
                          noch keine Antwort
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => setBearbeitet(g.id)}
                        className="text-xs text-grau underline underline-offset-2"
                      >
                        Bearbeiten
                      </button>
                      <button
                        onClick={() => loeschen(g)}
                        className="ml-3 text-xs text-altrosa underline underline-offset-2"
                      >
                        Löschen
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ---- Einzelnen Gast anlegen ---- */
function NeuerGast({
  onMeldung,
}: {
  onMeldung: (m: { art: "ok" | "fehler"; text: string }) => void;
}) {
  const router = useRouter();
  const [offen, setOffen] = useState(false);
  const [f, setF] = useState({
    vorname: "",
    nachname: "",
    email: "",
    gruppe: "",
    seite: "",
  });

  const speichern = async (e: React.FormEvent) => {
    e.preventDefault();
    const supabase = createClient();
    const { error } = await supabase.from("gaeste").insert({
      vorname: f.vorname.trim(),
      nachname: f.nachname.trim(),
      email: f.email.trim() || null,
      gruppe: f.gruppe.trim() || null,
      seite: f.seite.trim() || null,
    });
    if (error) return onMeldung({ art: "fehler", text: error.message });

    onMeldung({
      art: "ok",
      text: `${f.vorname} ${f.nachname} hinzugefügt.`,
    });
    setF({ vorname: "", nachname: "", email: "", gruppe: "", seite: "" });
    setOffen(false);
    router.refresh();
  };

  if (!offen) {
    return (
      <button
        onClick={() => setOffen(true)}
        className="mt-4 text-sm text-grau underline underline-offset-4"
      >
        + Einzelnen Gast hinzufügen
      </button>
    );
  }

  return (
    <form onSubmit={speichern} className="karte mt-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <input
          className="feld"
          placeholder="Vorname"
          required
          value={f.vorname}
          onChange={(e) => setF({ ...f, vorname: e.target.value })}
        />
        <input
          className="feld"
          placeholder="Nachname"
          required
          value={f.nachname}
          onChange={(e) => setF({ ...f, nachname: e.target.value })}
        />
        <input
          className="feld"
          type="email"
          placeholder="E-Mail (optional)"
          value={f.email}
          onChange={(e) => setF({ ...f, email: e.target.value })}
        />
        <input
          className="feld"
          placeholder="Gruppe (optional)"
          value={f.gruppe}
          onChange={(e) => setF({ ...f, gruppe: e.target.value })}
        />
        <input
          className="feld"
          placeholder="Seite (optional)"
          value={f.seite}
          onChange={(e) => setF({ ...f, seite: e.target.value })}
        />
      </div>
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn btn-primar !py-2 !text-sm">
          Hinzufügen
        </button>
        <button
          type="button"
          onClick={() => setOffen(false)}
          className="btn btn-rand !py-2 !text-sm"
        >
          Abbrechen
        </button>
      </div>
    </form>
  );
}

/* ---- Gast bearbeiten ---- */
function GastBearbeiten({
  gast,
  onFertig,
  onMeldung,
}: {
  gast: Gast;
  onFertig: () => void;
  onMeldung: (m: { art: "ok" | "fehler"; text: string }) => void;
}) {
  const router = useRouter();
  const [f, setF] = useState({
    vorname: gast.vorname,
    nachname: gast.nachname,
    email: gast.email ?? "",
    gruppe: gast.gruppe ?? "",
    seite: gast.seite ?? "",
    notiz: gast.notiz ?? "",
  });

  const speichern = async (e: React.FormEvent) => {
    e.preventDefault();
    const supabase = createClient();
    const { error } = await supabase
      .from("gaeste")
      .update({
        vorname: f.vorname.trim(),
        nachname: f.nachname.trim(),
        email: f.email.trim() || null,
        gruppe: f.gruppe.trim() || null,
        seite: f.seite.trim() || null,
        notiz: f.notiz.trim() || null,
      })
      .eq("id", gast.id);

    if (error) return onMeldung({ art: "fehler", text: error.message });
    onMeldung({ art: "ok", text: "Gespeichert." });
    onFertig();
    router.refresh();
  };

  return (
    <form onSubmit={speichern}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <input
          className="feld"
          placeholder="Vorname"
          required
          value={f.vorname}
          onChange={(e) => setF({ ...f, vorname: e.target.value })}
        />
        <input
          className="feld"
          placeholder="Nachname"
          required
          value={f.nachname}
          onChange={(e) => setF({ ...f, nachname: e.target.value })}
        />
        <input
          className="feld"
          type="email"
          placeholder="E-Mail"
          value={f.email}
          onChange={(e) => setF({ ...f, email: e.target.value })}
        />
        <input
          className="feld"
          placeholder="Gruppe"
          value={f.gruppe}
          onChange={(e) => setF({ ...f, gruppe: e.target.value })}
        />
        <input
          className="feld"
          placeholder="Seite"
          value={f.seite}
          onChange={(e) => setF({ ...f, seite: e.target.value })}
        />
        <input
          className="feld"
          placeholder="Notiz"
          value={f.notiz}
          onChange={(e) => setF({ ...f, notiz: e.target.value })}
        />
      </div>
      <div className="mt-3 flex gap-2">
        <button type="submit" className="btn btn-primar !py-2 !text-sm">
          Speichern
        </button>
        <button
          type="button"
          onClick={onFertig}
          className="btn btn-rand !py-2 !text-sm"
        >
          Abbrechen
        </button>
      </div>
    </form>
  );
}

/* ==========================================================================
 *  Reiter 2: Zuordnen
 * ======================================================================== */
function Zuordnen({
  offeneRsvps,
  freieGaeste,
  onMeldung,
}: {
  offeneRsvps: RsvpKurz[];
  freieGaeste: Gast[];
  onMeldung: (m: { art: "ok" | "fehler"; text: string }) => void;
}) {
  const router = useRouter();
  const [laueft, setLaueft] = useState<string | null>(null);

  const zuordnen = async (rsvp: RsvpKurz, gastId: string) => {
    if (!gastId) return;
    setLaueft(rsvp.id);
    const supabase = createClient();
    const { error } = await supabase
      .from("rsvps")
      .update({ gast_id: gastId })
      .eq("id", rsvp.id);
    setLaueft(null);

    if (error) {
      return onMeldung({
        art: "fehler",
        text: error.message.includes("rsvps_gast_id_idx")
          ? "Dieser Eintrag der Gästeliste ist schon einer anderen Anmeldung zugeordnet."
          : error.message,
      });
    }
    onMeldung({ art: "ok", text: "Zugeordnet." });
    router.refresh();
  };

  if (offeneRsvps.length === 0) {
    return (
      <p className="karte text-center text-grau">
        Alles zugeordnet — jede Anmeldung hängt an einem Eintrag der Gästeliste.
      </p>
    );
  }

  return (
    <div>
      <p className="text-sm text-grau">
        Diese Anmeldungen passten zu keinem oder zu mehreren Einträgen der
        Gästeliste. Ordne sie hier von Hand zu. Vorschläge mit ähnlichem Namen
        stehen oben in der Auswahl.
      </p>

      <div className="mt-5 space-y-3">
        {offeneRsvps.map((r) => {
          // Vorschläge: gleicher Nachname zuerst, dann alle übrigen
          const passend = freieGaeste.filter(
            (g) => norm(g.nachname) === norm(r.nachname),
          );
          const rest = freieGaeste.filter(
            (g) => norm(g.nachname) !== norm(r.nachname),
          );

          return (
            <div
              key={r.id}
              className="karte flex flex-wrap items-center justify-between gap-4"
            >
              <div>
                <p className="font-medium">
                  {r.vorname} {r.nachname}
                  <span
                    className={`ml-2 rounded-full px-2 py-0.5 text-xs font-medium ${
                      r.teilnahme === "ja"
                        ? "bg-salbei/25 text-salbei-dunkel"
                        : "bg-altrosa/25 text-tinte"
                    }`}
                  >
                    {r.teilnahme === "ja" ? "Zusage" : "Absage"}
                  </span>
                </p>
                <p className="text-sm text-grau">{r.email}</p>
              </div>

              <select
                className="feld max-w-72"
                defaultValue=""
                disabled={laueft === r.id || freieGaeste.length === 0}
                onChange={(e) => zuordnen(r, e.target.value)}
              >
                <option value="">
                  {freieGaeste.length === 0
                    ? "Keine freien Einträge"
                    : "Eintrag auswählen …"}
                </option>
                {passend.length > 0 && (
                  <optgroup label="Gleicher Nachname">
                    {passend.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.vorname} {g.nachname}
                        {g.gruppe ? ` — ${g.gruppe}` : ""}
                      </option>
                    ))}
                  </optgroup>
                )}
                <optgroup label="Alle offenen Einträge">
                  {rest.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.vorname} {g.nachname}
                      {g.gruppe ? ` — ${g.gruppe}` : ""}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
          );
        })}
      </div>

      <p className="mt-5 text-sm text-grau">
        Steht jemand gar nicht auf der Gästeliste (z.B. eine kurzfristige
        Einladung)? Dann leg den Eintrag unter „Gästeliste“ an und ordne hier
        erneut zu.
      </p>
    </div>
  );
}

/* ==========================================================================
 *  Reiter 3: Import
 * ======================================================================== */
type ImportZeile = {
  vorname: string;
  nachname: string;
  email: string | null;
  gruppe: string | null;
  seite: string | null;
  notiz: string | null;
};

function Import({
  vorhanden,
  onMeldung,
}: {
  vorhanden: Gast[];
  onMeldung: (m: { art: "ok" | "fehler"; text: string }) => void;
}) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [laedt, setLaedt] = useState(false);

  const { neu, doppelt, fehlerhaft } = useMemo(() => {
    const bekannt = new Set(
      vorhanden.map((g) => `${norm(g.vorname)}|${norm(g.nachname)}`),
    );
    const neu: ImportZeile[] = [];
    const doppelt: string[] = [];
    const fehlerhaft: string[] = [];

    text
      .split(/\r?\n/)
      .map((z) => z.trim())
      .filter(Boolean)
      .forEach((zeile) => {
        // Trennzeichen automatisch erkennen: Semikolon, Tab oder Komma
        const trenner = zeile.includes(";")
          ? ";"
          : zeile.includes("\t")
            ? "\t"
            : ",";
        const teile = zeile.split(trenner).map((t) => t.trim());

        // Kopfzeile überspringen
        if (norm(teile[0]) === "vorname") return;

        const [vorname, nachname, email, gruppe, seite, notiz] = teile;
        if (!vorname || !nachname) {
          fehlerhaft.push(zeile);
          return;
        }

        const schluessel = `${norm(vorname)}|${norm(nachname)}`;
        if (bekannt.has(schluessel)) {
          doppelt.push(`${vorname} ${nachname}`);
          return;
        }
        bekannt.add(schluessel);

        neu.push({
          vorname,
          nachname,
          email: email || null,
          gruppe: gruppe || null,
          seite: seite || null,
          notiz: notiz || null,
        });
      });

    return { neu, doppelt, fehlerhaft };
  }, [text, vorhanden]);

  const importieren = async () => {
    if (neu.length === 0) return;
    setLaedt(true);
    const supabase = createClient();
    const { error } = await supabase.from("gaeste").insert(neu);
    setLaedt(false);

    if (error) return onMeldung({ art: "fehler", text: error.message });
    onMeldung({
      art: "ok",
      text: `${neu.length} Gäste importiert.`,
    });
    setText("");
    router.refresh();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <div className="karte">
        <h2 className="font-display text-xl">Gästeliste einfügen</h2>
        <p className="mt-2 text-sm text-grau">
          Eine Person pro Zeile. Spalten mit Semikolon, Tab oder Komma trennen.
          Du kannst direkt aus Excel oder Google Sheets kopieren und hier
          einfügen — dann passt das Format automatisch.
        </p>

        <pre className="mt-4 overflow-x-auto rounded-lg bg-sand/40 p-3 text-xs">
          {`Vorname;Nachname;E-Mail;Gruppe;Seite;Notiz
Lisa;Müller;lisa.mueller@web.de;Familie Müller;Braut;
Tom;Müller;;Familie Müller;Braut;Sohn von Lisa
Jan;Schneider;jan@beispiel.de;;Bräutigam;Trauzeuge`}
        </pre>

        <ul className="mt-4 space-y-1 text-sm text-grau">
          <li>
            <strong>Vorname</strong> und <strong>Nachname</strong> sind Pflicht,
            der Rest ist optional.
          </li>
          <li>
            Die <strong>E-Mail</strong> macht die Zuordnung eindeutig — trag sie
            ein, wo du sie kennst.
          </li>
          <li>
            Eine Kopfzeile darf drin bleiben, sie wird automatisch übersprungen.
          </li>
        </ul>

        <textarea
          className="feld mt-5 min-h-56 resize-y font-mono text-xs"
          placeholder="Hier die Liste einfügen …"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <button
          onClick={importieren}
          disabled={laedt || neu.length === 0}
          className="btn btn-primar mt-4"
        >
          {laedt
            ? "Importiere …"
            : neu.length === 0
              ? "Nichts zu importieren"
              : `${neu.length} Gäste importieren`}
        </button>
      </div>

      <div className="karte h-fit">
        <h3 className="font-display text-lg">Vorschau</h3>

        <ul className="mt-4 space-y-2 text-sm">
          <li className="flex justify-between">
            <span className="text-grau">Neu</span>
            <strong className="text-salbei-dunkel">{neu.length}</strong>
          </li>
          <li className="flex justify-between">
            <span className="text-grau">Schon vorhanden</span>
            <strong>{doppelt.length}</strong>
          </li>
          <li className="flex justify-between">
            <span className="text-grau">Unvollständig</span>
            <strong className={fehlerhaft.length ? "text-altrosa" : ""}>
              {fehlerhaft.length}
            </strong>
          </li>
        </ul>

        {doppelt.length > 0 && (
          <div className="mt-4 border-t border-sand pt-3">
            <p className="text-xs tracking-wide text-grau uppercase">
              Wird übersprungen
            </p>
            <p className="mt-1 text-sm text-grau">
              {doppelt.slice(0, 8).join(", ")}
              {doppelt.length > 8 && ` … (+${doppelt.length - 8})`}
            </p>
          </div>
        )}

        {fehlerhaft.length > 0 && (
          <div className="mt-4 border-t border-sand pt-3">
            <p className="text-xs tracking-wide text-altrosa uppercase">
              Fehlt Vor- oder Nachname
            </p>
            <ul className="mt-1 space-y-1 text-sm text-grau">
              {fehlerhaft.slice(0, 5).map((z, i) => (
                <li key={i} className="truncate font-mono text-xs">
                  {z}
                </li>
              ))}
            </ul>
          </div>
        )}

        {neu.length > 0 && (
          <div className="mt-4 border-t border-sand pt-3">
            <p className="text-xs tracking-wide text-grau uppercase">
              Wird angelegt
            </p>
            <ul className="mt-1 max-h-52 space-y-1 overflow-y-auto text-sm">
              {neu.map((g, i) => (
                <li key={i}>
                  {g.vorname} {g.nachname}
                  {g.email && (
                    <span className="text-grau"> · {g.email}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
