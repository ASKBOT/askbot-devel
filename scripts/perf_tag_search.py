"""One-off perf script for the tag-intersection query.

Picks a real thread that carries the largest tag set in the database, then
issues GETs to /questions/tags:t1,t2,.../ for increasing tag counts so the
intersection always returns at least one question. Times each request with
warm-up + repeats so the numbers are stable enough to compare branches.

Usage:
    cd askbot_site
    ../env-md/bin/python ../perf_tag_search.py --base-url http://127.0.0.1:8000

The dev server must already be running (manage.py runserver, gunicorn, etc.)
on the URL passed in. Run the script once before applying the optimization
and once after; compare the columns.
"""
import argparse
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import django


def setup_django():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'askbot_site.settings')
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    django.setup()


def pick_tag_set(min_count, max_count):
    """Return a list of tag names that all co-occur on the same thread.

    Uses the thread carrying the most tags so the intersection is guaranteed
    non-empty for any prefix of the returned list.
    """
    from askbot.models import Thread
    from django.db.models import Count

    threads = (
        Thread.objects
        .annotate(n_tags=Count('tags'))
        .filter(n_tags__gte=min_count)
        .order_by('-n_tags')
    )
    thread = threads.first()
    if thread is None:
        raise SystemExit(
            f'No thread has at least {min_count} tags - lower --min-tags or '
            'load a larger dataset.'
        )
    names = list(thread.tags.values_list('name', flat=True))
    if max_count:
        names = names[:max_count]
    print(f'Using thread id={thread.id} with {len(names)} tags: {names}')
    return names


def build_url(base_url, tags):
    encoded = urllib.parse.quote(','.join(tags), safe=',+.-_')
    return f'{base_url.rstrip("/")}/questions/tags:{encoded}/'


def time_request(url, timeout):
    start = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read()
        status = resp.status
    elapsed = time.perf_counter() - start
    return elapsed, status, len(body)


def run(base_url, tags, repeats, warmups, timeout, sleep):
    header = f'{"N tags":>6} | {"min ms":>8} | {"med ms":>8} | {"max ms":>8} | {"bytes":>8} | status'
    print(header)
    print('-' * len(header))
    for n in range(1, len(tags) + 1):
        url = build_url(base_url, tags[:n])
        last_status = None
        last_size = None
        for _ in range(warmups):
            _, last_status, last_size = time_request(url, timeout)
            if sleep:
                time.sleep(sleep)
        samples = []
        for _ in range(repeats):
            elapsed, last_status, last_size = time_request(url, timeout)
            samples.append(elapsed * 1000)
            if sleep:
                time.sleep(sleep)
        print(
            f'{n:>6} | {min(samples):>8.1f} | {statistics.median(samples):>8.1f} | '
            f'{max(samples):>8.1f} | {last_size:>8} | {last_status}'
        )
        print(f'         url: {url}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000',
                        help='Base URL of the running askbot site.')
    parser.add_argument('--min-tags', type=int, default=2,
                        help='Skip threads that carry fewer tags than this.')
    parser.add_argument('--max-tags', type=int, default=8,
                        help='Cap the tag list length (0 = no cap).')
    parser.add_argument('--repeats', type=int, default=5,
                        help='Timed requests per tag count.')
    parser.add_argument('--warmups', type=int, default=1,
                        help='Untimed requests per tag count before timing.')
    parser.add_argument('--timeout', type=float, default=60.0,
                        help='Per-request timeout in seconds.')
    parser.add_argument('--sleep', type=float, default=1.5,
                        help='Pause between requests to avoid the rate limiter.')
    args = parser.parse_args()

    setup_django()
    tags = pick_tag_set(args.min_tags, args.max_tags)
    print(f'Base URL: {args.base_url}')
    print(f'Repeats: {args.repeats}, warmups: {args.warmups}')
    print()
    try:
        run(args.base_url, tags, args.repeats, args.warmups, args.timeout,
            args.sleep)
    except urllib.error.URLError as exc:
        print(f'Request failed - is the dev server running? {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
