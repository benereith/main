import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { supabaseKonfiguriert } from "@/lib/supabase/konfiguriert";
import VorschauHinweis from "@/components/VorschauHinweis";
import { hochzeit } from "@/content/hochzeit";
import GaesteVerwaltung, {
  type Gast,
  type RsvpKurz,
} from "@/components/GaesteVerwaltung";

export const dynamic = "force-dynamic";

export default async function GaesteSeite() {
  if (!supabaseKonfiguriert) {
    return <VorschauHinweis was="Die Gästeliste ist" />;
  }

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login?weiter=/admin/gaeste");

  const istAdmin = hochzeit.adminEmails
    .map((e) => e.toLowerCase())
    .includes((user.email ?? "").toLowerCase());

  if (!istAdmin) {
    return (
      <div className="container-seite flex min-h-[70vh] items-center justify-center">
        <div className="karte max-w-md text-center">
          <h1 className="font-display text-2xl">Kein Zugriff</h1>
          <p className="mt-3 text-grau">
            Dieser Bereich ist nur für das Brautpaar.
          </p>
          <Link href="/" className="btn btn-rand mt-6">
            Zur Startseite
          </Link>
        </div>
      </div>
    );
  }

  const [{ data: gaeste, error: gaesteFehler }, { data: rsvps }] =
    await Promise.all([
      supabase
        .from("gaeste")
        .select("*")
        .order("nachname", { ascending: true })
        .order("vorname", { ascending: true }),
      supabase
        .from("rsvps")
        .select(
          "id, user_id, vorname, nachname, email, teilnahme, gast_id, zuordnung_art, created_at",
        )
        .order("created_at", { ascending: false }),
    ]);

  return (
    <div className="container-seite py-14">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">Nur für euch beide</p>
          <h1 className="ueberschrift mt-2">Gästeliste</h1>
          <p className="mt-2 text-grau">
            Wer ist eingeladen, wer hat schon geantwortet — und wer noch nicht.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/admin" className="btn btn-rand !py-2 !text-sm">
            Zur Übersicht
          </Link>
          <Link href="/" className="btn btn-rand !py-2 !text-sm">
            Zur Webseite
          </Link>
        </div>
      </header>

      {gaesteFehler && (
        <p className="mt-8 rounded-lg bg-altrosa/20 p-4 text-sm">
          Die Gästeliste konnte nicht geladen werden: {gaesteFehler.message}
          <br />
          Wahrscheinlich fehlt der neue Teil des Schemas. Spiel bitte{" "}
          <code>supabase/schema.sql</code> im SQL-Editor noch einmal komplett
          ein — das Skript ist wiederholbar und löscht nichts.
        </p>
      )}

      <div className="mt-10">
        <GaesteVerwaltung
          gaeste={(gaeste ?? []) as Gast[]}
          rsvps={(rsvps ?? []) as RsvpKurz[]}
        />
      </div>
    </div>
  );
}
