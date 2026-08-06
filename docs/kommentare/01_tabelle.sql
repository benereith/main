/*
    Flash-Bericht: Kommentartabelle
    -------------------------------
    Anzulegen in einer Fabric-SQL-Datenbank (Fabric SQL Database, nicht Warehouse -
    Translytical Task Flows schreiben über eine User Data Function in eine SQL-Datenbank).

    Der Bericht liest die Tabelle per DirectQuery (Tabelle "Kommentare" im semantischen Modell),
    damit ein neu erfasster Kommentar ohne Modell-Refresh sofort sichtbar ist.
*/

CREATE TABLE dbo.Flash_Kommentare
(
    Kommentar_ID  BIGINT IDENTITY(1,1) NOT NULL,
    Werk          INT           NOT NULL,
    Fiscal_Year   INT           NOT NULL,
    Periode       TINYINT       NOT NULL,
    Kommentar     NVARCHAR(2000) NOT NULL,
    Kategorie     NVARCHAR(50)  NOT NULL CONSTRAINT DF_Flash_Kommentare_Kategorie DEFAULT ('Sonstiges'),
    Erfasst_von   NVARCHAR(200) NOT NULL,
    Erfasst_am    DATETIME2(0)  NOT NULL CONSTRAINT DF_Flash_Kommentare_Erfasst_am DEFAULT (SYSUTCDATETIME()),
    Ist_Aktiv     BIT           NOT NULL CONSTRAINT DF_Flash_Kommentare_Ist_Aktiv  DEFAULT (1),

    -- Schlüssel wie in Unit_Status und V_SAP_EXPORTS_cleansed: Werk|Geschäftsjahr|Periode
    Status_Key AS CONCAT(CAST(Werk AS VARCHAR(10)), '|', CAST(Fiscal_Year AS VARCHAR(4)), '|', CAST(Periode AS VARCHAR(2))) PERSISTED,

    -- Erster Kalendertag der Periode; gleiche Regel wie fnPeriodeStart im Modell
    -- (Periode 1-3 = Okt-Dez des Geschäftsjahres, Periode 4-12 = Jan-Sep des Folgejahres)
    Datum AS DATEFROMPARTS(
                 CASE WHEN Periode <= 3 THEN Fiscal_Year ELSE Fiscal_Year + 1 END,
                 CASE WHEN Periode <= 3 THEN Periode + 9  ELSE Periode - 3     END,
                 1) PERSISTED,

    CONSTRAINT PK_Flash_Kommentare PRIMARY KEY CLUSTERED (Kommentar_ID),
    CONSTRAINT CK_Flash_Kommentare_Periode CHECK (Periode BETWEEN 1 AND 12)
);
GO

-- Der Bericht filtert praktisch immer auf Werk + Periode.
CREATE NONCLUSTERED INDEX IX_Flash_Kommentare_Werk_Periode
    ON dbo.Flash_Kommentare (Werk, Fiscal_Year, Periode)
    INCLUDE (Kommentar, Kategorie, Erfasst_von, Erfasst_am)
    WHERE Ist_Aktiv = 1;
GO
