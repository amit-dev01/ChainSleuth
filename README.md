# ChainSleuth 🔍⚖️
### Real-Time Cryptocurrency Fraud Tracing & Attribution System for Indian Law Enforcement
**Smart India Hackathon 2026 &bull; Problem Statement: SIH26183**

---

## 📌 Executive Summary

When victims of cyber fraud (task frauds, digital arrest scams, fake trading apps, extortion) report suspect crypto wallet addresses to State Cyber Crime Cells or on the National Cyber Crime Reporting Portal (1930 / cybercrime.gov.in), Investigating Officers (IOs) face a critical bottleneck: **funds move across multiple mule wallets within minutes, but manual forensic tracing takes days.** By the time subpoenas are issued, funds have already been cashed out via offshore exchanges or P2P desks.

**ChainSleuth slashes investigation turnaround time from days to minutes.** It provides:
1. **Multi-Chain Tracing**: Primary focus on **Tron (USDT-TRC20)** which accounts for **80%+ of Indian cyber fraud**, with full secondary support for **Ethereum (ERC-20)** and **Solana (SPL)**.
2. **High-Speed BFS Tracing Engine**: Follows stolen fund flows hop-by-hop in real time, automatically pruning dust transactions and zero-value phishing attacks.
3. **Automated VASP Attribution**: Instantly maps terminal deposit addresses to verified Virtual Asset Service Providers (Binance, WazirX, CoinDCX, KuCoin, OKX, etc.) and tags their FIU-India registration status.
4. **Obfuscation Detection**: Automatically flags peeling chains, rapid automated hopping (< 10 minutes latency), mixer interactions (Tornado Cash, Tron mixers), and instant no-KYC swappers (FixedFloat).
5. **Law Enforcement Risk Scoring (0-100)**: Behavioral feature extraction combined with rule heuristics to calculate mule risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
6. **Court-Ready Section 91 Cr.P.C. / Section 94 BNSS Notices**: One-click generation of formal legal notices with digital audit hash, hop breakdown, and mandatory directives to VASP compliance officers for asset freezing.

---

## 🏗️ System Architecture

```
                                  [ Victim / IO Input ]
                                            │
                                            ▼
                           ┌────────────────────────────────┐
                           │    FastAPI Backend Router      │
                           │   Auth (RBAC) & Rate Limiter   │
                           └──────────────┬─────────────────┘
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
     ┌────────────────────────┐                      ┌────────────────────────┐
     │  Celery Task Queue     │                      │  Blockchain Adapters   │
     │  (Redis Broker)        │                      │  • TronGrid (USDT)     │
     └────────────┬───────────┘                      │  • Etherscan (ERC-20)  │
                  │                                  │  • Helius (Solana SPL) │
                  ▼                                  └────────────┬───────────┘
     ┌────────────────────────┐                                   │
     │   BFS Tracer Engine    │◄──────────────────────────────────┘
     │   • Depth & Dust Filter│
     │   • Obfuscation Detect │
     └────────────┬───────────┘
                  │
        ┌─────────┴──────────────┬────────────────────────┬──────────────────────┐
        ▼                        ▼                        ▼                      ▼
┌──────────────┐         ┌──────────────┐         ┌──────────────┐        ┌──────────────┐
│ VASP / Exch  │         │   Neo4j      │         │ Risk Scorer  │        │ Report Engine│
│ Attribution  │         │   Graph DB   │         │ (ML + AML)   │        │ (Sec 91 CrPC)│
│ (FIU-IND)    │         │ (Visual Tree)│         │ (Score 0-100)│        │ (WeasyPrint) │
└──────────────┘         └──────────────┘         └──────────────┘        └──────────────┘
```

---

## 💻 Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **Web Framework** | FastAPI (Async/Await native) |
| **Validation & Schemas**| Pydantic v2 & Pydantic Settings |
| **Task Queue** | Celery + Redis |
| **Graph Database** | Neo4j Community Edition 5 (Bolt protocol) |
| **Relational Database**| PostgreSQL 15 (SQLAlchemy 2.0 asyncpg) |
| **Cache & State** | Redis 7 (In-memory fallback included) |
| **Blockchain APIs** | TronGrid API (TRC-20), Etherscan API (ETH), Helius API (Solana) |
| **Report Generation** | Jinja2 + WeasyPrint (A4 PDF Legal Requisition) |
| **Machine Learning** | Scikit-Learn + XGBoost (Behavioral Feature Scoring) |
| **Containerization** | Docker + Docker Compose |

