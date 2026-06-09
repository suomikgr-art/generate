# core/game_connect.py
import asyncio, ssl, threading
import aiohttp
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import config.settings as settings
from ui.display import print_success, print_warning

try:
    from TERBO_FF_EXPERIMENT import MajoRLoGinrEq_pb2, MajoRLoGinrEs_pb2, PorTs_pb2
    _PROTO_OK = True
except ImportError:
    _PROTO_OK = False

KEY = b'Yg&tc%DEuh6%Zc^8'
IV  = b'6oyZDr22E3ychjM%'

Hr = {
    'User-Agent':      'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
    'Connection':      'Keep-Alive',
    'Accept-Encoding': 'deflate, gzip',
    'Content-Type':    'application/x-www-form-urlencoded',
    'X-Unity-Version': '2022.3.47f1',
    'X-GA':            'v1 1',
    'ReleaseVersion':  'OB53',
}

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

async def _dec_hex(n):
    f = hex(int(n))[2:]
    return '0' + f if len(f) == 1 else f

async def _enc_packet(hex_str, k, v):
    return AES.new(k, AES.MODE_CBC, v).encrypt(pad(bytes.fromhex(hex_str), 16)).hex()

async def _auth_startup(target, token, timestamp, key, iv):
    uid_hex = hex(target)[2:]
    uid_len = len(uid_hex)
    enc_ts  = await _dec_hex(timestamp)
    enc_tok = token.encode().hex()
    enc_pk  = await _enc_packet(enc_tok, key, iv)
    enc_len = hex(len(enc_pk) // 2)[2:]
    if uid_len == 9:    hdr = '0000000'
    elif uid_len == 8:  hdr = '00000000'
    elif uid_len == 10: hdr = '000000'
    elif uid_len == 7:  hdr = '000000000'
    else:               hdr = '0000000'
    return f'0115{hdr}{uid_hex}{enc_ts}00000{enc_len}{enc_pk}'

async def _get_token(uid, password):
    url = 'https://100067.connect.garena.com/oauth/guest/token/grant'
    data = {
        'uid':           str(uid),
        'password':      password,
        'response_type': 'token',
        'client_type':   '2',
        'client_secret': '2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3',
        'client_id':     '100067',
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, headers=dict(Hr), data=data, ssl=_ssl_ctx()) as r:
                if r.status != 200:
                    return None, None
                res = await r.json()
                return res.get('open_id'), res.get('access_token')
    except Exception as e:
        print_warning(f'[GAME] OAuth error: {e}')
        return None, None

async def _major_login_req(open_id, access_token):
    req = MajoRLoGinrEq_pb2.MajorLogin()
    req.event_time            = str(datetime.now())[:-7]
    req.game_name             = 'free fire'
    req.platform_id           = 1
    req.client_version        = '1.123.1'
    req.system_software       = 'Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)'
    req.system_hardware       = 'Handheld'
    req.telecom_operator      = 'Verizon'
    req.network_type          = 'WIFI'
    req.screen_width          = 1920
    req.screen_height         = 1080
    req.screen_dpi            = '280'
    req.processor_details     = 'ARM64 FP ASIMD AES VMH | 2865 | 4'
    req.memory                = 3003
    req.gpu_renderer          = 'Adreno (TM) 640'
    req.gpu_version           = 'OpenGL ES 3.1 v1.46'
    req.unique_device_id      = 'Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57'
    req.client_ip             = '223.191.51.89'
    req.language              = 'en'
    req.open_id               = open_id
    req.open_id_type          = '4'
    req.device_type           = 'Handheld'
    req.memory_available.version      = 55
    req.memory_available.hidden_value = 81
    req.access_token          = access_token
    req.platform_sdk_id       = 1
    req.login_by              = 3
    req.login_open_id_type    = 4
    req.release_channel       = 'android'
    req.origin_platform_type  = '4'
    req.primary_platform_type = '4'
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(req.SerializeToString(), AES.block_size))

