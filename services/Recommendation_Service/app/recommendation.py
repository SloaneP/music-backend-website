import random
from .recommendation_service import get_start_index, save_start_index

async def recommend_tracks(user_id, analytics, all_tracks, recent_ids, used_tracks=None):
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

    available_tracks = [t for t in filtered_by_mood if t["id"] not in used_tracks]

    if start_index >= len(available_tracks):
        start_index = 0

    selected_tracks = available_tracks[start_index:start_index + 6]
    used_tracks.update([t["id"] for t in selected_tracks])

    if len(selected_tracks) < 6:
        remaining = [t for t in available_tracks if t["id"] not in used_tracks]
        selected_tracks.extend(random.sample(remaining, min(6 - len(selected_tracks), len(remaining))))

    next_index = start_index + len(selected_tracks)
    await save_start_index(user_id, next_index)

    random.shuffle(selected_tracks)
    return selected_tracks[:6]