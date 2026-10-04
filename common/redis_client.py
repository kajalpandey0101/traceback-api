import time

import redis
from django.conf import settings


redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def rate_limit(key_prefix, limit, window_seconds=60):
    bucket = f'{key_prefix}:{int(time.time() // window_seconds)}'
    current = redis_client.incr(bucket)
    if current == 1:
        redis_client.expire(bucket, window_seconds)
    return current <= limit
