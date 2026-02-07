import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- Google Sheets Setup ---
SHEET_NAME = "Expo-Sales-Management"
SHEET_TAB = "exhibitors-1"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = "/etc/secrets/service_account.json"

# --- Pitch Deck Mapping ---
PITCHDECK_URLS = {
    "isle of man": "https://b2bgrowthexpo.com/isle-of-man-exhibitor-pitch-deck/",
    "london expo": "https://b2bgrowthexpo.com/london-exhibitor-pitch-deck/",
    "cardiff": "https://b2bgrowthexpo.com/cardiff-exhibitor-pitch-deck/",
    "business innovation": "https://b2bgrowthexpo.com/business-innovation-expo-pack/",
    "bournemouth": "https://b2bgrowthexpo.com/bournemouth-exhibitor-pitch-deck/",
    "corporate wellbeing": "https://b2bgrowthexpo.com/corporate-wellbeing-expo-pitch-deck/",
    "milton keynes": "https://b2bgrowthexpo.com/milton-keynes-exhibitor-pitch-deck/",
    "dubai": "https://b2bgrowthexpo.com/dubai-exhibitor-pitch-deck/",
    "birmingham": "https://b2bgrowthexpo.com/birmingham-exhibitor-pitch-deck/",
    "southampton": "https://b2bgrowthexpo.com/southampton-exhibitor-pitch-deck-2/",
    "portsmouth": "https://b2bgrowthexpo.com/portsmouth-exhibitor-pitch-deck/",
    "basingstoke": "https://b2bgrowthexpo.com/basingstoke-exhibitor-pitch-deck/"
}

# --- Names to Exclude ---
EXCLUDED_NAMES = {"sibi abraham", "sujeet pandit"}

# --- Date Cutoff ---
DATE_CUTOFF = datetime(2025, 8, 20, 23, 59, 59)  # only add leads AFTER this date


def run_script():
    print("🔧 Setting up Google Sheets access...", flush=True)
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open(SHEET_NAME).worksheet(SHEET_TAB)

    # --- Step 1: Get existing emails from sheet ---
    print("📦 Fetching existing emails from sheet...", flush=True)
    header_row = sheet.row_values(1)
    try:
        email_col_index = header_row.index("Email") + 1  # find column dynamically
    except ValueError:
        raise Exception("❌ Could not find 'Email' column in sheet header row")

    existing_emails = set(email.strip().lower() for email in sheet.col_values(email_col_index)[1:])
    print(f"📊 Found {len(existing_emails)} existing emails in sheet.", flush=True)

    # --- Step 2: Fetch data from protected API ---
    print("🌐 Fetching leads from API...", flush=True)
    url = "https://b2bgrowthexpo.com/wp-json/custom-api/v1/protected/exhibitor-media-pack-form-data"
    headers = {
        "Authorization": "Bearer e3e6836eb425245556aebc1e0a9e5bfbb41ee9c81ec5db1bc121debc5907fd85				"
    }

    response = requests.get(url, headers=headers)
    form_data = response.json()
    entries = form_data.get("data", [])
    # --- SAFETY CHECK: validate API response shape ---
    if not isinstance(entries, list):
        print(f"❌ Unexpected API response type for 'data': {type(entries)}")
        print("🔍 Raw API response:", form_data)
        return


    print(f"📥 Received {len(entries)} entries from API.", flush=True)

    # --- Collect new leads ---
    new_leads = []

    for item in entries:
        if not isinstance(item, dict):
            print(f"⚠️ Skipping invalid item (not dict): {item}")
            continue
            
        form_entry = item.get("form_value", {})
        if not isinstance(form_entry, dict):
            print(f"⚠️ Invalid form_value for item: {item}")
            continue

        # --- Email Handling ---
        email = form_entry.get("your-email", "").strip().lower()
        if not email:
            print(f"⚠️ Skipping entry (no email): {form_entry}")
            continue

        if email in existing_emails:
            print(f"⏭️ Skipping duplicate email: {email}")
            continue

        # --- Parse form date ---
        form_date_raw = item.get("form_date", "")
        form_date = ""
        if form_date_raw:
            try:
                parsed_form_date = datetime.strptime(form_date_raw, "%Y-%m-%d %H:%M:%S")
                if parsed_form_date <= DATE_CUTOFF:
                    print(f"⏭️ Skipping old lead ({form_date_raw}) for {email}")
                    continue
                form_date = parsed_form_date.strftime("%d/%m/%Y")
            except Exception as e:
                print(f"⚠️ Failed to parse date '{form_date_raw}' for {email}: {e}")
                continue

        # --- Name Handling ---
        full_name = form_entry.get("your-name", "").strip()
        first_name, last_name = "", ""
        if full_name:
            parts = full_name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            # Check excluded names
            if full_name.lower() in EXCLUDED_NAMES:
                print(f"⏭️ Skipping excluded lead: {full_name}")
                continue

        # --- Expo Name ---
        expo_name = item.get("expo_label", "").strip()

        # --- Pitch Deck URL ---
        pitchdeck_url = ""
        expo_lower = expo_name.lower()
        for key, url_val in PITCHDECK_URLS.items():
            if key in expo_lower:
                pitchdeck_url = url_val
                break
        if not pitchdeck_url:
            print(f"⚠️ No pitchdeck found for Expo: {expo_name}")

        # --- Prepare row ---
        row = [
            form_date,                           # Lead Date
            "B2B Website",                       # Lead Source
            first_name,                          # First Name
            last_name,                           # Last Name
            form_entry.get("your-company", ""),  # Company Name
            form_entry.get("phone-number", ""),  # Mobile
            form_entry.get("your-email", ""),    # Email
            expo_name,                           # Show
            "",                                  # Next Followup
            "",                                  #Email Count
            "",                                  # Call Attempt
            "",                                  # Linkedin Msg Count
            "",                                  # WhatsApp msg count
            "",                                  # Comments
            pitchdeck_url,                       # Pitch Deck URL
            "Exhibitors_opportunity",            # Interested for
            "",                                  # Follow-Up Count
            "",                                  # Last Follow-Up Date
            ""                                   # Reply Status
        ]

        new_leads.append(row)
        existing_emails.add(email)

    print(f"🧾 Found {len(new_leads)} new unique leads to insert.", flush=True)

    # --- Step 3: Batch Insert into Google Sheet ---
    if new_leads:
        # Insert all new leads at once, newest on top
        sheet.insert_rows(new_leads[::-1], row=2, value_input_option="USER_ENTERED")
        print(f"✅ Inserted {len(new_leads)} leads in one batch at row 2.", flush=True)

        # Optional: format inserted rows white
        end_row = 1 + len(new_leads)
        cell_range = f"A2:Z{end_row}"
        sheet.format(cell_range, {"backgroundColor": {"red": 1, "green": 1, "blue": 1}})
    else:
        print("🔁 No new leads to add.", flush=True)


# --- Repeat every 2 hours ---
while True:
    try:
        print("\n🔄 Starting new sync run...", flush=True)
        run_script()
    except Exception as e:
        print(f"❌ Error during execution: {e}", flush=True)

    print("⏸ Sleeping for 2 hours (7200 seconds)...", flush=True)
    time.sleep(7200)
