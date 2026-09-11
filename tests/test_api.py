"""
Integration tests for FastAPI REST API endpoints using httpx AsyncClient.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_root_and_health():
    """Verify system info and healthcheck endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["system"] == "ChainSleuth"
        assert data["hackathon"] == "Smart India Hackathon 2026 (SIH26183)"

        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["status"] == "UP"


@pytest.mark.asyncio
async def test_dashboard_metrics():
    """Verify LEA dashboard analytics endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "chain_distribution" in data
        assert "top_destination_vasps" in data
        assert data["summary"]["total_stolen_usdt"] > 0


@pytest.mark.asyncio
async def test_exchange_endpoints():
    """Verify VASP directory and address lookup."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # List known exchanges
        list_resp = await client.get("/api/v1/exchange/list")
        assert list_resp.status_code == 200
        exchanges = list_resp.json()
        assert len(exchanges) > 0

        # Lookup Binance Tron Hot Wallet
        lookup_resp = await client.get("/api/v1/exchange/lookup/TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR?chain=tron")
        assert lookup_resp.status_code == 200
        lookup_data = lookup_resp.json()
        assert lookup_data["is_attributed"] is True
        assert lookup_data["entity"]["name"] == "Binance"


@pytest.mark.asyncio
async def test_wallet_overview_and_risk():
    """Verify wallet overview and risk assessment endpoints."""
    transport = ASGITransport(app=app)
    test_addr = "TMuleWallet88910238128381928312783912"
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Overview
        resp = await client.get(f"/api/v1/wallet/{test_addr}?chain=tron")
        assert resp.status_code == 200
        data = resp.json()
        assert data["address"] == test_addr
        assert data["chain"] == "tron"

        # Risk scoring
        risk_resp = await client.get(f"/api/v1/wallet/{test_addr}/risk?chain=tron")
        assert risk_resp.status_code == 200
        risk_data = risk_resp.json()
        assert "risk_score" in risk_data
        assert "risk_tier" in risk_data
        assert "recommendation_for_io" in risk_data


@pytest.mark.asyncio
async def test_trace_synchronous():
    """Verify synchronous trace execution."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "seed_address": "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR",
            "chain": "tron",
            "max_hops": 3,
            "min_amount_usd": 10.0,
            "async_mode": False
        }
        resp = await client.post("/api/v1/trace", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["result"] is not None
        assert data["result"]["total_stolen_amount"] > 0


@pytest.mark.asyncio
async def test_report_generation_and_preview():
    """Verify Section 91 CrPC notice generation and HTML preview."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "case_number": "CYBER/FIR/2026/9001",
            "victim_name": "Ramesh Kumar (Victim)",
            "victim_loss_inr": 1500000.0,
            "police_station": "Cyber Crime PS, Cyberabad",
            "io_name": "Insp. Vikram Singh"
        }
        gen_resp = await client.post("/api/v1/report/generate", json=payload)
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        assert gen_data["status"] == "SUCCESS"
        assert "report_id" in gen_data
        report_id = gen_data["report_id"]

        # Preview HTML
        prev_resp = await client.get(f"/api/v1/report/{report_id}/preview")
        assert prev_resp.status_code == 200
        assert "SECTION 91 Cr.P.C." in prev_resp.text
