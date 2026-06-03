import telebot
from telebot import types
import requests
import json
import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = '8474746750:AAGiYxECSZ3T-V6UQUN9y0umUkUXu1kI9Pg'
ADMIN_ID  = 6601184733
API_URL   = 'https://ppcp.rudochk.com/check'
MAX_FILE  = 500

PREMIUM_EMOJI_IDS = {
    "✅": "5123163417326126159",
    "❌": "5121063440311386962",
    "🔥": "5116414868357907335",
    "⚡": "5219943216781995020",
    "💳": "5447453226498552490",
    "💠": "5870498447068502918",
    "📝": "5444860552310457690",
    "🌐": "5447602197439218445",
    "📊": "4911241630633165627",
    "📦": "5303102515301083665",
    "📋": "5305618829265628111",
    "⏳": "5303382628773161521",
    "🚀": "5303534082204920602",
    "⚠️": "5305473345838410805",
    "💎": "5305726937887433606",
    "👋": "5134653266591744867",
    "💡": "5231264265242954153",
    "📈": "5134457377428341766",
    "🔌": "5305622454218024328",
    "⭐": "5801104080646444587",
    "👑": "5303547611351902889",
    "🔍": "5305346287820895195",
    "💥": "5122933683820430249",
    "🆔": "5447311106030726740",
    "👤": "5445174334031166029",
    "📅": "5082628525303792441",
    "🔄": "5454245266305604993",
    "🏦": "5303159080020372094",
    "💰": "5303159080020372094",
}

def pe(text):
    """Wrap emojis with Telegram premium animated emoji tags."""
    for emoji, eid in PREMIUM_EMOJI_IDS.items():
        text = text.replace(emoji, f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>')
    return text

bot = telebot.TeleBot(BOT_TOKEN, num_threads=10)
USERS_FILE = 'ppcp_users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE) as f:
                d = json.load(f)
                return set(d.get('approved', [])), d.get('pending', {})
        except:
            pass
    return set(), {}

def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump({'approved': list(approved_users), 'pending': pending_requests}, f, indent=2)

approved_users, pending_requests = load_users()

def is_approved(uid):
    return uid == ADMIN_ID or uid in approved_users

def require_approval(fn):
    def wrapper(msg):
        if not is_approved(msg.from_user.id):
            send_safe(msg.chat.id,
                "𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗 🚫\n\n"
                "You don't have access to this bot.\n"
                "Use /request to apply for access.")
            return
        return fn(msg)
    return wrapper

user_cooldowns = {}

def check_cooldown(chat_id, kind):
    now   = time.time()
    limit = 5 if kind == 'chk' else 15
    last  = user_cooldowns.get(f"{chat_id}_{kind}", 0)
    diff  = now - last
    if diff < limit:
        return False, int(limit - diff) + 1
    user_cooldowns[f"{chat_id}_{kind}"] = now
    return True, 0

def send_safe(chat_id, text, **kw):
    try:
        return bot.send_message(chat_id, text, **kw)
    except:
        return None

def edit_safe(chat_id, msg_id, text, **kw):
    try:
        return bot.edit_message_text(text, chat_id, msg_id, **kw)
    except:
        return None

def get_card_info(number):
    info = {'brand': 'Unknown', 'type': 'Unknown', 'bank': 'Unknown',
            'country': 'Unknown', 'flag': '🌍', 'level': 'Unknown'}
    try:
        r = requests.get(
            f'https://lookup.binlist.net/{number[:6]}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
            timeout=5, verify=False
        )
        if r.status_code == 200:
            d = r.json()
            if d.get('scheme'):  info['brand']  = d['scheme'].upper()
            if d.get('type'):    info['type']   = d['type'].title()
            if d.get('brand'):   info['level']  = d['brand'].title()
            if d.get('bank', {}).get('name'):
                info['bank'] = d['bank']['name'].title()
            if d.get('country', {}).get('name'):
                info['country'] = d['country']['name'].upper()
            if d.get('country', {}).get('alpha2'):
                a2 = d['country']['alpha2']
                info['flag'] = ''.join(chr(127397 + ord(c)) for c in a2.upper())
    except:
        pass
    return info

def check_card(card):
    card = card.strip()
    if not card:
        return None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/json',
    }
    try:
        r = requests.post(API_URL, headers=headers,
                          data=json.dumps({"card": card}),
                          verify=False, timeout=65)
        text = r.text.strip()
        if not text:
            return {'status': 'DEAD', 'card': card, 'message': 'Empty response', 'price': ''}
        try:
            data = r.json()
        except:
            return {'status': 'DEAD', 'card': card, 'message': 'Invalid response', 'price': ''}
        return {
            'status':  str(data.get('status', '')).upper(),
            'card':    data.get('card', card),
            'message': data.get('message', ''),
            'price':   data.get('price', ''),
        }
    except Exception as e:
        return {'status': 'DEAD', 'card': card, 'message': f'Error: {str(e)[:50]}', 'price': ''}