---

## 📂 Project Structure

```
chainsleuth/
├── docker-compose.yml           # Complete container stack (API, Celery, Postgres, Redis, Neo4j)
├── Dockerfile                   # Multi-stage image with Pango/Cairo for PDF rendering
├── requirements.txt             # Pinned modern production dependencies
├── .env.example                 # Comprehensive environment variable template
├── README.md                    # System architecture and deployment guide
├── backend/
│   ├── main.py                  # FastAPI app entrypoint, lifecycles, CORS
│   ├── config/
│   │   ├── settings.py          # Pydantic BaseSettings for dynamic secrets
│   │   └── chains.py            # Token contracts, decimals, and address regexes
│   ├── adapters/
│   │   ├── base.py              # Abstract adapter with rate-limiting & retries
│   │   ├── models.py            # Unified Transfer, TxInfo, WalletBalance models
│   │   ├── tron_adapter.py      # TronGrid TRC20 USDT tracing
│   │   ├── eth_adapter.py       # Etherscan ERC20 & native ETH tracing
│   │   └── solana_adapter.py    # Helius SPL & native SOL tracing
│   ├── exchange_db/
│   │   ├── service.py           # Entity lookup, FIU registry, in-memory caching
│   │   ├── seed_data/           # Verified seed databases
│   │   │   ├── tron_exchanges.json
│   │   │   ├── eth_exchanges.json
│   │   │   └── solana_exchanges.json
│   │   └── cluster.py           # Sweep detection & heuristic clustering
│   ├── tracer/
│   │   ├── engine.py            # High-speed asynchronous BFS tracing engine
│   │   ├── filters.py           # Graph pruning, dust elimination, anti-poisoning
│   │   ├── obfuscation.py       # Peeling chains, mixers, rapid automated hopping
│   │   └── result.py            # Court-ready TraceResult and TracePath models
│   ├── storage/
│   │   ├── neo4j_client.py      # Neo4j async client & Cypher graph queries
│   │   ├── postgres_client.py   # SQLAlchemy async models (Cases, Traces, Alerts)
│   │   └── redis_client.py      # Async Redis client, rate-limiter, fallback cache
│   ├── risk/
│   │   ├── scorer.py            # Composite risk calculation & IO recommendations
│   │   ├── features.py          # Behavioral feature extraction from tx history
│   │   └── rules.py             # Heuristic rules tailored for Indian cyber fraud
│   ├── api/
│   │   ├── routes/
│   │   │   ├── trace.py         # Start trace, poll status, graph visualization
│   │   │   ├── wallet.py        # Wallet overview, risk assessment, monitoring
│   │   │   ├── exchange.py      # VASP directory and custom LEA tagging
│   │   │   ├── report.py        # Section 91 CrPC notice generation & download
│   │   │   └── dashboard.py     # Command center analytics & fraud metrics
│   │   ├── middleware/
│   │   │   ├── auth.py          # LEA officer authentication & RBAC
│   │   │   └── rate_limit.py    # Sliding window rate limiter
│   │   └── schemas/
│   │       ├── trace.py         # Pydantic v2 trace request & response schemas
│   │       └── wallet.py        # Pydantic v2 wallet intelligence schemas
│   ├── tasks/
│   │   ├── celery_app.py        # Celery application & beat periodic schedule
│   │   ├── trace_task.py        # Background BFS trace worker
│   │   └── alert_task.py        # Periodic suspect wallet monitor worker
│   ├── reports/
│   │   ├── generator.py         # WeasyPrint PDF compiler & HTML renderer
│   │   └── templates/
│   │       └── investigation.html # Official Indian LEA legal requisition template
│   └── alerts/
│       ├── dispatcher.py        # Multi-channel priority alert router
│       └── channels/
│           ├── webhook.py       # Async HTTP webhook (CCTNS / 1930 portal)
│           └── email.py         # SMTP email dispatcher for IOs
└── tests/
    ├── test_adapters.py         # Multi-chain adapter verification
    ├── test_tracer.py           # BFS engine, filters & obfuscation tests
    ├── test_exchange_db.py      # Exchange lookup and clustering tests
    └── test_api.py              # End-to-end FastAPI endpoint integration tests
```

---

## 🚀 Quick Start & Deployment

