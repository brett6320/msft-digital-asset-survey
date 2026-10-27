# msft-digital-asset-survey

Power Automate flows that survey the owners of digital assets (applications),
based on an Excel inventory, using Microsoft Forms for the survey.

| Flow | Trigger | What it does |
| --- | --- | --- |
| **DAS 1 - Send Surveys** | Manual (enter a CampaignID, or `*` for all) | Emails the survey link to the owner of every `Pending` row, sets `Status = Sent` and `SentDate`. Emails the admin a summary. |
| **DAS 2 - Send Reminders** | Weekdays 13:00 UTC | For `Sent` rows with no response after the reminder interval, sends a reminder and bumps `ReminderCount` / `LastReminder`. After the maximum reminders, sets `Status = Escalated`. Emails the admin only when something was escalated or failed. |
| **DAS 3 - Process Responses** | Each new Microsoft Forms response | Reads the AppID from the response, finds that row, and sets `Status = Completed`, `ResponseID`, `ResponseEmail`, `CompletedDate`. Emails the admin if the response can't be matched or recorded. |

All three ship in one unmanaged Dataverse solution (`DigitalAssetSurvey`) with
connection references and environment variables, so nothing is hard-coded to
one tenant.

## How it works

```
Inventory (Excel table)          Owner                    Microsoft Forms
        |                          |                            |
  DAS 1 |-- survey email --------->|                            |
        |   Status = Sent          |-- opens pre-filled link -->|
  DAS 2 |-- reminder (every N d) ->|                            |
        |   ReminderCount += 1     |-- submits ---------------->|
        |   ...max reached:        |                            |
        |   Status = Escalated     |                            |
  DAS 3 |<-------------- AppID from response -------------------|
        |   Status = Completed
```

Each row's `FormsUrl` is a **pre-filled** Forms link that sets an AppID
question, so DAS 3 knows which application a response belongs to. One form
serves every application in a campaign.

### Status lifecycle

| Status | Set by | Meaning |
| --- | --- | --- |
| `Pending` | You | Ready to send. DAS 1 picks these up. |
| `Sent` | DAS 1 | Survey sent, awaiting response. DAS 2 reminds these. |
| `Escalated` | DAS 2 | Max reminders sent with no response. No more reminders; follow up directly. A late response is still recorded. |
| `Completed` | DAS 3 | Response received. |
| `Error` | DAS 1 | Couldn't send (blank OwnerEmail/FormsUrl, or email failed). See `LastError`; fix and set back to `Pending`. |
| `Excluded` | You | Ignored by every flow. |

`LastError` is overwritten on each successful action, so it only ever shows the
latest problem. DAS 3 also uses it for warnings that don't block completion:
the responder isn't the listed `OwnerEmail` (for example, a delegate), or a
second response superseded an earlier one.

## Inventory columns

The workbook must contain an Excel **table** (default name `Inventory`) with
these exact column headers. `templates/inventory-template.xlsx` has the table
ready, with dropdowns for `Status` and `Criticality`.

| Column | Filled by | Notes |
| --- | --- | --- |
| `AppID` | You | **Unique key.** Every update matches on this, so it must be unique across the whole table, not just per campaign. |
| `CampaignID` | You | Groups rows into a send. |
| `AppCatID` | You | Internal application catalogue ID. Shown in emails. |
| `ApplicationName` | You | Friendly name from the IdP. Shown in emails. |
| `Criticality` | You | Business criticality, `L1`–`L5`. Shown in emails and escalation reports. |
| `OwnerName` | You | Used in the greeting. |
| `OwnerEmail` | You | Survey recipient. |
| `Status` | You / flows | See lifecycle above. |
| `FormsUrl` | You | Pre-filled link for this row (see [setup](docs/setup.md#3-build-the-formsurl-for-each-row)). |
| `SentDate` | DAS 1 | UTC, ISO 8601 (`2026-10-27T13:00:00Z`). |
| `LastReminder` | DAS 2 | UTC, ISO 8601. |
| `ReminderCount` | DAS 1 / DAS 2 | Reset to 0 when a survey is (re)sent. |
| `ResponseID` | DAS 3 | Forms response number. |
| `ResponseEmail` | DAS 3 | Who submitted (needs the form restricted to your org). |
| `CompletedDate` | DAS 3 | UTC, ISO 8601, when the response was processed. |
| `LastError` | Flows | Latest error or warning, prefixed with a timestamp and the flow step. |

Dates are written as ISO 8601 text, not Excel dates, so they read back
unchanged. The template formats those columns as text.

## Setup

See **[docs/setup.md](docs/setup.md)**: build the form, prepare the
workbook, import the solution, set the environment variables, and test.

## Repository layout

```
solution/src/                 Unpacked solution (edit these)
  Workflows/*.json            Flow definitions
  environmentvariabledefinitions/
  customizations.xml          Workflow + connection reference registrations
  solution.xml                Manifest
templates/inventory-template.xlsx
scripts/validate.py           Static checks on the flow JSON and manifest
scripts/pack.sh               Validate, then zip to dist/DigitalAssetSurvey_<version>.zip
scripts/make_template.py      Regenerates the Excel template (needs openpyxl)
```

To build the importable zip: `scripts/pack.sh`.

If you change a flow in the Power Automate designer, export the solution
(unmanaged) and copy the changed files back into `solution/src` so the repo
stays the source of truth. `pac solution unpack` produces the same layout.
