/**
 * Terminal Manager for VPSPilot
 * Bridges xterm.js frontend with backend PTY via WebSocket
 */

let term = null;
let fitAddon = null;
let termSocket = null;
let isConnecting = false;

function getAuthToken() {
  return localStorage.getItem("vpspilot_token") || "";
}

function initTerminal() {
  const container = document.getElementById("terminal-container");
  if (!container || term) return;

  // Verify xterm is loaded
  if (typeof Terminal === "undefined") {
    console.error("xterm.js is not loaded yet.");
    return;
  }

  term = new Terminal({
    cursorBlink: true,
    cursorStyle: "block",
    fontSize: 14,
    fontFamily: '"JetBrains Mono", "Fira Code", monospace, monospace',
    theme: {
      background: "#07090e",
      foreground: "#f3f4f6",
      cursor: "#3b82f6",
      selectionBackground: "rgba(59, 130, 246, 0.4)",
      black: "#0b0f19",
      red: "#ef4444",
      green: "#10b981",
      yellow: "#f59e0b",
      blue: "#3b82f6",
      magenta: "#8b5cf6",
      cyan: "#06b6d4",
      white: "#f3f4f6",
      brightBlack: "#4b5563",
      brightRed: "#f87171",
      brightGreen: "#34d399",
      brightYellow: "#fbbf24",
      brightBlue: "#60a5fa",
      brightMagenta: "#a78bfa",
      brightCyan: "#22d3ee",
      brightWhite: "#ffffff"
    }
  });

  if (typeof FitAddon !== "undefined" && FitAddon.FitAddon) {
    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
  }

  term.open(container);
  if (fitAddon) {
    fitAddon.fit();
  }

  // Handle user typing input
  term.onData((data) => {
    if (termSocket && termSocket.readyState === WebSocket.OPEN) {
      termSocket.send(data);
    }
  });

  // Handle window resizing
  window.addEventListener("resize", () => {
    fitTerminal();
  });

  connectTerminalSocket();
}

function fitTerminal() {
  if (!term || !fitAddon) return;
  try {
    fitAddon.fit();
    if (termSocket && termSocket.readyState === WebSocket.OPEN) {
      const resizeMsg = JSON.stringify({
        type: "resize",
        cols: term.cols,
        rows: term.rows
      });
      termSocket.send(resizeMsg);
    }
  } catch (err) {
    console.warn("Terminal fit error:", err);
  }
}

function connectTerminalSocket() {
  if (termSocket && (termSocket.readyState === WebSocket.OPEN || termSocket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  isConnecting = true;
  const token = getAuthToken();
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/terminal?token=${encodeURIComponent(token)}`;

  const statusIndicator = document.getElementById("terminal-status");
  if (statusIndicator) statusIndicator.textContent = "Connecting...";

  termSocket = new WebSocket(wsUrl);

  termSocket.onopen = () => {
    isConnecting = false;
    if (statusIndicator) statusIndicator.textContent = "Connected";
    term.focus();
    // Notify server of dimensions
    setTimeout(() => fitTerminal(), 150);
  };

  termSocket.onmessage = (event) => {
    if (term) {
      term.write(event.data);
    }
  };

  termSocket.onclose = () => {
    isConnecting = false;
    if (statusIndicator) statusIndicator.textContent = "Disconnected";
    if (term) {
      term.write("\r\n\x1b[31m[VPSPilot] Terminal session ended.\x1b[0m\r\n");
    }
  };

  termSocket.onerror = (err) => {
    isConnecting = false;
    if (statusIndicator) statusIndicator.textContent = "Connection Error";
  };
}

function clearTerminal() {
  if (term) {
    term.clear();
  }
}

function sendTerminalSignal(char) {
  if (termSocket && termSocket.readyState === WebSocket.OPEN) {
    termSocket.send(char);
    if (term) term.focus();
  }
}

function reconnectTerminal() {
  if (termSocket) {
    try {
      termSocket.close();
    } catch (e) {}
  }
  if (term) {
    term.reset();
  }
  connectTerminalSocket();
}

window.initTerminal = initTerminal;
window.fitTerminal = fitTerminal;
window.clearTerminal = clearTerminal;
window.sendTerminalSignal = sendTerminalSignal;
window.reconnectTerminal = reconnectTerminal;