def fmt_result(result, card_info, username='User'):
    status = result['status']
    price  = f" | 💰 {result['price']}" if result['price'] else ''

    if 'CHARGED' in status:
        icon, label = '💎', 'Charged'
    elif 'CCN' in status:
        icon, label = '⚠️', 'CVV Mismatch'
    else:
        icon, label = '❌', 'Declined'

    return pe(
        f"{icon} <b>{label}</b>\n"
        f"<blockquote>💳 Card: <code>{result['card']}</code></blockquote>"
        f"<blockquote>📝 Response: {result['message']}{price}</blockquote>"
        f"<blockquote>🌐 Gateway: 🔥 PPCP</blockquote>"
        f"<blockquote>🏦 Bank: {card_info.get('flag','🌍')} {card_info.get('bank','Unknown')} | {card_info.get('country','Unknown')}</blockquote>"
        f"<blockquote>💠 Info: {card_info.get('brand','Unknown')} - {card_info.get('type','Unknown')} - {card_info.get('level','Unknown')}</blockquote>"
        f"<blockquote>👤 By: @{username}</blockquote>"
    )


@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = msg.from_user.id
    if not is_approved(uid):
        send_safe(msg.chat.id,
            "𝗣𝗣𝗖𝗣 𝗖𝗛𝗘𝗖𝗞𝗘𝗥 💳\n\n"
            "You need access to use this bot.\n"
            "Use /request to apply.")
        return

    text = pe(
        "💳 𝗣𝗣𝗖𝗣 𝗖𝗛𝗘𝗖𝗞𝗘𝗥\n\n"
        "💥 /pchk — Single card check\n"
        "📦 /pfile — Check cards from file\n"
    )
    if uid == ADMIN_ID:
        text += pe(
            "\n👑 𝗔𝗗𝗠𝗜𝗡\n\n"
            "👤 /users — Approved users\n"
            "⏳ /pending — Pending requests\n"
            "📢 /broadcast — Broadcast message\n"
        )
    text += pe("\n💡 𝗕𝗼𝘁 𝗕𝘆: @Xyoshy")
    send_safe(msg.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['request'])
def cmd_request(msg):
    uid = msg.from_user.id
    if is_approved(uid):
        send_safe(msg.chat.id, "✅ You already have access!")
        return
    if uid in pending_requests:
        send_safe(msg.chat.id, "⏳ Your request is already pending...")
        return
    uname = msg.from_user.username or 'No username'
    fname = msg.from_user.first_name or 'Unknown'
    pending_requests[uid] = {'username': uname, 'name': fname,
                              'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    save_users()
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"),
        types.InlineKeyboardButton("❌ Deny",    callback_data=f"deny_{uid}")
    )
    send_safe(ADMIN_ID,
        f"📥 New Access Request\n\n"
        f"👤 {fname}\n"
        f"🔗 @{uname}\n"
        f"🆔 {uid}",
        reply_markup=markup)
    send_safe(msg.chat.id, "📤 Request sent! Waiting for admin approval...")


