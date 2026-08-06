import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import RsvpFormular from "@/components/RsvpFormular";

export const dynamic = "force-dynamic";

export default async function RsvpSeite() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login?weiter=/rsvp");

  const { data: vorhanden } = await supabase
    .from("rsvps")
    .select("*")
    .eq("user_id", user.id)
    .maybeSingle();

  const meta = user.user_metadata ?? {};

  return (
    <div className="container-seite max-w-2xl py-16">
      <RsvpFormular
        userId={user.id}
        email={user.email ?? ""}
        vornameVorgabe={meta.vorname ?? ""}
        nachnameVorgabe={meta.nachname ?? ""}
        vorhanden={vorhanden}
      />
    </div>
  );
}
