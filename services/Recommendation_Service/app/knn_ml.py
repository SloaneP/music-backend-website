from uuid import UUID

from sklearn.neighbors import NearestNeighbors
import numpy as np
from .fetch_from_music_service.fetch_analytics import fetch_user_analytics

# Функция для поиска похожих пользователей
async def find_similar_users(user_id: UUID, all_user_analytics: list) -> list:
    """
    Находит похожих пользователей на основе их аналитики с использованием K-NN.
    """
    # Собираем вектора предпочтений для всех пользователей
    user_vectors = []
    for user_analytics in all_user_analytics:
        # Пример того, как можно превратить аналитику в вектор признаков
        # Мы можем использовать различные метрики, например, для жанров и настроений
        vector = [
            len(user_analytics.get('top_genres_from_history', [])),
            len(user_analytics.get('top_moods_from_history', [])),
            user_analytics.get('avg_duration_from_history', 0),
            user_analytics.get('avg_release_year_from_history', 0)
        ]
        user_vectors.append(vector)

    # Преобразуем вектора в массив NumPy
    X = np.array(user_vectors)

    # Инициализация модели K-NN
    model = NearestNeighbors(n_neighbors=5, algorithm='auto')
    model.fit(X)

    # Получаем вектор текущего пользователя
    current_user_analytics = next(u for u in all_user_analytics if u["user_id"] == user_id)
    current_user_vector = np.array([
        len(current_user_analytics.get('top_genres_from_history', [])),
        len(current_user_analytics.get('top_moods_from_history', [])),
        current_user_analytics.get('avg_duration_from_history', 0),
        current_user_analytics.get('avg_release_year_from_history', 0)
    ]).reshape(1, -1)

    # Находим K похожих пользователей
    distances, indices = model.kneighbors(current_user_vector)

    # Возвращаем IDs похожих пользователей
    similar_user_ids = [all_user_analytics[i]["user_id"] for i in indices[0]]
    return similar_user_ids