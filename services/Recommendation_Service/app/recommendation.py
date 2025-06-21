import random

from .broker.redis import redis_client, check_redis_connection
from .recommendation_service import get_start_index, save_start_index
from .redis_recent import push_recent_track_ids, track_recent_key


async def recommend_tracks(user_id, analytics, all_tracks, used_tracks=None):
    redis_connected = await check_redis_connection()
    if not redis_connected:
        print(f"[{user_id}] Redis connection failed. Cannot fetch recommendations.")
        return []

    if used_tracks is None:
        used_tracks = set()

    start_index = await get_start_index(user_id)

    fav_moods = analytics.get("analytics", {}).get("top_moods_from_favorites", [])
    hist_moods = analytics.get("analytics", {}).get("top_moods_from_history", [])
    fav_genres = analytics.get("analytics", {}).get("top_genres_from_favorites", [])
    hist_genres = analytics.get("analytics", {}).get("top_genres_from_history", [])

    moods = fav_moods + hist_moods
    genres = fav_genres + hist_genres

    filtered_by_mood = [t for t in all_tracks if t.get("mood") in moods]
    filtered_by_mood_fav = [t for t in all_tracks if t.get("mood") in fav_moods]
    filtered_by_mood_hist = [t for t in all_tracks if t.get("mood") in hist_moods]

    if len(filtered_by_mood) < 6:
        print(f"[{user_id}] Not enough tracks by mood, applying genre filter.")
        filtered_by_mood = [
            t for t in all_tracks
            if t.get("mood") in fav_moods or t.get("genre") in genres
        ]

    if not filtered_by_mood:
        print(f"[{user_id}] No tracks found after mood+genre filtering, using all.")
        filtered_by_mood = all_tracks
        await save_start_index(user_id, 0)
        print(f"[{user_id}] Resetting index to 0 due to insufficient tracks.")

    available_tracks = [t for t in filtered_by_mood if t["id"] not in used_tracks]

    if len(available_tracks) < 6:
        print(f"[{user_id}] Not enough available tracks, clearing recent history.")
        await redis_client.delete(track_recent_key(user_id))
        available_tracks = all_tracks

    if start_index >= len(available_tracks):
        print(f"[{user_id}] Start index {start_index} exceeds available tracks, resetting to 0.")
        start_index = 0

    selected_tracks = available_tracks[start_index:start_index + 6]
    used_tracks.update([t["id"] for t in selected_tracks])

    await push_recent_track_ids(redis_client, user_id, [t["id"] for t in selected_tracks if t.get("id")])

    if len(selected_tracks) < 6:
        remaining = [t for t in available_tracks if t["id"] not in used_tracks]
        selected_tracks.extend(random.sample(remaining, min(6 - len(selected_tracks), len(remaining))))

    next_index = start_index + len(selected_tracks)
    await save_start_index(user_id, next_index)
    print(f"[{user_id}] Saved next index {next_index} after selection.")

    random.shuffle(selected_tracks)
    return selected_tracks[:6]