async def _do_major_login(payload, token, region):
    headers = dict(Hr)
    headers['Authorization'] = f'Bearer {token}'
    urls = (
        ['https://loginbp.ggpolarbear.com/MajorLogin',
         'https://loginbp.ggblueshark.com/MajorLogin',
         'https://loginbp.common.ggbluefox.com/MajorLogin']
        if region.upper() in ('ME', 'TH') else
        ['https://loginbp.ggblueshark.com/MajorLogin',
         'https://loginbp.ggpolarbear.com/MajorLogin']
    )
    for url in urls:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, data=payload, headers=headers, ssl=_ssl_ctx()) as r:
                    if r.status == 200:
                        return await r.read()
        except Exception:
            continue
    return None

async def _get_login_data(base_url, payload, token):
    headers = dict(Hr)
    headers['Authorization'] = f'Bearer {token}'
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f'{base_url.rstrip("/")}/GetLoginData',
                data=payload, headers=headers, ssl=_ssl_ctx(),
            ) as r:
                if r.status == 200:
                    return await r.read()
    except Exception as e:
        print_warning(f'[GAME] GetLoginData: {e}')
    return None

async def _tcp_once(ip, port, auth_token, name):
    """يتصل مرة وحدة — يبعث الـ auth packet — يسكر فورًا."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, int(port)), timeout=8
        )
        writer.write(bytes.fromhex(auth_token))
        await writer.drain()
        # انتظر ثانية عشان السيرفر يسجّل الحساب قبل نقفل
        await asyncio.sleep(1)
        print_success(f'[GAME] [{name}] ظهر على السيرفر')
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
    except asyncio.TimeoutError:
        print_warning(f'[GAME] [{name}] timeout')
    except Exception as e:
        print_warning(f'[GAME] [{name}] خطأ TCP: {e}')

async def _run_login(uid_garena, password, region, account_name, uid_str):
    open_id, access_token = await _get_token(uid_garena, password)
    if not open_id:
        print_warning(f'[GAME] OAuth فشل لـ {account_name}')
        return

    payload  = await _major_login_req(open_id, access_token)
    response = await _do_major_login(payload, access_token, region)
    if not response:
        print_warning(f'[GAME] MajorLogin فشل لـ {account_name}')
        return

    login_res = MajoRLoGinrEs_pb2.MajorLoginRes()
    try:    login_res.ParseFromString(response)
    except: login_res.ParseFromString(response[5:])

    if not login_res.account_uid:
        print_warning(f'[GAME] Parse فشل لـ {account_name}')
        return

    gld_raw = await _get_login_data(login_res.url, payload, login_res.token)
    if not gld_raw:
        print_warning(f'[GAME] GetLoginData فشل لـ {account_name}')
        return

    gld = PorTs_pb2.GetLoginData()
    gld.ParseFromString(gld_raw)
    if ':' not in gld.Online_IP_Port:
        print_warning(f'[GAME] IP:Port غير موجود لـ {account_name}')
        return
    ip, port = gld.Online_IP_Port.split(':')

    auth = await _auth_startup(
        int(login_res.account_uid), login_res.token,
        int(login_res.timestamp), login_res.key, login_res.iv
    )

    # مرة وحدة فقط — لا إعادة اتصال
    await _tcp_once(ip, port, auth, account_name)


def connect_account_to_server(uid_str, jwt_token, region, account_name,
                               uid_garena='', password='',
                               open_id='', access_token=''):
    if not _PROTO_OK:
        print_warning('[GAME] protobuf غير متاح')
        return

    uid_g = uid_garena or uid_str

    def _thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                _run_login(uid_g, password, region, account_name, uid_str)
            )
        except Exception as e:
            print_warning(f'[GAME] خطأ: {e}')
        finally:
            try: loop.close()
            except: pass

    threading.Thread(target=_thread, daemon=True).start()
