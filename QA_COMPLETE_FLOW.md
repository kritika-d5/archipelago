# Complete Q&A System Flow - Request to Response

## Organization Q&A Complete Flow

### Step 1: User Interface (Frontend)
```
User on Knowledge Graph page
↓
Selects from dropdown: "Organization: my-org"
↓
Enters question: "What's the architecture of our microservices?"
↓
Clicks "Ask" button
```

### Step 2: Frontend HTTP Request
```javascript
POST /api/query/ask?repo_key=org:my-org

Headers:
  Content-Type: application/json

Body:
{
  "query": "What's the architecture of our microservices?",
  "include_code": true,
  "max_context_elements": 10
}
```

### Step 3: Backend Processing (query.py)
```python
# Handler: ask_question()

# Decode the repo_key
repo_key = "org:my-org"
decoded_key = unquote(repo_key)  # Still "org:my-org"

# Check if it's an organization query
if repo_key.startswith("org:"):
    # YES - it's an organization!
    
    # Fetch from MongoDB:
    org_data = get_organization_data(decoded_key)
    
    # This retrieves:
    org_data = {
        "repos_data": {
            # All individual repository JSONs
            "api-gateway": {...},
            "payment-service": {...},
            "order-service": {...}
        },
        "dependency_graph": {
            # Cross-repository dependency graph
            "nodes": [...],
            "edges": [...],
            "violations": [...],
            "statistics": {...}
        }
    }
    
    # Pass to LLM
    response = llm_service.answer_org_query(org_data, request)
```

### Step 4: LLM Context Building (llm.py)
```python
# Method: _build_org_context()

# Input: org_data (repos_data + dependency_graph)

context_parts = []

# 1. Add organization header
context_parts.append("=== ORGANIZATION OVERVIEW ===")
context_parts.append("Total Repositories: 3")
context_parts.append("Repository Names: api-gateway, payment-service, order-service")

# 2. Add key repositories (up to 5)
for repo_name in list(org_data["repos_data"].keys())[:5]:
    repo_info = org_data["repos_data"][repo_name]
    
    context_parts.append(f"\nRepository: {repo_name}")
    
    # Add services
    services = repo_info.get("services", [])
    context_parts.append(f"Services: {', '.join([s.get('name') for s in services])}")
    
    # Add endpoints
    endpoints = repo_info.get("api_endpoints", [])
    context_parts.append(f"Endpoints: {', '.join([e.get('path') for e in endpoints])}")
    
    # Add databases
    db_tables = repo_info.get("database_access", [])
    context_parts.append(f"Database Tables: {', '.join([d.get('table') for d in db_tables])}")

# 3. Add cross-repository dependencies
dependency_graph = org_data["dependency_graph"]
edges = dependency_graph.get("edges", [])

# Group by type
import_deps = [e for e in edges if e.get("dependency_type") == "import"]
rest_deps = [e for e in edges if e.get("type") == "REST"]
event_deps = [e for e in edges if e.get("type") == "EVENT"]

context_parts.append("\n=== CROSS-REPOSITORY DEPENDENCIES ===")

if import_deps:
    context_parts.append(f"\nImport Dependencies: {len(import_deps)}")
    for dep in import_deps[:3]:
        context_parts.append(f"  {dep['from']} -> {dep['to']}")

if rest_deps:
    context_parts.append(f"\nREST API Dependencies: {len(rest_deps)}")
    for dep in rest_deps[:3]:
        endpoint = dep.get('endpoint', 'unknown')
        context_parts.append(f"  {dep['from']} -[{endpoint}]-> {dep['to']}")

if event_deps:
    context_parts.append(f"\nEvent Dependencies: {len(event_deps)}")
    for dep in event_deps[:3]:
        event = dep.get('event_name', 'unknown')
        context_parts.append(f"  {dep['from']} -[event: {event}]-> {dep['to']}")

# 4. Add statistics
context_parts.append("\n=== STATISTICS ===")
stats = dependency_graph.get("statistics", {})
context_parts.append(f"Total Dependencies: {stats.get('total_dependencies', 0)}")
context_parts.append(f"Total Services: {stats.get('total_services', 0)}")
context_parts.append(f"Total Endpoints: {stats.get('total_endpoints', 0)}")

# Highlight violations
violations = dependency_graph.get("violations", [])
if violations:
    context_parts.append(f"⚠️ Architecture Violations: {len(violations)}")

# 5. Join all parts
context = "\n".join(context_parts)

# Result: A comprehensive context string about the entire organization
```

