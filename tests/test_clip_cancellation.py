"""Cancellation must stop a subprocess even while its output pipe is idle."""

import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from ytclipper import iter_clip


class ClipProcessCancellationTests(unittest.TestCase):
    def test_cancel_stops_blocked_encoder_and_reaps_process(self):
        cancel = threading.Event()
        started = threading.Event()
        processes, errors = [], []
        real_popen = subprocess.Popen

        def spawn(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            started.set()
            return process

        def consume():
            try:
                list(iter_clip('unused', 0, 10, 'mp4', cancel_event=cancel))
            except Exception as error:
                errors.append(error)

        with patch('ytclipper.ytclipper._build_ffmpeg_args', return_value=[sys.executable, '-c', 'import time; time.sleep(30)']), patch('ytclipper.ytclipper.subprocess.Popen', side_effect=spawn):
            worker = threading.Thread(target=consume, daemon=True)
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                cancel.set()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertIsInstance(errors[0], InterruptedError)
                self.assertIsNotNone(processes[0].poll())
                self.assertTrue(processes[0].stdout.closed)
            finally:
                cancel.set()
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                worker.join(2)
