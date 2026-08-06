import Link from "next/link";

export default async function Bestaetigt({
  searchParams,
}: {
  searchParams: Promise<{ weiter?: string }>;
}) {
  const { weiter } = await searchParams;
  const ziel = weiter?.startsWith("/") ? weiter : "/rsvp";

  return (
    <div className="container-seite flex min-h-[80vh] items-center justify-center py-16">
      <div className="w-full max-w-md karte text-center">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-salbei/25 text-salbei-dunkel">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <path
              d="M5 12.5l4.5 4.5L19 7.5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <h1 className="font-display text-3xl">E-Mail bestätigt</h1>
        <p className="mt-4 leading-relaxed text-grau">
          Dein Zugang ist aktiv. Jetzt fehlt nur noch das Anmeldeformular —
          dauert zwei Minuten.
        </p>
        <Link href={ziel} className="btn btn-primar mt-7">
          Weiter zum Formular
        </Link>
      </div>
    </div>
  );
}
