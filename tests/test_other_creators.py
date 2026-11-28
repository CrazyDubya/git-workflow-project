"""Sibling helpers of create_feature, same rule: if the base branch cannot be checked out
(dirty tree), do not create the new branch from the wrong branch or report success.
Actual sourced Bash helper in disposable local Git repos. No remote configured."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SOURCE = Path(os.environ.get('GIT_HELPER_SOURCE', Path(__file__).resolve().parents[1] / 'scripts/git-helpers.sh'))

CASES = [
    # function, args, base branch, created branch, success text
    ('create_experiment', ['x1'], 'draft', 'experiment/x1', 'Created experiment branch:'),
    ('create_personal', ['sam', 'x1'], 'develop', 'personal/sam/x1', 'Created personal branch:'),
    ('create_hotfix', ['x1'], 'main', 'hotfix/x1', 'Created hotfix branch:'),
]

class SiblingCreatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.env = {**os.environ, 'HOME': self.temp.name, 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_TERMINAL_PROMPT': '0'}
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic test')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        (self.repo / 'state.txt').write_text('main\n')
        self.git('add', '.')
        self.git('commit', '-m', 'Synthetic main')

    def git(self, *args):
        r = subprocess.run(['git', *args], cwd=self.repo, env=self.env, text=True,
                           capture_output=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def call(self, fn, args):
        return subprocess.run(['bash', '-c', 'source "$1"; fn="$2"; shift 2; "$fn" "$@"',
                               'fixture', str(SOURCE), fn, *args], cwd=self.repo,
                              env=self.env, text=True, capture_output=True, timeout=10)

    def make_base_differ(self, base):
        """Base branch exists with different content; we sit on another branch."""
        if base != 'main':
            self.git('checkout', '-b', base)
        (self.repo / 'state.txt').write_text(f'{base}-base\n')
        self.git('commit', '-am', f'Synthetic {base}')
        self.git('checkout', '-b', 'topic', 'main') if base != 'main' else self.git('checkout', '-b', 'topic')
        (self.repo / 'state.txt').write_text('topic\n')
        self.git('commit', '-am', 'Synthetic topic')
        if base == 'main':
            self.git('checkout', 'main')
            (self.repo / 'state.txt').write_text('main2\n')
            self.git('commit', '-am', 'Synthetic main2')
            self.git('checkout', 'topic')

    def test_clean_checkout_of_base_works(self):
        for fn, args, base, created, text in CASES:
            with self.subTest(fn=fn):
                self.setUp()
                self.make_base_differ(base)
                base_head = self.git('rev-parse', base)
                r = self.call(fn, args)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.git('branch', '--show-current'), created)
                self.assertEqual(self.git('rev-parse', 'HEAD'), base_head)
                self.assertIn(text, r.stdout)

    def test_dirty_tree_blocking_base_checkout_stops(self):
        for fn, args, base, created, text in CASES:
            with self.subTest(fn=fn):
                self.setUp()
                self.make_base_differ(base)
                dirty = 'Unsaved synthetic changes\n'
                (self.repo / 'state.txt').write_text(dirty)
                topic_head = self.git('rev-parse', 'HEAD')
                r = self.call(fn, args)
                self.assertNotEqual(r.returncode, 0)
                self.assertNotIn(text, r.stdout)
                self.assertEqual(self.git('branch', '--show-current'), 'topic')
                self.assertEqual(self.git('rev-parse', 'HEAD'), topic_head)
                self.assertEqual((self.repo / 'state.txt').read_text(), dirty)
                self.assertNotIn(created, self.git('branch', '--list'))

if __name__ == '__main__':
    unittest.main()
