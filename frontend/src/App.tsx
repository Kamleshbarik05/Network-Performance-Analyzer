// frontend/src/App.tsx

import { useState, useEffect, useRef } from 'react';
import { 
  Activity, Wifi, ShieldAlert, RefreshCw, 
  Cpu, Globe, Database, ArrowUp, ArrowDown, ScanFace
} from 'lucide-react';
import { Line, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend, ArcElement, Filler
} from 'chart.js';

import './App.css';

// Register Chart.js components including the Filler plugin for area charts
ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, ArcElement, Filler
);

export default function App() {
  // --- WebSockets Telemetry State ---
  const [isConnected, setIsConnected] = useState(false);
  const [latency, setLatency] = useState<number | null>(null);
  const [jitter, setJitter] = useState<number | null>(null);
  const [packetLoss, setPacketLoss] = useState<number>(0);
  const [bandwidth, setBandwidth] = useState({ download_kbps: 0, upload_kbps: 0 });
  const [interfaces, setInterfaces] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [sniffer, setSniffer] = useState<any>({ total_packets: 0, total_bytes: 0, protocols: {}, top_hosts: [] });
  
  // Historical latency queue for the line chart (max 20 points)
  const [latencyHistory, setLatencyHistory] = useState<number[]>([]);
  const [timeLabels, setTimeLabels] = useState<string[]>([]);

  // --- Port Scanner State ---
  const [scanIp, setScanIp] = useState('127.0.0.1');
  const [scanPorts, setScanPorts] = useState('22,80,443,3306,8080');
  const [scanResults, setScanResults] = useState<any[]>([]);
  const [isScanning, setIsScanning] = useState(false);

  // --- Speed Test State ---
  const [speedTest, setSpeedTest] = useState<any>(null);
  const [isSpeedTesting, setIsSpeedTesting] = useState(false);
  const [speedtestHistory, setSpeedtestHistory] = useState<any[]>([]);

  const wsRef = useRef<WebSocket | null>(null);

  // --- WebSocket Connection with Auto-Reconnect (Resilience) ---
  useEffect(() => {
    connectWS();
    fetchSpeedtestHistory();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const connectWS = () => {
    console.log("Connecting to WebSocket telemetry...");
    const ws = new WebSocket("ws://localhost:8000/ws/telemetry");
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log("WebSocket connected.");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // Update telemetry variables
      setLatency(data.latency);
      setJitter(data.jitter);
      setPacketLoss(data.packet_loss);
      setBandwidth(data.bandwidth);
      setInterfaces(data.interfaces || []);
      if (data.active_alerts) setAlerts(prev => [...data.active_alerts, ...prev].slice(0, 15));
      if (data.sniffer) setSniffer(data.sniffer);

      // Append new ping value to chart history
      const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setLatencyHistory(prev => [...prev, data.latency || 0].slice(-20));
      setTimeLabels(prev => [...prev, now].slice(-20));
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log("WebSocket disconnected. Retrying in 3 seconds...");
      setTimeout(connectWS, 3000); // Exponential reconnect
    };
  };

  // --- API Handlers ---

  const triggerSpeedTest = async () => {
    setIsSpeedTesting(true);
    setSpeedTest(null);
    try {
      const response = await fetch("http://localhost:8000/api/speedtest", { method: 'POST' });
      const result = await response.json();
      if (response.ok) {
        setSpeedTest(result);
        fetchSpeedtestHistory();
      } else {
        alert(result.detail || "Speed test failed.");
      }
    } catch (err) {
      alert("Failed to connect to backend api.");
    } finally {
      setIsSpeedTesting(false);
    }
  };

  const fetchSpeedtestHistory = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/history/speedtest");
      const result = await response.json();
      setSpeedtestHistory(result);
    } catch (err) {
      console.error("Failed to load speed test history:", err);
    }
  };

  const triggerPortScan = async () => {
    setIsScanning(true);
    setScanResults([]);
    try {
      const url = `http://localhost:8000/api/scan?ip=${scanIp}&ports=${scanPorts}`;
      const response = await fetch(url);
      const result = await response.json();
      if (response.ok) {
        setScanResults(result);
      } else {
        alert(result.detail || "Port scan failed.");
      }
    } catch (err) {
      alert("Failed to connect to scanner API.");
    } finally {
      setIsScanning(false);
    }
  };

  // --- Chart Data Configurations ---

  // 1. Latency Line Chart
  const lineChartData = {
    labels: timeLabels,
    datasets: [
      {
        label: 'Ping Latency (ms)',
        data: latencyHistory,
        borderColor: '#00f0ff',
        backgroundColor: 'rgba(0, 240, 255, 0.1)',
        tension: 0.4,
        fill: true,
        borderWidth: 2,
        pointRadius: 3,
      }
    ]
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#9ca3af' } },
      x: { grid: { display: false }, ticks: { color: '#9ca3af', maxRotation: 45 } }
    },
    plugins: {
      legend: { display: false }
    }
  };

  // 2. Sniffer Protocol Distribution Chart
  const protoLabels = Object.keys(sniffer.protocols || {});
  const protoBytes = protoLabels.map(label => sniffer.protocols[label].bytes);
  
  const doughnutData = {
    labels: protoLabels.length > 0 ? protoLabels : ["No traffic"],
    datasets: [
      {
        data: protoBytes.length > 0 ? protoBytes : [1],
        backgroundColor: ['#00f0ff', '#0072ff', '#39ff14', '#ff0055', '#a855f7', '#6b7280'],
        borderWidth: 0,
      }
    ]
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="title-section">
          <h1>Enterprise Network Monitor</h1>
          <p>Real-time Systems Telemetry & Vulnerability Audit</p>
        </div>
        <div className="status-badge">
          <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
          <span>{isConnected ? 'LIVE FEED' : 'RECONNECTING'}</span>
        </div>
      </header>

      {/* Grid Dashboard */}
      <div className="dashboard-grid">
        
        {/* Card 1: Latency & Jitter */}
        <div className="glass-card col-4">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Ping Diagnostics</h3>
            <Wifi size={20} color="#00f0ff" />
          </div>
          <div className="metric-value">
            {latency ? `${latency}` : '--'}
            <span className="metric-unit">ms</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#9ca3af', fontSize: '0.85rem' }}>
            <span>Jitter: {jitter ? `${jitter} ms` : '--'}</span>
            <span style={{ color: packetLoss > 0 ? '#ff0055' : '#39ff14' }}>
              Loss: {packetLoss}%
            </span>
          </div>
        </div>

        {/* Card 2: Bandwidth Rates */}
        <div className="glass-card col-4">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>NIC Throughput</h3>
            <Activity size={20} color="#0072ff" />
          </div>
          <div style={{ display: 'flex', gap: '1.5rem', marginTop: '0.5rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#9ca3af', fontSize: '0.8rem' }}>
                <ArrowDown size={14} color="#39ff14" /> Download
              </div>
              <div className="metric-value" style={{ fontSize: '2rem' }}>
                {bandwidth.download_kbps > 1000 
                  ? `${(bandwidth.download_kbps / 1000).toFixed(2)}` 
                  : `${bandwidth.download_kbps}`}
                <span className="metric-unit">{bandwidth.download_kbps > 1000 ? 'Mbps' : 'kbps'}</span>
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#9ca3af', fontSize: '0.8rem' }}>
                <ArrowUp size={14} color="#00f0ff" /> Upload
              </div>
              <div className="metric-value" style={{ fontSize: '2rem' }}>
                {bandwidth.upload_kbps > 1000 
                  ? `${(bandwidth.upload_kbps / 1000).toFixed(2)}` 
                  : `${bandwidth.upload_kbps}`}
                <span className="metric-unit">{bandwidth.upload_kbps > 1000 ? 'Mbps' : 'kbps'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Sniffer Overview */}
        <div className="glass-card col-4">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Deep Packet Inspection</h3>
            <Cpu size={20} color="#39ff14" />
          </div>
          <div className="metric-value" style={{ fontSize: '2rem', marginTop: '0.5rem' }}>
            {sniffer.total_packets}
            <span className="metric-unit">packets</span>
          </div>
          <p style={{ color: '#9ca3af', fontSize: '0.85rem' }}>
            Volume: {(sniffer.total_bytes / (1024 * 1024)).toFixed(2)} MB
          </p>
        </div>

        {/* Chart 1: Latency Trends */}
        <div className="glass-card col-8" style={{ height: '320px' }}>
          <h3>Real-Time Latency (RTT)</h3>
          <div style={{ height: '240px', marginTop: '1rem' }}>
            <Line data={lineChartData} options={lineChartOptions} />
          </div>
        </div>

        {/* Chart 2: Protocol Breakdown */}
        <div className="glass-card col-4" style={{ height: '320px' }}>
          <h3>Traffic distribution</h3>
          <div style={{ height: '180px', display: 'flex', justifyContent: 'center', marginTop: '1.5rem' }}>
            <Doughnut data={doughnutData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#9ca3af', boxWidth: 12 } } } }} />
          </div>
        </div>

        {/* Alerts Center */}
        <div className="glass-card col-4">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <ShieldAlert size={20} color="#ff0055" />
            <h3>System Alerts</h3>
          </div>
          <div className="alerts-list">
            {alerts.length === 0 ? (
              <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>No system warnings detected.</p>
            ) : (
              alerts.map((alert, idx) => (
                <div key={idx} className={`alert-item ${alert.severity === 'CRITICAL' ? 'critical' : 'warning'}`}>
                  <div>
                    <strong>[{alert.severity}]</strong> {alert.message}
                    <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.2rem' }}>
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Active NIC Interfaces */}
        <div className="glass-card col-8">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Database size={20} color="#0072ff" />
            <h3>Active Interfaces (NICs)</h3>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="custom-table">
              <thead>
                <tr>
                  <th>Interface</th>
                  <th>Packets Rx/Tx</th>
                  <th>Data Rx/Tx</th>
                  <th>Errors In/Out</th>
                  <th>Drops In/Out</th>
                </tr>
              </thead>
              <tbody>
                {Array.isArray(interfaces) && interfaces.map((nic, idx) => (
                  <tr key={idx}>
                    <td><strong>{nic.name}</strong></td>
                    <td>{nic.packets_recv} / {nic.packets_sent}</td>
                    <td>{(nic.bytes_recv / (1024 * 1024)).toFixed(1)}MB / {(nic.bytes_sent / (1024 * 1024)).toFixed(1)}MB</td>
                    <td style={{ color: nic.errin > 0 || nic.errout > 0 ? '#ff0055' : 'inherit' }}>
                      {nic.errin} / {nic.errout}
                    </td>
                    <td style={{ color: nic.dropin > 0 || nic.dropout > 0 ? '#ff0055' : 'inherit' }}>
                      {nic.dropin} / {nic.dropout}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Security Scan Tool */}
        <div className="glass-card col-6">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <ScanFace size={20} color="#39ff14" />
            <h3>Asynchronous Security Port Auditor</h3>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
            <input 
              type="text" 
              className="custom-input" 
              value={scanIp} 
              onChange={(e) => setScanIp(e.target.value)} 
              placeholder="Target IP Address" 
            />
            <input 
              type="text" 
              className="custom-input" 
              value={scanPorts} 
              onChange={(e) => setScanPorts(e.target.value)} 
              placeholder="Ports (e.g. 80,443)" 
            />
            <button className="action-button" onClick={triggerPortScan} disabled={isScanning}>
              {isScanning ? <RefreshCw className="animate-spin" size={16} /> : 'Scan'}
            </button>
          </div>

          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {Array.isArray(scanResults) && scanResults.length > 0 && (
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Port</th>
                    <th>Service</th>
                    <th>Status</th>
                    <th>RTT (ms)</th>
                  </tr>
                </thead>
                <tbody>
                  {scanResults.map((r, idx) => (
                    <tr key={idx}>
                      <td>{r.port}</td>
                      <td>{r.service}</td>
                      <td>
                        <span style={{ 
                          color: r.status === 'Open' ? '#39ff14' : '#ff0055',
                          fontWeight: 'bold'
                        }}>
                          {r.status}
                        </span>
                      </td>
                      <td>{r.rtt_ms ? `${r.rtt_ms} ms` : '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Broadband Speed Test Tool */}
        <div className="glass-card col-6">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <Globe size={20} color="#00f0ff" />
            <h3>Speedtest Engine</h3>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <button className="action-button" onClick={triggerSpeedTest} disabled={isSpeedTesting}>
              {isSpeedTesting ? 'Running Speed Test...' : 'Run Bandwidth Speed Test'}
            </button>
            {speedTest && (
              <div style={{ display: 'flex', gap: '1rem' }}>
                <div>Down: <strong style={{ color: '#39ff14' }}>{speedTest.download_mbps} Mbps</strong></div>
                <div>Up: <strong style={{ color: '#00f0ff' }}>{speedTest.upload_mbps} Mbps</strong></div>
              </div>
            )}
          </div>

          <div style={{ maxHeight: '180px', overflowY: 'auto' }}>
            <h4>Historical Speeds</h4>
            {Array.isArray(speedtestHistory) && speedtestHistory.length === 0 ? (
              <p style={{ color: '#6b7280', fontSize: '0.85rem', marginTop: '0.5rem' }}>No past test data.</p>
            ) : (
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Download</th>
                    <th>Upload</th>
                    <th>Ping</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.isArray(speedtestHistory) && speedtestHistory.slice(0, 4).map((hist, idx) => (
                    <tr key={idx}>
                      <td>{new Date(hist.timestamp).toLocaleDateString()}</td>
                      <td style={{ color: '#39ff14' }}>{hist.download_mbps} Mbps</td>
                      <td style={{ color: '#00f0ff' }}>{hist.upload_mbps} Mbps</td>
                      <td>{hist.ping_ms} ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}