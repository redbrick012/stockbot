import os
import json
import gspread
from google.oauth2.service_account import Credentials

# =====================
# ENV
# =====================
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SERVICE_ACCOUNT_INFO = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

# =====================
# AUTH
# =====================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]

creds = Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO,
    scopes=SCOPES
)

client = gspread.authorize(creds)

# =====================
# API
# =====================
def get_sheet_values(sheet_name, worksheet_only=False):
    sh = client.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(sheet_name)

    if worksheet_only:
        return worksheet

    return worksheet.get_all_values()
