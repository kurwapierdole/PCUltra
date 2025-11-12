#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Информация о версии PCUltra.
Значение APP_VERSION следует обновлять при подготовке нового релиза.
"""

APP_VERSION: str = "0.1.0"
GITHUB_REPOSITORY: str = "kurwapierdole/PCUltra"
RELEASES_URL: str = f"https://github.com/{GITHUB_REPOSITORY}/releases"


def get_version() -> str:
    """Возвращает текущую версию приложения."""
    return APP_VERSION

