# Enterprise Network Performance & Security Monitor

A high-performance, real-time network diagnostics and security auditing dashboard. This application features a decoupled client-server architecture combining **FastAPI (Python)** and **React (TypeScript)** to stream OS-level network telemetry (latency, jitter, interface throughput, Scapy packet sniffing) straight to a glassmorphic web dashboard.

Designed with advanced software engineering patterns—**asynchronous I/O concurrency**, **multi-threaded background processing**, **thread-safe memory state synchronization**, and **resilient WebSockets**—to demonstrate production-grade system designs expected in FAANG software engineering interviews.

---

## 🏗️ System Architecture

```
                    +------------------------------------+
                    |        React + TypeScript          |
                    |        Frontend Dashboard          |
                    +------------------------------------+
                                      |
                      WebSockets      |     REST APIs
                      (Telemetry)     |     (Scanner / Speedtest)
                                      v
                    +------------------------------------+
                    |          FastAPI Backend           |
                    |           (Uvicorn ASGI)           |
                    +------------------------------------+
                               |              |
                    SQLAlchemy |              | Async Task
                               v              v
                        +-----------+   +-----------------------+
                        |  SQLite   |   | Asynchronous Telemetry|
                        |  Database |   |      Loop (2s)        |
                        +-----------+   +-----------------------+
                                                    |
                                       +------------+------------+
                                       |            |            |
                                       v            v            v
                                   [ping3]       [psutil]     [Thread]
                                   Latency       Bandwidth       |
                                                             [Scapy]
                                                          Packet Sniffer
```

---

## 🚀 Key Features

*   **Real-time WebSocket Telemetry**: Low-latency, full-duplex WebSocket connections streaming ping, standard deviation jitter, packet loss, and global NIC throughput.
*   **Multi-threaded Packet Sniffer**: Background packet capturing using `scapy` on a dedicated thread, compiling packet distribution percentages (TCP/UDP/ICMP/DNS) and monitoring top hosts without blocking the web server.
*   **Asynchronous TCP Port Scanner**: An ultra-fast scanner built with `asyncio.open_connection` capped at 100 concurrent sockets using an `asyncio.Semaphore` to prevent OS socket exhaustion.
*   **Active Alerts Center**: Automated backend monitors logging warnings/critical alerts (e.g. latency > 120ms or packet loss > 10%) to the DB and pushing toast alerts to the UI.
*   **Speedtest.net Integration**: Offloads blocking multi-threaded download/upload benchmarks to background thread-pool executors (`asyncio.to_thread`) to maintain server responsiveness.
*   **CORS Bypass Middleware**: A custom ASGI middleware wrapper allowing WebSockets to bypass CORS upgrades safely while securing HTTP REST endpoints.

---

## 🛠️ Tech Stack

*   **Backend**: Python 3.11, FastAPI, Uvicorn, SQLAlchemy (SQLite), Psutil, Scapy, Ping3, Speedtest-cli.
*   **Frontend**: React, TypeScript, Vite, Chart.js, React-ChartJS-2, Lucide Icons.

---

## 📁 Repository Structure

```text
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── bandwidth.py   # NIC speed/error/drop monitoring (psutil)
│   │   │   ├── latency.py     # Ping, jitter, and traceroute engine (ping3)
│   │   │   ├── scanner.py     # Asynchronous TCP port scanner (asyncio)
│   │   │   ├── sniffer.py     # Background packet sniffer thread (scapy)
│   │   │   └── speedtest.py   # Asynchronous Speedtest.net runner
│   │   ├── __init__.py
│   │   ├── database.py        # SQLAlchemy configuration & DB session managers
│   │   ├── main.py            # FastAPI ASGI server, routing & WebSockets
│   │   ├── models.py          # SQLAlchemy SQLite database models
│   │   └── schemas.py         # Pydantic validation & serialization models
│   ├── .env                   # Configuration & alert threshold variables
│   ├── .gitignore
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # Main dashboard, WS listeners, API triggers
│   │   ├── App.css            # Glassmorphic dark theme variables & CSS styles
│   │   ├── index.css
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
└── README.md
```

---

## ⚙️ Setup and Installation

### 1. Backend (Run as Administrator)
The packet sniffer requires raw socket access to read interface packets, which requires **Administrator privileges** on Windows/Linux.

Open a PowerShell/Terminal window as **Administrator**:
```powershell
# 1. Navigate to the backend folder
cd backend

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install packages
pip install -r requirements.txt

# 4. Set up environment variables (.env is gitignored, populate it)
# (Ensure D:\Project_SDE\backend\.env contains the configuration variables)

# 5. Launch the FastAPI server
uvicorn app.main:app --reload --ws wsproto
```

### 2. Frontend
Open a **second terminal** (standard permissions are fine):
```powershell
# 1. Navigate to the frontend folder
cd frontend

# 2. Install dependencies
npm install

# 3. Launch Vite development server
npm run dev
```

Open your browser to **[http://localhost:5173](http://localhost:5173)** to see the dashboard!

---

## 💡 Systems & Concurrency Talking Points for Interviews

Prepare to speak about these architectural designs in your FAANG coding and system design interviews:

### 1. Hybrid Concurrency: Asynchronous vs. Multi-threading
*   **The Problem**: Network monitoring requires both waiting on network sockets (I/O-bound) and parsing high-velocity raw packets from interfaces (CPU/blocking system calls).
*   **The Choice**:
    *   `asyncio` is used for the **Port Scanner** because it's I/O-bound and waiting for replies sequentially is slow. Async allows a single thread to multiplex connection attempts.
    *   `threading` is used for the **Scapy Sniffer** because sniffing is a blocking system-level loop with C-bindings. If run on the event loop, it freezes the entire server. Running it on a background thread preserves UI responsiveness.

### 2. Thread Synchronization & Locking
*   To prevent **race conditions**, the background sniffer thread writes metrics under a `threading.Lock()`. The main thread reads snapshots using the same lock, ensuring all operations on shared statistics are **atomic**.

### 3. Connection Resilience
*   The React client does not fail on server disconnects. It uses an **auto-reconnect handler** in the WebSocket event loop, establishing connection durability.

### 4. Custom ASGI CORS Wrapper
*   Wildcard CORS allows (`"*"`) are insecure when `allow_credentials=True` is enabled. Since standard browsers don't support CORS preflights on WebSocket upgrades, we designed a custom ASGI middleware wrapper `CustomCORSMiddleware` to selectively bypass CORS checks on WebSockets while protecting REST APIs.