"""Check repository-first deployment against isolated homes and real GNU Stow."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tasks import dotfiles_deploy as deploy


class DotfilesDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="archsetup-dotfiles-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dotfiles = self.root / "dotfiles"
        self.home = self.root / "home"
        self.dotfiles.mkdir()
        self.home.mkdir()
        for name, value in [("DOTFILES_DIR", self.dotfiles), ("TARGET_DIR", self.home)]:
            patcher = patch.object(deploy, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name in ["show_dotfiles_summary", "log_success"]:
            patcher = patch.object(deploy, name)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def package(self, name, relative, content="repository config\n"):
        source = self.dotfiles / name / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(content)
        return source

    def real_stow(self, command, **kwargs):
        self.assertEqual(command[0], "stow")
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.returncode, ""

    @unittest.skipUnless(shutil.which("stow"), "GNU Stow is required")
    def test_empty_home_supports_multiple_packages_and_repeat_deployment(self):
        kitty = self.package("kitty", ".config/kitty/kitty.conf")
        fish = self.package("fish", ".config/fish/config.fish")
        with patch.object(deploy.logger, 'run_cmd', side_effect=self.real_stow):
            self.assertTrue(deploy.run(auto_confirm=True))
            self.assertFalse((self.home / '.config').is_symlink())
            self.assertEqual((self.home / '.config/kitty/kitty.conf').resolve(), kitty)
            self.assertEqual((self.home / '.config/fish/config.fish').resolve(), fish)
            with patch.object(deploy.Path, 'unlink', side_effect=AssertionError('correct links must stay')):
                self.assertTrue(deploy.run(auto_confirm=True))
        self.assertEqual(self.show_dotfiles_summary.call_args.args[1], 0)

    @unittest.skipUnless(shutil.which("stow"), "GNU Stow is required")
    def test_defaults_and_foreign_links_are_replaced_without_backups(self):
        source = self.package("kitty", ".config/kitty/kitty.conf")
        self.package("kitty", ".config/kitty/theme.conf", "new theme\n")
        target_dir = self.home / '.config/kitty'
        target_dir.mkdir(parents=True)
        (target_dir / 'kitty.conf').write_text('default config\n')
        old_theme = self.root / 'old-theme'
        old_theme.write_text('old theme\n')
        (target_dir / 'theme.conf').symlink_to(old_theme)
        (self.home / '.config/legacy').symlink_to(self.root / 'missing-dotfiles/legacy')
        with patch.object(deploy.logger, 'run_cmd', side_effect=self.real_stow):
            self.assertTrue(deploy.run(auto_confirm=True))
        self.assertEqual((target_dir / 'kitty.conf').resolve(), source)
        self.assertEqual((target_dir / 'theme.conf').read_text(), 'new theme\n')
        self.assertEqual(old_theme.read_text(), 'old theme\n')
        self.assertFalse((self.home / '.config/legacy').is_symlink())
        self.assertEqual(list(self.home.rglob('*backup*')), [])
        self.assertEqual(self.show_dotfiles_summary.call_args.args[1:3], (2, 1))

    @unittest.skipUnless(shutil.which("stow"), "GNU Stow is required")
    def test_foreign_directory_link_is_replaced_without_writing_through_it(self):
        source = self.package("kitty", ".config/kitty/kitty.conf")
        old_dir = self.root / 'old-kitty'
        old_dir.mkdir()
        (old_dir / 'kitty.conf').write_text('old config')
        (self.home / '.config').mkdir()
        (self.home / '.config/kitty').symlink_to(old_dir, target_is_directory=True)
        with patch.object(deploy.logger, 'run_cmd', side_effect=self.real_stow):
            self.assertTrue(deploy.run(auto_confirm=True))
        self.assertEqual((self.home / '.config/kitty/kitty.conf').resolve(), source)
        self.assertEqual((old_dir / 'kitty.conf').read_text(), 'old config')

    @unittest.skipUnless(shutil.which("stow"), "GNU Stow is required")
    def test_file_blocking_a_config_directory_is_replaced(self):
        self.package("kitty", ".config/kitty/kitty.conf")
        (self.home / '.config').write_text('conflicting file')
        with patch.object(deploy.logger, 'run_cmd', side_effect=self.real_stow):
            self.assertTrue(deploy.run(auto_confirm=True))
        self.assertTrue((self.home / '.config/kitty/kitty.conf').is_symlink())

    def test_stow_failure_stops_remaining_packages_and_reports_failure(self):
        for name in ['alpha', 'beta', 'gamma']:
            self.package(name, f'.config/{name}/config')
        with patch.object(deploy, '_ensure_stow', return_value=True), \
             patch.object(deploy.logger, 'run_cmd', side_effect=[(0, ''), (1, '')]) as run:
            self.assertFalse(deploy.run(auto_confirm=True))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(self.show_dotfiles_summary.call_args.args[0], [
            ('alpha', 'Linked'), ('beta', 'Failed'), ('gamma', 'Skipped'),
        ])
        self.log_success.assert_not_called()

    def test_dependency_failure_does_not_retry_with_direct_pacman(self):
        self.package('kitty', '.config/kitty/kitty.conf')
        with patch.object(deploy.shutil, 'which', return_value=None), \
             patch.object(deploy.pm, 'install_package', return_value=False) as install, \
             patch.object(deploy.logger, 'run_cmd') as run:
            self.assertFalse(deploy.run(auto_confirm=True))
        install.assert_called_once_with('stow')
        run.assert_not_called()
        self.log_success.assert_not_called()

    def test_declined_deployment_makes_no_changes(self):
        self.package('kitty', '.config/kitty/kitty.conf')
        with patch.object(deploy, 'prompt_yes_no', return_value=False), \
             patch.object(deploy, '_ensure_stow') as ensure:
            self.assertTrue(deploy.run())
        ensure.assert_not_called()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_empty_package_directory_is_an_error(self):
        self.assertFalse(deploy.run(auto_confirm=True))
        self.log_success.assert_not_called()


if __name__ == '__main__':
    unittest.main()
