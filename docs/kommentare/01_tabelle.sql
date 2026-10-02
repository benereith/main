/*
    Flash-Bericht: Kommentartabelle
    -------------------------------
    Anzulegen in einer Fabric-SQL-Datenbank (Fabric SQL Database, nicht Warehouse -
    Translytical Task Flows schreiben über eine User Data Function in eine SQL-Datenbank).

    Der Bericht liest die Tabelle per DirectQuery (Tabelle "Kommentare" im semantischen Modell),
    damit ein neu erfasster Kommentar ohne Modell-Refresh sofort sichtbar ist.

    Der Status_Key muss exakt wie im Modell gebildet werden (Dim_UnitStatus, Fakt_SAP):
        Werk * 1.000.000 + Geschäftsjahr * 100 + Periode
*/

CREATE TABLE dbo.Flash_Kommentare
(
    Kommentar_ID  BIGINT IDENTITY(1,1) NOT NULL,
    Werk          INT            NOT NULL,
    Fiscal_Year   INT            NOT NULL,
    Periode       TINYINT        NOT NULL,
    Kommentar     NVARCHAR(2000) NOT NULL,
    Kategorie     NVARCHAR(50)   NOT NULL CONSTRAINT DF_Flash_Kommentare_Kategorie DEFAULT ('Sonstiges'),
    Erfasst_von   NVARCHAR(200)  NOT NULL,
    Erfasst_am    DATETIME2(0)   NOT NULL CONSTRAINT DF_Flash_Kommentare_Erfasst_am DEFAULT (SYSUTCDATETIME()),
    Ist_Aktiv     BIT            NOT NULL CONSTRAINT DF_Flash_Kommentare_Ist_Aktiv DEFAULT (1),

    -- Verknüpfung zu Dim_UnitStatus im Modell (ganzzahlig, wie Fakt_SAP)
    Status_Key AS (CAST(Werk AS BIGINT) * 1000000 + CAST(Fiscal_Year AS BIGINT) * 100 + CAST(Periode AS BIGINT)) PERSISTED,

    CONSTRAINT PK_Flash_Kommentare PRIMARY KEY CLUSTERED (Kommentar_ID),
    CONSTRAINT CK_Flash_Kommentare_Periode CHECK (Periode BETWEEN 1 AND 12)
);
GO

-- Der Bericht filtert praktisch immer über den Status_Key (Werk + Periode).
CREATE NONCLUSTERED INDEX IX_Flash_Kommentare_Status_Key
    ON dbo.Flash_Kommentare (Status_Key)
    INCLUDE (Kommentar, Kategorie, Erfasst_von, Erfasst_am)
    WHERE Ist_Aktiv = 1;
GO
