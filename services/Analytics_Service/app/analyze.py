from collections import Counter
from typing import List

def analyze_play_history(track_list: List[dict]):
    total_tracks = len(track_list)

    if total_tracks == 0:
        return {
            'total_tracks': 0,
            'avg_duration': 0,
            'avg_release_year': 0,
            'top_genres': [],
            'top_moods': []
        }

    durations = [
        entry['track'].get('duration')
        for entry in track_list
        if entry['track'].get('duration') is not None
    ]
    total_duration = sum(durations)
    avg_duration = total_duration / len(durations) if durations else 0

    years = [
        entry['track'].get('release_year')
        for entry in track_list
        if entry['track'].get('release_year') is not None
    ]
    total_years = sum(years)
    avg_release_year = total_years / len(years) if years else 0

    genres = [
        entry['track'].get('genre')
        for entry in track_list
        if entry['track'].get('genre') is not None
    ]
    top_genres = [item[0] for item in Counter(genres).most_common(3)]

    moods = [
        entry['track'].get('mood')
        for entry in track_list
        if entry['track'].get('mood') is not None
    ]
    top_moods = [item[0] for item in Counter(moods).most_common(2)]

    return {
        'total_tracks': total_tracks,
        'avg_duration': avg_duration,
        'avg_release_year': avg_release_year,
        'top_genres': top_genres,
        'top_moods': top_moods
    }


def analyze_favorites(favorites: List[dict]):
    total_favorites = len(favorites)

    if total_favorites == 0:
        return {
            'total_favorites': 0,
            'avg_duration': 0,
            'avg_release_year': 0,
            'top_genres': [],
            'top_moods': [],
            'top_favorites': []
        }

    durations = [
        entry.get('duration')
        for entry in favorites
        if entry.get('duration') is not None
    ]
    avg_duration = sum(durations) / len(durations) if durations else 0

    years = [
        entry.get('release_year')
        for entry in favorites
        if entry.get('release_year') is not None
    ]
    avg_release_year = sum(years) / len(years) if years else 0

    genres = [
        entry.get('genre')
        for entry in favorites
        if entry.get('genre') is not None
    ]
    top_genres = [item[0] for item in Counter(genres).most_common(3)]

    moods = [
        entry.get('mood')
        for entry in favorites
        if entry.get('mood') is not None
    ]
    top_moods = [item[0] for item in Counter(moods).most_common(2)]

    sorted_favorites = sorted(favorites, key=lambda x: x.get('timestamp', ''), reverse=True)
    top_favorites = [entry['id'] for entry in sorted_favorites[:5] if 'id' in entry]

    return {
        'total_favorites': total_favorites,
        'avg_duration': avg_duration,
        'avg_release_year': avg_release_year,
        'top_genres': top_genres,
        'top_moods': top_moods,
        'top_favorites': top_favorites
    }

