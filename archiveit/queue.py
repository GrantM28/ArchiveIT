from redis import Redis
from rq import Queue

from .settings import settings

def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)

def get_queue() -> Queue:
    return Queue(name=settings.queue_name, connection=get_redis(), default_timeout=60 * 60 * 2)  # 2h
