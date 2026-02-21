# Q&A System - Test Payloads & Examples

## Exact Request/Response Examples

### 1. Organization Q&A Example

#### Request
```http
POST /api/query/ask?repo_key=org:my-company HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "query": "What's the overall architecture of our microservices and how do they communicate?",
  "include_code": true,
  "max_context_elements": 10
}
```

#### Response (200 OK)
```json
{
  "answer": "Your microservices architecture consists of 3 main services:\n\n## API Gateway\n- **Services**: AuthService (login, register, verify), UserService (crud operations)\n- **Endpoints**: /api/auth/login, /api/users, /api/health\n- **Databases**: users, auth_tokens, sessions\n- **Outgoing**: REST calls to payment-service, order-service\n\n## Payment Service\n- **Services**: PaymentProcessor (process_payment, refund), TransactionLogger\n- **Endpoints**: /api/payments/process, /api/payments/status\n- **Databases**: transactions, payment_methods\n- **Incoming**: REST from api-gateway, events from order-service\n\n## Order Service  \n- **Services**: OrderManager (create, update), OrderTracker (status)\n- **Endpoints**: /api/orders, /api/orders/{id}\n- **Databases**: orders, order_items\n- **Outgoing**: Events to payment-service\n\n## Communication Patterns:\n- **REST APIs**: api-gateway → payment-service for payment processing\n- **Events**: order-service publishes 'order_created' event that payment-service subscribes to\n- **Shared Libraries**: All services use common auth-client package\n\n⚠️ **Architecture Issues Found:**\n1. Circular dependency: payment-service calls back to api-gateway for user info\n2. Missing API contracts between services\n3. No circuit breaker pattern for REST calls\n\n**Recommendations:**\n1. Implement API versioning and contracts\n2. Add circuit breaker for inter-service calls\n3. Use saga pattern for distributed transactions\n4. Document service boundaries clearly",
  
  "relevant_elements": [
    "api-gateway",
    "payment-service",
    "order-service"
  ],
  
  "confidence": 0.85,
  
  "sources": [
    {
      "type": "organization",
      "element_id": "api-gateway"
    },
    {
      "type": "organization",
      "element_id": "payment-service"
    },
    {
      "type": "organization",
      "element_id": "order-service"
    }
  ]
}
```

---

### 2. Organization What-If Example

#### Request
```http
POST /api/query/what-if?repo_key=org:my-company HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "scenario": "What if we split the payment service into card-payments and digital-wallet services?",
  "include_impact_chain": true,
  "max_depth": 5
}
```

#### Response (200 OK)
```json
{
  "analysis": "Splitting the payment service would have HIGH impact across your organization:\n\n## Affected Services:\n1. **API Gateway** - Must route to correct payment service (card vs digital-wallet)\n2. **Order Service** - Must handle events from both payment services\n3. **Notification Service** - Payment event structure may change\n\n## Required Changes:\n\n### API Gateway:\n- Update payment routing logic\n- Detect payment method and route accordingly\n- Handle responses from both payment services\n- Estimated effort: 2-3 days\n\n### Order Service:\n- Subscribe to events from both payment services\n- Handle different response schemas\n- Implement transaction saga for both paths\n- Estimated effort: 3-4 days\n\n### Database:\n- Split payment_methods table\n- Create separate transaction logs\n- Setup data migration strategy\n- Estimated effort: 1-2 days\n\n## Breaking Changes:\n- Current /api/payments/process endpoint changes\n- Event schema for payment_processed changes\n- Response format for payment status changes\n\n## Impact Analysis:\n- **Backward Compatibility**: LOW - Multiple breaking changes\n- **Testing Scope**: HIGH - Need to test both payment paths\n- **Deployment Risk**: HIGH - Affects critical payment flow\n- **Data Migration**: COMPLEX - Need zero-downtime strategy\n\n## Performance Implications:\n- Potential latency increase during API routing\n- Database read/write increases temporarily\n- Message queue load increases with dual events\n\n## Risk Factors:\n- Payment processing is critical path\n- Multiple integration points\n- Complex transaction handling\n- Data consistency concerns\n\n## Deployment Strategy:\n1. **Phase 1 (Week 1)**: Deploy new service structure, dual-write transactions\n2. **Phase 2 (Week 2)**: Gradual traffic shift via feature flags\n3. **Phase 3 (Week 3)**: Monitor, validate, complete cutover\n4. **Phase 4 (Week 4)**: Cleanup, decommission old service\n\n## Mitigation Strategies:\n1. Use feature flags for gradual rollout\n2. Implement comprehensive circuit breakers\n3. Add extensive logging for debugging\n4. Setup monitoring and alerts for both services\n5. Maintain fallback to original service during transition\n\n## Testing Requirements:\n- Unit tests for routing logic (3-4 days)\n- Integration tests for both payment paths (5-6 days)\n- Load testing with dual services (2-3 days)\n- User acceptance testing (2 days)\n- Disaster recovery scenarios (2 days)\n\n## Specific Recommendations:\n1. Use async saga pattern, not synchronous transactions\n2. Implement idempotency keys for payment retries\n3. Add comprehensive audit logging\n4. Setup canary deployment with 10% traffic first\n5. Maintain A/B testing capability\n6. Document all API changes thoroughly\n7. Create detailed runbooks for operations team",
  
  "affected_elements": [
    "api-gateway",
    "order-service",
    "payment-service",
    "notification-service"
  ],
  
  "impact_chain": [],
  
  "risk_level": "high",
  
  "recommendations": [
    "Use feature flags for gradual rollout",
    "Implement API versioning before changes",
    "Add comprehensive circuit breakers",
    "Setup extensive monitoring and alerts",
    "Create detailed migration runbook",
    "Plan for data consistency issues",
    "Conduct thorough integration testing"
  ]
}
```

