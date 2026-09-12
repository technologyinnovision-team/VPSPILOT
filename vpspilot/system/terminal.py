"""
Interactive Web Terminal Bridge for VPSPilot
Spawns an interactive shell PTY and bridges it to an aiohttp WebSocket.
"""

import os
import pty
import fcntl
import termios
import struct
import asyncio
import subprocess
import json
import logging
from aiohttp import web, WSMsgType

logger = logging.getLogger("vpspilot.terminal")

class TerminalSession:
    def __init__(self, ws: web.WebSocketResponse, loop: asyncio.AbstractEventLoop, cols: int = 80, rows: int = 24):
        self.ws = ws
        self.loop = loop
        self.cols = cols
        self.rows = rows
        self.master_fd = None
        self.proc = None
        self.is_alive = False

    def resize(self, cols: int, rows: int):
        if self.master_fd is not None:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
                self.cols = cols
                self.rows = rows
            except OSError as e:
                logger.warning(f"Failed to resize terminal: {e}")

    def _on_pty_read(self):
        if not self.is_alive or self.master_fd is None:
            return
        try:
            data = os.read(self.master_fd, 8192)
            if data:
                text = data.decode("utf-8", errors="replace")
                if not self.ws.closed:
                    asyncio.create_task(self.ws.send_str(text))
            else:
                # EOF reached
                self.close()
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            self.close()

    def start(self):
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd

        # Set non-blocking I/O on master_fd
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Set initial terminal dimensions
        self.resize(self.cols, self.rows)

        # Environment variables
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"
        env["LANG"] = env.get("LANG", "en_US.UTF-8")

        shell = os.environ.get("SHELL", "/bin/bash")
        if not os.path.exists(shell):
            shell = "/bin/sh"

        self.proc = subprocess.Popen(
            [shell, "-l"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            close_fds=True,
            env=env
        )
        os.close(slave_fd)
        self.is_alive = True

        # Register asyncio reader on master_fd
        self.loop.add_reader(self.master_fd, self._on_pty_read)

    def write(self, data: str):
        if self.master_fd is not None and self.is_alive:
            try:
                os.write(self.master_fd, data.encode("utf-8"))
            except OSError as e:
                logger.warning(f"Error writing to terminal PTY: {e}")

    def close(self):
        if not self.is_alive:
            return
        self.is_alive = False

        if self.master_fd is not None:
            try:
                self.loop.remove_reader(self.master_fd)
            except Exception:
                pass
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=0.5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None

        if not self.ws.closed:
            asyncio.create_task(self.ws.close())

async def handle_terminal_ws(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=15.0)
    await ws.prepare(request)

    loop = asyncio.get_running_loop()
    session = TerminalSession(ws, loop)

    try:
        session.start()

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = msg.data
                # Check for control packets (resize: JSON {"type": "resize", "cols": 100, "rows": 30})
                if data.startswith('{"type":') or data.startswith('{"action":'):
                    try:
                        payload = json.loads(data)
                        if payload.get("type") == "resize":
                            session.resize(int(payload.get("cols", 80)), int(payload.get("rows", 24)))
                            continue
                    except Exception:
                        pass
                session.write(data)

            elif msg.type == WSMsgType.BINARY:
                session.write(msg.data.decode("utf-8", errors="replace"))

            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.ERROR):
                break

    except Exception as e:
        logger.error(f"WebSocket terminal exception: {e}")
    finally:
        session.close()

    return ws
