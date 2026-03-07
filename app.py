<from flask import Flask, request, jsonify
import asyncio, aiohttp, requests, json, binascii, urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import like_pb2, like_count_pb2, uid_generator_pb2

app = Flask(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def load_tokens(server):
    path = "token_ind.json" if server == "IND" else "token_bd.json"
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return [{"token": t} for t in data] if isinstance(data, list) else []
    except: return []

def encrypt_message(plaintext):
    key, iv = b'Yg&tc%DEuh6%Zc^8', b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return binascii.hexlify(cipher.encrypt(pad(plaintext, AES.block_size))).decode('utf-8')

# Profile Check Payload
def create_profile_proto(uid):
    msg = uid_generator_pb2.uid_generator()
    msg.krishna_, msg.teamXdarks = int(uid), 1
    return msg.SerializeToString()

# Like Payload
def create_like_proto(uid, region):
    msg = like_pb2.like()
    msg.uid, msg.region = int(uid), region
    return msg.SerializeToString()

def get_profile_info(uid, server, token):
    url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow" if server == "IND" else "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
    payload = encrypt_message(create_profile_proto(uid))
    headers = {'Authorization': f"Bearer {token}", 'Content-Type': "application/x-www-form-urlencoded", 'ReleaseVersion': "OB52"}
    try:
        resp = requests.post(url, data=bytes.fromhex(payload), headers=headers, verify=False, timeout=10)
        info = like_count_pb2.Info()
        info.ParseFromString(resp.content)
        return info
    except: return None

async def send_like(session, url, payload, token):
    headers = {
        'Authorization': f"Bearer {token['token']}",
        'Content-Type': "application/x-www-form-urlencoded",
        'ReleaseVersion': "OB52",
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)"
    }
    try:
        async with session.post(url, data=bytes.fromhex(payload), headers=headers, timeout=10) as r:
            return r.status
    except: return 500

@app.route('/like', methods=['GET'])
def handle_like():
    uid = request.args.get("uid")
    server = request.args.get("server_name", "IND").upper()
    if not uid: return jsonify({"error": "UID missing"}), 400

    tokens = load_tokens(server)
    if not tokens: return jsonify({"error": "No tokens found"}), 500

    # 1. Pehle profile check karo (Before Likes)
    visit_token = tokens[0]['token']
    before_info = get_profile_info(uid, server, visit_token)
    before_likes = int(before_info.AccountInfo.Likes) if before_info else 0
    player_name = str(before_info.AccountInfo.PlayerNickname) if before_info else "Unknown"

    # 2. Likes Send Karo
    like_url = "https://client.ind.freefiremobile.com/LikeProfile" if server == "IND" else "https://clientbp.ggblueshark.com/LikeProfile"
    
    async def run_tasks():
        payload = encrypt_message(create_like_proto(uid, server))
        async with aiohttp.ClientSession() as session:
            tasks = [send_like(session, like_url, payload, t) for t in tokens[:50]] # Batch of 50
            await asyncio.gather(*tasks)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_tasks())
    loop.close()

    # 3. Baad mein profile check karo (After Likes)
    after_info = get_profile_info(uid, server, visit_token)
    after_likes = int(after_info.AccountInfo.Likes) if after_info else before_likes

    # Final Result Output
    return jsonify({
        "status": "Success",
        "PlayerNickname": player_name,
        "UID": uid,
        "LikesBefore": before_likes,
        "LikesAfter": after_likes,
        "LikesSent": after_likes - before_likes,
        "Server": server
    })
