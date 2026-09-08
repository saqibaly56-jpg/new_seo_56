import os

from redis import Redis
from rq import Queue, Worker
from utils.queue import get_redis_url


def main() -> None:
    redis_url = get_redis_url()
    if not redis_url or redis_url == "redis://localhost:6379/0":
        raise RuntimeError("A valid Railway REDIS_URL or REDISHOST/REDISPASSWORD configuration is required")

    connection = Redis.from_url(redis_url, socket_connect_timeout=5)
    connection.ping()
    worker = Worker([Queue("seo_automation_queue", connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()