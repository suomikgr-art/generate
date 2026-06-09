#!/usr/bin/env python3
"""
login_accounts.py
~~~~~~~~~~~~~~~~~
يُدخل حسابات موجودة في ملف JSON للسيرفر — مرة وحدة لكل حساب ثم يوقف.

الاستخدام:
    python login_accounts.py                    ← يقرأ من accounts.json
    python login_accounts.py ME                 ← يقرأ من TSun-Studio/ACCOUNTS/accounts-ME.json
    python login_accounts.py path/to/file.json  ← يقرأ الملف مباشرة
"""

import asyncio
import json
import os
import sys
import ssl
from datetime import datetime

try:
    import aiohttp
    _AIOHTTP = True
except ImportError:
    _AIOHTTP = False

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from TERBO_FF_EXPERIMENT import MajoRLoGinrEq_pb2, MajoRLoGinrEs_pb2, PorTs_pb2

KEY = b'Yg&tc%DEuh6%Zc^8'
IV  = b'6oyZDr22E3ychjM%'
CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
MAX_CONCURRENT = 10

HR = {
    'User-Agent':      'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection':      'Keep-Alive',
    'Accept-Encoding': 'deflate, gzip',
    'Content-Type':    'application/x-www-form-urlencoded',
    'X-Unity-Version': '2022.3.47f1',
    'X-GA':            'v1 1',
    'ReleaseVersion':  'OB53',
}

def ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def _aes(data, key=KEY, iv=IV):
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(data, 16))

