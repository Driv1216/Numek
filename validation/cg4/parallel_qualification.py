"""Bounded independent seed subprocess orchestration for validation only."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import threading

_output_lock = threading.Lock()


def emit(value):
    with _output_lock:
        print(json.dumps(value), flush=True)


def run_fixed_seeds(seeds, workers, run):
    seeds = list(seeds)
    if type(workers) is not int or not 1 <= workers <= 4 or len(set(seeds)) != len(seeds):
        raise ValueError('Use 1–4 workers and unique fixed seeds.')
    if workers == 1:
        for seed in seeds:
            run(seed)
        return
    stopped = threading.Event()

    def guarded(seed):
        if stopped.is_set():
            return
        try:
            run(seed)
        except BaseException:
            stopped.set()
            raise

    # A failed seed stops queued work. Already running independent trials finish
    # and preserve their evidence before the failure is returned to the caller.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(guarded, seed) for seed in seeds]
        try:
            for future in as_completed(futures):
                future.result()
        except BaseException:
            stopped.set()
            for future in futures:
                future.cancel()
            raise
