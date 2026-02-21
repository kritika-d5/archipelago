# Q&A Input Data Structure - Complete Reference

## Overview
This document shows exactly what inputs are provided to the LLM for both single repository and organization-level Q&A.

## Single Repository Q&A Input

### Code Flow:
```
Frontend sends: { query: "...", include_code: true, max_context_elements: 10 }
↓
Backend fetches: CodebaseGraph from parsed_graphs
↓
LLMService._build_context(codebase_graph)
↓
Constructs context string with:
```

### Context String Structure:
```
=== SINGLE REPOSITORY CONTEXT ===

Repository: my-app
Languages: python, javascript
Total files: 245
Total lines: 45000

=== Codebase Structure ===

CLASS: UserService
File: src/services/UserService.py
Lines: 10-150
Description: Handles user authentication and profile management
Code:
  def login(self, username, password):
    # Full code snippet if include_code=true
  ...
Parameters: username: str, password: str
Returns: bool

FUNCTION: authenticate
File: src/auth/auth.py
Lines: 200-220
Description: Validates credentials
Code: ...
Parameters: username: str, password: str
Returns: AuthToken

=== Key Dependencies ===

UserService -> DatabaseManager (import)
AuthModule -> UserService (call)
RequestHandler -> AuthModule (import)
...
```

### LLM Receives:
- Repository name and metadata
- Up to 10 code elements (classes, functions, modules)
- Code snippets (if `include_code=true`)
- Function signatures and parameters
- Return types
- Key dependencies between elements
- File paths and line numbers

---

## Organization Q&A Input (NEW!)

### Code Flow:
```
Frontend sends: { query: "...", include_code: true, max_context_elements: 10 }
↓
Backend decodes repo_key as "org:my-org"
↓
Backend fetches from MongoDB:
  - repos_data: {all parsed repo JSONs}
  - dependency_graph: {cross-repo dependencies, violations, stats}
↓
LLMService._build_org_context(org_data)
↓
Constructs context string with all repos + dependencies
```

### Full Data Structure (What Gets Passed to LLM):

```python
org_data = {
    "repos_data": {
        "api-service": {
            "services": [
                {
                    "name": "AuthService",
                    "methods": ["login", "register", "verify_token"],
                    "endpoints": ["/api/auth/login", "/api/auth/register"]
                },
                {
                    "name": "UserService",
                    "methods": ["get_user", "update_user", "delete_user"],
                    "endpoints": ["/api/users/{id}"]
                }
            ],
            "api_endpoints": [
                {
                    "path": "/api/auth/login",
                    "method": "POST",
                    "description": "User login endpoint",
                    "auth_required": true
                },
                {
                    "path": "/api/users",
                    "method": "GET",
                    "description": "Get all users",
                    "auth_required": true
                }
            ],
            "database_access": [
                {
                    "type": "query",
                    "table": "users",
                    "operations": ["SELECT", "INSERT", "UPDATE"]
                },
                {
                    "type": "query",
                    "table": "auth_tokens",
                    "operations": ["INSERT", "DELETE"]
                }
            ],
            "imports": ["requests", "fastapi", "sqlalchemy"],
            "external_services": ["mongodb", "redis"]
        },
        "payment-service": {
            "services": [
                {
                    "name": "PaymentProcessor",
                    "methods": ["process_payment", "refund", "get_status"],
                    "endpoints": ["/api/payments"]
                }
            ],
            "api_endpoints": [
                {
                    "path": "/api/payments/process",
                    "method": "POST",
                    "description": "Process payment"
                }
            ],
            "database_access": [
                {
                    "type": "query",
                    "table": "transactions",
                    "operations": ["INSERT", "SELECT"]
                }
            ],
            "imports": ["stripe", "fastapi"],
            "external_services": ["stripe", "mongodb"]
        },
        "order-service": {
            "services": [...],
            "api_endpoints": [...],
            "database_access": [...]
        }
    },
    
    "dependency_graph": {
        "nodes": [
            {
                "id": "api-service",
                "type": "microservice",
                "language": "python",
                "description": "API Gateway and Authentication"
            },
            {
                "id": "payment-service",
                "type": "microservice",
                "language": "python",
                "description": "Payment Processing"
            },
            {
                "id": "order-service",
                "type": "microservice",
                "language": "python",
                "description": "Order Management"
            }
        ],
        
        "edges": [
            # REST API dependencies
            {
                "from": "api-service",
                "to": "payment-service",
                "type": "REST",
                "dependency_type": "http_call",
                "endpoint": "/api/payments/process",
                "method": "POST"
            },
            
            # Event-driven dependencies
            {
                "from": "order-service",
                "to": "payment-service",
                "type": "EVENT",
                "dependency_type": "event_trigger",
                "event_name": "order_created",
                "description": "Payment service listens for new orders"
            },
            
            # Import/Code dependencies
            {
                "from": "api-service",
                "to": "order-service",
                "type": "IMPORT",
                "dependency_type": "shared_library",
                "module": "order_client"
            },
            
            # Circular dependency (VIOLATION!)
            {
                "from": "service-a",
                "to": "service-b",
                "type": "REST",
                "dependency_type": "circular",
                "circular": true,
                "depth": 2
            }
        ],
        
        "violations": [
            {
                "type": "circular_dependency",
                "from": "service-a",
                "to": "service-b",
                "severity": "high",
                "description": "Circular API dependency detected"
            },
            {
                "type": "missing_contract",
                "from": "api-service",
                "to": "payment-service",
                "severity": "medium",
                "description": "No API contract defined"
            }
        ],
        
        "statistics": {
            "total_repositories": 3,
            "total_services": 5,
            "total_endpoints": 12,
            "total_dependencies": 8,
            "circular_dependencies": 1,
            "violations_count": 2,
            "avg_dependency_depth": 1.5
        }
    }
}
```

