import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Landepunkt für den Link aus der Bestätigungsmail.
 * Tauscht den Code gegen eine Session und leitet weiter.
 */
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type");
  const weiter = searchParams.get("weiter") ?? "/rsvp";

  const supabase = await createClient();

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}/auth/bestaetigt?weiter=${weiter}`);
    }
  }

  // Fallback für Bestätigungslinks im älteren Format (token_hash + type)
  if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({
      type: type as "signup" | "email" | "recovery" | "invite",
      token_hash: tokenHash,
    });
    if (!error) {
      return NextResponse.redirect(`${origin}/auth/bestaetigt?weiter=${weiter}`);
    }
  }

  return NextResponse.redirect(
    `${origin}/login?fehler=Der%20Best%C3%A4tigungslink%20ist%20abgelaufen`,
  );
}
