import os
import pandas as pd
from datetime import datetime
import re
import requests

# === CONFIGURATION ===
INPUT_DIR = "input_files"
LOG_DIR = "logs"
ALL_ERRORS = []

SLACK_WEBHOOK = "https://hooks.slack.com/services/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"  # <-- your actual webhook

# === SLACK ALERT FUNCTION ===
def send_slack_alert(message):
    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK, json=payload)
        if response.status_code != 200:
            print(f"Slack alert failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Slack error: {e}")

# === LOG ERROR FUNCTION ===
def log_error(file, error):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"{timestamp} | ❌ ERROR in file '{file}': {error}"
    
    print(f"\033[91m{msg}\033[0m")

    # Log to file
    log_file = os.path.join(LOG_DIR, "dq_errors.log")
    with open(log_file, "a") as f:
        f.write(f"{msg}\n")

    # Add to global error summary
    ALL_ERRORS.append(f"📂 File: {file}\n❌ {error}")

# === DATA QUALITY CHECKS ===

def check_missing_columns(df, required_cols):
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        return f"Missing column: {', '.join(missing)}"
    return None

def check_cross_field(df):
    if "Trade_Date" in df.columns and "Settlement_Date" in df.columns:
        try:
            df['Trade_Date'] = pd.to_datetime(df['Trade_Date'], errors='coerce')
            df['Settlement_Date'] = pd.to_datetime(df['Settlement_Date'], errors='coerce')
            invalid = df[df["Trade_Date"] > df["Settlement_Date"]]
            if not invalid.empty:
                return "Cross-field violation: Trade_Date > Settlement_Date"
        except Exception as e:
            return f"Cross-field date parsing failed: {e}"
    return None

def check_enum_violations(df):
    if "Region" in df.columns:
        allowed = {"US", "EMEA", "APAC"}  # tu jo values chahta hai, woh daal
        invalid = df[~df["Region"].isin(allowed)]
        if not invalid.empty:
            return "Invalid enum values in 'Region' column"
    return None

def check_account_id_format(df):
    if "Account_ID" in df.columns:
        # Allow only alphanumeric values
        pattern = r'^[A-Za-z0-9]+$'
        invalid = df[~df["Account_ID"].astype(str).str.match(pattern)]
        if not invalid.empty:
            return "Invalid characters found in 'Account_ID' (only A-Z, a-z, 0-9 allowed)"
    return None

def check_negative_or_zero(df):
    if "Amount" in df.columns:
        invalid = df[df["Amount"] <= 0]
        if not invalid.empty:
            return "'Amount' column has negative or zero values"
    return None 

def check_duplicates(df):
    if df.duplicated().any():
        return "Duplicate rows found in file"
    return None

def check_missing_fields(df):
    missing = df.isnull().sum()
    if missing.any():
        return f"Missing values in fields: {', '.join(missing[missing > 0].index)}"
    return None

def check_invalid_dates(df):
    for col in ["Trade_Date", "Settlement_Date"]:
        if col in df.columns:
            try:
                pd.to_datetime(df[col], errors="raise")
            except Exception:
                return f"Invalid date format in '{col}' column"
    return None

# === RUN ALL CHECKS ===
def run_checks(file_path, file):
    try:
        df = pd.read_csv(file_path, na_values=["", "NA", "N/A"])
    except Exception as e:
        log_error(file, f"Failed to read CSV: {e}")
        return

    errors = []

    # Modify this based on your expected schema
    required_cols = ['Trade_ID','Account_ID','Trade_Date','Settlement_Date','Amount']
    col_error = check_missing_columns(df, required_cols)
    if col_error:
        errors.append(col_error)

    # Run validations
    errors = [
        check_cross_field(df),
        check_enum_violations(df),
        check_account_id_format(df),
        check_negative_or_zero(df),
        check_duplicates(df),
        check_missing_fields(df),
        check_invalid_dates(df)
    ]

    for error in errors:
        if error:
            log_error(file, error)



# === MAIN SCRIPT ===
if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    for file in os.listdir(INPUT_DIR):
        if file.endswith(".csv"):
            path = os.path.join(INPUT_DIR, file)
            print(f"🔍 Checking file: {file}")
            run_checks(path, file)

    print(f"\n🧪 Final ALL_ERRORS content: {ALL_ERRORS}\n")
    if ALL_ERRORS:
        alert_message = "🚨 *Data Quality Issues Detected*\n-----------------------------------\n"
        alert_message += "\n\n".join(ALL_ERRORS)
        alert_message += "\n\n🧾 See logs in dq_errors.log for full trace."
        send_slack_alert(alert_message)