def _build_auth_token(uid, token, timestamp, key, iv):
    uid_hex = hex(uid)[2:]
    pad_map = {7:'000000000', 8:'00000000', 9:'0000000', 10:'000000'}
    uid_pad = pad_map.get(len(uid_hex), '0000000')
    ts_hex  = hex(int(timestamp))[2:]
    if len(ts_hex) == 1: ts_hex = '0' + ts_hex
    enc_tok = _aes(token.encode().hex().encode(), key, iv).hex()
    enc_len = hex(len(enc_tok) // 2)[2:]
    return f'0115{uid_pad}{uid_hex}{ts_hex}00000{enc_len}{enc_tok}'

async def get_access_token(session, uid, password):
    url  = 'https://100067.connect.garena.com/oauth/guest/token/grant'
    data = {
        'uid': uid, 'password': password,
        'response_type': 'token', 'client_type': '2',
        'client_secret': CLIENT_SECRET, 'client_id': '100067',
    }
    async with session.post(url, data=data, ssl=ssl_ctx()) as r:
        if r.status == 200:
            res = await r.json()
            return res.get('open_id'), res.get('access_token')
        return None, None

async def do_major_login(session, payload, access_token):
    h = dict(HR); h['Authorization'] = f'Bearer {access_token}'
    for url in [
        'https://loginbp.ggpolarbear.com/MajorLogin',
        'https://loginbp.common.ggbluefox.com/MajorLogin',
        'https://loginbp.ggblueshark.com/MajorLogin',
    ]:
        try:
            async with session.post(url, data=payload, headers=h, ssl=ssl_ctx()) as r:
                if r.status == 200:
                    return await r.read()
        except Exception:
            continue
    return None

async def get_login_data(session, base_url, payload, token):
    h = dict(HR); h['Authorization'] = f'Bearer {token}'
    async with session.post(
        f'{base_url.rstrip("/")}/GetLoginData',
        data=payload, headers=h, ssl=ssl_ctx()
    ) as r:
        if r.status == 200:
            return await r.read()
        return None

async def tcp_once(ip, port, auth_hex, name):
    """يتصل مرة وحدة — يبعث الـ auth — ينتظر ثانية — يسكر. لا إعادة اتصال."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, int(port)), timeout=8
        )
        writer.write(bytes.fromhex(auth_hex))
        await writer.drain()
        await asyncio.sleep(1)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        print(f'  ✅ [{name}] ظهر وتم الإغلاق')
    except asyncio.TimeoutError:
        print(f'  ⚠️  [{name}] timeout')
    except Exception as e:
        print(f'  ❌ [{name}] خطأ: {e}')

async def login_account(session, account, sem, counter, total):
    uid      = str(account['uid'])
    password = account['password']
    name     = account.get('name', uid)

    async with sem:
        try:
            open_id, access_token = await get_access_token(session, uid, password)
            if not open_id:
                print(f'  ❌ [{name}] OAuth فشل')
                return

            req = MajoRLoGinrEq_pb2.MajorLogin()
            req.event_time        = str(datetime.now())[:-7]
            req.game_name         = 'free fire'
            req.platform_id       = 1
            req.client_version    = '1.123.1'
            req.system_software   = 'Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)'
            req.system_hardware   = 'Handheld'
            req.telecom_operator  = 'Verizon'
            req.network_type      = 'WIFI'
            req.screen_width      = 1920
            req.screen_height     = 1080
            req.screen_dpi        = '280'
            req.processor_details = 'ARM64 FP ASIMD AES VMH | 2865 | 4'
            req.memory            = 3003
            req.gpu_renderer      = 'Adreno (TM) 640'
            req.gpu_version       = 'OpenGL ES 3.1 v1.46'
            req.unique_device_id  = 'Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57'
            req.client_ip         = '223.191.51.89'
            req.language          = 'en'
            req.open_id           = open_id
            req.open_id_type      = '4'
            req.device_type       = 'Handheld'
            req.memory_available.version      = 55
            req.memory_available.hidden_value = 81
            req.access_token      = access_token
            req.platform_sdk_id   = 1
            req.login_by          = 3
            req.login_open_id_type = 4
            payload = _aes(req.SerializeToString())

            ml_raw = await do_major_login(session, payload, access_token)
            if not ml_raw:
                print(f'  ❌ [{name}] MajorLogin فشل')
                return

            login_res = MajoRLoGinrEs_pb2.MajorLoginRes()
            try:    login_res.ParseFromString(ml_raw)
            except: login_res.ParseFromString(ml_raw[5:])

            if not login_res.account_uid:
                print(f'  ❌ [{name}] parse فشل')
                return

            key = bytes(login_res.key) or KEY
            iv  = bytes(login_res.iv)  or IV
            if len(key) != 16: key = KEY
            if len(iv)  != 16: iv  = IV

            gld_raw = await get_login_data(session, login_res.url, payload, login_res.token)
            if not gld_raw:
                print(f'  ❌ [{name}] GetLoginData فشل')
                return

            gld = PorTs_pb2.GetLoginData()
            gld.ParseFromString(gld_raw)
            ip, port = gld.Online_IP_Port.rsplit(':', 1)

            auth = _build_auth_token(
                int(login_res.account_uid), login_res.token,
                int(login_res.timestamp), key, iv
            )
            counter[0] += 1
            print(f'  🟢 [{counter[0]}/{total}] {name}')

            # مرة وحدة فقط — بدون while True أو إعادة اتصال
            await tcp_once(ip, port, auth, name)

        except Exception as e:
            print(f'  ❌ [{name}] استثناء: {e}')

async def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    if arg and os.path.isfile(arg):
        accounts_file = arg
    elif arg and not os.path.isfile(arg):
        region = arg.upper()
        accounts_file = os.path.join('TSun-Studio', 'ACCOUNTS', f'accounts-{region}.json')
    else:
        accounts_file = 'accounts.json'

    if not os.path.exists(accounts_file):
        print(f'❌ الملف غير موجود: {accounts_file}')
        print('الاستخدام:')
        print('  python login_accounts.py                    ← accounts.json')
        print('  python login_accounts.py ME                 ← accounts-ME.json')
        print('  python login_accounts.py path/to/file.json')
        return

    with open(accounts_file, 'r', encoding='utf-8') as f:
        accounts = json.load(f)

    total = len(accounts)
    print(f'\n🎮 FREE FIRE — تسجيل دخول مرة وحدة لكل حساب')
    print(f'📂 {total} حساب من {accounts_file}')
    print(f'{"─"*50}')

    sem     = asyncio.Semaphore(MAX_CONCURRENT)
    counter = [0]

    async with aiohttp.ClientSession(headers=HR) as session:
        tasks = [login_account(session, acc, sem, counter, total) for acc in accounts]
        await asyncio.gather(*tasks)

    # لا يوجد await asyncio.Event().wait() — البرنامج ينتهي هون
    print(f'\n✅ تم: {counter[0]}/{total} حساب')
    print('🏁 انتهى')

if __name__ == '__main__':
    if not _AIOHTTP:
        print('⚠️  aiohttp غير مثبّت — يثبّته الآن...')
        import subprocess, sys as _sys
        subprocess.check_call([_sys.executable, '-m', 'pip', 'install', 'aiohttp'])
        import aiohttp
        _AIOHTTP = True
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n⛔ تم الإيقاف')
