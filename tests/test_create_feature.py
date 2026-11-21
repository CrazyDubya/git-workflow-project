"""Actual sourced Bash helper in disposable local Git repos. No remote configured."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SOURCE = Path(os.environ.get('GIT_HELPER_SOURCE', Path(__file__).resolve().parents[1] / 'scripts/git-helpers.sh'))

class CreateFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir()
        self.env = {**os.environ, 'HOME': str(self.home), 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_TERMINAL_PROMPT': '0'}
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic test')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        (self.repo / 'state.txt').write_text('main\n')
        self.git('add', '.')
        self.git('commit', '-m', 'Synthetic main')
        self.main = self.git('rev-parse', 'HEAD')

    def git(self, *args):
        result = subprocess.run(['git', *args], cwd=self.repo, env=self.env,
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def develop(self):
        self.git('checkout', '-b', 'develop')
        (self.repo / 'state.txt').write_text('develop\n')
        self.git('commit', '-am', 'Synthetic develop')
        head = self.git('rev-parse', 'HEAD')
        self.git('checkout', 'main')
        return head

    def create(self, name):
        return subprocess.run(['bash', '-c', 'source "$1"; create_feature "$2"',
                               'fixture', str(SOURCE), name], cwd=self.repo,
                              env=self.env, text=True, capture_output=True, timeout=10)

    def test_dirty_base_checkout_stops_without_branch_or_work_loss(self):
        self.develop()
        dirty = 'Unsaved synthetic changes\n'
        (self.repo / 'state.txt').write_text(dirty)
        before = self.git('status', '--porcelain')
        result = self.create('synthetic-next')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Created feature branch:', result.stdout)
        self.assertEqual(self.git('branch', '--show-current'), 'main')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.main)
        self.assertEqual(self.git('status', '--porcelain'), before)
        self.assertEqual((self.repo / 'state.txt').read_text(), dirty)
        self.assertNotIn('feature/synthetic-next', self.git('branch', '--list'))

    def test_clean_existing_develop_base_and_offline_pull_compatibility(self):
        develop = self.develop()
        result = self.create('synthetic-next')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('branch', '--show-current'), 'feature/synthetic-next')
        self.assertEqual(self.git('rev-parse', 'HEAD'), develop)
        self.assertIn('Created feature branch:', result.stdout)
        self.assertEqual(self.git('remote'), '')

    def test_missing_develop_is_created_from_current_offline(self):
        result = self.create('synthetic-next')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('rev-parse', 'develop'), self.main)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.main)
        self.assertEqual(self.git('branch', '--show-current'), 'feature/synthetic-next')

    def test_existing_target_does_not_report_success(self):
        develop = self.develop()
        self.git('branch', 'feature/existing', 'main')
        result = self.create('existing')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Created feature branch:', result.stdout)
        self.assertEqual(self.git('rev-parse', 'feature/existing'), self.main)
        self.assertEqual(self.git('rev-parse', 'develop'), develop)

    def test_invalid_target_does_not_report_success(self):
        self.develop()
        result = self.create('invalid..name')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Created feature branch:', result.stdout)
        self.assertNotIn('feature/', self.git('branch', '--list'))

if __name__ == '__main__':
    unittest.main()
