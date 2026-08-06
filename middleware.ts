import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import {
  supabaseKey,
  supabaseKonfiguriert,
  supabaseUrl,
} from "@/lib/supabase/konfiguriert";

export async function middleware(request: NextRequest) {
  // Vorschau-Modus ohne Supabase: einfach durchlassen, die Seiten selbst
  // zeigen dann einen Hinweis.
  if (!supabaseKonfiguriert) return NextResponse.next({ request });

  let response = NextResponse.next({ request });

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
      },
    },
  });

  // Hält die Session frisch. Nicht entfernen.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const geschuetzt = ["/rsvp", "/admin"];
  const brauchtLogin = geschuetzt.some((p) =>
    request.nextUrl.pathname.startsWith(p),
  );

  if (brauchtLogin && !user) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("weiter", request.nextUrl.pathname);
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
