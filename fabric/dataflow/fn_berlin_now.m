// =====================================================================
// Dataflow Gen2 - Funktionsquery: fn_berlin_now
// Ergebnis: aktueller Zeitpunkt als datetimezone mit Berliner Versatz
//
// "Laden aktivieren" fuer diese Query ausschalten - sie ist ein Helfer,
// keine Zieltabelle.
//
// Warum nicht DateTimeZone.FixedLocalNow():
// Die Fabric-Kapazitaet laeuft in der Zeitzone der Gruppe (UK), Berlin liegt
// durchgehend eine Stunde davor. Ein Lauf zwischen 00:00 und 01:00 Berliner
// Zeit faellt in UK-Zeit noch auf den Vortag,
// der Snapshot bekaeme das falsche Datum. Da snapshot_date sowohl
// Partitionsschluessel als auch fachlicher Schluessel der
// Aenderungserkennung ist, verschoebe ein solcher Versatz die komplette
// Historie um einen Tag.
//
// M kennt keine Zeitzonendatenbank, deshalb ist die EU-Regel hier
// explizit hinterlegt: Sommerzeit vom letzten Sonntag im Maerz 01:00 UTC
// bis zum letzten Sonntag im Oktober 01:00 UTC. In diesem Fenster gilt
// UTC+2 (CEST), sonst UTC+1 (CET).
// =====================================================================
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
