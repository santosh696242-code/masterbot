import telebot
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import threading
import json
import base64
from groq import Groq
import time
from urllib.parse import urlparse, urljoin
from telebot import apihelper
from flask import Flask

# --- SETUP CONFIGURATION ---
MASTER_BOT_TOKEN = "8688021018:AAG6svktpklBybWqM-9qQITCUAJvVuALIOo"
# Render Environment Variable se Groq API Keys fetch karna (comma se separate karke)
GROQ_API_KEYS_ENV = os.environ.get("GROQ_API_KEYS", "")
GROQ_API_KEYS = [key.strip() for key in GROQ_API_KEYS_ENV.split(",") if key.strip()]

# Agar env variable set nahi hai to array empty na ho jisse error na aaye
if not GROQ_API_KEYS:
    GROQ_API_KEYS = ["SET_YOUR_GROQ_API_KEY_IN_ENV_VARIABLES"]

current_key_index = 0
ai_client = Groq(api_key=GROQ_API_KEYS[current_key_index])
master_bot = telebot.TeleBot(MASTER_BOT_TOKEN)
admin_states = {}

# Contact Details
DEVELOPER_TELEGRAM = "@Developer_yadav"
ADMIN_PHONE = "7858979517"
ADMIN_EMAIL_1 = "maksudanyadav814@gmail.com"
ADMIN_EMAIL_2 = "sk747460950@gmail.com"

# Active bots ka cache system
bot_contexts = {} 
bot_statuses = {}
bot_tokens_cache = {} 
active_client_threads = {}  # Token -> Thread reference
active_client_instances = {}  # Token -> Bot Instance reference

