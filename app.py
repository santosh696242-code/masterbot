import telebot
import gspread
import requests
import json
import base64
from bs4 import BeautifulSoup
from datetime import datetime
import os
import threading
from groq import Groq
import time
from urllib.parse import urlparse, urljoin
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask

# --- SETUP CONFIGURATION ---
MASTER_BOT_TOKEN = "8688021018:AAG6svktpklBybWqM-9qQITCUAJvVuALIOo"

# Environment se multiple GROQ keys fetch karna
GROQ_API_KEYS = []
for key_name in ["GROQ_API_KEYS"] + [f"GROQ_API_KEYS{i}" for i in range(1, 20)]:
    val = os.environ.get(key_name)
    if val and val.strip():
        GROQ_API_KEYS.append(val.strip())

# Agar environment variables me kuch nahi mila to default fallback use karein
if not GROQ_API_KEYS:
    GROQ_API_KEYS = ["hdfh"]

current_key_index = 0
ai_client = Groq(api_key=GROQ_API_KEYS[current_key_index].strip())
master_bot = telebot.TeleBot(MASTER_BOT_TOKEN)
admin_states = {}

# Contact Details
DEVELOPER_TELEGRAM = "@Developer_yadav"
ADMIN_PHONE = "7858979517"
ADMIN_EMAIL_1 = "maksudanyadav814@gmail.com"
ADMIN_EMAIL_2 = "sk747460950@gmail.com"

# Active bots ka context, status aur tokens track karne ke liye dict
bot_contexts = {} 
bot_statuses = {}
bot_tokens_cache = {} # Username -> Token mapping ke liye fast cache

