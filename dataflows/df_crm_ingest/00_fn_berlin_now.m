// ===========================================================================
// Dataflow Gen2  ·  Funktionsquery: fn_berlin_now
// ===========================================================================
// Ergebnis: aktueller Zeitpunkt als datetimezone mit Berliner Versatz.
//
// "Laden aktivieren" fuer diese Query AUSSCHALTEN - sie ist ein Helfer,
// keine Zieltabelle.
//
// WARUM NICHT DateTimeZone.FixedLocalNow()
// Die Fabric-Kapazitaet der Gruppe laeuft in UK-Zeit, TODAY()/NOW() im Power
// BI Service laufen in UTC. Berlin liegt gegenueber UK durchgehend eine
// Stunde, gegenueber UTC je nach Sommerzeit ein bis zwei Stunden vorn.
//
// Ein Ladelauf zwischen 00:00 und 01:00 Berliner Zeit bekaeme in UK-Zeit noch
// das Datum des Vortags. Da snapshot_date sowohl Partitionsschluessel als
// auch fachlicher Schluessel der Aenderungserkennung ist, wuerde der Snapshot
// in die Vortagspartition fallen, dort den echten Vortagsstand ueberschreiben
// und in den *_changes-Tabellen einen Tag Historie ausloeschen. Bei einem
// Nachtplan oder einem Retry nach Mitternacht passiert das unbemerkt.
//
// M kennt keine Zeitzonendatenbank, deshalb liegt die EU-Sommerzeitregel hier
// explizit: Sommerzeit vom letzten Sonntag im Maerz 01:00 UTC bis zum letzten
// Sonntag im Oktober 01:00 UTC. In diesem Fenster gilt UTC+2 (CEST), sonst
// UTC+1 (CET).
//
// RUECKGABETYP ist datetimezone. Die aufrufenden Queries schneiden den
// Versatz per DateTime.From ab, bevor sie schreiben: das Lakehouse-Ziel eines
// Dataflow Gen2 unterstuetzt datetimezone nicht ("Diese Spalte kann nicht
// eingeschlossen werden, da ihr Typ nicht unterstuetzt wird"). Der Versatz
// wird also nur zum Rechnen gebraucht, nicht zum Speichern. Zusammen mit der
// auf Europe/Berlin gesetzten Spark-Session bleibt die Wanduhrzeit ueber die
// ganze Strecke konsistent.
//
// Uebernommen aus der Vorarbeit (Branch claude/crm-report-rebuild-1bwcfg),
// dort stundenweise ueber 2024-2035 gegen die IANA-Zeitzonendaten geprueft.
// ===========================================================================
() as datetimezone =>
let
    UtcJetzt = DateTimeZone.FixedUtcNow(),
    UtcWert  = DateTime.From(UtcJetzt),
    Jahr     = Date.Year(UtcWert),

    // Date.StartOfWeek liefert den Sonntag am oder vor dem Stichtag -
    // angewendet auf den Monatsletzten also den letzten Sonntag im Monat.
    LetzterSonntagMaerz   = Date.StartOfWeek(#date(Jahr, 3, 31), Day.Sunday),
    LetzterSonntagOktober = Date.StartOfWeek(#date(Jahr, 10, 31), Day.Sunday),

    SommerzeitBeginn = #datetime(Jahr, 3, Date.Day(LetzterSonntagMaerz), 1, 0, 0),
    SommerzeitEnde   = #datetime(Jahr, 10, Date.Day(LetzterSonntagOktober), 1, 0, 0),

    IstSommerzeit = UtcWert >= SommerzeitBeginn and UtcWert < SommerzeitEnde,
    Versatz       = if IstSommerzeit then 2 else 1
in
    DateTimeZone.SwitchZone(UtcJetzt, Versatz)
