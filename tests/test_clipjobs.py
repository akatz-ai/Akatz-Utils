"""Clip completion, persistence, storage containment and failure regression checks."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, send_file
from io import BytesIO

from launcher.routes.clipjobs import bp, recover_jobs
from launcher.storage import configure_storage
from ytclipper import validate_time_range


class ClipJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = Flask(__name__)
        self.app.testing = True
        self.app.config.update(SHARED_ROOT=str(self.root), CLIP_JOB_ROOT=str(self.root / 'jobs'))
        self.app.register_blueprint(bp)
        self.client = self.app.test_client()
        for target, value in [('check_storage', None), ('extract_media_sources', ([], 'Test 🎬'))]:
            mock = patch('launcher.routes.clipjobs.' + target, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        self.payload = dict(url='https://youtu.be/Z8OgpJ4u7ZQ', start=0, end=1200, format='mp4',
                            destination='shared', folder='clips')

    def wait(self, job_id):
        for _ in range(300):
            job = self.client.get('/api/ytclipper/jobs/' + job_id).json
            if job['state'] != 'processing':
                # Manifest publication precedes worker-lock release by a few instructions.
                from launcher.routes.clipjobs import _worker_lock
                if _worker_lock.acquire(timeout=2):
                    _worker_lock.release()
                return job
            time.sleep(.01)
        self.fail('Job did not finish')

    def test_shared_clip_avoids_overwrite_and_supports_download(self):
        folder = self.root / 'clips'
        folder.mkdir()
        (folder / 'Test 🎬.mp4').write_bytes(b'original')
        with patch('launcher.routes.clipjobs.iter_youtube_clip', return_value=iter([b'clip'])):
            response = self.client.post('/api/ytclipper/jobs', json=self.payload)
            self.assertEqual(response.status_code, 202)
            job = self.wait(response.json['id'])
        self.assertEqual(job['state'], 'complete')
        self.assertEqual(Path(job['path']).read_bytes(), b'clip')
        self.assertEqual((folder / 'Test 🎬.mp4').read_bytes(), b'original')
        response = self.client.get(job['download_url'])
        self.assertEqual(response.data, b'clip')
        response.close()
        self.assertFalse(list(folder.glob('*.partial')))
        recover_jobs(self.app)
        self.assertEqual(self.client.get('/api/ytclipper/jobs/' + job['id']).json['state'], 'complete')

    def test_failure_does_not_publish_partial_clip(self):
        def fail(*args):
            yield b'partial'
            raise RuntimeError('encoding failed')
        with patch('launcher.routes.clipjobs.iter_youtube_clip', side_effect=fail), self.assertLogs(self.app.logger):
            response = self.client.post('/api/ytclipper/jobs', json=self.payload)
            job = self.wait(response.json['id'])
        self.assertEqual(job['state'], 'error')
        self.assertEqual(list((self.root / 'clips').iterdir()), [])

    def test_browser_job_is_disk_backed(self):
        with patch('launcher.routes.clipjobs.iter_youtube_clip', return_value=iter([b'media'])):
            response = self.client.post('/api/ytclipper/jobs', json={**self.payload, 'destination': 'browser'})
            job = self.wait(response.json['id'])
        self.assertEqual(Path(job['path']).parent, self.root / 'jobs')
        self.assertEqual(job['bytes'], 5)

    def test_rejects_traversal_symlink_and_invalid_times(self):
        (self.root / 'escape').symlink_to(self.root.parent, target_is_directory=True)
        for change in [dict(folder='../outside'), dict(folder='escape/outside'), dict(filename='../clip'), dict(start=float('nan'))]:
            response = self.client.post('/api/ytclipper/jobs', json={**self.payload, **change})
            self.assertEqual(response.status_code, 400, change)
        self.assertFalse((self.root / 'jobs').exists())

    def test_storage_failure_starts_no_job(self):
        with patch('launcher.routes.clipjobs.check_storage', side_effect=RuntimeError('storage offline')):
            response = self.client.post('/api/ytclipper/jobs', json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertFalse((self.root / 'jobs').exists())

    def test_concurrent_clip_is_rejected(self):
        from launcher.routes.clipjobs import _worker_lock
        with _worker_lock:
            response = self.client.post('/api/ytclipper/jobs', json=self.payload)
        self.assertEqual(response.status_code, 409)

    def test_long_clips_and_restart_recovery(self):
        validate_time_range(0, 21600)
        with self.assertRaises(ValueError):
            validate_time_range(0, 21601)
        folder = self.root / 'jobs'
        folder.mkdir()
        job = dict(id='a'*32, state='processing')
        (folder / ('a'*32 + '.json')).write_text(json.dumps(job))
        recover_jobs(self.app)
        self.assertEqual(self.client.get('/api/ytclipper/jobs/' + 'a'*32).json['state'], 'error')


class ExportSaveTests(unittest.TestCase):
    def test_other_tools_save_directly_on_server(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'AKATZ_SHARED_ROOT': ''}):
            app = Flask(__name__)
            configure_storage(app)
            app.config['SHARED_ROOT'] = directory

            @app.post('/api/imgsizer/export')
            def export():
                return send_file(BytesIO(b'image'), as_attachment=True, download_name='example.png')

            with patch('launcher.storage.check_storage'):
                response = app.test_client().post('/api/imgsizer/export', headers={'X-Akatz-Save-Folder': 'exports'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(Path(response.json['path']).read_bytes(), b'image')
                response = app.test_client().post('/api/imgsizer/export', headers={'X-Akatz-Save-Folder': '../escape'})
                self.assertEqual(response.status_code, 400)