# --- DATABASE SETUP (DRIVE + BASE64 BACKUP) ---
sheet = None 
try:
    print("Master Bot: Database se connect karne ki koshish kar raha hoon...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = None
    
    # METHOD 1: Google Drive se download karein
    try:
        print("Master Bot: Downloading fresh credentials from Google Drive...")
        drive_url = "https://drive.google.com/uc?export=download&id=1tsPWNQOD0S90Szv3vbB-v76dgrLzSXhO"
        response = requests.get(drive_url, timeout=10)
        if response.status_code == 200 and "private_key" in response.text:
            creds_dict = response.json()
            print("Master Bot: Credentials downloaded from Google Drive successfully!")
    except Exception as download_error:
        print(f"Master Bot: Google Drive download failed ({download_error}). Moving to secure backup...")
        
    # METHOD 2: Secure Base64 fallback agar Drive fail ho jaye
    if not creds_dict:
        print("Master Bot: Loading secure base64-encoded backup credentials...")
        b64_creds = (
            "eyJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsICJwcm9qZWN0X2lkIjogInJpdmVyLXN1"
            "bmxpZ2h0LTQwOTgwOSIsICJwcml2YXRlX2tleV9pZCI6ICI2M2JhNjVmNjA5MWI4Mjcx"
            "ZDI1NTgyNGNkNzkxNmUyN2QyMWM3MDAiLCAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJ"
            "TiBQUklWQVRFIEtFWS0tLS0tXG5NSUlFdmdBR0FEQU5CZ2txaGtpRzl3MEJBUUVGQUFT"
            "Q0JLZ2dnU2tBZ0VBQW9JQkFRRGZNRFArd2xXdzkvemFcbkJ0c213VlZ0VDZYQ2FNM1dl"
            "V0p2Rk5NMGFRSlVkdWVkOWJ4K2hKSHh2Uzh0WkhZTDNaallyb0diU3ZWN0MrblxuU3dl"
            "dk9aVWhVc3BWOTJMMkF6b252WXgxd0tOMmdBZ0JuYXlhUGVuYnA3L01XWnJVMmkscUJn"
            "NnZWZU53dDQwXG5jbTJScWw3alovWVpEMmFqQlBnQUZvUjU1eEREcXV1N2F1T2R6ZmRH"
            "TURZTHVVWERwUzIvY3dxVjU4SjBOblx1S0hjeERXRnBkMEF5dzV1U1JmVUo3MVdKbGYw"
            "bFNScEF5Sk1LYzhSWTQyeVgzUEN6TW5EMU5LRkdaalEyezBcbjB3Vit0RGxULytaa0xZ"
            "dVg4REtZL1dReGVkclVFcTh4K2tha2o0V1lMR3VqR2JDeUVhdE1BQ1ZjYTc1Tkg4MTFc"
            "bnVGVXdaYjN2QWdNQkFBRUNnZ0VBRURPcUdwelU1cVpoOHl3MVRYRmVzUXkrbnJuSC9G"
            "VlRYWUlEUDV3ZmxTXG5rcUxsZGlSdXJrbzVtdmRkVW9IRGlOeHlYNlFPTWhYV3NjREhn"
            "b2ZHRlNpeTZvR3VhK2gxRU1oNFNWR0Y1L05NXG5OZ2J5RitwNXkreENTUE8zbVZ1eHR2"
            "SHc3RmF4WStlWkJOcW5ySkxmRjRnRScrL2dPYmRnZlNSeFoxaTg5SDFVcFxuSk1SY3hH"
            "ZlNGaWExMU92NUpnb2t2VVVML1FKS0tvTk5SWFpsUjFDTlJSbGJsT2RhR2NVZ1loY1pQ"
            "RjJNMUphZlxuUGI2R1ZUSndwcHVnd3hKL0RNRzFkbTBFUnZ1bW9aZXNnOUpuOUYzYnlE"
            "TTZFRHByOUQrRUZXNXErRHNHVktcb nVxL0dQUGVMTnRRckNkd2FJbG04Nzc2bUZsUE9G"
            "ZWdLd21iTHBMQlROUUtCZ1REMEJRMm5ISzgyNW5HbzBlTjhcbnlVKzhKajJzcVQzYlJk"
            "bDgyeHB3OUVEZDN2NnptcjZTVWVUSkxKU3N4MGJnUUVTT3hSVmxSSksyZmxRSnNSNmFc"
            "bmZtTnVudmdwaE82SGNnTDRoMVowM0JsVDZDRUcxREFNeEJ3d0lXRG4rTVY2VmNBT2pu"
            "SndCbU1ZcVlzcmNHVEJcbkVSZE9BbjJhY3BwUmhoM0piQXJNZGt5U3dLQmdRRFB3YlNE"
            "cEVOSlB4dlR2Qk9SdWZZN1JDS1pOYkdjZHhcbjgyMWx5R0Y1VUdQTGxXS2dsbDNKdTVl"
            "NmhLa2J6b1JNOFBoTzFMalE1eGl5ZkxDd3hxSHBYUld3RTBiLGR4empcbjRVU0Q5dlE4"
            "ajE1V1pGYnBoZ2lxVUxVYWhSaFcvZFpvMDVSMnkyNzdvZFNWSmx3aUYzc2g1eEJDUlpj"
            "Sk4yWVxueXl4cGshOGJRS0JnUlowejExK3hSNzJoOG9BSjZraw9FenVXbHZ2S0Vyd3Jz"
            "dm9EY1ppV0pkMVF2b3VGUEx3VDlhZjRCdE8xUW1TWkVvSDJSc2NLWnZOTVpaMUpnL2Fc"
            "bFBMZnkzMEJoeXBvM0pQcG1ZYjFoTk4xNXFQZmQ1OWJOV1BML0ZOMnloa2xjRndoOUd0"
            "STZJbEQ3WTFpUWRORkFpYmJmQUM2bDlJUjVDV1h3WDlJUzIwMlxuLS0tLS1FTkQgUFJJ"
            "VkFURSBLRVktLS0tLVxuIiwgImNsaWVudF9lbWFpbCI6ICJ0ZWxlYm90QHJpdmVyLXN1"
            "bmxpZ2h0LTQwOTgwOS5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsICJjbGllbnRfaWQi"
            "OiAiMTEzMDAxODIyNjEyMzg1MjIyNzM0IiwgImF1dGhfdXJpIjogImh0dHBzOi8vYWNj"
            "b3VudHMuZ29vZ2xlLmNvbS9vL29hdXRoMi9hdXRoIiwgInRva2VuX3VyaSI6ICJodHRw"
            "czovL29hdXRoMi5nb29nbGVhcGlzLmNvbS90b2tlbiIsICJhdXRoX3Byb3ZpZGVyX3g1"
            "MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93dy5nb29nbGVhcGlzLmNvbS9vYXV0aDIvdjEv"
            "Y2VydHIsICJjbGllbnRfeDUwOV9jZXJ0X3VybCI6ICJodHRwczovL3d3dy5nb29nbGVh"
            "cGlzLmNvbS9yb2JvdC92MS9tZXRhZGF0YS94NTA5L3RlbGVib3QlNDByaXZlci1zdW5s"
            "aWdodC00MDk4MDkuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLCAidW5pdmVyc2VfZG9t"
            "YWluIjogImdvb2dsZWFwaXMuY29tIn0="
        )
        decoded_data = base64.b64decode(b64_creds).decode('utf-8')
        creds_dict = json.loads(decoded_data)
        print("Master Bot: Secure backup credentials parsed successfully!")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    SHEET_URL = "https://docs.google.com/spreadsheets/d/16DfTvs0PIADBqELyImh4FsDH7F00r39FYuQEdlLGP0s/edit?usp=sharing"
    sheet = client.open_by_url(SHEET_URL).get_worksheet(0) 
    print("Master Bot: Database connected successfully.")
except Exception as e:
    print(f"Master Bot Connection Error: {e}")

# --- HELPER FUNCTIONS ---
def rotate_api_key():
    global current_key_index, ai_client
    current_key_index = (current_key_index + 1) % len(GROQ_API_KEYS)
    new_key = GROQ_API_KEYS[current_key_index].strip()
    ai_client = Groq(api_key=new_key)
    print(f"API Key limit reached! Switched to Key Index {current_key_index}")

def parse_status(status_str):
    status_str = str(status_str).strip().lower()
    
    plan_name = "Trial"
    max_bots = 1
    max_chars = 15000
    is_trial = True

    if "premium" in status_str or "platinum" in status_str or "unlimited" in status_str:
        plan_name = "Premium"
        max_bots = 999  # Unlimited
        max_chars = 50000
        is_trial = False
    elif "standard" in status_str:
        plan_name = "Standard"
        max_bots = 3
        max_chars = 30000
        is_trial = False
        
    if status_str.startswith("custom-") or "custom" in status_str:
        try:
            parts = status_str.replace("_", "-").replace(" ", "-").split("-")
            numbers = [int(p) for p in parts if p.isdigit()]
            if len(numbers) >= 2:
                plan_name = f"Custom Limit ({numbers[0]} Bots)"
                max_bots = numbers[0]
                max_chars = numbers[1]
                is_trial = False
            elif len(numbers) == 1:
                plan_name = f"Custom Limit ({numbers[0]} Bots)"
                max_bots = numbers[0]
                max_chars = 30000
                is_trial = False
        except Exception as e:
            print(f"Error parsing custom status: {e}")
            
    return plan_name, max_bots, max_chars, is_trial

def get_user_limits(chat_id):
    global sheet
    plan_name = "Trial"
    max_bots = 1
    max_chars = 15000
    is_trial = True
    user_bots_count = 0
    
    if sheet is None:
        return plan_name, max_bots, max_chars, is_trial, 0
        
    try:
        records = sheet.get_all_records()
        user_rows = [row for row in records if str(row.get('Admin_ID', '')).strip() == str(chat_id)]
        
        # Unique tokens count karein, taaki chunking (doosri row) ek extra bot count na ho
        unique_tokens = set(str(r.get('Bot_Token', '')).strip() for r in user_rows if str(r.get('Bot_Token', '')).strip())
        user_bots_count = len(unique_tokens)
        
        for row in user_rows:
            status = str(row.get('Status', 'Trial')).strip()
            p_name, m_bots, m_chars, t_trial = parse_status(status)
            
            if m_bots > max_bots:
                max_bots = m_bots
            if m_chars > max_chars:
                max_chars = m_chars
            if not t_trial:
                is_trial = False
                plan_name = p_name
    except Exception as e:
        print("Error fetching user limits from DB:", e)
        
    return plan_name, max_bots, max_chars, is_trial, user_bots_count

def activate_token_in_db(chat_id, token):
    """
    FIXED Token REPLACE logic: 
    owner.py ke banaye gaye empty row me se data replace karega 
    aur sheet errors (shifting) ko bachane ke liye DELETE ka istemal nahi hoga.
    Sirf us empty row ka data CLEAR kiya jayega taaki wo dobara use ho sake.
    """
    global sheet
    if sheet is None:
        return None, "System Database connected nahi hai."
    try:
        records = sheet.get_all_records()
        headers = sheet.row_values(1)
        
        # Dynamic Columns Find Karna
        status_col = headers.index('Status') + 1 if 'Status' in headers else 6
        plan_token_col = headers.index('PlanToken') + 1 if 'PlanToken' in headers else 7
        temp_col = headers.index('Temp') + 1 if 'Temp' in headers else 11
        admin_id_col = headers.index('Admin_ID') + 1 if 'Admin_ID' in headers else 1

        token_row_idx = -1
        row_status = "Standard"
        assigned_admin_id = ""

        # 1. Wo token find karein jo owner.py ne generate kiya hai (Khali Bot_Token ke sath)
        for i, row in enumerate(records):
            if str(row.get('PlanToken', '')).strip() == token and not str(row.get('Bot_Token', '')).strip():
                token_row_idx = i + 2 # +2 due to header and 0-index
                row_status = str(row.get('Temp', 'Trial')).strip()
                assigned_admin_id = str(row.get('Admin_ID', '')).strip()
                if not row_status:
                    row_status = "Standard"
                break

        if token_row_idx == -1:
            for row in records:
                if str(row.get('PlanToken', '')).strip() == token and str(row.get('Admin_ID', '')).strip() == str(chat_id):
                    return None, "Ye plan aapne pehle hi activate kar liya hai!"
            return None, "Token valid nahi mila ya pehle kisi aur dwara use kiya ja chuka hai."

        if assigned_admin_id and assigned_admin_id != str(chat_id):
            return None, "Ye token specific user (Kisi aur Admin ID) ke liye generate kiya gaya hai!"

        # 2. Find karein ki is user ki pehle se "Active Bots" wali rows hain ya nahi
        admin_rows_indices = []
        for i, row in enumerate(records):
            if str(row.get('Admin_ID', '')).strip() == str(chat_id) and str(row.get('Bot_Token', '')).strip():
                admin_rows_indices.append(i + 2)

        if admin_rows_indices:
            # USER EXISTS: User ke sabhi purane rows mein Naya Status Replace Karein
            for row_idx in admin_rows_indices:
                sheet.update_cell(row_idx, status_col, row_status)
                time.sleep(0.5) # Rate Limit Error Bypass
                sheet.update_cell(row_idx, plan_token_col, token) 
                time.sleep(0.5)
            
            # IMPORTANT: Purana plan replace hote hi owner.py wali Khali Row CLEAR hogi, DELETE nahi! (No Shifting Error)
            sheet.update_cell(token_row_idx, admin_id_col, "")
            time.sleep(0.5)
            sheet.update_cell(token_row_idx, plan_token_col, "")
            time.sleep(0.5)
            sheet.update_cell(token_row_idx, temp_col, "")
            time.sleep(0.5)
            sheet.update_cell(token_row_idx, status_col, "")
            time.sleep(0.5)
        else:
            # NEW USER: Inke paas abhi bot nahi hai, toh yehi row unki basic ID ban jayegi
            sheet.update_cell(token_row_idx, admin_id_col, str(chat_id))
            time.sleep(0.5)
            sheet.update_cell(token_row_idx, status_col, row_status)
            time.sleep(0.5)
            # Khali row ki 'Temp' column empty (clear) kar dena chahiye
            sheet.update_cell(token_row_idx, temp_col, "") 
            time.sleep(0.5)
                
        plan_name, max_bots, max_chars, is_trial = parse_status(row_status)
        return {
            'plan_name': plan_name,
            'max_bots': max_bots,
            'max_chars': max_chars,
            'status': row_status,
        }, None
    except Exception as e:
        print("Token activation error:", e)
        return None, f"Database update fail ho gaya: API Error (Too Many Requests). Kripya thodi der baad try karein."

def extract_text_from_url(base_url, max_pages=5, max_chars=15000):
    try:
        visited = set()
        urls_to_visit = [base_url]
        domain = urlparse(base_url).netloc
        all_text = ""

        while urls_to_visit and len(visited) < max_pages:
            current_url = urls_to_visit.pop(0)
            if current_url in visited:
                continue
            
            visited.add(current_url)
            try:
                response = requests.get(current_url, timeout=5)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                paragraphs = soup.find_all('p')
                page_text = ' '.join([p.get_text() for p in paragraphs])
                all_text += f" {page_text}"

                for link in soup.find_all('a', href=True):
                    next_url = urljoin(base_url, link['href'])
                    if urlparse(next_url).netloc == domain and next_url not in visited:
                        urls_to_visit.append(next_url)

            except Exception as e:
                print(f"Skipping url {current_url}: {e}")
                
        return all_text[:max_chars] 
    except Exception as e:
        print("Scraping Error:", e)
        return None

def check_trial_status(join_date_str):
    try:
        join_date = datetime.strptime(join_date_str, "%Y-%m-%d")
        current_date = datetime.now()
        days_used = (current_date - join_date).days
        if days_used <= 7:
            return True, 7 - days_used
        else:
            return False, 0
    except:
        return False, 0

def save_to_sheet(admin_id, bot_token, username, context_data):
    global sheet
    join_date = datetime.now().strftime("%Y-%m-%d")
    
    if not username.startswith('@'):
        username = '@' + username
        
    if sheet is None:
        print("Warning: Database connected nahi hai, data save nahi hoga.")
        return join_date
        
    active_status = "Trial"
    active_token = ""
    empty_row_indices = []
    
    try:
        records = sheet.get_all_records()
        for i, row in enumerate(records):
            if str(row.get('Admin_ID', '')).strip() == str(admin_id):
                row_status = str(row.get('Status', 'Trial')).strip()
                row_plan_token = str(row.get('PlanToken', '')).strip()
                
                if "premium" in row_status.lower() or "platinum" in row_status.lower() or "unlimited" in row_status.lower():
                    active_status = row_status
                    active_token = row_plan_token
                elif "standard" in row_status.lower() and "premium" not in active_status.lower():
                    active_status = row_status
                    active_token = row_plan_token
                elif "custom" in row_status.lower() and "premium" not in active_status.lower() and "standard" not in active_status.lower():
                    active_status = row_status
                    active_token = row_plan_token
                
            # Sheet ko clean rakhne ke liye sirf completely Blank/Clear rows find karna (Taki dobara use kar sake)
            if not str(row.get('Admin_ID', '')).strip() and not str(row.get('Bot_Token', '')).strip() and not str(row.get('PlanToken', '')).strip():
                empty_row_indices.append(i + 2)
    except Exception as e:
        print("Error checking status during bot save:", e)

    context_str = str(context_data) if context_data else "No Context"
    
    # 50,000 cell limit protection - Chunking data 
    CHUNK_SIZE = 49000
    chunks = [context_str[i:i+CHUNK_SIZE] for i in range(0, len(context_str), CHUNK_SIZE)]
    if not chunks:
        chunks = ["No Context"]
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Database me data save kar raha hoon... (Attempt {attempt + 1}/{max_retries})")
            for chunk in chunks:
                # Basic Structure: Admin_ID, Bot_Token, Username, Context, Join_Date, Status, PlanToken
                new_row = [str(admin_id), str(bot_token), str(username), chunk, join_date, active_status, active_token]
                
                # Agar koi khali (cleared) row mojood hai toh use hi overwrite karke reuse karo! (No Appending unless required)
                if empty_row_indices:
                    reuse_idx = empty_row_indices.pop(0)
                    cell_list = sheet.range(f'A{reuse_idx}:G{reuse_idx}')
                    for col_idx, val in enumerate(new_row):
                        cell_list[col_idx].value = val
                    sheet.update_cells(cell_list)
                    time.sleep(1)
                else:
                    sheet.append_row(new_row)
                    time.sleep(1) # Delay for multi-row logic safety
                
            print("Data system database me safely save ho gaya!")
            bot_tokens_cache[username.lower()] = bot_token
            return join_date
        except Exception as e:
            print(f"Error saving to DB: {e}")
            time.sleep(2) 
            
    print("Database connection failure after retries.")
    return join_date

def append_context_to_sheet(token, extra_context):
    global sheet
    if sheet is None:
        return False
    try:
        records = sheet.get_all_records()
        bot_rows = []
        empty_row_indices = []
        admin_id, username, status, plan_token, join_date = "", "", "", "", ""
        
        # Purane sabhi chunks (rows) aur Khali (Reusable) rows find karein
        for i, row in enumerate(records):
            if str(row.get('Bot_Token', '')).strip() == str(token).strip():
                bot_rows.append({'index': i + 2, 'context': str(row.get('Context', ''))})
                if not admin_id:
                    admin_id = str(row.get('Admin_ID', ''))
                    username = str(row.get('Username', ''))
                    status = str(row.get('Status', ''))
                    plan_token = str(row.get('PlanToken', ''))
                    join_date = str(row.get('Join_Date', ''))
                    
            if not str(row.get('Admin_ID', '')).strip() and not str(row.get('Bot_Token', '')).strip() and not str(row.get('PlanToken', '')).strip():
                empty_row_indices.append(i + 2)
                    
        if not bot_rows:
            return None

        # Purana data mila kar extra data add karna
        full_context = ""
        for r in bot_rows:
            full_context += r['context'] + "\n\n"
        full_context += "--- Extra Data ---\n\n" + extra_context
        
        # Naya data fit karne ke liye 49000 chars me split karna
        CHUNK_SIZE = 49000
        chunks = [full_context[i:i+CHUNK_SIZE] for i in range(0, len(full_context), CHUNK_SIZE)]
        
        for j, chunk in enumerate(chunks):
            if j < len(bot_rows):
                # Pehle ke row overwrite karein
                row_idx = bot_rows[j]['index']
                sheet.update_cell(row_idx, 4, chunk)
                time.sleep(1)
            else:
                # Agar limit par kar gaye to doosri row add karein, (Reusable row mile toh wo use karo)
                new_row = [admin_id, token, username, chunk, join_date, status, plan_token]
                if empty_row_indices:
                    reuse_idx = empty_row_indices.pop(0)
                    cell_list = sheet.range(f'A{reuse_idx}:G{reuse_idx}')
                    for col_idx, val in enumerate(new_row):
                        cell_list[col_idx].value = val
                    sheet.update_cells(cell_list)
                    time.sleep(1)
                else:
                    sheet.append_row(new_row)
                    time.sleep(1)
                
        return full_context
    except Exception as e:
        print(f"Error updating DB: {e}")
        return False

# --- RATE CARD DATA ---
def get_plans_text():
    return (
        "🌟 <b>AI Bot SaaS Premium Plans & Rate Card</b> 🌟\n"
        "--------------------------------------\n\n"
        "⚡ <b>1. BASIC PLAN (FREE TRIAL)</b>\n"
        "• <b>Price:</b> Free (For 7 Days)\n"
        "• <b>Bot Limit:</b> Max 1 Bot\n"
        "• <b>Data Limit:</b> Up to 15k Chars data\n\n"
        "🚀 <b>2. STANDARD PLAN (STARTER PRO)</b>\n"
        "• <b>Price:</b> ₹499 / Month\n"
        "• <b>Bot Limit:</b> Max 3 Bots\n"
        "• <b>Data Limit:</b> Up to 30k Chars data\n\n"
        "👑 <b>3. UNLIMITED PLATINUM PLAN</b>\n"
        "• <b>Price:</b> ₹999 / Month\n"
        "• <b>Bot Limit:</b> Unlimited Bots 🔥\n"
        "• <b>Data Limit:</b> Up to 50k Chars data\n\n"
        "⚙️ <b>4. CUSTOM PLAN (High-Performance Pro)</b>\n"
        "• <b>Price:</b> ₹1499+ / Month (Varies on requirements) 💎\n"
        "• <b>Bot Limit:</b> Choose your own bot count limits\n"
        "• <b>Data Limit:</b> Large Deep Crawling database (up to 100k+ Chars)\n"
        "--------------------------------------\n"
        "📌 <i>Status upgrade karne ke liye Activation Token enter karein ya niche contacts par DM karein!</i>"
    )

# --- AI CHAT FUNCTION ---
def generate_groq_reply(context, user_message, retry=0):
    if retry >= len(GROQ_API_KEYS):
        return "Hamare system par abhi load zyada hai. Kripya thodi der baad try karein."
        
    try:
        response = ai_client.chat.completions.create(
            model="openai/gpt-oss-120b", 
            messages=[
                {"role": "system", "content": f"Aap ek company ke assistant bot hain. Sirf is context ke adhar par short aur sidha jawab dein: {context}. Markdown, star ya kisi bhi special symbol ka use bilkul na karein. Jab bahut zaroori ho tabhi thoda lamba jawab dein warna ek do line me baat khatam karein."},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        error_str = str(e).lower()
        if "rate limit" in error_str or "429" in error_str or "limit" in error_str:
            print(f"Key limit Hit! Rotating...")
            rotate_api_key()
            return generate_groq_reply(context, user_message, retry + 1)
        else:
            print("Groq Error:", e)
            return "Abhi main reply nahi kar pa raha hoon. Kripya baad me try karein."

# --- CLIENT BOT ENGINE (Multi-Threading) ---
def run_bot_polling(client_bot, token, join_date_str):
    print(f"🚀 Client Bot Polling Thread Started (Token: {token[:10]}...)")
    while True:
        try:
            client_bot.polling(non_stop=True, timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Polling Exception in bot {token[:10]}...: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)

def start_client_bot(token, context, join_date_str, status="Trial"):
    bot_statuses[token] = status
    
    if token in bot_contexts:
        bot_contexts[token] = context
        print(f"Bot {token[:10]}... ka data memory me update ho gaya.")
        return

    bot_contexts[token] = context
    client_bot = telebot.TeleBot(token)
    
    @client_bot.message_handler(func=lambda message: True)
    def handle_customer_message(message):
        current_status = bot_statuses.get(token, "Trial")
        
        plan_name, max_bots, max_chars, is_trial = parse_status(current_status)
        if is_trial:
            is_active, days_left = check_trial_status(join_date_str)
            if not is_active:
                expired_msg = (
                    "❌ <b>Premium status active nahi hai!</b>\n\n"
                    "Is bot ka 7-Day free trial samapt ho chuka hai aur iski services ko pause kar diya gaya hai.\n\n"
                    f"📢 <b>SaaS Platform se Premium plan khareedne ke liye turant Developer ko DM karein:</b>\n"
                    f"• <b>Telegram DM:</b> {DEVELOPER_TELEGRAM}\n"
                    f"• <b>WhatsApp:</b> {ADMIN_PHONE}\n"
                    f"• <b>Emails:</b> {ADMIN_EMAIL_1}, {ADMIN_EMAIL_2}\n\n"
                    "<i>Apne AI assistant ko dobara active karne ke liye abhi contact karein!</i>"
                )
                client_bot.reply_to(message, expired_msg, parse_mode="HTML")
                return
            
        if message.text:
            if message.text.startswith('/'):
                 return

            client_bot.send_chat_action(message.chat.id, 'typing')
            current_context = bot_contexts.get(token, "")
            reply = generate_groq_reply(current_context, message.text)
            client_bot.reply_to(message, reply)

    t = threading.Thread(target=run_bot_polling, args=(client_bot, token, join_date_str))
    t.daemon = True
    t.start()

# --- MASTER BOT LOGIC ---
@master_bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👑 <b>Master AI Platform me aapka swagat hai!</b>\n\n"
        "Commands:\n"
        "/newbot - Naya AI Bot banayein\n"
        "/mybots - Aapke bots aur settings dekhein\n"
        "/activate - Code se premium plan activate karein\n"
        "/status - Aapka current plan status dekhein\n"
        "/plans - Price aur Plan Rate Card dekhein\n"
        "/addmoredata - Bot mein aur data jodein\n"
        "/contact - Developer aur support contact jankari\n"
        "/help - System ki detailed jankari"
    )
    master_bot.reply_to(message, welcome_text, parse_mode="HTML")

@master_bot.message_handler(commands=['help'])
def master_help(message):
    help_text = (
        "ℹ️ <b>Master Bot System Help Guide:</b>\n\n"
        "<b>1. Bot Kaise Banayein (Step-by-Step):</b>\n"
        "• Sabse pehle @BotFather par jayein aur <code>/newbot</code> command se apna naya bot banayein.\n"
        "• BotFather se apna naya Bot Token copy karein.\n"
        "• Hamare Master Bot me wapas aakar <code>/newbot</code> command type karein, aur naya Token yahan paste karein.\n"
        "• Apne bot ka username (@ ke sath) type karein.\n"
        "• Apne bot ko training dene ke liye URL ya TXT file upload karein.\n\n"
        "<b>2. Premium Activation & Status:</b>\n"
        "• Humare premium/custom plans active karne ke liye <code>/activate &lt;PlanToken&gt;</code> command ka use karein.\n"
        "• Apne account ke active limits aur details ko check karne ke liye <code>/status</code> command bhejhein.\n\n"
        "<b>3. Bot Settings Manage Kaise Karein:</b>\n"
        "• Master bot me <code>/mybots</code> command bhejein.\n"
        "• Aapke saare active bots ki list samne aayegi.\n"
        "• Kisi bhi bot par click karke aap uski details settings open kar sakte hain.\n"
        "• Settings panel se aap Bot ka <b>Name</b>, <b>Description</b>, aur <b>Training Data</b> directly update kar sakte hain bina bot ko restart kiye!\n\n"
        "<b>4. Group ya Private me AI Kaise use karein:</b>\n"
        "• <b>Private:</b> Customers direct bot ko /start bhej kar baat kar sakte hain.\n"
        "• <b>Groups:</b> Apne bot ko group me add karein aur use Admin permissions dein.\n\n"
        "🤖 <b>@santosh_devloperbot Use this for More information.</b>\n\n"
        f"📞 Support support ke liye <code>/contact</code> command ka use karein."
    )
    master_bot.reply_to(message, help_text, parse_mode="HTML")

@master_bot.message_handler(commands=['contact'])
def master_contact(message):
    contact_text = (
        "📞 <b>Support & Developer Contact details:</b>\n"
        "--------------------------------------\n\n"
        f"• <b>Telegram DM:</b> {DEVELOPER_TELEGRAM}\n"
        f"• <b>WhatsApp Support:</b> {ADMIN_PHONE}\n"
        f"• <b>Support Email 1:</b> {ADMIN_EMAIL_1}\n"
        f"• <b>Support Email 2:</b> {ADMIN_EMAIL_2}\n\n"
        "Premium status upgrade karwane, rate list badalne ya kisi technical query ke liye hume kabhi bhi contact karein."
    )
    master_bot.reply_to(message, contact_text, parse_mode="HTML")

@master_bot.message_handler(commands=['plans'])
def list_plans(message):
    plans_msg = get_plans_text()
    master_bot.reply_to(message, plans_msg, parse_mode="HTML")

@master_bot.message_handler(commands=['status'])
def check_user_status(message):
    chat_id = message.chat.id
    plan_name, max_bots, max_chars, is_trial, user_bots_count = get_user_limits(chat_id)
    
    status_text = (
        "📊 <b>Aapka Account Status & Limits:</b>\n"
        "--------------------------------------\n"
        f"• <b>Current Plan:</b> {plan_name}\n"
        f"• <b>Total Bots Allowed:</b> {max_bots if max_bots < 999 else 'Unlimited 🔥'}\n"
        f"• <b>Active Bots Count:</b> {user_bots_count}\n"
        f"• <b>Remaining Bots Slot:</b> {max(0, max_bots - user_bots_count) if max_bots < 999 else 'Unlimited 🔥'}\n"
        f"• <b>Data Training Limit:</b> {max_chars:,} Characters\n"
        "--------------------------------------\n\n"
        "💡 <i>Naya plan activate karne ke liye use karein:</i>\n"
        "<code>/activate &lt;PlanToken&gt;</code>"
    )
    master_bot.reply_to(message, status_text, parse_mode="HTML")

@master_bot.message_handler(commands=['activate'])
def activate_plan_command(message):
    chat_id = message.chat.id
    text_parts = message.text.strip().split()
    if len(text_parts) < 2:
        master_bot.reply_to(message, "⚠️ Format sahi nahi hai! Kripya aise activate karein:\n<code>/activate &lt;Your_Token_Here&gt;</code>", parse_mode="HTML")
        return
        
    token = text_parts[1].strip()
    master_bot.reply_to(message, "⏳ Activation Token verify kar raha hoon, kripya pratiksha karein...")
    
    plan_info, error = activate_token_in_db(chat_id, token)
    if error:
        master_bot.reply_to(message, f"❌ {error}")
    else:
        success_msg = (
            "🎉 <b>Success! Aapka Plan Activate/Update Ho Gaya Hai!</b>\n"
            "--------------------------------------\n"
            f"• <b>New Plan:</b> {plan_info['plan_name']}\n"
            f"• <b>Bot Limit:</b> {plan_info['max_bots'] if plan_info['max_bots'] < 999 else 'Unlimited 🔥'}\n"
            f"• <b>Training Chars Limit:</b> {plan_info['max_chars']:,} Characters\n"
            "--------------------------------------\n\n"
            "💡 Aapke existing sabhi bots par naya plan lagoo kar diya gaya hai. /status se limits check karein!"
        )
        master_bot.reply_to(message, success_msg, parse_mode="HTML")

@master_bot.message_handler(commands=['mybots'])
def list_my_bots(message):
    chat_id = str(message.chat.id)
    if sheet is None:
        master_bot.reply_to(message, "Error: System Database connected nahi hai.")
        return
        
    try:
        records = sheet.get_all_records()
        user_bots = [row for row in records if str(row.get('Admin_ID', '')).strip() == chat_id]
        
        active_user_bots = [r for r in user_bots if str(r.get('Bot_Token', '')).strip()]
        
        if not active_user_bots:
            master_bot.reply_to(message, "Aapne abhi tak koi bot add nahi kiya hai. Naya bot banane ke liye /newbot use karein.")
            return
            
        markup = telebot.types.InlineKeyboardMarkup()
        for row in active_user_bots:
            username = row.get('Username', 'Unknown Bot')
            markup.add(telebot.types.InlineKeyboardButton(text=f"🤖 {username}", callback_data=f"bot_{username}"))
            
        master_bot.reply_to(message, "📋 <b>Aapke Registered Bots:</b>\nKisi bhi bot par click karke uski settings manage karein:", reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print("Error in /mybots:", e)
        master_bot.reply_to(message, "Error: Bots list load nahi ho payi.")

# --- CALLBACK QUERY HANDLER FOR SETTINGS ---
@master_bot.callback_query_handler(func=lambda call: True)
def handle_bot_settings(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data
    
    if data == "back_to_list":
        try:
            records = sheet.get_all_records()
            user_bots = [row for row in records if str(row.get('Admin_ID', '')).strip() == str(chat_id)]
            active_user_bots = [r for r in user_bots if str(r.get('Bot_Token', '')).strip()]
            markup = telebot.types.InlineKeyboardMarkup()
            for row in active_user_bots:
                username = row.get('Username', 'Unknown Bot')
                markup.add(telebot.types.InlineKeyboardButton(text=f"🤖 {username}", callback_data=f"bot_{username}"))
            master_bot.edit_message_text("📋 <b>Aapke Registered Bots:</b>\nSettings manage karne ke liye bot chunein:", chat_id, message_id, reply_markup=markup, parse_mode="HTML")
        except:
            master_bot.answer_callback_query(call.id, "Error loading list.")
        return

    if data.startswith("bot_"):
        bot_username = data.replace("bot_", "")
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("🏷️ Name Change", callback_data=f"editname_{bot_username}"),
            telebot.types.InlineKeyboardButton("📝 Desc Change", callback_data=f"editdesc_{bot_username}")
        )
        markup.row(
            telebot.types.InlineKeyboardButton("📥 Add More Data", callback_data=f"adddata_{bot_username}"),
            telebot.types.InlineKeyboardButton("🔙 Back to List", callback_data="back_to_list")
        )
        
        settings_text = (
            f"🛠️ <b>Bot Control Panel</b>\n\n"
            f"• <b>Bot Username:</b> {bot_username}\n"
            "• Niche diye gaye options se aap is bot ke details live change kar sakte hain."
        )
        master_bot.edit_message_text(settings_text, chat_id, message_id, reply_markup=markup, parse_mode="HTML")
        return

    action, target_username = data.split("_", 1)
    
    target_token = bot_tokens_cache.get(target_username.lower())
    if not target_token and sheet is not None:
        try:
            records = sheet.get_all_records()
            for row in records:
                if str(row.get('Username', '')).strip().lower() == target_username.lower():
                    target_token = str(row.get('Bot_Token', '')).strip()
                    bot_tokens_cache[target_username.lower()] = target_token
                    break
        except Exception as e:
            print("Token cache lookup failed:", e)

    if not target_token:
        master_bot.answer_callback_query(call.id, "Error: Token nahi mila.")
        return

    if action == "editname":
        admin_states[chat_id] = {'step': 'wait_for_botname', 'token': target_token, 'username': target_username}
        master_bot.send_message(chat_id, f"📝 <b>{target_username}</b> ke liye naya Name type karke bhejein:")
        master_bot.answer_callback_query(call.id)
        
    elif action == "editdesc":
        admin_states[chat_id] = {'step': 'wait_for_botdesc', 'token': target_token, 'username': target_username}
        master_bot.send_message(chat_id, f"📝 <b>{target_username}</b> ke liye naya Description text type karke bhejein:")
        master_bot.answer_callback_query(call.id)
        
    elif action == "adddata":
        plan_name, max_bots, max_chars, is_trial, user_bots_count = get_user_limits(chat_id)
        admin_states[chat_id] = {'step': 'add_data_type', 'token': target_token, 'username': target_username, 'max_chars': max_chars}
        master_bot.send_message(chat_id, f"📥 <b>{target_username}</b> me data kaise dena hai? Type karein <code>URL</code> ya <code>TXT</code>.", parse_mode="HTML")
        master_bot.answer_callback_query(call.id)

@master_bot.message_handler(commands=['newbot'])
def ask_token(message):
    chat_id = str(message.chat.id)
    plan_name, max_bots, max_chars, is_trial, user_bots_count = get_user_limits(chat_id)
            
    if user_bots_count >= max_bots:
        block_msg = (
            f"❌ <b>Aapki plan limit ({max_bots} bot) poori ho chuki hai!</b>\n"
            f"Current Plan: <b>{plan_name}</b>\n\n"
            "Ek se zyada bot add karne ke liye aapko <b>Premium ya Custom Plan</b> lena hoga.\n\n"
            "🌟 <b>Premium/Custom active karne ke liye humse sampark (DM) karein:</b>\n"
            f"• <b>Telegram DM:</b> {DEVELOPER_TELEGRAM}\n"
            f"• <b>WhatsApp:</b> {ADMIN_PHONE}\n"
            f"• <b>Emails:</b> {ADMIN_EMAIL_1}, {ADMIN_EMAIL_2}\n\n"
            "<i>Agar aapke paas valid activation token hai, toh code use karein: <code>/activate &lt;PlanToken&gt;</code></i>"
        )
        master_bot.reply_to(message, block_msg, parse_mode="HTML")
        return
            
    admin_states[int(chat_id)] = {'step': 'token', 'max_chars': max_chars}
    master_bot.reply_to(message, "1. Apna Bot Token bhejein:")

@master_bot.message_handler(commands=['addmoredata'])
def add_more_data(message):
    chat_id = message.chat.id
    admin_states[chat_id] = {'step': 'wait_for_username'}
    master_bot.reply_to(message, "📝 Apna wo <b>Bot Username</b> (e.g. @MyBot) bhejein jisme naya data jodna hai:")

@master_bot.message_handler(content_types=['document'])
def handle_txt_file(message):
    chat_id = message.chat.id
    if chat_id in admin_states:
        step = admin_states[chat_id].get('step')
        max_chars = admin_states[chat_id].get('max_chars', 15000)
        
        if step in ['context_data', 'add_data_txt']:
            if message.document.file_name.endswith('.txt'):
                master_bot.reply_to(message, "Document process kar raha hoon...")
                file_info = master_bot.get_file(message.document.file_id)
                downloaded_file = master_bot.download_file(file_info.file_path)
                context_text = downloaded_file.decode('utf-8')[:max_chars] 
                
                if step == 'context_data':
                    finalize_registration(message, chat_id, context_text)
                else:
                    finalize_add_data(message, chat_id, context_text)
            else:
                master_bot.reply_to(message, "Kripya sirf .txt file hi upload karein.")

@master_bot.message_handler(func=lambda message: True)
def handle_text_steps(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if chat_id not in admin_states:
        return

    step = admin_states[chat_id].get('step')
    max_chars = admin_states[chat_id].get('max_chars', 15000)

    if step == 'token':
        admin_states[chat_id]['token'] = text
        admin_states[chat_id]['step'] = 'username'
        master_bot.reply_to(message, "2. Apne bot ka Username bhejein (jaise @MyBot):")
        
    elif step == 'username':
        if not text.startswith('@'):
            text = '@' + text
        admin_states[chat_id]['username'] = text
        admin_states[chat_id]['step'] = 'context_type'
        master_bot.reply_to(message, "3. Data kaise dena hai? URL ya TXT likhein.")
        
    elif step == 'context_type':
        if text.upper() == 'URL':
            admin_states[chat_id]['step'] = 'url'
            master_bot.reply_to(message, "Apni website ka URL bhejein (isme thoda time lag sakta hai):")
        elif text.upper() == 'TXT':
            admin_states[chat_id]['step'] = 'context_data'
            master_bot.reply_to(message, "Ab apni .txt file upload karein.")
        else:
            master_bot.reply_to(message, "Sirf URL ya TXT type karein.")
            
    elif step == 'url':
        master_bot.reply_to(message, "Website aur uske links se data nikal raha hoon, thoda intezaar karein...")
        context_text = extract_text_from_url(text, max_chars=max_chars)
        if context_text:
            finalize_registration(message, chat_id, context_text)
        else:
            master_bot.reply_to(message, "URL se text nahi mila. Sahi URL dein ya TXT chunein.")

    elif step == 'wait_for_username':
        username_query = text.lower()
        if not username_query.startswith('@'):
            username_query = '@' + username_query
            
        target_token = None
        user_max_chars = 15000
        if sheet is not None:
            try:
                records = sheet.get_all_records()
                for row in records:
                    if str(row.get('Username', '')).strip().lower() == username_query:
                        target_token = str(row.get('Bot_Token', '')).strip()
                        user_rows = [r for r in records if str(r.get('Admin_ID', '')).strip() == str(chat_id)]
                        for r in user_rows:
                            p_name, m_bots, m_chars, t_trial = parse_status(r.get('Status', 'Trial'))
                            if m_chars > user_max_chars:
                                user_max_chars = m_chars
                        break
            except Exception as e:
                print("Username query DB error:", e)
                
        if target_token:
            admin_states[chat_id] = {'step': 'add_data_type', 'token': target_token, 'username': username_query, 'max_chars': user_max_chars}
            master_bot.reply_to(message, f"✅ Bot mil gaya!\nNaya data kaise dena hai? URL ya TXT type karein.")
        else:
            master_bot.reply_to(message, "❌ Bot username data system me nahi mila. Kripya correct username type karein.")
            del admin_states[chat_id]

    elif step == 'add_data_type':
        if text.upper() == 'URL':
            admin_states[chat_id]['step'] = 'add_data_url'
            master_bot.reply_to(message, "Naya URL bhejein:")
        elif text.upper() == 'TXT':
            admin_states[chat_id]['step'] = 'add_data_txt'
            master_bot.reply_to(message, "Nayi .txt file upload karein.")
        else:
            master_bot.reply_to(message, "Sirf URL ya TXT type karein.")
            
    elif step == 'add_data_url':
        master_bot.reply_to(message, "Website aur links se naya data nikal raha hoon, intezaar karein...")
        extra_context = extract_text_from_url(text, max_chars=max_chars)
        if extra_context:
            finalize_add_data(message, chat_id, extra_context)
        else:
            master_bot.reply_to(message, "URL fail ho gaya. Sahi URL dein.")

    elif step == 'wait_for_botname':
        token = admin_states[chat_id]['token']
        username = admin_states[chat_id]['username']
        master_bot.reply_to(message, "⏳ Live update process kar raha hoon...")
        try:
            temp_bot = telebot.TeleBot(token)
            temp_bot.set_my_name(name=text)
            master_bot.reply_to(message, f"✅ Success! <b>{username}</b> ka name live change hokar <b>{text}</b> ho gaya hai.", parse_mode="HTML")
        except Exception as e:
            master_bot.reply_to(message, f"⚠️ Error name update karne me: {e}")
        del admin_states[chat_id]

    elif step == 'wait_for_botdesc':
        token = admin_states[chat_id]['token']
        username = admin_states[chat_id]['username']
        master_bot.reply_to(message, "⏳ Live update process kar raha hoon...")
        try:
            temp_bot = telebot.TeleBot(token)
            temp_bot.set_my_description(description=text)
            master_bot.reply_to(message, f"✅ Success! <b>{username}</b> ka description live update ho gaya hai.", parse_mode="HTML")
        except Exception as e:
            master_bot.reply_to(message, f"⚠️ Error description update karne me: {e}")
        del admin_states[chat_id]

def finalize_registration(message, chat_id, context_text):
    data = admin_states[chat_id]
    join_date = save_to_sheet(str(chat_id), data['token'], data['username'], context_text)
    
    start_client_bot(data['token'], context_text, join_date, "Trial")
    
    del admin_states[chat_id]
    
    success_text = f"Badhaai ho! Aapka bot ({data['username']}) shuru ho gaya hai.\nTrial: 7 din ka free trial aaj ({join_date}) se chalu hai.\n\nIse private chat me ya group me admin banakar test karein."
    master_bot.reply_to(message, success_text)

def finalize_add_data(message, chat_id, extra_context):
    token = admin_states[chat_id]['token']
    master_bot.reply_to(message, "Database mein data update kar raha hoon...")
    
    updated_context = append_context_to_sheet(token, extra_context)
    
    if updated_context:
        if token in bot_contexts:
            bot_contexts[token] = updated_context
        master_bot.reply_to(message, "Success! Naya data bot mein add ho gaya hai.")
    elif updated_context is None:
        master_bot.reply_to(message, "Error: Ye Bot database me nahi mila.")
    else:
        master_bot.reply_to(message, "Error: Database update me problem aayi.")
        
    del admin_states[chat_id]

def run_bot():
    print("Master System Booting up...")
    master_bot.set_my_commands([
        telebot.types.BotCommand("/start", "Main menu"),
        telebot.types.BotCommand("/newbot", "Naya AI Bot banayein"),
        telebot.types.BotCommand("/mybots", "Aapke bots ki list"),
        telebot.types.BotCommand("/activate", "Premium code activate karein"),
        telebot.types.BotCommand("/status", "Current plan limits status"),
        telebot.types.BotCommand("/plans", "Plans aur Price details"),
        telebot.types.BotCommand("/addmoredata", "Purane bot me data jodein"),
        telebot.types.BotCommand("/contact", "Developer & Support details"),
        telebot.types.BotCommand("/help", "Detailed help guide")
    ])
    
    if sheet is not None:
        try:
            all_records = sheet.get_all_records()
            print(f"Total {len(all_records)} rows found in DB.")
            
            # Context Aggregation: Ek bot ke sabhi multiple rows ka data jodne ke liye
            bot_data_map = {}
            for row in all_records:
                token = str(row.get('Bot_Token', '')).strip()
                if not token: continue
                
                username = str(row.get('Username', '')).strip()
                status = str(row.get('Status', '')).strip()
                join_date = str(row.get('Join_Date', '')).strip()
                context = str(row.get('Context', ''))
                
                if token not in bot_data_map:
                    bot_data_map[token] = {
                        'username': username,
                        'status': status,
                        'join_date': join_date,
                        'context': context
                    }
                else:
                    bot_data_map[token]['context'] += "\n\n" + context

            # Aggregated data se bots memory load karein
            for token, data in bot_data_map.items():
                username = data['username']
                if username:
                    bot_tokens_cache[username.lower()] = token
                    
                plan_name, max_bots, max_chars, is_trial = parse_status(data['status'])
                
                is_active = True
                if is_trial and data['join_date']:
                    is_active, _ = check_trial_status(data['join_date'])
                
                if is_active:
                    start_client_bot(token, data['context'], data['join_date'], data['status'])
        except Exception as e:
            print("Purane bots load nahi ho paye.", e)
    else:
        print("Database connect na hone ke karan purane bots load nahi hue.")

    print("Master Bot is ready for registrations!")
    while True:
        try:
            master_bot.polling(non_stop=True, timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Polling Exception in Master Bot: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)

# --- FLASK SERVER SETUP FOR RENDER HEALTH CHECKS ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Master AI Platform is running 24/7 on Render!"

@flask_app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    # Start bot in a background thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask web server for Render on the main thread
    port = int(os.environ.get("PORT", 8080))
    print(f"Flask Web Server started on port {port}...")
    flask_app.run(host="0.0.0.0", port=port)