### Option 1: Docker Compose (Recommended for Production)

Launch the entire stack (FastAPI, Celery Worker, Celery Beat, Neo4j, PostgreSQL, Redis) with one command:

```bash
# Clone repository
git clone https://github.com/amit-dev01/ChainSleuth.git
cd ChainSleuth

# Configure environment variables
cp .env.example .env

# Build and start all services
docker-compose up --build -d

# Verify running containers
docker-compose ps
```

Once running:
- **FastAPI Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Neo4j Graph Browser**: [http://localhost:7474](http://localhost:7474) (Credentials: `neo4j` / `chainsleuth_neo4j_pass_2026`)
- **API Healthcheck**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Option 2: Local Standalone Development

The system is architected with **intelligent in-memory fallbacks** for Neo4j, Redis, and Blockchain APIs. You can run and test the complete backend locally even without external DB instances installed:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI dev server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Running Automated Tests

Run the full pytest suite covering adapters, BFS traversal, exchange attribution, and REST endpoints:

```bash
python -m pytest tests/ -v
```

---

## 📡 Key API Endpoints & Usage

### 1. Initiate Real-Time Trace (`POST /api/v1/trace`)

```bash
curl -X POST "http://localhost:8000/api/v1/trace" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: chainsleuth-lea-internal-api-secret-key" \
     -d '{
       "seed_address": "TMuleWallet88910238128381928312783912",
       "chain": "tron",
       "max_hops": 5,
       "min_amount_usd": 10.0,
       "async_mode": false
     }'
```

**Response Highlights:**
- `total_stolen_amount`: Stolen USDT tracked from seed
- `destination_vasps`: Terminal exchanges reached (e.g. Binance, WazirX)
- `attribution_percentage`: Percentage of funds located in exchange custody
- `paths`: Hop-by-hop audit trail with transactions and obfuscation indicators

---

### 2. Wallet Intelligence & Risk Score (`GET /api/v1/wallet/{address}/risk`)

```bash
curl -X GET "http://localhost:8000/api/v1/wallet/TMuleWallet88910238128381928312783912/risk?chain=tron" \
     -H "X-API-Key: chainsleuth-lea-internal-api-secret-key"
```

**Output:**
- `risk_score`: 92.5 (0 - 100)
- `risk_tier`: `CRITICAL`
- `triggered_rules`: Mule account pass-through, zero-balance pattern, high turnover velocity
- `recommendation_for_io`: Immediate Section 91 CrPC notice directive for asset freezing

---

### 3. Generate Section 91 Cr.P.C. Legal Freezing Requisition (`POST /api/v1/report/generate`)

```bash
curl -X POST "http://localhost:8000/api/v1/report/generate" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: chainsleuth-lea-internal-api-secret-key" \
     -d '{
       "case_number": "CYBER/FIR/2026/8912",
       "police_station": "State Cyber Crime Police Station",
       "victim_name": "Suresh Patel",
       "victim_loss_inr": 2187500.0,
       "io_name": "Insp. Rajesh Kumar"
     }'
```

**Output:**
```json
{
  "status": "SUCCESS",
  "report_id": "848b8a5a-...",
  "preview_url": "/api/v1/report/848b8a5a-.../preview",
  "download_url": "/api/v1/report/848b8a5a-.../download",
  "message": "Section 91 CrPC Requisition Notice generated successfully."
}
```

---

## ⚖️ Indian Legal & Regulatory Alignment

1. **Section 91 Cr.P.C. & Section 94 BNSS (2023)**:
   Empowers Police Officers to issue summons/requisition for production of documents or electronic assets. ChainSleuth's notice templates comply directly with state police circulars on VASP notices.
2. **FIU-IND Anti-Money Laundering Regulations**:
   Exchanges operating in India must be registered with the Financial Intelligence Unit (FIU-IND). ChainSleuth flags whether destination VASPs are FIU-compliant (e.g. CoinDCX, WazirX, Binance) or offshore unregulated entities.
3. **Evidence Integrity**:
   Every generated report embeds a SHA-256 digital audit hash tying the report timestamp, FIR number, seed wallet, and hop evidence trail for admissibility under Section 65B of the Indian Evidence Act / Section 63 of BSA.

---

## 👥 Hackathon Team (SIH26183)
Built with dedication for India's Law Enforcement Community to combat transnational cyber financial crime.
