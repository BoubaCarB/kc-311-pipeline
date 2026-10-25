"""Write the report to Google Sheets via a service account.

Sheets is the final output on purpose: someone non-technical can open it.
Each run rebuilds the tabs from scratch, so the Sheet always matches the
latest pull and nothing has to be remembered between runs.

Everything goes in a handful of batched requests rather than several per
tab, to stay well inside the Sheets API's per-minute write quota.
"""

import json

import gspread

from pipeline.config import Settings


def _client(settings: Settings) -> gspread.Client:
    # In CI the key arrives as a JSON string in a secret; locally it is a file.
    if settings.service_account_json:
        return gspread.service_account_from_dict(json.loads(settings.service_account_json))
    return gspread.service_account(filename=str(settings.service_account_file))


def _range(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def write_report(settings: Settings, tabs: dict[str, list[list]]) -> str:
    """Replace each tab's contents. Returns the spreadsheet URL."""
    sheet = _client(settings).open_by_key(settings.sheet_id)
    existing = {ws.title: ws for ws in sheet.worksheets()}
    width = {title: max(len(row) for row in rows) for title, rows in tabs.items()}

    for title, rows in tabs.items():
        if title not in existing:
            existing[title] = sheet.add_worksheet(title=title, rows=len(rows), cols=width[title])
    ids = {title: existing[title].id for title in tabs}

    # Size each grid to its table first; a write past the grid's edge fails.
    sheet.batch_update({"requests": [
        {"updateSheetProperties": {
            "properties": {"sheetId": ids[title], "gridProperties": {
                # Sheets refuses to freeze every row, so a header-only tab keeps a spare.
                "rowCount": max(len(rows), 2), "columnCount": width[title], "frozenRowCount": 1}},
            "fields": "gridProperties(rowCount,columnCount,frozenRowCount)",
        }}
        for title, rows in tabs.items()
    ]})
    sheet.values_batch_clear(body={"ranges": [_range(title) for title in tabs]})
    sheet.values_batch_update(body={
        "valueInputOption": "RAW",
        "data": [{"range": f"{_range(title)}!A1", "values": rows} for title, rows in tabs.items()],
    })

    requests = []
    for title in tabs:
        requests.append({"repeatCell": {
            "range": {"sheetId": ids[title], "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }})
        requests.append({"autoResizeDimensions": {"dimensions": {
            "sheetId": ids[title], "dimension": "COLUMNS", "startIndex": 0, "endIndex": width[title]}}})
    sheet.batch_update({"requests": requests})

    # The blank tab every new spreadsheet starts with is not ours to keep.
    # Any tab someone added by hand is left alone, after the report tabs.
    if "Sheet1" in existing and "Sheet1" not in tabs:
        sheet.del_worksheet(existing["Sheet1"])
    order = list(tabs)
    sheet.reorder_worksheets(
        sorted(sheet.worksheets(), key=lambda ws: order.index(ws.title) if ws.title in order else len(order))
    )
    return sheet.url