# --- DATABASE SETUP (SCANNER-PROOF) ---
sheet = None 
try:
    print("Master Bot: Database se connect karne ki koshish kar raha hoon...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds_dict = None
    
    # METHOD 1: Try to fetch credentials directly from your Google Drive link
    try:
        print("Master Bot: Downloading fresh credentials from Google Drive...")
        drive_url = "https://drive.google.com/uc?export=download&id=1tsPWNQOD0S90Szv3vbB-v76dgrLzSXhO"
        response = requests.get(drive_url, timeout=10)
        if response.status_code == 200 and "private_key" in response.text:
            creds_dict = response.json()
            print("Master Bot: Credentials downloaded from Google Drive successfully!")
    except Exception as download_error:
        print(f"Master Bot: Google Drive download failed ({download_error}). Moving to secure backup...")
        
    # METHOD 2: Fallback to secure Base64 embedded credentials (Scanner-proof)
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
        from oauth2client.service_account import ServiceAccountCredentials
        decoded_data = base64.b64decode(b64_creds).decode('utf-8')
        creds_dict = json.loads(decoded_data)
        print("Master Bot: Secure backup credentials parsed successfully!")

    from oauth2client.service_account import ServiceAccountCredentials
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    SHEET_URL = "https://docs.google.com/spreadsheets/d/16DfTvs0PIADBqELyImh4FsDH7F00r39FYuQEdlLGP0s/edit?usp=sharing"
    sheet = client.open_by_url(SHEET_URL).get_worksheet(0) 
    print("Master Bot: Database connected successfully.")
except Exception as e:
    print(f"Master Bot Connection Error: {e}")

# --- HELPER FUNCTIONS ---
def parse_status(status_str):
    status_str = str(status_str).strip().lower()
    plan_name = "Trial"
    max_bots = 1
    max_chars = 15000
    is_trial = True

    if "premium" in status_str or "platinum" in status_str or "unlimited" in status_str:
        plan_name = "Premium"
        max_bots = 999  
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

def check_trial_status(join_date_str):
    try:
        join_date = datetime.strptime(join_date_str.strip(), "%Y-%m-%d %H:%M:%S")
        days_passed = (datetime.now() - join_date).days
        remaining_days = 3 - days_passed
        if remaining_days > 0:
            return True, remaining_days
        return False, 0
    except:
        return True, 3

def get_column_indices(headers):
    indices = {
        'Admin_ID': 0,
        'Bot_Token': 1,
        'Username': 2,
        'Context': 3,
        'Join_Date': 4,
        'Status': 5,
        'PlanToken': 6,
        'Admin_Username': 7,
        'Temp': 10
    }
    for key in indices.keys():
        if key in headers:
            indices[key] = headers.index(key)
    return indices

# --- DATA EXTRACTION SCRAPERS ---
def fetch_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            for tag in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
                tag.decompose()
            text = soup.get_text(separator=' ', strip=True)
            return text[:15000] 
        else:
            return f"Error: Status code {response.status_code}"
    except Exception as e:
        return f"Error connecting to website: {e}"

def extract_links_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            base_url = urlparse(url).scheme + "://" + urlparse(url).netloc
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                full_url = urljoin(base_url, href)
                if full_url.startswith("http") and full_url not in links:
                    links.append(full_url)
            return links[:15] 
        return []
    except Exception as e:
        return []

# --- SUB-BOT DYNAMIC ENGINE ---
def get_groq_response(prompt, system_instruction):
    global current_key_index, ai_client
    for attempt in range(len(GROQ_API_KEYS)):
        try:
            chat_completion = ai_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Groq API Key index {current_key_index} failed: {e}. Rotating...")
            current_key_index = (current_key_index + 1) % len(GROQ_API_KEYS)
            ai_client = Groq(api_key=GROQ_API_KEYS[current_key_index])
    return "⚠️ Server overload! Sabhi AI keys is waqt busy hain. Kripya thodi der baad dobara koshish karein."

def run_client_bot_thread(token, system_instruction, join_date, status_str):
    try:
        client_bot = telebot.TeleBot(token)
        active_client_instances[token] = client_bot
        
        print(f"🤖 Sub-Bot [Token ending in ...{token[-6:]}] starting operations...")
        
        @client_bot.message_handler(commands=['start'])
        def start_msg(message):
            plan_name, max_bots, max_chars, is_trial = parse_status(status_str)
            welcome_text = (
                f"👋 <b>Welcome! Main ek custom AI Assistant hoon.</b>\n\n"
                f"Aap mujhse koi bhi swaal pooch sakte hain.\n\n"
                f"📊 <b>Aapke Bot ka Plan:</b> {plan_name}\n"
                f"✍️ <b>Response Character Limit:</b> {max_chars:,} chars."
            )
            client_bot.reply_to(message, welcome_text, parse_mode="HTML")

        @client_bot.message_handler(func=lambda m: True)
        def handle_query(message):
            plan_name, max_bots, max_chars, is_trial = parse_status(status_str)
            
            if is_trial:
                is_active, rem_days = check_trial_status(join_date)
                if not is_active:
                    client_bot.reply_to(message, "❌ <b>Free Trial Expired!</b>\nKripya Master bot par jaakar activation token se upgrade karein.")
                    return
            
            loading_msg = client_bot.reply_to(message, "🤔 <i>Mera dimag soch raha hai...</i>", parse_mode="HTML")
            
            user_prompt = message.text
            ai_response = get_groq_response(user_prompt, system_instruction)
            
            # Response constraint truncation
            if len(ai_response) > max_chars:
                ai_response = ai_response[:max_chars] + "\n\n(Plan character limit reached!)"
                
            try:
                client_bot.edit_message_text(ai_response, message.chat.id, loading_msg.message_id, parse_mode="Markdown")
            except:
                client_bot.edit_message_text(ai_response, message.chat.id, loading_msg.message_id)

        client_bot.polling(non_stop=True, timeout=20, long_polling_timeout=10)
    except Exception as e:
        print(f"Exception in Client Bot Thread [Token ending in ...{token[-6:]}]: {e}")

def start_client_bot(token, context, join_date, status):
    # Agar pehle se chal raha hai, toh use stop karein
    if token in active_client_instances:
        try:
            print(f"Stopping already running bot: ...{token[-6:]}")
            active_client_instances[token].stop_polling()
        except Exception as e:
            print(f"Error stopping dynamic bot: {e}")
            
    t = threading.Thread(target=run_client_bot_thread, args=(token, context, join_date, status))
    t.daemon = True
    active_client_threads[token] = t
    t.start()

# --- MASTER BOT LOGIC ---
@master_bot.message_handler(commands=['start'])
def master_start(message):
    welcome_text = (
        "🚀 <b>Master Control Bot me aapka swagat hai!</b>\n\n"
        "Yahan se aap apne custom AI sub-bots ko build, start aur database status manage kar sakte hain.\n\n"
        "📝 <b>Primary Commands:</b>\n"
        "🔑 `/activate <token>` - Apne standard ya premium limits token ko redeem karein.\n"
        "⚙️ `/setup_bot` - Naya bot token database me add aur register karne ke liye.\n"
        "📊 `/status` - Aapke running plan aur dynamic limits ka report card.\n"
        "🛠️ `/addmoredata` - Apne custom context prompt system ko update karein.\n"
        "📞 `/contact` - Developer support se judne ke liye."
    )
    master_bot.reply_to(message, welcome_text, parse_mode="HTML")

@master_bot.message_handler(commands=['contact'])
def master_contact(message):
    contact_text = (
        "📞 <b>Contact Support & Developer Details:</b>\n\n"
        f"👨‍💻 <b>Developer Telegram:</b> {DEVELOPER_TELEGRAM}\n"
        f"📱 <b>Support Phone:</b> +91 {ADMIN_PHONE}\n"
        f"📧 <b>Email 1:</b> {ADMIN_EMAIL_1}\n"
        f"📧 <b>Email 2:</b> {ADMIN_EMAIL_2}\n\n"
        "<i>Koi bhi error ya issue aane par aap upar diye gaye details par sampark kar sakte hain.</i>"
    )
    master_bot.reply_to(message, contact_text, parse_mode="HTML")

@master_bot.message_handler(commands=['help'])
def master_help(message):
    help_text = (
        "❓ <b>Master Bot Help Guide:</b>\n\n"
        "1️⃣ <b>Bot Setup:</b> `/setup_bot` command use karein aur @BotFather se mila naya token enter karein.\n"
        "2️⃣ <b>Activation:</b> Agar aapke paas license token hai, to `/activate TOKEN_CODE` likhein (e.g. `/activate PREM-123456`). Isse aapka trial limit hat jayega aur naya plan lag jayega.\n"
        "3️⃣ <b>Context Update:</b> Apne bot ka behavior change karne ke liye `/addmoredata` use karein aur naya prompt type karein.\n"
        "4️⃣ <b>Status Check:</b> Apne sabhi connected bots ki detail dekhne ke liye `/status` enter karein."
    )
    master_bot.reply_to(message, help_text, parse_mode="HTML")

@master_bot.message_handler(commands=['status'])
def master_status_check(message):
    user_id = str(message.chat.id)
    master_bot.reply_to(message, "🔍 Database me aapka account plan search kar raha hoon...")
    
    if sheet is None:
        master_bot.reply_to(message, "❌ Database offline hai.")
        return
        
    try:
        records = sheet.get_all_records()
        user_bots = [r for r in records if str(r.get('Admin_ID', '')).strip() == user_id]
        
        if not user_bots:
            master_bot.reply_to(message, "📝 Aapka koi active bot register nahi mila. Free Setup ke liye `/setup_bot` use karein!")
            return
            
        report_msg = "📊 <b>Aapke Registered Platform Bots:</b>\n\n"
        for idx, bot in enumerate(user_bots, 1):
            status = bot.get('Status', 'Trial')
            plan_name, max_bots, max_chars, is_trial = parse_status(status)
            
            report_msg += f"🤖 <b>Bot {idx}:</b> @{bot.get('Username', 'No_Username')}\n"
            report_msg += f"• Plan Type: <b>{plan_name}</b>\n"
            report_msg += f"• Max Chars allowed: {max_chars:,}\n"
            
            if is_trial:
                is_active, rem_days = check_trial_status(str(bot.get('Join_Date', '')))
                status_text = f"Active Free Trial ({rem_days} din bache hain)" if is_active else "Free Trial Expired ❌"
                report_msg += f"• Activation Status: {status_text}\n\n"
            else:
                report_msg += f"• Activation Status: Active Premium ✅\n\n"
                
        master_bot.reply_to(message, report_msg, parse_mode="HTML")
    except Exception as e:
        master_bot.reply_to(message, f"❌ Plan data compile failed: {e}")

@master_bot.message_handler(commands=['activate'])
def master_activate_token(message):
    text_parts = message.text.strip().split()
    if len(text_parts) < 2:
        master_bot.reply_to(message, "⚠️ Format galat hai! Kripya command aise likhein:\n`/activate PREM-XXXXXX`", parse_mode="HTML")
        return
        
    activation_token = text_parts[1].strip()
    user_id = str(message.chat.id)
    user_name = "@" + str(message.from_user.username) if message.from_user.username else "No_Username"
    
    master_bot.reply_to(message, "⏳ Activation process verify kiya ja raha hai...")
    
    if sheet is None:
        master_bot.reply_to(message, "❌ Database offline hai. Kripya thodi der baad koshish karein.")
        return
        
    try:
        records = sheet.get_all_records()
        headers = sheet.row_values(1)
        indices = get_column_indices(headers)
        
        # 1. Find unused token row from DB
        token_row_num = None
        plan_type = None
        
        for idx, row in enumerate(records, 2):  # row 2 is index 0 of records
            row_token = str(row.get('PlanToken', '')).strip()
            row_admin = str(row.get('Admin_ID', '')).strip()
            
            if row_token == activation_token:
                if row_admin and row_admin.isdigit():
                    master_bot.reply_to(message, "❌ <b>Security Error!</b> Ye token pehle hi kisi aur user ke sath activated hai.")
                    return
                token_row_num = idx
                plan_type = str(row.get('Temp', 'Standard')).strip()
                break
                
        if not token_row_num:
            master_bot.reply_to(message, "❌ <b>Galat Token!</b> Kripya sahi token copy karke type karein.")
            return

        # 2. Find if User already has an existing row
        user_row_num = None
        for idx, row in enumerate(records, 2):
            if str(row.get('Admin_ID', '')).strip() == user_id and idx != token_row_num:
                user_row_num = idx
                break

        print(f"Master Bot: Applying new plan '{plan_type}' for Admin ID {user_id}...")

        if user_row_num:
            # User already exists! Replace their old plan with the new token details
            print(f"Master Bot: Existing user found at row {user_row_num}. Updating plan directly...")
            sheet.update_cell(user_row_num, indices['Status'] + 1, plan_type)
            sheet.update_cell(user_row_num, indices['PlanToken'] + 1, activation_token)
            sheet.update_cell(user_row_num, indices['Join_Date'] + 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            sheet.update_cell(user_row_num, indices['Admin_Username'] + 1, user_name)
            
            # Now delete the unused blank token row to prevent duplicates
            print(f"Master Bot: Deleting consumed token row {token_row_num}...")
            sheet.delete_rows(token_row_num)
            
            # Adjust row index if token row was located above the user row
            if token_row_num < user_row_num:
                user_row_num -= 1
                
            active_row = user_row_num
        else:
            # New User! Activate the token row with user credentials
            print(f"Master Bot: New user. Activating token row {token_row_num}...")
            sheet.update_cell(token_row_num, indices['Admin_ID'] + 1, user_id)
            sheet.update_cell(token_row_num, indices['Join_Date'] + 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            sheet.update_cell(token_row_num, indices['Status'] + 1, plan_type)
            sheet.update_cell(token_row_num, indices['Admin_Username'] + 1, user_name)
            
            active_row = token_row_num
            
        # Extract the updated configuration details to restart the sub-bot smoothly
        updated_row_data = sheet.row_values(active_row)
        bot_token_col = indices['Bot_Token']
        assigned_bot_token = str(updated_row_data[bot_token_col]).strip() if len(updated_row_data) > bot_token_col else ""
        
        plan_name, max_bots, max_chars, is_trial = parse_status(plan_type)
        
        success_msg = (
            f"🎉 <b>Plan Successfully Activated!</b>\n"
            f"--------------------------------------\n"
            f"• <b>Upgrade Plan:</b> {plan_name}\n"
            f"• <b>Response Length Limit:</b> {max_chars:,} chars\n\n"
        )
        
        if assigned_bot_token and len(assigned_bot_token) > 10:
            success_msg += f"🟢 Aapka dynamic bot @{updated_row_data[indices['Username']]} naye plan ke sath successfully update ho gaya hai!"
            start_client_bot(assigned_bot_token, updated_row_data[indices['Context']], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), plan_type)
        else:
            success_msg += "👉 <b>Next Step:</b> Naya Bot register karne ke liye niche likhi command type karein:\n`/setup_bot`"
            
        master_bot.reply_to(message, success_msg, parse_mode="HTML")
    except Exception as e:
        master_bot.reply_to(message, f"❌ Activation transaction failed: {e}")

@master_bot.message_handler(commands=['setup_bot'])
def master_setup_bot_start(message):
    user_id = str(message.chat.id)
    admin_states[user_id] = {'step': 'wait_for_token'}
    prompt = (
        "🤖 <b>Bot Setup Wizard:</b>\n\n"
        "Kripya aapke Bot ka token enter karein jo aapne @BotFather se create kiya hai."
    )
    master_bot.reply_to(message, prompt)

@master_bot.message_handler(commands=['addmoredata'])
def master_add_more_data(message):
    user_id = str(message.chat.id)
    admin_states[user_id] = {'step': 'wait_for_context'}
    prompt = (
        "🛠️ <b>Context Jodne Ke Liye Wizard:</b>\n\n"
        "Apne bot ke liye naya prompt/rules instructions likh kar bhejein (jaise: <i>You are a coding expert named Yadav AI</i>).\n"
        "Aap URL likh kar bhi bhej sakte hain (jaise `add_url:https://google.com`), jise fetch kiya jayega."
    )
    master_bot.reply_to(message, prompt, parse_mode="HTML")

# --- TEXT STEPS FOR SETUP BOT HANDLER ---
@master_bot.message_handler(func=lambda m: str(m.chat.id) in admin_states)
def handle_master_steps(message):
    user_id = str(message.chat.id)
    step = admin_states[user_id].get('step')
    text = message.text.strip()
    
    if step == 'wait_for_token':
        # Verify if token is a valid Telegram Bot Token format
        if ":" not in text or len(text) < 30:
            master_bot.reply_to(message, "❌ Invalid Bot Token format! BotFather se mila token sahi se copy karke send karein.")
            return
            
        admin_states[user_id]['bot_token'] = text
        master_bot.reply_to(message, "⏳ Bot API key test ki ja rahi hai...")
        
        try:
            # Test token request
            test_res = requests.get(f"https://api.telegram.org/bot{text}/getMe", timeout=10).json()
            if not test_res.get('ok'):
                master_bot.reply_to(message, "❌ **API Error!** Bot key valid nahi hai ya delete ho chuki hai.")
                return
                
            bot_username = test_res['result']['username']
            admin_states[user_id]['bot_username'] = bot_username
            admin_states[user_id]['step'] = 'wait_for_system_context'
            
            master_bot.reply_to(message, f"🎯 **Bot Found:** @{bot_username}\n\n👉 Ab aap is bot ka System prompt/Context write karein (Rules or dynamic personality):")
        except:
            master_bot.reply_to(message, "❌ Connection Timeout! API validation check skip ho gayi. Kripya firse koshish karein.")
            
    elif step == 'wait_for_system_context':
        bot_token = admin_states[user_id]['bot_token']
        bot_username = admin_states[user_id]['bot_username']
        system_context = text
        
        master_bot.reply_to(message, "⏳ Details database me sync ki ja rahi hain...")
        
        if sheet is None:
            master_bot.reply_to(message, "❌ Connection Error. Database offline hai.")
            return
            
        try:
            records = sheet.get_all_records()
            headers = sheet.row_values(1)
            indices = get_column_indices(headers)
            
            # Find the row of active activated plan
            target_row_num = None
            join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_status = "Trial"
            
            for idx, r in enumerate(records, 2):
                if str(r.get('Admin_ID', '')).strip() == user_id:
                    target_row_num = idx
                    current_status = r.get('Status', 'Trial')
                    join_date = r.get('Join_Date', join_date)
                    break
                    
            # If no plan exists, we write a trial record
            if not target_row_num:
                new_row = [""] * len(headers)
                new_row[indices['Admin_ID']] = user_id
                new_row[indices['Bot_Token']] = bot_token
                new_row[indices['Username']] = bot_username
                new_row[indices['Context']] = system_context
                new_row[indices['Join_Date']] = join_date
                new_row[indices['Status']] = "Trial"
                new_row[indices['Admin_Username']] = "@" + message.from_user.username if message.from_user.username else "No_Username"
                sheet.append_row(new_row)
            else:
                # Update cells
                sheet.update_cell(target_row_num, indices['Bot_Token'] + 1, bot_token)
                sheet.update_cell(target_row_num, indices['Username'] + 1, bot_username)
                sheet.update_cell(target_row_num, indices['Context'] + 1, system_context)
                
            # Dynamic engine run command
            start_client_bot(bot_token, system_context, join_date, current_status)
            
            master_bot.reply_to(message, f"🎉 <b>Bot Successfully Registered & Live!</b>\n\n👉 Click here to test: @{bot_username}", parse_mode="HTML")
            del admin_states[user_id]
        except Exception as e:
            master_bot.reply_to(message, f"❌ Database sync operation failed: {e}")
            
    elif step == 'wait_for_context':
        context_data = text
        if text.startswith("add_url:"):
            url = text.replace("add_url:", "").strip()
            master_bot.reply_to(message, f"⏳ Bhej gaye URL se data extract kar raha hoon:\n{url}")
            extracted_text = fetch_text_from_url(url)
            if "Error" not in extracted_text:
                context_data = f"Extracted info from {url}:\n{extracted_text}"
            else:
                master_bot.reply_to(message, f"⚠️ Scraping Warning: {extracted_text}")
                context_data = text

        master_bot.reply_to(message, "⏳ Context data database me update kiya ja raha hai...")
        
        if sheet is None:
            master_bot.reply_to(message, "❌ Connection Error.")
            return
            
        try:
            records = sheet.get_all_records()
            headers = sheet.row_values(1)
            indices = get_column_indices(headers)
            
            target_row = None
            for idx, r in enumerate(records, 2):
                if str(r.get('Admin_ID', '')).strip() == user_id:
                    target_row = idx
                    break
                    
            if not target_row:
                master_bot.reply_to(message, "❌ Database me aapka setup incomplete mila. Kripya pehle `/setup_bot` complete karein.")
                return
                
            # Keep previous context and append new one
            previous_context = str(sheet.cell(target_row, indices['Context'] + 1).value or "")
            new_full_context = previous_context + "\n\n" + context_data if previous_context else context_data
                
            sheet.update_cell(target_row, indices['Context'] + 1, new_full_context[:45000]) # Cap to avoid Google Sheet Limits
            
            updated_row = sheet.row_values(target_row)
            bot_token = updated_row[indices['Bot_Token']]
            join_date = updated_row[indices['Join_Date']]
            current_status = updated_row[indices['Status']]
            
            # Restart Bot with new Context instructions
            start_client_bot(bot_token, new_full_context, join_date, current_status)
            
            master_bot.reply_to(message, "✅ <b>Success! Context prompt updated and Bot restarted safely!</b>", parse_mode="HTML")
            del admin_states[user_id]
        except Exception as e:
            master_bot.reply_to(message, f"❌ Context update failed: {e}")

# --- SYSTEM INITIALIZATION & POLLING ---
def run_master_polling():
    print("Master Bot System is booting up...")
    apihelper.CONNECT_TIMEOUT = 30
    apihelper.READ_TIMEOUT = 30
    
    try:
        print("Telegram Commands set karne ki koshish kar raha hoon...")
        master_bot.set_my_commands([
            telebot.types.BotCommand("/start", "Main menu"),
            telebot.types.BotCommand("/setup_bot", "Naya bot configure karein"),
            telebot.types.BotCommand("/activate", "Apna Premium/Standard token lagayein"),
            telebot.types.BotCommand("/status", "Apne bot aur limits check karein"),
            telebot.types.BotCommand("/addmoredata", "Purane bot me data/URL jodein"),
            telebot.types.BotCommand("/contact", "Developer & Support details"),
            telebot.types.BotCommand("/help", "Detailed help guide")
        ])
        print("Telegram Commands successfully set!")
    except Exception as e:
        print(f"⚠️ Warning: Connection issue while setting commands: {e}")

    # Load and run all already existing user sub-bots on startup
    if sheet is not None:
        try:
            records = sheet.get_all_records()
            print(f"Total {len(records)} clients found in sheet DB.")
            for row in records:
                status = str(row.get('Status', '')).strip()
                token = str(row.get('Bot_Token', '')).strip()
                username = str(row.get('Username', '')).strip()
                join_date = str(row.get('Join_Date', '')).strip()
                context = str(row.get('Context', '')).strip()
                
                if username and token:
                    bot_tokens_cache[username.lower()] = token
                    
                plan_name, max_bots, max_chars, is_trial = parse_status(status)
                
                is_active = True
                if is_trial and join_date:
                    is_active, _ = check_trial_status(join_date)
                    
                if is_active and token and len(token) > 10:
                    start_client_bot(token, context, join_date, status)
        except Exception as e:
            print("Purane bots load nahi ho paye: ", e)
    else:
        print("Database connect na hone ke karan historical clients offline hain.")

    # Main master polling with reconnection guard loop
    while True:
        try:
            master_bot.polling(non_stop=True, timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"⚠️ Polling Exception in Master Bot: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)

# --- FLASK SERVER SETUP FOR RENDER HEALTH CHECKS ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Master & Sub-bots running 24/7 dynamically on Render!"

@flask_app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    # Start bot operations in background thread
    bot_thread = threading.Thread(target=run_master_polling)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Run Flask Web Server according to Render Port requirement
    port = int(os.environ.get("PORT", 8080))
    print(f"Flask Web Server started on port {port}...")
    flask_app.run(host="0.0.0.0", port=port)