@bot.callback_query_handler(func=lambda c: c.data.startswith(('approve_','deny_')))
def cb_approval(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Admin only!")
        return
    action, uid = call.data.split('_', 1)
    uid = int(uid)
    if action == 'approve':
        approved_users.add(uid)
        pending_requests.pop(uid, None)
        save_users()
        bot.answer_callback_query(call.id, "✅ Approved!")
        edit_safe(call.message.chat.id, call.message.message_id, f"✅ User {uid} approved!")
        send_safe(uid, "🎉 Access granted! Type /start to begin.")
    else:
        pending_requests.pop(uid, None)
        save_users()
        bot.answer_callback_query(call.id, "❌ Denied!")
        edit_safe(call.message.chat.id, call.message.message_id, f"❌ User {uid} denied!")
        send_safe(uid, "🚫 Your request was denied.")


@bot.message_handler(commands=['pchk'])
@require_approval
def cmd_pchk(msg):
    ok, wait = check_cooldown(msg.chat.id, 'chk')
    if not ok:
        send_safe(msg.chat.id, f"⏳ Wait {wait}s before checking again.")
        return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        send_safe(msg.chat.id, "Usage: /pchk card|mm|yy|cvv")
        return
    card = parts[1].strip()
    status_msg = send_safe(msg.chat.id, f"⏳ Checking...\n💳 {card}")
    if not status_msg:
        return
    result    = check_card(card)
    card_info = get_card_info(card.split('|')[0])
    uname     = msg.from_user.username or 'User'
    edit_safe(msg.chat.id, status_msg.message_id,
              fmt_result(result, card_info, uname), parse_mode='HTML')


@bot.message_handler(commands=['pfile'])
@require_approval
def cmd_pfile(msg):
    send_safe(msg.chat.id,
        f"📁 Send your .txt file\n"
        f"One card per line: card|mm|yy|cvv\n"
        f"Max {MAX_FILE} cards.")


@bot.message_handler(content_types=['document'])
@require_approval
def handle_file(msg):
    if not msg.document or not msg.document.file_name.endswith('.txt'):
        send_safe(msg.chat.id, "❌ Please send a .txt file.")
        return

    status_msg = send_safe(msg.chat.id, "⏳ Reading file...")
    if not status_msg:
        return

    try:
        file_info = bot.get_file(msg.document.file_id)
        file_data = bot.download_file(file_info.file_path)
        cards = [c.strip() for c in file_data.decode('utf-8').splitlines() if c.strip()]
    except Exception as e:
        edit_safe(msg.chat.id, status_msg.message_id, f"❌ Error: {e}")
        return

    if not cards:
        edit_safe(msg.chat.id, status_msg.message_id, "❌ No cards found.")
        return

    if len(cards) > MAX_FILE:
        cards = cards[:MAX_FILE]

    edit_safe(msg.chat.id, status_msg.message_id,
        f"⏳ Checking {len(cards)} cards...")

    def run():
        results  = []
        charged  = []
        ccn_list = []

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(check_card, card): card for card in cards}
            for i, future in enumerate(as_completed(futures), 1):
                try:
                    res = future.result()
                except Exception as e:
                    card = futures[future]
                    res  = {'status':'DEAD','card':card,'message':str(e)[:50],'price':''}
                results.append(res)
                if 'CHARGED' in res['status']:
                    charged.append(res)
                elif 'CCN' in res['status']:
                    ccn_list.append(res)
                if i % 20 == 0 or i == len(cards):
                    edit_safe(msg.chat.id, status_msg.message_id,
                        f"⏳ Checked {i}/{len(cards)}\n"
                        f"💎 Charged: {len(charged)} | ⚠️ CCN: {len(ccn_list)}")

        dead = len(results) - len(charged) - len(ccn_list)
        edit_safe(msg.chat.id, status_msg.message_id,
            f"✅ Done!\n\n"
            f"💎 Charged: {len(charged)}\n"
            f"⚠️ CCN: {len(ccn_list)}\n"
            f"❌ Dead: {dead}\n"
            f"📊 Total: {len(results)}",
            parse_mode='HTML')

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        if charged:
            fname = f'charged_{ts}.txt'
            with open(fname, 'w') as f:
                for r in charged:
                    price = f"  {r['price']}" if r['price'] else ''
                    f.write(f"CHARGE\n{r['card']}\n{r['message']}{price}\n\n")
            with open(fname, 'rb') as f:
                bot.send_document(msg.chat.id, f,
                    caption=f"💎 {len(charged)} Charged Cards",
                    visible_file_name=fname)
            os.remove(fname)

        if ccn_list:
            fname = f'ccn_{ts}.txt'
            with open(fname, 'w') as f:
                for r in ccn_list:
                    price = f"  {r['price']}" if r['price'] else ''
                    f.write(f"CCN\n{r['card']}\n{r['message']}{price}\n\n")
            with open(fname, 'rb') as f:
                bot.send_document(msg.chat.id, f,
                    caption=f"⚠️ {len(ccn_list)} CCN Cards",
                    visible_file_name=fname)
            os.remove(fname)

    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=['users'])
def cmd_users(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    if not approved_users:
        send_safe(msg.chat.id, "📭 No approved users.")
        return
    text = "👥 Approved Users\n\n"
    for i, uid in enumerate(approved_users, 1):
        text += f"{i}. {uid}\n"
    send_safe(msg.chat.id, text)


@bot.message_handler(commands=['pending'])
def cmd_pending(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    if not pending_requests:
        send_safe(msg.chat.id, "📭 No pending requests.")
        return
    text = "⏳ Pending Requests\n\n"
    for uid, info in pending_requests.items():
        text += f"👤 {info['name']} | @{info['username']} | {uid}\n"
    send_safe(msg.chat.id, text)


@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        send_safe(msg.chat.id, "Usage: /broadcast message")
        return
    ok = fail = 0
    for uid in approved_users:
        try:
            send_safe(uid, parts[1].strip())
            ok += 1
        except:
            fail += 1
        time.sleep(0.3)
    send_safe(msg.chat.id, f"✅ Sent: {ok} | ❌ Failed: {fail}")


if __name__ == '__main__':
    print("💳 Bot Started!")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Crashed: {e}, restarting in 5s...")
            time.sleep(5)
