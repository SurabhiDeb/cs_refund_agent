# Beat 13.1, load

Laptop, Docker Postgres, two Granian workers, `FAKE_MODEL=true` so the
gateway is out of the path and what is measured is our own code. Writes
off, since TestModel calls every tool it is given.

## The pool was the first ceiling

`create_engine` was called with no pool arguments, so SQLAlchemy's
defaults applied: 5 connections plus 10 overflow per process, with a 30
second checkout timeout. Under the ramp that produced a 49 second request
against a 268ms median, and 1.03% failures.

Raised to 10 plus 20, with a 5 second timeout so an overloaded caller is
told quickly instead of held, and `pool_pre_ping` so a connection idle
through a Postgres restart does not return a 500. Same ramp afterwards:
0% failures, worst request 2.89s.

| | before | after |
|---|---|---|
| failures | 1.03% | 0% |
| slowest request | 49.45s | 2.89s |
| throughput | 19.3/s | 21.7/s |

## Breaking concurrency

Thirty seconds at each level, held steady.

| VUs | p95 | failed | throughput |
|---|---|---|---|
| 5 | 377ms | 0% | 26.8/s |
| 10 | 678ms | 0% | 31.5/s |
| 20 | 4.84s | 2.0% | 23.1/s |
| 40 | 34.19s | 33.2% | 3.7/s |

A 500ms p95 budget breaks between 5 and 10 concurrent callers. The service
itself breaks between 10 and 20: throughput peaks at 10 and falls after,
so beyond that point more load produces less work. At 40 a third of
requests fail and throughput is a sixth of its peak.

At 20 the distribution is bimodal, median 141ms against a p95 of 4.84s.
Most callers get a connection at once and the rest wait out the five
second pool timeout and fail. That is the pool, not the CPU.

## What this says to do

Bound concurrency at the edge. A caller that cannot be served should get
a fast 503 rather than a slow timeout, and the service should shed load
rather than collapse. Nothing in the code does that today: the rate limit
is per key, not global, so ten keys at ten requests each walk straight
past it.

## What this does not measure

A real model in the path, which dominates latency and changes the shape
entirely. The write path, since writes were off. Anything other than this
laptop. These are relative numbers for finding a knee, not a capacity
plan for a deployment that does not exist yet.

## Load shedding, added after the first measurement

A bounded semaphore per worker, five slots, checked before any work. Over
capacity the caller gets a 503 and a Retry-After immediately instead of
queueing into a pool timeout.

Forty virtual users, the level where the service previously collapsed:

| | before shedding | after |
|---|---|---|
| throughput | 6.7/s | 32.9/s |
| slowest request | 58.4s | 9.4s |
| timeouts | 39 | 0 |
| refused at the door | 0 | ~777 |
| p95, served requests | 1.77s | 3.53s |

Three quarters of the offered load is refused, which is the honest answer
from a service sized for ten concurrent callers when forty arrive. It now
does five times the useful work while refusing them, and nothing hangs.

The shed counter read 278 at the scrape, not 777. Two workers, one
counter each, and `/metrics` is answered by whichever worker picks up the
request. That is the known per-process metrics limitation, demonstrated
rather than argued.
