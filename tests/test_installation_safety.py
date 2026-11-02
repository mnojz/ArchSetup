"""Regression tests for failure propagation without modifying the host system."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import auth, main
from core.pacman import PackageManager
from tasks import package_installer, system_configuration, mirror_ranking


class PackageSafetyTests(unittest.TestCase):
    def setUp(self):
        with patch.object(PackageManager, '_refresh_installed_cache'):
            self.pm = PackageManager()

    def test_failed_upgrade_blocks_selective_install(self):
        with patch('core.pacman.logger.run_cmd', return_value=(1, '')) as run, \
             patch.object(self.pm, '_refresh_installed_cache'), \
             patch.object(self.pm, 'in_official_repo') as query:
            self.assertFalse(self.pm.install_package('example'))
        query.assert_not_called()
        self.assertEqual(run.call_args.args[0], ['sudo', 'pacman', '-Syu', '--noconfirm'])
        self.assertEqual(self.pm.failed_packages, ['example'])

    def test_successful_upgrade_is_reused_until_operation_reset(self):
        with patch('core.pacman.logger.run_cmd', return_value=(0, '')) as run, \
             patch.object(self.pm, '_refresh_installed_cache'):
            self.assertTrue(self.pm.prepare_transaction())
            self.assertTrue(self.pm.prepare_transaction())
            self.assertEqual(run.call_count, 1)
            self.pm.failed_packages.append('old-failure')
            self.pm.reset_operation()
            self.assertEqual(self.pm.failed_packages, [])
            self.assertTrue(self.pm.prepare_transaction())
            self.assertEqual(run.call_count, 2)

    def test_official_install_failure_does_not_fall_back_to_aur(self):
        with patch.object(self.pm, 'prepare_transaction', return_value=True), \
             patch.object(self.pm, 'in_official_repo', return_value=True), \
             patch.object(self.pm, 'get_aur_helper') as helper, \
             patch('core.pacman.logger.run_cmd', return_value=(1, '')):
            self.assertFalse(self.pm.install_package('example'))
        helper.assert_not_called()

    def test_batch_and_manifest_report_package_failures(self):
        with patch.object(package_installer.pm, 'prepare_transaction', return_value=True), \
             patch.object(package_installer.pm, 'install_package', side_effect=[False, True, False]):
            self.assertFalse(package_installer.install_package_batch('test', ['one', 'two']))
            self.assertFalse(package_installer.run(categories_list=[{'packages': ['three']}]))

    def test_failed_upgrade_stops_batch(self):
        with patch.object(package_installer.pm, 'prepare_transaction', return_value=False), \
             patch.object(package_installer.pm, 'install_package') as install:
            self.assertFalse(package_installer.install_package_batch('test', ['one']))
        install.assert_not_called()


class PipelineSafetyTests(unittest.TestCase):
    def test_failed_phase_skips_dependents_and_reboot(self):
        with patch('socket.create_connection'), \
             patch.object(main.auth, 'request_sudo_auth', return_value=True), \
             patch.object(main.pacman_tuning, 'run', return_value=True), \
             patch.object(main.aur_bootstrap, 'run', return_value=False), \
             patch.object(main.package_installer, 'run') as packages, \
             patch.object(main.system_configuration, 'run') as system, \
             patch.object(main.tui, 'prompt_yes_no') as prompt, \
             patch.object(main.tui, 'show_summary_panel'):
            self.assertFalse(main.do_full(Path('packages.json'), []))
        packages.assert_not_called()
        system.assert_not_called()
        prompt.assert_not_called()

    def test_system_phase_failure_suppresses_reboot(self):
        with patch('socket.create_connection'), \
             patch.object(main.auth, 'request_sudo_auth', return_value=True), \
             patch.object(main.pacman_tuning, 'run', return_value=True), \
             patch.object(main.aur_bootstrap, 'run', return_value=True), \
             patch.object(main.mirror_ranking, 'run', return_value=True), \
             patch.object(main.package_installer, 'run', return_value=True), \
             patch.object(main.desktop_integration, 'run', return_value=True), \
             patch.object(main.ambxst_shell, 'run', return_value=True), \
             patch.object(main.dotfiles_deploy, 'run', return_value=True), \
             patch.object(main.system_configuration, 'run', return_value=False), \
             patch.object(main.tui, 'prompt_yes_no') as prompt, \
             patch.object(main.tui, 'show_summary_panel'):
            self.assertFalse(main.do_full(Path('packages.json'), []))
        prompt.assert_not_called()


class InitramfsSafetyTests(unittest.TestCase):
    def run_system(self, command):
        with patch.object(system_configuration, 'detect_gpu', return_value=[]), \
             patch.object(system_configuration.pm, 'is_installed', return_value=False), \
             patch.object(system_configuration.shutil, 'which', return_value=None), \
             patch.object(system_configuration.Path, 'is_file', return_value=True), \
             patch.object(system_configuration.Path, 'is_dir', return_value=False), \
             patch.object(system_configuration.logger, 'run_cmd', side_effect=command) as run:
            result = system_configuration.run(Path('/unused-assets'))
        return result, run

    def test_preserves_configuration_without_copying_template(self):
        result, run = self.run_system(lambda *a, **kw: (0, ''))
        self.assertTrue(result)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][:4], ['sudo', 'cp', '-p', '/etc/mkinitcpio.conf'])
        self.assertEqual(commands[1], ['sudo', 'mkinitcpio', '-P'])

    def test_failed_rebuild_stops_configuration(self):
        result, run = self.run_system(lambda cmd, **kw: (1 if 'mkinitcpio' in cmd else 0, ''))
        self.assertFalse(result)
        self.assertEqual(run.call_count, 2)

    def test_backup_failure_prevents_rebuild(self):
        def fail(cmd, **kw):
            raise subprocess.CalledProcessError(1, cmd)
        result, run = self.run_system(fail)
        self.assertFalse(result)
        self.assertEqual(run.call_count, 1)


class MirrorSafetyTests(unittest.TestCase):
    def test_success_does_not_refresh_databases(self):
        def command(cmd, **kwargs):
            if cmd[0] == "rate-mirrors":
                Path(cmd[1].split("=", 1)[1]).write_text("Server = https://example.invalid/$repo/os/$arch\n")
            return 0, ""
        with patch.object(mirror_ranking, 'prompt_yes_no', return_value=True), \
             patch.object(mirror_ranking.shutil, 'which', return_value='/usr/bin/rate-mirrors'), \
             patch.object(mirror_ranking.Path, 'exists', return_value=False), \
             patch.object(mirror_ranking.logger, 'run_cmd', side_effect=command) as run, \
             patch.object(mirror_ranking.pm, 'invalidate_transaction') as invalidate:
            self.assertTrue(mirror_ranking.run())
        self.assertFalse(any('pacman' in call.args[0] for call in run.call_args_list))
        invalidate.assert_called_once()

    def test_backup_failure_leaves_mirrorlist_alone(self):
        with patch.object(mirror_ranking, 'prompt_yes_no', return_value=True), \
             patch.object(mirror_ranking.shutil, 'which', return_value='/usr/bin/rate-mirrors'), \
             patch.object(mirror_ranking.Path, 'exists', return_value=True), \
             patch.object(mirror_ranking.logger, 'run_cmd', return_value=(1, '')) as run:
            self.assertFalse(mirror_ranking.run())
        self.assertEqual(run.call_count, 1)

    def test_mirror_write_failure_is_reported(self):
        def command(cmd, **kwargs):
            if cmd[0] == "rate-mirrors":
                Path(cmd[1].split("=", 1)[1]).write_text("Server = example\n")
                return 0, ""
            return 1, ""
        with patch.object(mirror_ranking, 'prompt_yes_no', return_value=True), \
             patch.object(mirror_ranking.shutil, 'which', return_value='/usr/bin/rate-mirrors'), \
             patch.object(mirror_ranking.Path, 'exists', return_value=False), \
             patch.object(mirror_ranking.logger, 'run_cmd', side_effect=command):
            self.assertFalse(mirror_ranking.run())


class AuthenticationTests(unittest.TestCase):
    def tearDown(self):
        auth.stop_keepalive()

    def test_username_lookup_does_not_require_controlling_terminal(self):
        with patch.object(auth, 'is_sudo_active', return_value=False), \
             patch('os.getlogin', side_effect=OSError('no tty')), \
             patch.object(auth.getpass, 'getuser', return_value='test-user'), \
             patch.object(auth.getpass, 'getpass', return_value=''):
            self.assertFalse(auth.request_sudo_auth())

    def test_keepalive_stops_and_can_restart(self):
        auth.start_keepalive()
        first = auth._keepalive_thread
        self.assertTrue(first.daemon)
        auth.start_keepalive()
        self.assertIs(auth._keepalive_thread, first)
        auth.stop_keepalive()
        self.assertFalse(first.is_alive())
        auth.start_keepalive()
        self.assertIsNot(auth._keepalive_thread, first)

    def test_keepalive_stops_on_expired_credentials(self):
        event = MagicMock()
        event.wait.return_value = False
        with patch.object(auth, '_keepalive_stop', event), \
             patch.object(auth.subprocess, 'run', return_value=MagicMock(returncode=1)) as run:
            auth._keepalive_loop()
        run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
