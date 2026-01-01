import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=SCOPES
)

client = gspread.authorize(creds)

def get_sheet_values(sheet_name):
    sheet = client.open(sheet_name).sheet1
    return sheet.get_all_values()