---

### 3. Single Repository Q&A Example

#### Request
```http
POST /api/query/ask?repo_key=https://github.com/user/my-app.git:main HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "query": "What's the main architecture of this codebase?",
  "include_code": true,
  "max_context_elements": 10
}
```

#### Response (200 OK)
```json
{
  "answer": "This codebase has a modular architecture with clear separation of concerns:\n\n## Main Modules:\n\n### api/\n- **Routes** (api/routes.py): Defines all REST endpoints\n- **Controllers** (api/controllers.py): Handles request processing\n- **Serializers** (api/serializers.py): Data transformation\n\n### models/\n- **User** (models/user.py): User entity and relationships\n- **Order** (models/order.py): Order management\n- **Product** (models/product.py): Product catalog\n\n### services/\n- **UserService** (services/user.py): User business logic\n- **OrderService** (services/order.py): Order processing\n- **PaymentService** (services/payment.py): Payment handling\n\n## Architecture Pattern: MVC/Clean Architecture\n\n1. **Routing Layer**: API routes defined in api/routes.py\n2. **Controller Layer**: Business logic in controllers/\n3. **Service Layer**: Core business rules in services/\n4. **Data Layer**: Database access in models/\n\n## Key Dependencies:\n- UserService depends on User model\n- OrderService depends on Product and User models\n- PaymentService depends on Order model\n\n## Database Access:\n- ORM: SQLAlchemy\n- Models handle database operations\n- Services use models for data access\n\n## Design Patterns Used:\n- Repository Pattern: Models act as repositories\n- Service Pattern: Encapsulate business logic\n- Dependency Injection: Services injected into controllers\n\n## Code Quality:\n- Well-documented functions\n- Clear error handling\n- Consistent naming conventions\n- Good separation of concerns",
  
  "relevant_elements": [
    "UserService",
    "OrderService",
    "User",
    "Order",
    "PaymentService"
  ],
  
  "confidence": 0.82,
  
  "sources": [
    {
      "type": "codebase",
      "element_id": "UserService"
    },
    {
      "type": "codebase",
      "element_id": "OrderService"
    }
  ]
}
```

---

### 4. Error Response Examples

#### 4a. Organization Not Found
```http
POST /api/query/ask?repo_key=org:nonexistent HTTP/1.1
```

**Response (404 Not Found)**
```json
{
  "detail": "Organization data not found: org:nonexistent"
}
```

#### 4b. LLM Service Not Available
```http
POST /api/query/ask?repo_key=org:my-org HTTP/1.1
```

**Response (503 Service Unavailable)**
```json
{
  "detail": "LLM service not available. Check GROQ_API_KEY in .env"
}
```

#### 4c. Invalid Repository Key
```http
POST /api/query/ask?repo_key=invalid-key HTTP/1.1
```

**Response (404 Not Found)**
```json
{
  "detail": "Graph not found for key: invalid-key"
}
```

---

## cURL Examples

