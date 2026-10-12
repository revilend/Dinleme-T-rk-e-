#!/usr/bin/env python3
"""Moslashuvchikilot (backwards compatibility).

Asosiy kirish nuqtasi **`bot.py`**: Render'da `python bot.py` ishga tushiriladi
(HTTP healthcheck + long-polling bitta loopda). `python main.py` ham ishlashda
davom etadi — u shu zamonaviy kodni chaqiradi.
"""

from bot import HOST, PORT, main, run, start_http_server

__all__ = ["HOST", "PORT", "main", "run", "start_http_server"]


if __name__ == "__main__":
    run()
