import os
import redis
from rq import Worker, Queue, Connection

listen = ["default"]

r = redis.from_url(os.environ.get("REDIS_URL", ""))
assert r.ping(), "No connection to Redis"

if __name__ == "__main__":
    with Connection(r):
        worker = Worker(list(map(Queue, listen)))
        worker.work()