### Context String Built for LLM:

```
=== ORGANIZATION OVERVIEW ===
Total Repositories: 3
Repository Names: api-service, payment-service, order-service

=== KEY REPOSITORIES ===

Repository: api-service
Services: AuthService, UserService, HealthService
Endpoints: /api/auth/login, /api/users, /api/health
Database Tables: users, auth_tokens, sessions

Repository: payment-service
Services: PaymentProcessor, RefundService
Endpoints: /api/payments/process, /api/payments/refund
Database Tables: transactions, payment_methods

Repository: order-service
Services: OrderManager, OrderTracker
Endpoints: /api/orders, /api/orders/{id}
Database Tables: orders, order_items

=== CROSS-REPOSITORY DEPENDENCIES ===

Import Dependencies: 2
  api-service -> order-service
  payment-service -> api-service

REST API Dependencies: 3
  api-service -[/api/payments/process]-> payment-service
  order-service -[/api/orders/create]-> api-service
  api-service -[/api/users/{id}]-> ...

Event-driven Dependencies: 2
  order-service -[event: order_created]-> payment-service
  payment-service -[event: payment_completed]-> order-service

Circular Dependencies (⚠️ Violations): 1
  ⚠️ CIRCULAR: order-service <-> payment-service

=== STATISTICS ===
Total Dependencies: 8
Total Services: 5
Total Endpoints: 12
⚠️ Architecture Violations: 2
```

---

## What the LLM Actually Sees

When you ask an organization question like: **"What's the overall architecture?"**

The LLM receives:
1. **Complete organizational structure** - All repos, services, endpoints
2. **All dependencies** - Import, REST, Event relationships
3. **Violation flags** - Circular dependencies marked with ⚠️
4. **Statistics** - Aggregate metrics across org
5. **Database schema** - What each service accesses

Then it generates a response like:
```
"Your organization has 3 microservices: API Gateway, Payment Service, 
and Order Service. The API Gateway exposes 12 endpoints and uses REST 
calls to the Payment Service for transaction processing. The Order 
Service communicates with Payment Service via events. 

⚠️ ARCHITECTURAL ISSUE: There's a circular dependency between Order 
Service and Payment Service - they both call each other. This should 
be resolved by introducing an event queue or saga pattern.

The system accesses 8 total databases distributed across services..."
```

---

## Example Queries and Their Context

### Question 1: "What services talk to the payment service?"
**Context provided:**
- All services in org
- All edges where target = payment-service
- Payment service's endpoints
- Payment service's database tables

**LLM analyzes:** Services with outgoing edges to payment-service

---

### Question 2: "Are there any circular dependencies?"
**Context provided:**
- All edges with `circular: true` flag
- Violations list showing circular deps
- Statistics showing violation count
- Full dependency graph

**LLM analyzes:** Violation objects and dependency chains

---

### Question 3: "What would happen if we split the API service?"
**This is a What-If question:**
**Context provided:**
- Complete api-service structure
- All services that depend on it (incoming edges)
- All services it depends on (outgoing edges)
- REST endpoints and event subscriptions

**LLM analyzes:** Impact chain of splitting a service

---

## Key Differences: Single Repo vs Organization

| Aspect | Single Repo | Organization |
|--------|-------------|--------------|
| **Data Source** | In-memory `CodebaseGraph` | MongoDB (repos_data + dependency_graph) |
| **Context Elements** | Code classes, functions, modules | Services, APIs, databases, inter-service dependencies |
| **Dependencies** | Within-file/within-module | Between repositories/microservices |
| **Violation Types** | Circular imports, unused code | Circular REST calls, missing contracts |
| **Focus** | Code structure & patterns | Service interactions & architecture |
| **LLM Method** | `answer_query()` | `answer_org_query()` |
| **Impact Analysis** | Code elements affected | Services affected across repos |

---

## How to Use This Information

### For Debugging:
If Q&A is returning unexpected answers:
1. Check what repo was selected (single vs org)
2. Verify MongoDB has the correct data
3. Check the context string that would be built
4. Test with a simpler, more specific question

### For Better Questions:
- Organization Q&A works best with questions about:
  - Service interactions
  - Architecture patterns
  - Cross-service impacts
  - Violations and risks
  
- Single repo Q&A works best with:
  - Code structure
  - Implementation details
  - Design patterns
  - Specific functions/classes

### For Optimization:
- Large organizations: Ask about 1-2 services at a time
- Complex architectures: Use What-If for change impact
- Multiple violations: Ask about specific violation types
