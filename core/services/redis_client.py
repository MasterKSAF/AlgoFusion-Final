# core/services/redis_client.py
"""
Redis клиент для очередей и Pub/Sub.
Используется всеми контейнерами для коммуникации.
"""

import redis
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from shared.utils.json_utils import json_dumps, json_loads
from shared.utils.logger import setup_logger

logger = setup_logger("core.services.redis_client")


class RedisClient:
    """Обёртка над Redis для очередей и Pub/Sub."""

    RECENT_EVENTS_KEY = "files:events:recent"
    RECENT_EVENTS_LIMIT = 200

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: int = 0
    ):
        self.host = host or os.getenv("REDIS_HOST", "redis")
        self.port = int(port or os.getenv("REDIS_PORT", 6379))
        self.db = db
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        logger.info(f"RedisClient инициализирован: {self.host}:{self.port}")

    @property
    def client(self) -> redis.Redis:
        """Ленивая инициализация клиента."""
        if self._client is None:
            try:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    health_check_interval=30  # ← Авто-переподключение
                )
                # Проверка подключения
                self._client.ping()
                logger.info("Подключение к Redis успешно")
            except redis.ConnectionError as e:
                logger.error(f"Ошибка подключения к Redis: {e}")
                raise
        return self._client

    def publish_event(self, channel: str, event: Dict[str, Any]) -> int:
        """Публикация события в канал."""
        try:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
            payload = json_dumps(event)
            pipe = self.client.pipeline()
            pipe.lpush(self.RECENT_EVENTS_KEY, self._ensure_str(payload))
            pipe.ltrim(self.RECENT_EVENTS_KEY, 0, self.RECENT_EVENTS_LIMIT - 1)
            pipe.publish(channel, self._ensure_str(payload))
            _, _, result = pipe.execute()
            logger.debug(f"Опубликовано событие в {channel}: {event.get('type')}")
            return result  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Ошибка публикации события: {e}")
            return 0

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent UI events, oldest first."""
        try:
            raw_items = self.client.lrange(self.RECENT_EVENTS_KEY, 0, max(0, limit - 1))
            events: List[Dict[str, Any]] = []
            for item in reversed(raw_items):
                try:
                    events.append(json_loads(self._ensure_str(item)))
                except Exception as exc:
                    logger.debug("Skipping invalid recent event payload: %s", exc)
            return events
        except Exception as e:
            logger.error(f"Ошибка получения recent events: {e}")
            return []

    def push_to_queue(self, queue: str, job_payload: str, priority: int = 0) -> int:
        """Добавление задания в очередь (с приоритетом)."""
        try:
            if priority > 0:
                queue = f"priority:{priority}:{queue}"
            result = self.client.lpush(queue, self._ensure_str(job_payload))
            logger.debug(f"Добавлено в очередь {queue}")
            return result
        except Exception as e:
            logger.error(f"Ошибка добавления в очередь {queue}: {e}")
            return 0

    def pop_from_queue(self, queue: str, timeout: int = 0) -> Optional[str]:
        """Получение задания из очереди (блокирующее)."""
        try:
            if timeout > 0:
                result = self.client.brpop(queue, timeout=timeout)
            else:
                result = self.client.rpop(queue)
            if result:
                value = result[1] if isinstance(result, tuple) else result
                return self._ensure_str(value)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения из очереди {queue}: {e}")
            return None

    def subscribe(self, channels: List[str]) -> redis.client.PubSub:
        """Подписка на каналы."""
        try:
            if self._pubsub is None:
                self._pubsub = self.client.pubsub(ignore_subscribe_messages=True)
            self._pubsub.subscribe(*channels)
            logger.info(f"Подписка на каналы: {channels}")
            return self._pubsub
        except Exception as e:
            logger.error(f"Ошибка подписки: {e}")
            raise

    def get_file_status(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Получение статуса файла из Redis."""
        try:
            key = f"file:{file_id}:status"
            data = self.client.get(key)
            if data is None:
                return None
            return json_loads(self._ensure_str(data))
        except Exception as e:
            logger.error(f"Ошибка получения статуса файла {file_id}: {e}")
            return None

    def set_file_status(self, file_id: str, status: Dict[str, Any], ttl: int = 3600) -> bool:
        """Установка статуса файла в Redis."""
        try:
            key = f"file:{file_id}:status"
            payload = json_dumps(status)
            self.client.setex(key, ttl, self._ensure_str(payload))
            logger.debug(f"Статус файла {file_id} обновлён")
            return True
        except Exception as e:
            logger.error(f"Ошибка установки статуса файла {file_id}: {e}")
            return False

    def get_all_files(self) -> List[Dict[str, Any]]:
        """Получение всех файлов из Redis."""
        try:
            files = []
            for key in self.client.scan_iter("file:*:status"):
                data = self.client.get(key)
                if data:
                    files.append(json_loads(self._ensure_str(data)))
            return files
        except Exception as e:
            logger.error(f"Ошибка получения всех файлов: {e}")
            return []

    def delete_file_status(self, file_id: str) -> bool:
        """Удаление статуса файла."""
        try:
            key = f"file:{file_id}:status"
            self.client.delete(key)
            logger.debug(f"Статус файла {file_id} удалён")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления статуса файла {file_id}: {e}")
            return False

    def close(self):
        """Закрытие соединений."""
        if self._pubsub:
            self._pubsub.close()
        if self._client:
            self._client.close()
        logger.info("Соединения Redis закрыты")

    @staticmethod
    def _ensure_str(value: Any) -> str:
        """
        Гарантирует возврат строки из любого типа.
        Решает проблему 'Expected str | bytes | bytearray, got Awaitable'.
        """
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8")
        if hasattr(value, "__await__"):
            # ← Критическая защита: если передали coroutine, это ошибка вызова
            logger.error(f"Попытка передать Awaitable вместо значения: {type(value)}")
            raise TypeError(
                f"Expected str|bytes, got Awaitable. "
                f"Проверьте, не используете ли вы async-метод без 'await': {value}"
            )
        return str(value)


# Глобальный экземпляр (синглтон)
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Получение глобального экземпляра RedisClient."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
