import Link from "next/link";

/**
 * Wird auf allen Seiten angezeigt, die Supabase brauchen, solange die
 * Zugangsdaten fehlen.
 */
export default function VorschauHinweis({ was }: { was: string }) {
  return (
    <div className="container-seite flex min-h-[75vh] items-center justify-center py-16">
      <div className="w-full max-w-lg karte text-center">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-sand text-gold">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 9v4m0 3.5h.01M10.3 3.9L2.4 17.1c-.7 1.2.2 2.6 1.6 2.6h16c1.4 0 2.3-1.4 1.6-2.6L13.7 3.9a1.9 1.9 0 00-3.4 0z"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        <p className="kicker">Vorschau-Modus</p>
        <h1 className="mt-3 font-display text-3xl">{was} noch nicht aktiv</h1>

        <p className="mt-4 leading-relaxed text-grau">
          Du siehst die Seite gerade ohne Datenbank. Alle Inhalte —{" "}
          Ablauf, Location, Anfahrt, Dresscode und FAQ — funktionieren normal
          und du kannst sie in Ruhe anpassen.
        </p>
        <p className="mt-3 leading-relaxed text-grau">
          Für Gäste-Zugänge, das Anmeldeformular und den Admin-Bereich brauchst
          du ein kostenloses Supabase-Projekt. Schritt 1 bis 3 im README
          erklären das in etwa zehn Minuten.
        </p>

        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Link href="/" className="btn btn-primar">
            Zurück zur Webseite
          </Link>
          <a
            href="https://supabase.com"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-rand"
          >
            Supabase öffnen
          </a>
        </div>

        <p className="mt-6 rounded-lg bg-sand/50 p-3 text-left text-xs text-grau">
          Konkret fehlen die beiden Werte{" "}
          <code className="text-tinte">NEXT_PUBLIC_SUPABASE_URL</code> und{" "}
          <code className="text-tinte">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> —
          lokal in der Datei <code className="text-tinte">.env.local</code>, bei
          Vercel unter Settings → Environment Variables.
        </p>
      </div>
    </div>
  );
}
