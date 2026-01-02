import os
import json
import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
client = gspread.authorize(creds)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    credentials = Credentials.from_service_account_info(
        creds_json,
        scopes=SCOPES
    )
    return gspread.authorize(credentials)

client = get_gspread_client()


def get_sheet_values(sheet_name, worksheet_only=False):
    sh = client.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(sheet_name)

    if worksheet_only:
        return worksheet

    return worksheet.get_all_values()
