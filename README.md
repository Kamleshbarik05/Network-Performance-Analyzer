# Realtime Network Telemetry & Security Auditor

An enterprise-grade, high-performance network diagnostics and security auditing suite featuring real-time WebSocket telemetry, thread-offloaded packet sniffing, and concurrent TCP port scanning. Deployed across a multi-cloud architecture utilizing AWS EC2 for backend services and AWS S3/CloudFront + Azure Static Web Apps for frontend hosting.

![Backend CI](https://github.com/Kamleshbarik05/Realtime-Network-Telemetry-and-Security-Auditor/actions/workflows/ci.yml/badge.svg)
![Frontend Build](https://github.com/Kamleshbarik05/Realtime-Network-Telemetry-and-Security-Auditor/actions/workflows/ci.yml/badge.svg)

## Live Demo
* **AWS CloudFront (S3 Origin)**: *[(https://d1eds33nsxdon1.cloudfront.net)]*
* **Azure Static Web Apps**: *[(https://telemetrykamlesh05.z29.web.core.windows.net/)]*

## Performance Metrics

| Component                  | Metric              | Value                        |
|---------------------------|---------------------|------------------------------|
| WebSocket refresh cycle   | End-to-end latency  | ~3.5s, sub-100ms delivery    |
| Port scanner throughput   | Ports/sec           | 98.2 (5,000 ports in 50.9s)  |
| DB write performance      | Latency per record  | 0.20ms (42x vs 8.26ms base)  |
| Concurrent socket cap     | Max sockets         | 100 (asyncio.Semaphore)      |
| Frontend uptime           | During network drops| Near-100% (backoff reconnect)|

---

## Architecture

```text
React Dashboard (TypeScript / Vite)
       ↕ [Full-Duplex WebSockets / REST API]
FastAPI (ASGI Backend / asyncio)
  ├── Custom ASGI Middleware (CORS Bypass for WS Upgrades)
  │
  ├── TelemetryPipeline (Strategy Pattern Context)
  │     ├── CPUTelemetry Strategy (psutil)
  │     ├── NetworkTelemetry Strategy (ping3 + psutil)
  │     └── DiskTelemetry Strategy (psutil)
  │
  ├── WebSocketBroadcaster (Observer Pattern) ──> Broadcasts to active connections
  │
  ├── Port Scanner (asyncio.Semaphore-limited concurrency cap of 100 sockets)
  │
  ├── Thread-Safe Packet Sniffer (Multi-threaded Scapy queue)
  │
  └── SQLAlchemy ORM ──> SQLite (Transactional bulk-commits under 1ms/record)
```

---

## Key Engineering Decisions

### Exposure & Attack-Surface Detection (asyncio Port Scanner)
To audit system vulnerability, we built an automated exposure detection engine that scans target networks for open ports. Because port scanning is heavily I/O-bound, spawning standard OS threads for socket handshakes is highly inefficient. Conversely, running an unconstrained `asyncio` loop will attempt to open thousands of file descriptors concurrently, triggering `OSError: [Errno 24] Too many open files` and exposing the system to resource exhaustion.
To mitigate this risk, the exposure scanner is governed by a strict `asyncio.Semaphore` concurrency cap of `100`. This allows the scanner to achieve a high audit throughput of **98.2 ports/second** while keeping socket descriptors safely within operating system safety limits.

### SQLAlchemy Bulk Commits
Writing telemetry logs row-by-row forces the database engine (SQLite) to perform individual disk write transactions. Each commit initiates a disk write block sync, limiting performance to **8.26ms per record**.
By refactoring the database logger to use batch insertions, we stage records in memory and commit them within a single transaction wrapper. This reduces disk I/O operations, dropping latency to **0.20ms per record**—a **42x speed improvement** that allows our services to scale to high-throughput logging.

### Remediating WebSocket CORS Vulnerabilities (OWASP-Adjacent)
Cross-Origin Resource Sharing (CORS) misconfigurations are a major security vulnerability (related to OWASP Top 10 Security Misconfigurations). Standard Starlette/FastAPI `CORSMiddleware` blocks WebSocket upgrade handshake headers by default, which frequently leads developers to disable CORS checks globally (`allow_origins=["*"]`) for both HTTP and WebSockets, leaving HTTP REST APIs exposed.
Rather than sacrificing security, we engineered a custom ASGI middleware wrapper. It intercepts incoming traffic, identifies if the scope type is `websocket` to allow the connection handshake, while applying strict CORS origin constraints on all standard HTTP REST endpoints.

### Exponential Backoff Reconnect
Real-world networks drop packets, causing WebSockets to disconnect. A naive reconnection mechanism that polls the backend constantly can trigger a self-induced Denial of Service (DoS) when a server restarts.
We implemented client-side reconnection logic governed by **exponential backoff with jitter** ($delay = \min(30s, base \times 2^{attempt})$). This spaces out reconnection attempts dynamically up to a maximum cap of 30 seconds, maintaining frontend resilience during temporary network disconnects.

---

## Design Patterns Used

1. **Strategy Pattern (`TelemetrySource`)**: Abstracted system telemetry metrics collection. Different concrete strategies (`CPUTelemetry`, `NetworkTelemetry`, `DiskTelemetry`) collect hardware and network data independently and are merged dynamically by the pipeline.
2. **Observer Pattern (`TelemetryObserver`)**: The telemetry pipeline acts as the subject, notifying registered observers (such as the `WebSocketBroadcaster`) when new system metrics frames are gathered. This decoupling makes it easy to add future observers (like file exporters or alert hooks).

---

## Running Locally

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Activate your virtual environment and install dependencies:
   ```bash
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run the FastAPI server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies and run the Vite dev server:
   ```bash
   npm install
   npm run dev
   ```

---

## Running Tests

Run the complete pytest test suite checking async sockets, mock hardware telemetry strategies, database bulk write limits, and API CORS enforcement:

```bash
cd backend
python -m pytest --cov=app --cov-report=term-missing tests/
```

### Expected Output
```text
tests\test_main.py ....................                              [100%]
TOTAL                                  501     82    84%
===================== 20 passed, 9 warnings in 3.49s ======================
```

---

## STRIDE Threat Model & Mitigations

We analyzed the architecture using the Microsoft **STRIDE** threat modeling framework:

* **S (Spoofing):** Mitigated by introducing optional `API_SECURITY_TOKEN` authentication on sensitive control endpoints (`/api/scan`, `/api/speedtest`).
* **T (Tampering):** Remediated by Nginx reverse-proxying with TLS (HTTPS/WSS) to encrypt traffic in transit.
* **R (Repudiation):** Covered by logging audit details (timestamps, latency histories, scan logs) directly to transactional database records.
* **I (Information Disclosure):** Mitigated by custom ASGI middleware error handling to mask internal tracebacks from API error responses.
* **D (Denial of Service):** Addressed by capping concurrent sockets to a strict `asyncio.Semaphore(100)` to prevent host file descriptor exhaustion.
* **E (Elevation of Privilege):** Mitigated by running the uvicorn service under a dedicated, restricted daemon manager rather than open-root execution.

