#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для проверки обновлений и скачивания новых версий PCUltra.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"


@dataclass
class UpdateInfo:
    """Информация о доступном обновлении."""

    version: str
    tag_name: str
    download_url: str
    asset_name: str
    release_url: str
    notes_preview: str = ""


class UpdateManager:
    """Менеджер для проверки и загрузки обновлений из GitHub releases."""

    def __init__(
        self,
        repository: str,
        current_version: str,
        *,
        session: Optional[requests.Session] = None,
    ):
        self.repository = repository
        self.current_version = current_version
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": f"PCUltra/{current_version}",
                "Accept": "application/vnd.github+json",
            }
        )
        self._lock = threading.Lock()
        self._last_available: Optional[UpdateInfo] = None

    # -------------------- Публичные методы --------------------

    def check_for_updates(self) -> Optional[UpdateInfo]:
        """Проверяет наличие обновлений. Возвращает UpdateInfo или None."""
        with self._lock:
            try:
                release_data = self._fetch_latest_release()
            except Exception as exc:
                logger.warning("Не удалось получить данные о релизах: %s", exc)
                return None

            if not release_data:
                return None

            tag_name = release_data.get("tag_name") or ""
            normalized_new = self._normalize_version(tag_name)
            normalized_current = self._normalize_version(self.current_version)

            if not normalized_new:
                logger.debug("Не удалось распознать версию в теге: %s", tag_name)
                return None

            if self._compare_versions(normalized_new, normalized_current) <= 0:
                logger.debug(
                    "Обновление не требуется. Текущая версия: %s, релиз: %s",
                    self.current_version,
                    tag_name,
                )
                return None

            asset = self._select_asset(release_data)
            if not asset:
                logger.debug("Не найден .exe файл в релизе %s", tag_name)
                return None

            download_url = asset.get("browser_download_url")
            asset_name = asset.get("name") or Path(download_url).name
            release_url = release_data.get("html_url") or self._build_release_url(tag_name)
            notes_preview = self._make_notes_preview(release_data.get("body") or "")

            update_info = UpdateInfo(
                version=self._display_version(tag_name),
                tag_name=tag_name,
                download_url=download_url,
                asset_name=asset_name,
                release_url=release_url,
                notes_preview=notes_preview,
            )

            self._last_available = update_info
            return update_info

    def download_update(self, update: UpdateInfo, *, target_dir: Optional[Path] = None) -> Path:
        """
        Скачивает указанный релиз в target_dir (по умолчанию – директория текущего exe).
        Возвращает путь к скачанному файлу.
        """
        target_dir = target_dir or self.get_install_directory()
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = self._make_target_filename(update)
        target_path = target_dir / filename

        if target_path.exists():
            logger.info("Удаляю предыдущий файл обновления %s", target_path)
            target_path.unlink()

        logger.info("Скачиваю обновление %s → %s", update.download_url, target_path)
        try:
            tmp_path: Optional[Path] = None
            with self._session.get(update.download_url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(delete=False, dir=target_dir, suffix=".download") as tmp:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            tmp.write(chunk)
                    tmp_path = Path(tmp.name)
            if tmp_path is None:
                raise RuntimeError("Не удалось сохранить временный файл обновления")
            tmp_path.replace(target_path)
        except Exception as exc:
            logger.error("Ошибка скачивания обновления: %s", exc)
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

        return target_path

    def launch_executable(self, executable_path: Path, *args: str) -> None:
        """Запускает указанный exe-файл."""
        try:
            logger.info("Запускаю новую версию: %s", executable_path)
            subprocess.Popen(
                [str(executable_path), *args],
                cwd=str(executable_path.parent),
                shell=False,
            )
        except Exception as exc:
            logger.error("Не удалось запустить файл обновления: %s", exc)
            raise

    def can_self_update(self) -> bool:
        """Проверяет, запущено ли приложение из exe и доступно ли автообновление."""
        return self.is_running_from_executable() and self.get_current_executable_path().suffix.lower() == ".exe"

    def is_running_from_executable(self) -> bool:
        return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

    def get_current_executable_path(self) -> Path:
        if self.is_running_from_executable():
            return Path(sys.executable).resolve()
        return Path(__file__).resolve()

    def get_install_directory(self) -> Path:
        return self.get_current_executable_path().parent

    # -------------------- Вспомогательные методы --------------------

    def _fetch_latest_release(self) -> Optional[dict]:
        url = f"{GITHUB_API_URL}/repos/{self.repository}/releases/latest"
        response = self._session.get(url, timeout=10)
        if response.status_code == 404:
            logger.warning("Релизы репозитория %s не найдены", self.repository)
            return None
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _select_asset(release_data: dict) -> Optional[dict]:
        assets = release_data.get("assets") or []
        for asset in assets:
            download_url = asset.get("browser_download_url", "").lower()
            if download_url.endswith(".exe"):
                return asset
        return None

    def _build_release_url(self, tag_name: str) -> str:
        clean_tag = tag_name.strip()
        if not clean_tag:
            return f"https://github.com/{self.repository}/releases"
        return f"https://github.com/{self.repository}/releases/tag/{clean_tag}"

    @staticmethod
    def _make_notes_preview(notes: str, limit: int = 800) -> str:
        text = (notes or "").strip()
        if not text:
            return ""
        text = re.sub(r"\r\n", "\n", text)
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    @staticmethod
    def _display_version(tag_name: str) -> str:
        tag = tag_name.strip()
        if tag.lower().startswith("v"):
            tag = tag[1:]
        return tag or tag_name

    @staticmethod
    def _normalize_version(version: str) -> tuple:
        if not version:
            return tuple()
        version = version.strip()
        if version.lower().startswith("v"):
            version = version[1:]
        tokens = []
        for part in re.split(r"[^\w]+", version):
            if not part:
                continue
            if part.isdigit():
                tokens.append(int(part))
            else:
                tokens.append(part.lower())
        return tuple(tokens)

    @staticmethod
    def _compare_versions(new_version: tuple, current_version: tuple) -> int:
        for new_token, current_token in zip_longest(new_version, current_version, fillvalue=0):
            if isinstance(new_token, int) and isinstance(current_token, int):
                if new_token != current_token:
                    return 1 if new_token > current_token else -1
            else:
                new_str = str(new_token)
                current_str = str(current_token)
                if new_str != current_str:
                    return 1 if new_str > current_str else -1
        return 0

    def _make_target_filename(self, update: UpdateInfo) -> str:
        base_name = Path(update.asset_name).stem or "PCUltra"
        safe_version = re.sub(r"[^\w.-]", "_", update.version)
        suffix = Path(update.asset_name).suffix or ".exe"
        return f"{base_name}_{safe_version}{suffix}"

