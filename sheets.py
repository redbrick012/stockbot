import os
import json
import gspread
from google.oauth2.service_account import Credentials

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


def get_sheet_values(spreadsheet_id, worksheet_name=None):
    if worksheet_name:
        sheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    else:
        sheet = client.open_by_key(spreadsheet_id).sheet1

    return sheet.get_all_values()
