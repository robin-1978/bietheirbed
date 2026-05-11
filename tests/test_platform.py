from __future__ import annotations

import pytest

from pc_assistant import platform_


class TestGetPlatform:
    @pytest.mark.parametrize("system_value,expected", [
        ("Windows", "windows"),
        ("Linux", "linux"),
        ("Darwin", "macos"),
    ])
    def test_known_platforms(self, monkeypatch, system_value, expected):
        monkeypatch.setattr(platform_.platform, "system", lambda: system_value)
        assert platform_.get_platform() == expected

    def test_unsupported_platform(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "FreeBSD")
        with pytest.raises(RuntimeError, match="Unsupported platform"):
            platform_.get_platform()


class TestGetShellCommand:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Windows")
        assert platform_.get_shell_command() == ("powershell", "-Command")

    def test_linux(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        assert platform_.get_shell_command() == ("/bin/bash", "-c")

    def test_macos(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Darwin")
        assert platform_.get_shell_command() == ("/bin/zsh", "-c")


class TestGetShellName:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Windows")
        assert platform_.get_shell_name() == "PowerShell"

    def test_linux(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        assert platform_.get_shell_name() == "bash"

    def test_macos(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Darwin")
        assert platform_.get_shell_name() == "zsh"


class TestGetDefaultDangerousCommands:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Windows")
        cmds = platform_.get_default_dangerous_commands()
        assert "del /s /q" in cmds
        assert "rd /s" in cmds
        assert "rmdir /s" in cmds
        assert "remove-item -recurse" in cmds
        assert "format" in cmds
        assert "shutdown" in cmds
        assert "taskkill /f" in cmds
        assert "reg delete" in cmds
        assert "net user" in cmds
        assert "cipher /w" in cmds
        assert "diskpart" in cmds
        assert "bcdedit" in cmds

    def test_linux(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        cmds = platform_.get_default_dangerous_commands()
        assert "rm -rf /" in cmds
        assert "mkfs" in cmds
        assert "dd if=" in cmds
        assert "shutdown" in cmds
        assert "reboot" in cmds
        assert "fdisk" in cmds
        assert "mkswap" in cmds
        assert "systemctl stop" in cmds
        assert "init 0" in cmds
        assert "init 6" in cmds
        assert ":(){ :|:& };:" in cmds

    def test_macos(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Darwin")
        cmds = platform_.get_default_dangerous_commands()
        assert "rm -rf /" in cmds
        assert "diskutil eraseDisk" in cmds
        assert "diskutil partitionDisk" in cmds
        assert "shutdown" in cmds
        assert "mkfs" in cmds
        assert "dd if=" in cmds

    def test_returns_copy(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        a = platform_.get_default_dangerous_commands()
        b = platform_.get_default_dangerous_commands()
        assert a == b
        assert a is not b


class TestGetDefaultProtectedPaths:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Windows")
        paths = platform_.get_default_protected_paths()
        assert "C:\\Windows\\System32" in paths
        assert "C:\\Windows\\SysWOW64" in paths
        assert "C:\\Program Files" in paths
        assert "C:\\ProgramData" in paths

    def test_linux(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        paths = platform_.get_default_protected_paths()
        assert "/etc/passwd" in paths
        assert "/etc/shadow" in paths
        assert "/etc/sudoers" in paths
        assert "/boot" in paths
        assert "/proc" in paths
        assert "/sys" in paths

    def test_macos(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Darwin")
        paths = platform_.get_default_protected_paths()
        assert "/System" in paths
        assert "/Library" in paths
        assert "/usr/sbin" in paths
        assert "/private/var/db" in paths

    def test_returns_copy(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        a = platform_.get_default_protected_paths()
        b = platform_.get_default_protected_paths()
        assert a == b
        assert a is not b


class TestGetPathSeparator:
    def test_windows(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Windows")
        assert platform_.get_path_separator() == "\\"

    def test_linux(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        assert platform_.get_path_separator() == "/"

    def test_macos(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Darwin")
        assert platform_.get_path_separator() == "/"


class TestNormalizePath:
    def test_windows_forward_to_back(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Windows")
        assert platform_.normalize_path("C:/Users/test/file.txt") == "C:\\Users\\test\\file.txt"

    def test_windows_already_back(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Windows")
        assert platform_.normalize_path("C:\\Users\\test\\file.txt") == "C:\\Users\\test\\file.txt"

    def test_linux_back_to_forward(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        assert platform_.normalize_path("home\\user\\file.txt") == "home/user/file.txt"

    def test_linux_already_forward(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Linux")
        assert platform_.normalize_path("/home/user/file.txt") == "/home/user/file.txt"

    def test_macos_back_to_forward(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Darwin")
        assert platform_.normalize_path("Users\\test\\file.txt") == "Users/test/file.txt"

    def test_macos_already_forward(self, monkeypatch):
        monkeypatch.setattr(platform_.platform, "system", lambda: "Darwin")
        assert platform_.normalize_path("/Users/test/file.txt") == "/Users/test/file.txt"
