# Q&A System Architecture Diagram

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MANGOBYTES SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐         ┌──────────────────────┐    │
│  │   FRONTEND (React)   │         │  BACKEND (FastAPI)   │    │
│  │                      │         │                      │    │
│  │  Dashboard Page      │         │  /api/parse/*        │    │
│  │  - Parse URL input   │────────▶│  /api/graph/*        │    │
│  │  - Org or Repo       │         │  /api/query/*        │    │
│  │                      │         │                      │    │
│  │  KnowledgeGraph Page │         │  /api/organization/* │    │
│  │  - Select repo/org   │◀────────│                      │    │
│  │  - Ask questions     │         │                      │    │
│  │  - What-if analysis  │         │                      │    │
│  └──────────────────────┘         └──────────┬───────────┘    │
│                                               │                 │
│                                      ┌────────▼────────┐       │
│                                      │   LLMService    │       │
│                                      │   (Groq API)    │       │
│                                      │                 │       │
│                                      │ answer_query    │       │
│                                      │ answer_org_*    │       │
│                                      └────────┬────────┘       │
│                                               │                 │
│  ┌──────────────────────────────────────────▼──────────┐       │
│  │                    MONGODB                          │       │
│  │                                                     │       │
│  │  collections:                                       │       │
│  │  - graphs: {org:org_name -> dependency_graph}      │       │
│  │  - parsed_data: {org:org_name -> repos_data}       │       │
│  │                                                     │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Organization Parsing Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    ORGANIZATION PARSING                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Input: https://github.com/my-company                      │
│  │                                                               │
│  ├─▶ Parse Endpoint (/api/parse/)                               │
│  │                                                               │
│  ├─▶ Detect Organization (single path component)                │
│  │                                                               │
│  ├─▶ Route to analyze_organization()                            │
│  │      │                                                        │
│  │      ├─▶ Step 1: GitHubOrgDiscovery                          │
│  │      │            └─▶ Find all repos: [repo1, repo2, ...]   │
│  │      │                                                        │
│  │      ├─▶ Step 2: EnhancedParser                              │
│  │      │            └─▶ Parse each repo                        │
│  │      │                ├─▶ Extract services                   │
│  │      │                ├─▶ Extract API endpoints              │
│  │      │                ├─▶ Extract database access            │
│  │      │                └─▶ Extract imports/dependencies       │
│  │      │                                                        │
│  │      │            Output: repos_data = {                      │
│  │      │                repo1: {services: [...], ...},         │
│  │      │                repo2: {services: [...], ...}          │
│  │      │            }                                           │
│  │      │                                                        │
│  │      ├─▶ Step 3: CrossRepoDependencyEngine                   │
│  │      │            └─▶ Analyze organization()                 │
│  │      │                ├─▶ Find REST API calls                │
│  │      │                ├─▶ Find event dependencies            │
│  │      │                ├─▶ Find shared libraries              │
│  │      │                ├─▶ Detect circular deps               │
│  │      │                └─▶ Generate violations                │
│  │      │                                                        │
│  │      │            Output: dependency_graph = {               │
│  │      │                nodes: [...],                          │
│  │      │                edges: [...],                          │
│  │      │                violations: [...],                     │
│  │      │                statistics: {...}                      │
│  │      │            }                                           │
│  │      │                                                        │
│  │      ├─▶ Step 4: Save to MongoDB                             │
│  │      │            ├─▶ parsed_data: {repos_data}             │
│  │      │            └─▶ graphs: {dependency_graph}            │
│  │      │                                                        │
│  │      └─▶ Return to Frontend                                  │
│  │           └─▶ "Parsed: 5 repos, 20 services"                │
│  │                                                               │
│  └─▶ Frontend updates dropdown with "Organization: my-company"  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Q&A Request Flow (Organization)

```
┌────────────────────────────────────────────────────────────────────┐
│                  Q&A FOR ORGANIZATION (org:my-org)                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Frontend: POST /api/query/ask?repo_key=org:my-org                │
│  Body: { query: "...", include_code: true, max_context: 10 }      │
│  │                                                                 │
│  ├─▶ Backend query.py: ask_question()                             │
│  │    │                                                            │
│  │    ├─▶ Check if org: prefix                                    │
│  │    │   └─▶ YES! Organization query                             │
│  │    │                                                            │
│  │    ├─▶ get_organization_data(org_key)                          │
│  │    │   ├─▶ Query MongoDB: parsed_data collection              │
│  │    │   │   └─▶ repos_data = {all repo JSONs}                 │
│  │    │   └─▶ Query MongoDB: graphs collection                   │
│  │    │       └─▶ dependency_graph = {nodes, edges, violations}  │
│  │    │                                                            │
│  │    ├─▶ org_data = {repos_data, dependency_graph}              │
│  │    │                                                            │
│  │    └─▶ llm_service.answer_org_query(org_data, request)        │
│  │         │                                                       │
│  │         ├─▶ _build_org_context(org_data)                      │
│  │         │   └─▶ Context string with:                          │
│  │         │       ├─▶ Org overview (repo count)                 │
│  │         │       ├─▶ Key repos (5 max) with services           │
│  │         │       ├─▶ All endpoints and DB tables               │
│  │         │       ├─▶ Cross-repo dependencies                   │
│  │         │       │   ├─▶ REST API calls                        │
│  │         │       │   ├─▶ Event subscriptions                   │
│  │         │       │   ├─▶ Import dependencies                   │
│  │         │       │   └─▶ ⚠️ Circular deps (violations)         │
│  │         │       └─▶ Statistics (totals, counts)                │
│  │         │                                                       │
│  │         ├─▶ Groq API call                                      │
│  │         │   ├─▶ System: "expert in microservices..."          │
│  │         │   ├─▶ User: context + question                      │
│  │         │   └─▶ Response: detailed architecture answer        │
│  │         │                                                       │
│  │         ├─▶ Extract relevant services from answer             │
│  │         │                                                       │
│  │         └─▶ Return QueryResponse {                            │
│  │             answer: "...",                                    │
│  │             relevant_elements: [services],                    │
│  │             confidence: 0.85,                                 │
│  │             sources: [...]                                    │
│  │         }                                                      │
│  │                                                                 │
│  └─▶ Frontend displays answer + relevant services                 │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## What-If Analysis Flow (Organization)

```
┌────────────────────────────────────────────────────────────────────┐
│              WHAT-IF ANALYSIS FOR ORGANIZATION                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Frontend: POST /api/query/what-if?repo_key=org:my-org            │
│  Body: { scenario: "What if we...", max_depth: 5 }               │
│  │                                                                 │
│  ├─▶ Backend query.py: what_if_analysis()                         │
│  │    │                                                            │
│  │    ├─▶ Detect organization query (org: prefix)                │
│  │    │                                                            │
│  │    ├─▶ get_organization_data(org_key)                          │
│  │    │                                                            │
│  │    └─▶ llm_service.analyze_org_what_if(org_data, request)     │
│  │         │                                                       │
│  │         ├─▶ Build same org_context                             │
│  │         │                                                       │
│  │         ├─▶ Create what-if prompt                              │
│  │         │   "If we <scenario>, what's the impact?"            │
│  │         │                                                       │
│  │         ├─▶ Groq API analyzes:                                 │
│  │         │   ├─▶ Which services affected                        │
│  │         │   ├─▶ What changes needed                            │
│  │         │   ├─▶ Breaking changes                               │
│  │         │   ├─▶ Performance impact                             │
│  │         │   ├─▶ Testing considerations                         │
│  │         │   ├─▶ Deployment strategy                            │
│  │         │   └─▶ Risk level (low/med/high)                     │
│  │         │                                                       │
│  │         ├─▶ Extract affected services from response            │
│  │         │                                                       │
│  │         ├─▶ Determine risk_level from answer                  │
│  │         │   └─▶ high/medium/low                                │
│  │         │                                                       │
│  │         └─▶ Return WhatIfResponse {                            │
│  │             analysis: "...",                                  │
│  │             affected_elements: [services],                    │
│  │             risk_level: "medium",                             │
│  │             recommendations: [list]                           │
│  │         }                                                      │
│  │                                                                 │
│  └─▶ Frontend displays impact analysis with risk badge            │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Data Structure Hierarchy

```
ORGANIZATION (org:my-org)
│
├─▶ repos_data (MongoDB: parsed_data collection)
│   │
│   ├─▶ api-gateway
│   │   ├─ services: [AuthService, UserService, ...]
│   │   ├─ api_endpoints: [GET /api/users, POST /api/auth, ...]
│   │   ├─ database_access: [users table, auth_tokens table, ...]
│   │   ├─ imports: [requests, fastapi, ...]
│   │   └─ external_services: [mongodb, redis, ...]
│   │
│   ├─▶ payment-service
│   │   ├─ services: [PaymentProcessor, RefundService, ...]
│   │   ├─ api_endpoints: [POST /api/payments, GET /api/payments/status, ...]
│   │   ├─ database_access: [transactions table, ...]
│   │   └─ external_services: [stripe, mongodb, ...]
│   │
│   └─▶ order-service
│       ├─ services: [OrderManager, OrderTracker, ...]
│       ├─ api_endpoints: [GET /api/orders, POST /api/orders, ...]
│       ├─ database_access: [orders table, order_items table, ...]
│       └─ external_services: [mongodb, ...]
│
└─▶ dependency_graph (MongoDB: graphs collection)
    │
    ├─▶ nodes: [
    │   {id: api-gateway, type: microservice, language: python},
    │   {id: payment-service, type: microservice, language: python},
    │   {id: order-service, type: microservice, language: python}
    │   ]
    │
    ├─▶ edges: [
    │   {from: api-gateway, to: payment-service, type: REST, endpoint: /api/payments},
    │   {from: order-service, to: payment-service, type: EVENT, event_name: order_created},
    │   {from: api-gateway, to: order-service, type: IMPORT, module: order_client}
    │   ]
    │
    ├─▶ violations: [
    │   {type: circular_dependency, from: service-a, to: service-b},
    │   {type: missing_contract, from: api-gateway, to: payment-service}
    │   ]
    │
    └─▶ statistics: {
        total_repositories: 3,
        total_services: 5,
        total_endpoints: 12,
        total_dependencies: 8,
        circular_dependencies: 1
        }
```

## Request/Response Data Flow

```
┌─ FRONTEND REQUEST ─────────────────────┐
│                                        │
│  POST /api/query/ask                   │
│  ?repo_key=org:my-org                  │
│                                        │
│  {                                     │
│    "query": "...",                     │
│    "include_code": true,               │
│    "max_context_elements": 10          │
│  }                                     │
│                                        │
└────────────┬────────────────────────────┘
             │
             ▼
┌─ BACKEND PROCESSING ──────────────────┐
│                                       │
│  1. Decode repo_key: org:my-org       │
│  2. Fetch from MongoDB:               │
│     - repos_data (parsed_data)        │
│     - graph_data (graphs)             │
│  3. Build org_context string          │
│  4. Call Groq API with context        │
│  5. Extract answer + sources          │
│                                       │
└────────────┬────────────────────────────┘
             │
             ▼
┌─ FRONTEND RESPONSE ────────────────────┐
│                                        │
│  {                                     │
│    "answer": "Detailed answer...",     │
│    "relevant_elements": [              │
│      "api-gateway",                    │
│      "payment-service"                 │
│    ],                                  │
│    "confidence": 0.85,                 │
│    "sources": [                        │
│      {                                 │
│        "type": "organization",         │
│        "element_id": "api-gateway"     │
│      }                                 │
│    ]                                   │
│  }                                     │
│                                        │
└────────────────────────────────────────┘
```

## Key Integration Points

```
┌─────────────────────────────────────────────────────────┐
│                 SYSTEM INTEGRATION MAP                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Frontend (React)                                       │
│    │                                                    │
│    ├─▶ Dashboard: Parse org/repo                       │
│    └─▶ KnowledgeGraph: Ask questions                   │
│            │                                            │
│            ▼                                            │
│  Backend API (FastAPI)                                 │
│    │                                                    │
│    ├─▶ /api/parse/          ──▶  Organization.py       │
│    │   (routes to)              └──▶ CrossRepoDeps.py  │
│    │                             └──▶ MongoDB save     │
│    │                                                    │
│    ├─▶ /api/query/ask       ──▶  Query.py              │
│    │   (single & org)            └──▶ LLM.py           │
│    │                                  └──▶ Groq API    │
│    │                                                    │
│    ├─▶ /api/query/what-if   ──▶  Query.py              │
│    │   (single & org)            └──▶ LLM.py           │
│    │                                  └──▶ Groq API    │
│    │                                                    │
│    └─▶ /api/graph/          ──▶  Graph.py              │
│        (visualization)           └──▶ MongoDB fetch    │
│                                                         │
│  Database (MongoDB)                                     │
│    ├─ graphs: {org_name -> dependency_graph}           │
│    └─ parsed_data: {org_name -> repos_data}            │
│                                                         │
│  LLM API (Groq)                                         │
│    └─ Analyzes context + returns insights              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```
