/**
 * Ist Supabase eingerichtet?
 *
 * Solange die beiden Umgebungsvariablen fehlen, läuft die Seite im
 * Vorschau-Modus: Alle öffentlichen Inhalte funktionieren normal, nur
 * Login, Anmeldung und Admin-Bereich zeigen statt eines Fehlers einen
 * freundlichen Hinweis. So kannst du dir die Seite ansehen und Texte
 * anpassen, bevor du irgendetwas einrichtest.
 */
export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const supabaseKonfiguriert = Boolean(
  supabaseUrl && supabaseKey && supabaseUrl.startsWith("http"),
);
