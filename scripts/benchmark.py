"""Offline SQLite data-access benchmark. Not an end-to-end app benchmark."""
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc


def worker(database, mode):
    connection = sqlite3.connect(database)
    tracemalloc.start()
    cpu = time.process_time()
    start = time.perf_counter()
    if mode == 'before':
        rows = connection.execute('SELECT * FROM articles ORDER BY discovered_at DESC').fetchall()
        count = sum(1 for row in rows if row[1])
    else:
        cursor = connection.execute('SELECT id, title FROM articles ORDER BY discovered_at DESC')
        count = 0
        while batch := cursor.fetchmany(128):
            count += sum(1 for row in batch if row[1])
        cursor.close()
    result = {'rows': count, 'wall_ms': (time.perf_counter()-start)*1000,
              'cpu_ms': (time.process_time()-cpu)*1000,
              'python_peak_mib': tracemalloc.get_traced_memory()[1]/1024**2,
              'rss_peak_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
    connection.close()
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', nargs=2, metavar=('DB', 'MODE'))
    parser.add_argument('--rows', type=int, default=1500)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--output', default='docs/benchmark.json')
    args = parser.parse_args()
    if args.worker:
        return worker(*args.worker)
    with tempfile.TemporaryDirectory() as directory:
        database = str(Path(directory)/'fixture.db')
        with sqlite3.connect(database) as db:
            db.execute('CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT, content TEXT, translation_pt TEXT, discovered_at TEXT)')
            db.executemany('INSERT INTO articles VALUES (?, ?, ?, ?, ?)',
                           ((i, f'Article {i}', 'x'*32768, 'y'*8192, '2026-11-09') for i in range(args.rows)))
            db.execute('CREATE INDEX ix_date ON articles(discovered_at)')
        samples = {'before': [], 'after': []}
        for _ in range(args.repeats):
            for mode in samples:
                output = subprocess.check_output([sys.executable, __file__, '--worker', database, mode], text=True)
                samples[mode].append(json.loads(output))
        report = {'scope': 'SQLite read path only; no SQLAlchemy, HTTP, LLM or CT execution',
                  'python': platform.python_version(), 'platform': platform.platform(),
                  'rows': args.rows, 'body_bytes_per_row': 40960, 'repeats': args.repeats,
                  'method': 'Same DB, index and sort; fresh alternating subprocesses; medians; Linux ru_maxrss',
                  'samples': samples,
                  'median': {mode: {key: statistics.median(row[key] for row in values) for key in values[0]} for mode, values in samples.items()}}
        Path(args.output).write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report['median'], indent=2))


if __name__ == '__main__':
    main()
