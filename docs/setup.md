# Setup

## Prerequisites

- A Power Platform environment with Dataverse (needed to import solutions).
- An account to own the flows and connections. A dedicated service account
  is best, so the flows don't break when a person leaves. All three
  connectors (Excel Online (Business), Office 365 Outlook, Microsoft Forms)
  are standard, so no premium licence is needed.
- A shared mailbox to send from (for example `asset-survey@contoso.com`). The
  flow account needs **Send As** on it. Owners' replies go there.
- The flow account needs edit access to the inventory workbook and must own
  (or co-own) the form.

## 1. Build the form

1. Create the survey in Microsoft Forms. Under **Settings**, choose
   **Only people in my organization can respond** and **Record name**, so
   responses include the responder's email (this fills `ResponseEmail`).
2. Make the **first question** a required short-text question titled
   `AppID`, with a subtitle such as "Filled in for you. Please don't change it."
3. Add your own questions after it. Typical ones: *Are you the business owner
   of this application?* / *If not, who is?* / *Is the application still in
   use?* / *Does the listed criticality look right?* / *What data does it
   hold?*
4. Note two values:
   - **Form ID**: open the form for editing; it's the `id=` value in the
     browser URL (a long string ending in characters like `...UN0QzE5Ui4u`).
   - **AppID question ID**: choose **... > Get pre-filled URL**, type
     `TEST` into the AppID question, and click **Get prefilled link**. The
     link contains `&r<hex>=TEST`; the `r<hex>` part is the question ID.
     The part before `&r...` is the base link.

## 2. Prepare the workbook

1. Copy `templates/inventory-template.xlsx` into a SharePoint document
   library (or the flow account's OneDrive).
2. Delete the example row, or leave it; it's `Excluded`, so the flows ignore it.
3. On the **Config** sheet, paste the base link into `FormBaseUrl` and the
   question ID into `AppIdQuestionId`.
4. Paste your inventory into the **Inventory** table, keeping the column
   headers exactly as they are. Set `Status = Pending` on rows to send.

If you use your own workbook, it must have a **table** (Insert > Table)
with the headers listed in the [README](../README.md#inventory-columns).
Column order doesn't matter.

## 3. Build the FormsUrl for each row

Each `FormsUrl` is the base link plus the AppID question pre-filled:

```
https://forms.office.com/Pages/ResponsePage.aspx?id=<FormID>&r<QuestionID>=<AppID>
```

The template's example row has the formula
`=Config!$B$2&"&"&Config!$B$3&"="&A2`. Fill it down the column. If AppIDs
contain spaces, `&`, `#` or other characters that aren't URL-safe, wrap the
AppID in `ENCODEURL()` in the desktop Excel app (Excel for the web doesn't
support that function).

Open one or two links to check the AppID shows up already filled in.

## 4. Import the solution

1. Run `scripts/pack.sh` to produce `dist/DigitalAssetSurvey_1_0_0_0.zip`
   (or take it from a release).
2. In [make.powerautomate.com](https://make.powerautomate.com), pick the
   environment, then **Solutions > Import solution** and choose the zip.
3. On the **Connections** step, create or choose a connection for each
   reference, signed in as the flow account:
   - DAS Excel Online (Business)
   - DAS Office 365 Outlook
   - DAS Microsoft Forms
4. On the **Environment variables** step, enter the values below. You can
   change them later in the solution under **Environment variables**.

| Variable | Value |
| --- | --- |
| Inventory Source | See [below](#finding-the-excel-location-values). |
| Inventory Drive | See below. |
| Inventory File | See below. |
| Inventory Table | `Inventory` (default), or your table's name. |
| Sender Mailbox | The shared mailbox address. |
| Admin Email | Who gets summaries, escalations and errors. |
| Reminder Interval Days | Days between the survey and each reminder. Default `7`. |
| Max Reminders | Reminders before escalation. Default `3`. |
| Reminder Campaign Filter | `*` for all campaigns, or one CampaignID. |
| Form Id | From step 1. |
| Form AppID Question Id | From step 1 (starts with `r`). |

### Finding the Excel location values

The Excel connector identifies the workbook with three IDs that the designer
normally hides behind dropdowns. To get them:

1. Create a throwaway cloud flow with a manual trigger and one **Excel Online
   (Business) > List rows present in a table** action.
2. Pick the location, document library, file and table from the dropdowns.
3. Open the action's **... > Peek code** (or code view) and copy the values of
   `source`, `drive` and `file` exactly as shown into the three variables.
4. Delete the throwaway flow.

## 5. Turn on and test

Imported flows start **off**. In the solution, turn them on in this order:
DAS 3, then DAS 2, then DAS 1.

Test with a campaign that only contains you:

1. Add a row with `CampaignID = TEST`, your own email as `OwnerEmail`, a
   unique `AppID`, its `FormsUrl`, and `Status = Pending`.
2. Run **DAS 1 - Send Surveys** and enter `TEST`. Check: you get the survey
   email and the admin summary, and the row is `Sent` with a `SentDate`.
3. To test reminders without waiting a week, set the row's `SentDate` to a
   date older than the interval (for example `2020-01-01T00:00:00Z`), then
   open DAS 2 and choose **Run** (or **Test > Manually**). Check: a reminder
   arrives and `ReminderCount = 1`. Repeat with `LastReminder` backdated
   until the row becomes `Escalated` and the admin gets the escalation report.
4. Submit the form from the link. Within a minute or two DAS 3 should set the
   row to `Completed` with your response details.

## Running a campaign

1. Add the rows with a new `CampaignID` and `Status = Pending`.
2. Run DAS 1 with that CampaignID. Rows that fail go to `Error` and appear in
   the summary email; fix them, set them back to `Pending`, and run again.
   Only `Pending` rows are sent, so re-running is safe.
3. DAS 2 and DAS 3 run on their own from then on.
4. To re-survey an application, set its row back to `Pending`. DAS 1 resets
   the reminder fields when it sends.

## Changing things

- **Reminder schedule or time zone**: edit the Recurrence trigger in DAS 2.
  It's weekdays at 13:00 UTC by default.
- **Email wording**: edit the email actions in DAS 1 (`Send_survey_email`)
  and DAS 2 (`Send_reminder_email`).
- **More than one form**: DAS 3 listens to one form. For a second form, use
  **Save As** on DAS 3 and point the copy at the other form ID and question
  ID. AppID must still be unique across the table.

## Things to know

- **Edit the workbook in the browser.** If someone has it open in the desktop
  Excel app, the connector can get "file locked" errors. DAS 1 and DAS 2
  record these in `LastError`; DAS 2 retries the next day. For DAS 3, the
  admin gets an email, and you can resubmit the failed run from the flow's
  run history.
- **Updates match on AppID.** If two rows share an AppID, the connector
  updates only one of them, so keep AppIDs unique.
- **The AppID on the form is editable.** A respondent could change it. DAS 3
  emails the admin if the AppID doesn't match a row, and flags it in
  `LastError` when the responder isn't the listed owner.
- **Large tables**: the flows read up to 5,000 rows per run. Raise the
  pagination limit on the List rows actions for more.
- **Send limits**: Office 365 Outlook allows a limited number of emails per
  connection per day (thousands, depending on licence). Split very large
  campaigns over several days.