### 1. Ask Organization Question
```bash
curl -X POST "http://localhost:8000/api/query/ask?repo_key=org:my-org" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What services talk to the payment service?",
    "include_code": true,
    "max_context_elements": 10
  }' | jq .answer
```

### 2. What-If Analysis
```bash
curl -X POST "http://localhost:8000/api/query/what-if?repo_key=org:my-org" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "What if we add caching to the API gateway?",
    "include_impact_chain": true,
    "max_depth": 5
  }' | jq .analysis
```

### 3. Ask Single Repo Question
```bash
curl -X POST "http://localhost:8000/api/query/ask?repo_key=https://github.com/user/repo.git:main" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main architecture?",
    "include_code": true,
    "max_context_elements": 5
  }' | jq .
```

### 4. Parse Organization
```bash
curl -X POST "http://localhost:8000/api/parse/" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_url": "https://github.com/my-company",
    "branch": "main",
    "include_tests": true,
    "include_vendor": false,
    "languages": ["python", "javascript"],
    "max_file_size": 1000000
  }' | jq .
```

### 5. List Parsed Organizations
```bash
curl -X GET "http://localhost:8000/api/parse/" | jq '.graphs[] | select(.repository | contains("Organization"))'
```

---

## Postman Collection

### Q&A Ask (Organization)
```json
{
  "name": "Q&A - Ask Organization",
  "request": {
    "method": "POST",
    "header": [
      {
        "key": "Content-Type",
        "value": "application/json"
      }
    ],
    "url": {
      "raw": "{{baseUrl}}/api/query/ask?repo_key=org:my-org",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["api", "query", "ask"],
      "query": [
        {
          "key": "repo_key",
          "value": "org:my-org"
        }
      ]
    },
    "body": {
      "mode": "raw",
      "raw": "{\n  \"query\": \"What's the architecture?\",\n  \"include_code\": true,\n  \"max_context_elements\": 10\n}"
    }
  }
}
```

### What-If Analysis (Organization)
```json
{
  "name": "What-If - Organization",
  "request": {
    "method": "POST",
    "header": [
      {
        "key": "Content-Type",
        "value": "application/json"
      }
    ],
    "url": {
      "raw": "{{baseUrl}}/api/query/what-if?repo_key=org:my-org",
      "protocol": "http",
      "host": ["localhost"],
      "port": "8000",
      "path": ["api", "query", "what-if"],
      "query": [
        {
          "key": "repo_key",
          "value": "org:my-org"
        }
      ]
    },
    "body": {
      "mode": "raw",
      "raw": "{\n  \"scenario\": \"What if we split the payment service?\",\n  \"include_impact_chain\": true,\n  \"max_depth\": 5\n}"
    }
  }
}
```

---

## Testing Checklist

- [ ] **Parse Organization**: Successfully parse GitHub organization
- [ ] **List Graphs**: See organization in dropdown with "Organization: name" format
- [ ] **Ask Q&A**: Ask question about org architecture
  - [ ] Get meaningful answer about services
  - [ ] Relevant elements populated
  - [ ] Confidence score present
  - [ ] Sources included
- [ ] **What-If**: Ask what-if scenario
  - [ ] Get impact analysis
  - [ ] Affected services listed
  - [ ] Risk level determined
  - [ ] Recommendations provided
- [ ] **Single Repo Still Works**: Ensure single repo Q&A unchanged
  - [ ] Can parse single repo
  - [ ] Can ask questions
  - [ ] Can run what-if
- [ ] **Error Handling**
  - [ ] Missing GROQ_API_KEY handled
  - [ ] Invalid org_key handled
  - [ ] MongoDB connection issues handled

---

## Query Examples by Category

### Architecture Questions
- "What's the overall architecture?"
- "How many services are in this organization?"
- "What are the main microservices?"
- "How do services communicate?"

### Dependency Questions
- "Which services depend on the API gateway?"
- "What REST APIs exist between services?"
- "Are there any circular dependencies?"
- "What event-driven communication exists?"

### Database Questions
- "What databases do we have?"
- "Which services access the users table?"
- "How many tables exist across all services?"

### What-If Scenarios
- "What if we add a cache layer?"
- "What if we split the user service?"
- "What if we remove service X?"
- "What if we change the database?"

### Violation Questions
- "Are there any architectural violations?"
- "Show me circular dependencies"
- "What contracts are missing?"
