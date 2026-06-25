# backend/tests/conftest.py

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure the backend directory is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# In-memory SQLite Database for isolated testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    # Override get_db dependency to point to the in-memory test database
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

# Autouse mock targeting core services rather than just main.py
@pytest.fixture(autouse=True)
def mock_telemetry_dependencies():
    with patch("app.services.latency.ping", return_value=(15.2, 1.1, 0.0)), \
         patch("app.services.latency.ping_host", return_value=(15.2, 1.1, 0.0)), \
         patch("app.services.bandwidth.get_bandwidth_usage", return_value=({"download_kbps": 120.5, "upload_kbps": 45.2}, [
             {
                 "name": "eth0",
                 "bytes_sent": 10000,
                 "bytes_recv": 20000,
                 "packets_sent": 50,
                 "packets_recv": 80,
                 "errin": 0,
                 "errout": 0,
                 "dropin": 0,
                 "dropout": 0,
                 "download_kbps": 80.0,
                 "upload_kbps": 40.0
             }
         ])), \
         patch("app.main.run_speedtest_async", return_value={
             "download_mbps": 95.5,
             "upload_mbps": 42.1,
             "ping_ms": 12.0
         }), \
         patch("app.main.global_sniffer") as mock_sniffer:
        
        # Setup mock packet sniffer stats
        mock_sniffer.get_statistics.return_value = {
            "total_packets": 150,
            "total_bytes": 45000,
            "protocols": {
                "TCP": {"packets": 100, "bytes": 35000},
                "UDP": {"packets": 50, "bytes": 10000}
            },
            "top_hosts": [{"ip": "192.168.1.1", "bytes": 30000}]
        }
        
        yield