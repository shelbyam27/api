from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import instaloader
import requests
import re
import datetime
import httpx
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InstagramInfo(BaseModel):
    username: str
    full_name: str
    biography: str
    website: str
    num_posts: int
    followers: int
    following: int
    id: int
    fb_id: str
    is_private: bool
    created: str
    verified: bool = False 


class TikTokInfo(BaseModel):
    user_id: str
    unique_id: str
    nickname: str
    follower_count: int
    following_count: int
    likes_count: int
    video_count: int
    biography: str
    verified: bool
    sec_uid: str
    comment_settings: int
    is_private: bool
    region: str
    heart_count: int
    digg_count: int
    friend_count: int
    profile_pic_url: str
    created: str

SESSION_USER = "sikritpipelkiw"
SESSION_PATH = os.path.join(os.path.dirname(__file__), "sessions", f"session-{SESSION_USER}")

@app.get("/instagram/{username}", response_model=InstagramInfo)
def get_instagram_info(username: str):
    L = instaloader.Instaloader()
    try:
        L.load_session_from_file(SESSION_USER, filename=SESSION_PATH)
        profile = instaloader.Profile.from_username(L.context, username)
        return InstagramInfo(
            username=profile.username,
            full_name=profile.full_name,
            biography=profile.biography,
            website=profile.external_url or "",
            num_posts=profile.mediacount,
            followers=profile.followers,
            following=profile.followees,
            id=profile.userid,
            fb_id=getattr(profile, "fbid", ""),
            is_private=profile.is_private,
            created=str(getattr(profile, "date_joined", "")),
            verified=profile.is_verified
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Error: {e}")

@app.get("/instagram/{username}/profile-pic-proxy")
async def ig_profile_pic_proxy(username: str):
    try:
        L = instaloader.Instaloader()
        L.load_session_from_file(SESSION_USER, filename=SESSION_PATH)
        profile = instaloader.Profile.from_username(L.context, username)
        pic_url = getattr(profile, "profile_pic_url_hd", profile.profile_pic_url)
        async with httpx.AsyncClient() as client:
            pic = await client.get(pic_url)
            mtype = "image/jpeg" if pic_url.endswith(".jpg") else "image/png"
            return Response(content=pic.content, media_type=mtype)
    except Exception as e:
        # Fallback: avatar huruf
        fallback_url = f"https://ui-avatars.com/api/?name={username}&background=eee&color=222"
        async with httpx.AsyncClient() as client:
            pic = await client.get(fallback_url)
            return Response(content=pic.content, media_type="image/png")

@app.get("/instagram/{username}/stories")
def get_instagram_stories(username: str):
    try:
        L = instaloader.Instaloader()
        L.load_session_from_file(SESSION_USER, filename=SESSION_PATH)
        profile = instaloader.Profile.from_username(L.context, username)
        stories = []
        for story in L.get_stories(userids=[profile.userid]):
            for item in story.get_items():
                stories.append({
                    "url": item.url,
                    "type": item.typename,
                    "taken_at": str(item.date_utc)
                })
        if not stories:
            if profile.is_private and not profile.followed_by_viewer:
                raise HTTPException(status_code=403, detail="Akun private & kamu tidak follow")
            else:
                raise HTTPException(status_code=204, detail="Tidak ada story aktif")
        return {"stories": stories}
    except instaloader.exceptions.ProfileNotExistsException:
        raise HTTPException(status_code=404, detail="Username tidak ditemukan!")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error backend: {e}")

@app.get("/instagram/{username}/profile-pic")
def get_instagram_profile_pic(username: str):
    try:
        L = instaloader.Instaloader()
        L.load_session_from_file(SESSION_USER, filename=SESSION_PATH)
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "profile_pic_url": profile.profile_pic_url,
            "profile_pic_url_hd": getattr(profile, "profile_pic_url_hd", profile.profile_pic_url)
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Error: {e}")

@app.get("/tiktok/{username}", response_model=TikTokInfo)
def get_tiktok_info(username: str):
    url = f"https://www.tiktok.com/@{username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Error: Unable to fetch profile. Status code: {response.status_code}")
    html_content = response.text

    patterns = {
        'user_id': r'"webapp.user-detail":{"userInfo":{"user":{"id":"(\d+)"',
        'unique_id': r'"uniqueId":"(.*?)"',
        'nickname': r'"nickname":"(.*?)"',
        'followers': r'"followerCount":(\d+)',
        'following': r'"followingCount":(\d+)',
        'likes': r'"heartCount":(\d+)',
        'videos': r'"videoCount":(\d+)',
        'signature': r'"signature":"(.*?)"',
        'verified': r'"verified":(true|false)',
        'secUid': r'"secUid":"(.*?)"',
        'commentSetting': r'"commentSetting":(\d+)',
        'privateAccount': r'"privateAccount":(true|false)',
        'region': r'"ttSeller":false,"region":"([^"]*)"',
        'heart': r'"heart":(\d+)',
        'diggCount': r'"diggCount":(\d+)',
        'friendCount': r'"friendCount":(\d+)',
        'profile_pic': r'"avatarLarger":"(.*?)"',
        'create_time': r'"createTime":(\d+)'  
    }
    info = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, html_content)
        info[key] = match.group(1) if match else ""

    int_fields = [
        'followers', 'following', 'likes', 'videos', 'commentSetting',
        'heart', 'diggCount', 'friendCount', 'create_time'
    ]
    for key in int_fields:
        info[key] = int(info.get(key, 0) or 0)
    info['verified'] = info['verified'] == 'true'
    info['is_private'] = info['privateAccount'] == 'true'
    info['profile_pic_url'] = info.get('profile_pic', '').replace('\\u002F', '/')

    if info['create_time']:
        created_str = datetime.datetime.utcfromtimestamp(info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
    else:
        created_str = ""

    return TikTokInfo(
        user_id=info.get('user_id', ''),
        unique_id=info.get('unique_id', ''),
        nickname=info.get('nickname', ''),
        follower_count=info.get('followers', 0),
        following_count=info.get('following', 0),
        likes_count=info.get('likes', 0),
        video_count=info.get('videos', 0),
        biography=info.get('signature', ''),
        verified=info.get('verified', False),
        sec_uid=info.get('secUid', ''),
        comment_settings=info.get('commentSetting', 0),
        is_private=info.get('is_private', False),
        region=info.get('region', ''),
        heart_count=info.get('heart', 0),
        digg_count=info.get('diggCount', 0),
        friend_count=info.get('friendCount', 0),
        profile_pic_url=info.get('profile_pic_url', ''),
        created=created_str
    )

class RobloxUserInfo(BaseModel):
    user_id: int
    username: str
    display_name: str
    description: str
    is_banned: bool
    has_verified_badge: bool
    friends: int
    followers: int
    following: int
    created: str
    avatar: str
    previous_usernames: list[str]
    is_online: bool
    last_online: str
    last_location: str = None 

@app.get("/roblox/profile/{username}", response_model=RobloxUserInfo)
def roblox_userinfo(username: str):

    user_url = f"https://users.roblox.com/v1/usernames/users"
    profile_url = "https://users.roblox.com/v1/users/"
    avatar_url = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
    headers = {"Content-Type": "application/json"}
    r = requests.post(user_url, headers=headers, json={"usernames":[username],"excludeBannedUsers":False})
    j = r.json()
    if not j.get('data') or len(j['data'])==0:
        raise HTTPException(status_code=404, detail="User tidak ditemukan!")
    uid = j['data'][0]['id']
    p = requests.get(profile_url+str(uid)).json()
    img_req = requests.get(f"{avatar_url}?userIds={uid}&size=180x180&format=Png&isCircular=true").json()
    avatar_img = img_req['data'][0]['imageUrl'] if img_req.get("data") else ""
    prev_req = requests.get(f"https://users.roblox.com/v1/users/{uid}/username-history?limit=50&sortOrder=Desc").json()
    prev = [n['name'] for n in prev_req.get('data',[])] if prev_req.get('data') else []
    stat = requests.get(f"https://friends.roblox.com/v1/users/{uid}/friends/count").json()
    friends = stat.get('count',0)
    followers = requests.get(f"https://friends.roblox.com/v1/users/{uid}/followers/count").json().get('count',0)
    following = requests.get(f"https://friends.roblox.com/v1/users/{uid}/followings/count").json().get('count',0)
    presence = requests.post("https://presence.roblox.com/v1/presence/users", json={"userIds":[uid]}).json()
    userp = presence.get('userPresences',[{}])[0]
    is_online = userp.get('userPresenceType',0) == 2
    last_online = userp.get("lastOnline", "")
    last_location = userp.get("lastLocation", "")
    # Response
    return RobloxUserInfo(
        user_id=uid,
        username=p.get('name',''),
        display_name=p.get('displayName',''),
        description=p.get('description',''),
        is_banned=p.get('isBanned',False),
        has_verified_badge=p.get('hasVerifiedBadge',False),
        friends=friends,
        followers=followers,
        following=following,
        created=p.get('created',''),
        avatar=avatar_img,
        previous_usernames=prev,
        is_online=is_online,
        last_online=last_online,
        last_location=last_location
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
