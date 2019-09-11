#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from operator import itemgetter

import functools
import logging
import multiprocessing
import os
import tempfile


def _launch(func, rank, world_size, rendezvous_file, queue):
    import crypten

    communicator_args = {
        "WORLD_SIZE": world_size,
        "RANK": rank,
        "RENDEZVOUS": "file://%s" % rendezvous_file,
        "BACKEND": "gloo",
    }
    for key, val in communicator_args.items():
        os.environ[key] = str(val)

    crypten.init()

    return_value = func()
    queue.put((rank, return_value))


def run_multiprocess(world_size):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            rendezvous_file = tempfile.NamedTemporaryFile(delete=True).name
            queue = multiprocessing.Queue()

            processes = [
                multiprocessing.Process(
                    target=_launch,
                    args=(func, rank, world_size, rendezvous_file, queue),
                )
                for rank in range(world_size)
            ]

            for process in processes:
                process.start()

            for process in processes:
                process.join()

            successful = [process.exitcode == 0 for process in processes]
            if not all(successful):
                logging.error('One of the parties failed. Check past logs')
                return None

            return_values = []
            while not queue.empty():
                return_values.append(queue.get())

            return [value for _, value in sorted(return_values,
                                                 key=itemgetter(0))]

        return wrapper
    return decorator