### Step 5: LLM API Call (Groq)
```python
# Method: answer_org_query()

prompt = f"""You are an expert in microservices architecture and cross-repository analysis.
Analyze the following multi-repository organization and answer the user's question.

{context}  # <- The complete context built above

User Question: What's the architecture of our microservices?

Provide a detailed answer that considers:
1. The overall architecture of the organization
2. How services interact across repositories
3. Potential bottlenecks or dependencies
4. Any architectural issues or violations
5. Best practices and recommendations

Answer:"""

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {
            "role": "system",
            "content": "You are an expert in analyzing microservices architectures..."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    temperature=0.3,
    max_tokens=2000
)

answer = response.choices[0].message.content

# LLM now has ALL the context and generates answer
```

### Step 6: Response Processing
```python
# Extract relevant repositories mentioned in answer
repos_data = org_data.get("repos_data", {})
relevant_repos = []

for repo_name in repos_data.keys():
    if repo_name.lower() in answer.lower():
        relevant_repos.append(repo_name)

# Build response object
response = QueryResponse(
    answer=answer,
    relevant_elements=relevant_repos[:10],
    confidence=0.85,
    sources=[{"type": "organization", "element_id": repo} for repo in relevant_repos[:5]]
)

# Return to frontend
```

### Step 7: Frontend Response (HTTP 200)
```json
{
  "answer": "Your microservices architecture consists of 3 main services:\n\n1. **API Gateway** (api-gateway) - Entry point for all requests\n   - Services: AuthService, UserService, HealthService\n   - Endpoints: /api/auth/login, /api/users, /api/health\n   - Databases: users, auth_tokens, sessions\n\n2. **Payment Service** (payment-service) - Handles payment processing\n   - Services: PaymentProcessor, RefundService\n   - Endpoints: /api/payments/process, /api/payments/refund\n   - Databases: transactions, payment_methods\n\n3. **Order Service** (order-service) - Manages orders\n   - Services: OrderManager, OrderTracker\n   - Endpoints: /api/orders, /api/orders/{id}\n   - Databases: orders, order_items\n\n**Inter-Service Communication:**\n- REST APIs: API Gateway calls Payment Service for payments\n- Events: Order Service publishes 'order_created' events that Payment Service listens to\n- Imports: Shared libraries between services\n\n**⚠️ Architecture Concerns:**\n- Circular dependency detected between Order and Payment services\n- Missing API contracts between services\n\n**Recommendations:**\n1. Implement API versioning and contracts\n2. Resolve circular dependencies using saga pattern\n3. Document service boundaries clearly\n4. Implement circuit breakers for inter-service calls",\n\n  "relevant_elements": [\n    "api-gateway",\n    "payment-service", \n    "order-service\"\n  ],\n\n  \"confidence\": 0.85,\n\n  \"sources\": [\n    {\n      \"type\": \"organization\",\n      \"element_id\": \"api-gateway\"\n    },\n    {\n      \"type\": \"organization\",\n      \"element_id\": \"payment-service\"\n    },\n    {\n      \"type\": \"organization\",\n      \"element_id\": \"order-service\"\n    }\n  ]\n}
```

### Step 8: Frontend Display
```jsx
// KnowledgeGraph.jsx renders response

<div className="answer-box">
  <h3>Answer</h3>
  <ReactMarkdown>
    {answer}
  </ReactMarkdown>
  
  <div className="sources">
    <h4>Relevant Services:</h4>
    <ul>
      {relevant_elements.map(elem => (
        <li key={elem}>{elem}</li>
      ))}
    </ul>
  </div>
  
  <div className="confidence">
    Confidence: 85%
  </div>
</div>
```

---

## What-If Analysis Flow

### Complete Example: "What if we split the payment service?"

```
Frontend Request:
POST /api/query/what-if?repo_key=org:my-org
{
  "scenario": "What if we split the payment service into card-payments and digital-wallet?",
  "include_impact_chain": true,
  "max_depth": 5
}
```

