"""
Comprehensive Test Suite for ArchSetup Secure Boot Management
Tests all components across mock firmware interfaces, key states, bootloader adapters,
kernel architectures, Windows dual-boot scenarios, and error conditions.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from tasks.secureboot import (
    backup,
    config,
    enrollment,
    firmware,
    inventory,
    kernel,
    keys,
    preflight,
    recovery,
    report,
    signing,
    state,
    updates,
    verification,
)
from tasks.secureboot.adapters.grub import GrubAdapter
from tasks.secureboot.adapters.limine import LimineAdapter
from tasks.secureboot.adapters.refind import RefindAdapter
from tasks.secureboot.adapters.systemd_boot import SystemdBootAdapter


class TestFirmwareInspection(unittest.TestCase):
    """Test UEFI firmware and efivars detection."""

    @patch("tasks.secureboot.firmware.EFI_SYS_DIR")
    def test_uefi_boot_detection(self, mock_efi_dir):
        mock_efi_dir.is_dir.return_value = True
        self.assertTrue(firmware.is_uefi_boot())

        mock_efi_dir.is_dir.return_value = False
        self.assertFalse(firmware.is_uefi_boot())

    @patch("tasks.secureboot.firmware.read_efivar_raw")
    def test_secure_boot_enabled_efivar(self, mock_read):
        # Attributes: 6, Value: 1 (Enabled)
        mock_read.return_value = (6, b"\x01")
        self.assertTrue(firmware.is_secure_boot_enabled())

        # Attributes: 6, Value: 0 (Disabled)
        mock_read.return_value = (6, b"\x00")
        self.assertFalse(firmware.is_secure_boot_enabled())

        # Efivar unreadable -> fallback
        mock_read.return_value = None
        with patch("shutil.which", return_value=None):
            self.assertFalse(firmware.is_secure_boot_enabled())

    @patch("tasks.secureboot.firmware.read_efivar_raw")
    def test_setup_mode_detection(self, mock_read):
        # Attributes: 6, Value: 1 (Setup Mode)
        mock_read.return_value = (6, b"\x01")
        self.assertTrue(firmware.is_setup_mode())

        # Attributes: 6, Value: 0 (User Mode)
        mock_read.return_value = (6, b"\x00")
        self.assertFalse(firmware.is_setup_mode())

    @patch("tasks.secureboot.firmware.read_efivar_raw")
    def test_key_database_inspection(self, mock_read):
        def side_effect(var_name):
            if "PK-" in var_name:
                return (6, b"mock_pk_data_bytes")
            elif "KEK-" in var_name:
                return (6, b"mock_kek_data")
            return None

        mock_read.side_effect = side_effect
        dbs = firmware.inspect_efivars_keys()
        self.assertTrue(dbs["PK"]["enrolled"])
        self.assertTrue(dbs["KEK"]["enrolled"])
        self.assertFalse(dbs["db"]["enrolled"])
        self.assertFalse(dbs["dbx"]["enrolled"])


class TestPreflightChecks(unittest.TestCase):
    """Test environment preflight validation."""

    @patch("tasks.secureboot.preflight.is_uefi_boot", return_value=True)
    @patch("tasks.secureboot.preflight.is_efivars_mounted", return_value=True)
    @patch("tasks.secureboot.preflight.is_arch_linux", return_value=True)
    @patch("tasks.secureboot.preflight.get_sbctl_version", return_value="0.16")
    @patch("tasks.secureboot.preflight.check_tool_availability", return_value={"sbctl": True})
    @patch("tasks.secureboot.preflight.inspect_firmware", return_value={"secure_boot_enabled": False, "setup_mode": True})
    def test_preflight_success_in_setup_mode(self, *mocks):
        rep = preflight.run_preflight()
        self.assertTrue(rep.is_ready_for_setup)
        self.assertEqual(len(rep.blockers), 0)

    @patch("tasks.secureboot.preflight.is_uefi_boot", return_value=False)
    @patch("tasks.secureboot.preflight.is_efivars_mounted", return_value=False)
    def test_preflight_fails_on_legacy_bios(self, *mocks):
        rep = preflight.run_preflight()
        self.assertFalse(rep.is_ready_for_setup)
        self.assertTrue(any("Legacy BIOS" in b for b in rep.blockers))


class TestKeyManagement(unittest.TestCase):
    """Test key generation, inspection, permissions, and backups."""

    @patch("tasks.secureboot.keys.SBCTL_KEYS_DIR")
    @patch("shutil.which", return_value=None)
    def test_keys_exist_check(self, mock_which, mock_keys_dir):
        mock_keys_dir.is_dir.return_value = True
        pk_dir = MagicMock()
        pk_dir.is_dir.return_value = True
        pk_dir.glob.return_value = [Path("/usr/share/secureboot/keys/PK/PK.key")]
        mock_keys_dir.__truediv__.return_value = pk_dir

        self.assertTrue(keys.do_keys_exist())

    @patch("tasks.secureboot.keys.do_keys_exist", return_value=True)
    def test_create_keys_prevents_overwrite_without_force(self, mock_exist):
        ok, msg = keys.create_keys(force=False)
        self.assertFalse(ok)
        self.assertIn("prevent overwriting", msg)

    @patch("tasks.secureboot.keys.do_keys_exist", return_value=False)
    @patch("shutil.which", return_value="/usr/bin/sbctl")
    @patch("core.logger.logger.run_cmd", return_value=(0, ""))
    @patch("tasks.secureboot.keys._secure_key_permissions")
    def test_create_keys_success(self, mock_perm, mock_run, mock_which, mock_exist):
        ok, msg = keys.create_keys()
        self.assertTrue(ok)
        mock_run.assert_called_once_with(["sudo", "sbctl", "create-keys"], check=False)
        mock_perm.assert_called_once()


class TestBootloaderAdapters(unittest.TestCase):
    """Test bootloader adapters for systemd-boot, GRUB, rEFInd, and Limine."""

    def test_systemd_boot_adapter_detection(self):
        adapter = SystemdBootAdapter()
        inv = {"bootloader": {"name": "systemd-boot"}}
        self.assertTrue(adapter.detect(inv))

    def test_grub_adapter_detection(self):
        adapter = GrubAdapter()
        inv = {"bootloader": {"name": "grub"}}
        self.assertTrue(adapter.detect(inv))
        # GRUB must provide chain notes warning
        insp = adapter.inspect()
        self.assertIn("CRITICAL", insp["chain_notes"])

    def test_refind_adapter_detection(self):
        adapter = RefindAdapter()
        inv = {"bootloader": {"name": "refind"}}
        self.assertTrue(adapter.detect(inv))

    def test_limine_adapter_detection(self):
        adapter = LimineAdapter()
        inv = {"bootloader": {"name": "limine"}}
        self.assertTrue(adapter.detect(inv))

    @patch("shutil.which", return_value="/usr/bin/sbctl")
    @patch("core.logger.logger.run_cmd", return_value=(0, ""))
    def test_systemd_boot_sign(self, mock_run, mock_which):
        adapter = SystemdBootAdapter()
        with patch.object(adapter, "get_signable_files", return_value=[Path("/boot/EFI/systemd/systemd-bootx64.efi")]):
            ok, msg = adapter.sign()
            self.assertTrue(ok)
            mock_run.assert_called_once_with(
                ["sudo", "sbctl", "sign", "-s", "/boot/EFI/systemd/systemd-bootx64.efi"],
                check=False,
            )


class TestKernelAndUKIDetection(unittest.TestCase):
    """Test traditional kernels vs UKI detection."""

    @patch("tasks.secureboot.kernel.detect_installed_kernels")
    @patch("tasks.secureboot.kernel.detect_unified_kernel_images")
    @patch("tasks.secureboot.kernel.get_primary_esp_path", return_value=None)
    def test_traditional_kernel_detection(self, mock_esp, mock_ukis, mock_kernels):
        mock_kernels.return_value = [{"name": "linux", "vmlinuz_path": "/boot/vmlinuz-linux"}]
        mock_ukis.return_value = []

        cfg = kernel.inspect_kernel_configuration()
        self.assertFalse(cfg["uses_uki"])
        self.assertIsNotNone(cfg["tamper_warning"])
        self.assertIn("vmlinuz executable itself", cfg["tamper_warning"])

    @patch("tasks.secureboot.kernel.detect_installed_kernels")
    @patch("tasks.secureboot.kernel.detect_unified_kernel_images")
    @patch("tasks.secureboot.kernel.get_primary_esp_path", return_value=None)
    def test_uki_detection(self, mock_esp, mock_ukis, mock_kernels):
        mock_kernels.return_value = []
        mock_ukis.return_value = [{"name": "arch-linux", "path": "/boot/EFI/Linux/arch-linux.efi"}]

        cfg = kernel.inspect_kernel_configuration()
        self.assertTrue(cfg["uses_uki"])
        self.assertIsNone(cfg["tamper_warning"])


class TestWindowsDualBootProtection(unittest.TestCase):
    """Test Windows detection and signing protection."""

    def test_refuses_to_sign_windows_binaries(self):
        win_bin = Path("/efi/EFI/Microsoft/Boot/bootmgfw.efi")
        self.assertTrue(signing.is_windows_binary(win_bin))

        ok, msg = signing.sign_file(win_bin)
        self.assertFalse(ok)
        self.assertIn("Refusing to modify Windows binary", msg)

    @patch("tasks.secureboot.inventory.find_esp_mounts")
    def test_windows_detection(self, mock_findmnt):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            win_dir = tmp_p / "EFI/Microsoft/Boot"
            win_dir.mkdir(parents=True)
            (win_dir / "bootmgfw.efi").write_text("dummy")

            mock_findmnt.return_value = [{"mountpoint": str(tmp_p)}]
            win = inventory.detect_windows()
            self.assertTrue(win["detected"])
            self.assertTrue(win["bitlocker_warning"])


class TestFirmwareEnrollmentPreconditions(unittest.TestCase):
    """Test enrollment preconditions and guards."""

    @patch("tasks.secureboot.enrollment.is_uefi_boot", return_value=True)
    @patch("tasks.secureboot.enrollment.is_efivars_mounted", return_value=True)
    @patch("tasks.secureboot.enrollment.is_setup_mode", return_value=False)
    @patch("tasks.secureboot.enrollment.do_keys_exist", return_value=True)
    def test_enrollment_blocked_in_user_mode(self, *mocks):
        check = enrollment.EnrollmentPreconditionCheck()
        passed = check.run()
        self.assertFalse(passed)
        self.assertTrue(any("NOT in Setup Mode" in b for b in check.blockers))

    @patch("tasks.secureboot.enrollment.is_uefi_boot", return_value=True)
    @patch("tasks.secureboot.enrollment.is_efivars_mounted", return_value=True)
    @patch("tasks.secureboot.enrollment.is_setup_mode", return_value=True)
    @patch("tasks.secureboot.enrollment.do_keys_exist", return_value=True)
    @patch("tasks.secureboot.enrollment.inspect_key_inventory", return_value={
        "PK": {"ready": True}, "KEK": {"ready": True}, "db": {"ready": True}
    })
    @patch("tasks.secureboot.enrollment.verify_all_system_files", return_value={"all_verified": True})
    @patch("tasks.secureboot.enrollment.has_existing_backup", return_value=True)
    def test_enrollment_preconditions_pass(self, *mocks):
        check = enrollment.EnrollmentPreconditionCheck()
        passed = check.run()
        self.assertTrue(passed)
        self.assertEqual(len(check.blockers), 0)


class TestUpdateAutomation(unittest.TestCase):
    """Test pacman hook installation and inspection."""

    @patch("core.logger.logger.run_cmd", return_value=(0, ""))
    def test_install_update_hook(self, mock_run):
        ok, msg = updates.install_update_hooks()
        self.assertTrue(ok)
        self.assertIn("installed successfully", msg)


class TestStateEngineAndJournal(unittest.TestCase):
    """Test observed vs desired state engine and operation journal."""

    def test_execution_plan_generation(self):
        observed = state.ObservedState()
        observed.keys_exist = False
        observed.active_bootloader = "systemd-boot"

        desired = state.DesiredState()
        desired.keys_generated = True

        plan = state.ExecutionPlan(observed, desired)
        actions = plan.get_actions()
        action_types = [a["type"] for a in actions]

        self.assertIn("generate_keys", action_types)
        self.assertIn("sign_bootloader", action_types)

    def test_operation_journal_logging(self):
        journal = state.OperationJournal()
        journal.record("test_op", "SUCCESS", "Test operation completed", {"key": "safe_data"})
        entries = journal.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["operation"], "test_op")
        self.assertEqual(entries[0]["status"], "SUCCESS")


class TestHealthCheckAndVerification(unittest.TestCase):
    """Test multi-dimensional health check engine."""

    @patch("tasks.secureboot.verification.is_uefi_boot", return_value=True)
    @patch("tasks.secureboot.verification.is_efivars_mounted", return_value=True)
    @patch("tasks.secureboot.verification.is_secure_boot_enabled", return_value=True)
    @patch("tasks.secureboot.verification.is_setup_mode", return_value=False)
    @patch("tasks.secureboot.verification.do_keys_exist", return_value=True)
    @patch("tasks.secureboot.verification.inspect_key_inventory", return_value={
        "PK": {"ready": True}, "KEK": {"ready": True}, "db": {"ready": True}
    })
    @patch("tasks.secureboot.verification.find_esp_mounts", return_value=[{"mountpoint": "/boot"}])
    @patch("tasks.secureboot.verification.get_primary_esp_path", return_value=Path("/boot"))
    @patch("tasks.secureboot.verification.get_active_adapter")
    @patch("tasks.secureboot.verification.verify_all_system_files", return_value={"all_verified": True})
    @patch("tasks.secureboot.verification.inspect_update_hooks", return_value={"is_configured": True})
    def test_full_health_check_healthy(self, mock_hk, mock_ver, mock_adapter, *mocks):
        ad = MagicMock()
        ad.verify.return_value = {"all_signed": True}
        ad.display_name = "systemd-boot"
        mock_adapter.return_value = ad

        health = verification.run_full_health_check()
        self.assertEqual(health.overall_status, config.STATUS_HEALTHY)
        self.assertEqual(health.failed_count, 0)


class TestGuidedRecovery(unittest.TestCase):
    """Test diagnostics and recovery recommendation generator."""

    @patch("tasks.secureboot.recovery.is_uefi_boot", return_value=False)
    def test_recovery_identifies_legacy_bios(self, mock_uefi):
        issues = recovery.diagnose_system()
        self.assertTrue(any("Legacy BIOS" in i["title"] for i in issues))
        legacy_issue = next(i for i in issues if "Legacy BIOS" in i["title"])
        self.assertFalse(legacy_issue["automatic_fix"])  # Must be manual firmware setting!


class TestAdvancedScenarios(unittest.TestCase):
    """Tests complex real-world edge cases: multi-kernel, multi-ESP, unsupported bootloader, idempotency."""

    @patch("tasks.secureboot.kernel.detect_installed_kernels")
    @patch("tasks.secureboot.kernel.detect_unified_kernel_images")
    @patch("tasks.secureboot.kernel.find_esp_mounts")
    def test_multiple_kernels_signing(self, mock_esps, mock_ukis, mock_kernels):
        mock_esps.return_value = []
        mock_ukis.return_value = []
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            k1 = tmp_p / "vmlinuz-linux"
            k2 = tmp_p / "vmlinuz-linux-lts"
            k3 = tmp_p / "vmlinuz-linux-zen"
            for k in (k1, k2, k3):
                k.write_text("kernel_stub")

            with patch("tasks.secureboot.kernel.ARCH_KERNEL_NAMES", ("linux", "linux-lts", "linux-zen")):
                with patch("pathlib.Path.is_file", side_effect=lambda: True):
                    with patch("shutil.which", return_value="/usr/bin/sbctl"):
                        with patch("core.logger.logger.run_cmd", return_value=(0, "")) as mock_cmd:
                            with patch("tasks.secureboot.kernel.get_signable_kernel_files", return_value=[k1, k2, k3]):
                                ok, signed, failed = kernel.sign_all_kernels()
                                self.assertTrue(ok)
                                self.assertEqual(len(signed), 3)
                                self.assertEqual(len(failed), 0)

    def test_unsupported_bootloader_reported(self):
        from tasks.secureboot.adapters import get_active_adapter
        inv = {"bootloader": {"name": "unsupported_exotic_bootloader"}}
        adapter = get_active_adapter(inv)
        self.assertIsNone(adapter)

    def test_idempotency_of_execution_plan(self):
        """Validates that a system already in desired state produces no high-risk actions."""
        observed = state.ObservedState()
        observed.keys_exist = True
        observed.keys_enrolled = True
        observed.signing_hooks_present = True

        desired = state.DesiredState()
        desired.keys_generated = True
        desired.keys_enrolled = True
        desired.install_hooks = True

        plan = state.ExecutionPlan(observed, desired)
        # All actions should be skipped or non-destructive
        self.assertFalse(plan.has_high_risk())
        skipped = plan.get_skipped()
        skipped_types = [s["type"] for s in skipped]
        self.assertIn("skip_key_generation", skipped_types)
        self.assertIn("skip_enrollment", skipped_types)
        self.assertIn("verify_hooks", skipped_types)


class TestDiagnosticReport(unittest.TestCase):
    """Test report formatting and compilation."""

    def test_generate_report(self):
        content, path = report.generate_diagnostic_report()
        self.assertTrue(path.is_file())
        self.assertIn("ARCHSETUP SECURE BOOT DIAGNOSTIC REPORT", content)
        self.assertIn("FIRMWARE & PLATFORM", content)
        self.assertIn("SIGNATURE VERIFICATION", content)


if __name__ == "__main__":
    unittest.main()