```python
# Backend Processing

# 1. Fetch organization data (same as Q&A)
org_data = get_organization_data("org:my-org")

# 2. Build context with all repos + dependencies
context = _build_org_context(org_data)

# 3. Create what-if prompt
prompt = f"""You are an expert in system architecture and impact analysis.
Analyze the following organization and perform a what-if analysis.

{context}

Scenario: What if we split the payment service into card-payments and digital-wallet?

Provide impact analysis including:
1. Which repositories/services would be affected
2. What changes needed in each service
3. Breaking changes or compatibility issues
4. Performance implications
5. Testing considerations
6. Deployment strategy
7. Risk assessment (Low/Medium/High)
8. Specific recommendations

Impact Analysis:"""

# 4. Call LLM with what-if prompt
response = client.chat.completions.create(...)

# 5. Extract analysis
analysis = response.choices[0].message.content

# 6. Identify affected services
affected_repos = [repo for repo in org_data["repos_data"].keys() 
                  if repo.lower() in analysis.lower()]

# 7. Determine risk level
risk_level = "high" if "high risk" in analysis.lower() else \
             "medium" if "medium risk" in analysis.lower() else "low"

# 8. Return response
return WhatIfResponse(
    analysis=analysis,
    affected_elements=affected_repos,
    impact_chain=[],
    risk_level=risk_level,
    recommendations=[
        "Review affected services' dependencies",
        "Update integration tests",
        "Plan phased rollout"
    ]
)
```

```json
Frontend Response:
{
  "analysis": "Splitting the payment service would have significant impact:\n\n**Affected Services:**\n- Order Service: Currently calls payment service for payment processing\n- API Gateway: Routes payment requests to payment service\n- Notification Service: Listens to payment events\n\n**Required Changes:**\n1. Update Order Service to route to correct service (card-payments or digital-wallet)\n2. API Gateway needs new routing rules\n3. Event subscribers need to handle two payment services\n\n**Breaking Changes:**\n- Existing payment endpoints would change\n- Clients need updated endpoints\n- Event schema may need versioning\n\n**Risk Level:** HIGH\n- Complex deployment with multiple dependencies\n- High probability of runtime issues\n- Significant testing required\n\n**Recommendations:**\n1. Use API versioning during migration\n2. Implement feature flags for gradual rollout\n3. Set up comprehensive integration tests\n4. Consider using saga pattern for transactions",\n\n  "affected_elements": [\n    "order-service",\n    "api-gateway\",\n    "notification-service\"\n  ],\n\n  "impact_chain": [],\n\n  "risk_level": "high\",\n\n  "recommendations": [\n    \"Review affected services' dependencies\",\n    \"Update integration tests across services\",\n    \"Plan phased rollout of changes\",\n    \"Monitor cross-service communication\",\n    \"Document architectural changes\"\n  ]\n}
```

---

## Data Flow Diagram

```
┌─────────────────────┐
│   Frontend (React)  │
│ Selection: org:X    │
│ Question: "...?"    │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────┐
│  POST /api/query/ask         │
│  repo_key=org:my-org         │
│  query={...}                 │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Backend (query.py)          │
│  Detects org: prefix         │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  MongoDB Queries             │
│  Get repos_data              │
│  Get dependency_graph        │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────────┐
│  LLMService (llm.py)             │
│  _build_org_context(org_data)    │
│                                  │
│  Input: {                        │
│    repos_data: {...},            │
│    dependency_graph: {...}       │
│  }                               │
│                                  │
│  Output: context_string          │
└──────────┬──────────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Groq API Call               │
│  Model: openai/gpt-oss-20b   │
│  Context: organization data  │
│  Prompt: user question       │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  LLM Response Generation     │
│  Analyzes org architecture   │
│  Considers all services      │
│  Identifies dependencies     │
│  Highlights violations       │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Response Construction       │
│  Extract relevant services   │
│  Calculate confidence        │
│  Build sources               │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  HTTP Response (JSON)        │
│  answer: "..."               │
│  relevant_elements: [...]    │
│  confidence: 0.85            │
│  sources: [...]              │
└──────────┬───────────────────┘
           │
           ▼
┌─────────────────────┐
│   Frontend Display  │
│   Markdown answer   │
│   Sources list      │
│   Confidence badge  │
└─────────────────────┘
```

---

## Key Points

### What the LLM sees:
✅ All repositories' parsed JSONs  
✅ All inter-service dependencies  
✅ API endpoints between services  
✅ Event subscriptions  
✅ Database access patterns  
✅ Circular dependencies & violations  
✅ Architecture statistics  

### What makes good context:
- Comprehensive organizational overview
- Clear service responsibilities
- All dependency relationships
- Explicit violation markers
- Aggregate statistics

### Performance Notes:
- Context building: ~100ms
- MongoDB queries: ~200-500ms
- LLM inference: ~2-5 seconds
- Total response: ~3-6 seconds

### Accuracy Factors:
- Quality of parsed data
- Clarity of service names
- Completeness of dependency graph
- LLM model quality (temperature=0.3 for consistency)
