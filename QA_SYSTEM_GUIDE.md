# Q&A System Guide - Updated for Organization Support

## Overview
The Q&A (Question & Answer) and What-If Analysis systems now support both:
1. **Single Repository Analysis** - Questions about individual codebases
2. **Organization-Level Analysis** - Cross-repository questions about microservices architectures

## System Architecture

### Single Repository Q&A
```
Frontend (React)
    ↓
POST /api/query/ask?repo_key={repo_url}:{branch}
    ↓
Backend (FastAPI)
    ↓
LLMService.answer_query(codebase_graph)
    ↓
Returns: Answer with relevant code elements
```

### Organization Q&A (NEW!)
```
Frontend (React)
    ↓
POST /api/query/ask?repo_key=org:{org_name}
    ↓
Backend (FastAPI)
    ↓
Fetch from MongoDB:
  - repos_data: All individual repository JSONs
  - dependency_graph: Cross-repo dependencies (imports, REST, events, circular)
    ↓
LLMService.answer_org_query(org_data)
    ↓
Returns: Answer analyzing entire organization
```

## Input to LLM - Organization Level

### What the LLM receives for organization queries:

**1. All Repository JSONs:**
```json
{
  "repos_data": {
    "api-service": {
      "services": [
        {
          "name": "UserService",
          "methods": ["login", "register", "getUser"]
        }
      ],
      "api_endpoints": [
        {
          "path": "/api/users",
          "method": "GET",
          "description": "Get all users"
        }
      ],
      "database_access": [
        {
          "type": "query",
          "table": "users"
        }
      ]
    },
    "worker-service": {
      "services": [...],
      "api_endpoints": [...],
      "database_access": [...]
    }
  }
}
```

**2. Organization Dependency Graph:**
```json
{
  "nodes": [
    {
      "id": "api-service",
      "type": "service",
      "language": "python"
    },
    {
      "id": "worker-service",
      "type": "service",
      "language": "python"
    }
  ],
  "edges": [
    {
      "from": "api-service",
      "to": "worker-service",
      "dependency_type": "import",
      "type": "REST",
      "endpoint": "/api/tasks"
    },
    {
      "from": "api-service",
      "to": "worker-service",
      "type": "EVENT",
      "event_name": "task_created"
    }
  ],
  "violations": [
    {
      "type": "circular_dependency",
      "from": "service-a",
      "to": "service-b"
    }
  ],
  "statistics": {
    "total_dependencies": 15,
    "total_services": 5,
    "total_endpoints": 23,
    "circular_dependencies": 2
  }
}
```

### LLM Context Built From:

For organization queries, the LLM receives a comprehensive context including:

1. **Organization Overview**
   - Total repositories
   - List of all repository names

2. **Key Repositories (Up to 5 in detail)**
   - Services in each repo
   - API endpoints
   - Database tables accessed

3. **Cross-Repository Dependencies**
   - Import dependencies between repos
   - REST API calls between services
   - Event-driven communication
   - Circular dependencies (marked as violations ⚠️)

4. **Architecture Statistics**
   - Total dependencies count
   - Total services
   - Total endpoints
   - Violation count

## How to Use

### For Organization Q&A

**Step 1: Parse Organization**
- Go to Dashboard
- Enter organization URL: `https://github.com/your-org-name`
- Click "Parse Repository"
- Wait for parsing to complete

**Step 2: Ask Questions**
- Go to Knowledge Graph tab
- Select from dropdown: "Organization: your-org-name"
- Type your question
- Click "Ask" button

**Example Organization Questions:**
```
1. "What's the overall architecture of our microservices?"
2. "Which services communicate with the user service?"
3. "What are the circular dependencies in our system?"
4. "How does the order service interact with the payment service?"
5. "What databases are accessed by each service?"
6. "Where do REST API calls happen between services?"
7. "Which services handle events?"
8. "What are the main architectural violations?"
```

### For Single Repository Q&A

**Step 1: Parse Repository**
- Go to Dashboard
- Enter repo URL: `https://github.com/user/repo.git`
- Click "Parse Repository"

**Step 2: Ask Questions**
- Go to Knowledge Graph tab
- Select the repository from dropdown
- Type your question
- Click "Ask" button

**Example Single-Repo Questions:**
```
1. "What's the structure of this codebase?"
2. "How does the authentication module work?"
3. "What are the main classes and their relationships?"
4. "Which functions handle API requests?"
5. "What design patterns are used?"
```

## What-If Analysis

### Organization What-If
```
POST /api/query/what-if?repo_key=org:{org_name}
Body: {
  "scenario": "What if we split the user service into auth and profile services?",
  "include_impact_chain": true,
  "max_depth": 5
}
```

The LLM analyzes:
- Which services would be affected
- What changes needed in each repository
- Breaking changes and compatibility issues
- Performance implications
- Testing considerations
- Deployment strategy
- Risk level (Low/Medium/High)
- Recommendations

### Single Repository What-If
```
POST /api/query/what-if?repo_key={repo_url}:{branch}
Body: {
  "scenario": "What if we refactor the authentication module?",
  "include_impact_chain": true,
  "max_depth": 5
}
```

## API Endpoints

### Q&A Endpoints

**Single Repository:**
```
POST /api/query/ask?repo_key={repo_url}:{branch}
Headers: Content-Type: application/json
Body:
{
  "query": "Your question",
  "include_code": true,
  "max_context_elements": 10
}
```

**Organization:**
```
POST /api/query/ask?repo_key=org:{org_name}
Headers: Content-Type: application/json
Body:
{
  "query": "Your question",
  "include_code": true,
  "max_context_elements": 10
}
```

### What-If Endpoints

**Single Repository:**
```
POST /api/query/what-if?repo_key={repo_url}:{branch}
Headers: Content-Type: application/json
Body:
{
  "scenario": "Description of change",
  "include_impact_chain": true,
  "max_depth": 5
}
```

**Organization:**
```
POST /api/query/what-if?repo_key=org:{org_name}
Headers: Content-Type: application/json
Body:
{
  "scenario": "Description of change",
  "include_impact_chain": true,
  "max_depth": 5
}
```

## Response Format

### Query Response
```json
{
  "answer": "Detailed answer to the question...",
  "relevant_elements": ["service-a", "service-b"],
  "confidence": 0.85,
  "sources": [
    {
      "type": "organization",
      "element_id": "api-service"
    }
  ]
}
```

### What-If Response
```json
{
  "analysis": "Detailed impact analysis...",
  "affected_elements": ["service-a", "service-b", "service-c"],
  "impact_chain": [],
  "risk_level": "medium",
  "recommendations": [
    "Review affected services' dependencies",
    "Update integration tests",
    "Plan phased rollout"
  ]
}
```

## Prerequisites

### Required
- **GROQ_API_KEY** in `.env` file
  - Get from: https://console.groq.com
  - Add to `.env`: `GROQ_API_KEY=your_key_here`

- **MongoDB Connection**
  - Required for organization data storage
  - Add to `.env`: `MONGO_URI=mongodb://...`

### Optional
- **GitHub Token** (for large organizations)
  - Increases API rate limits
  - Add to `.env`: `GITHUB_TOKEN=your_token`

## Troubleshooting

### Organization Questions Return Generic Answers
**Cause:** Organization data not fully loaded or incomplete
**Solution:** 
1. Check MongoDB connection
2. Verify organization was fully parsed (check all repos listed)
3. Try again with a simpler question

### "LLM service not available"
**Cause:** GROQ_API_KEY not set
**Solution:** 
1. Create `.env` file in backend directory
2. Add: `GROQ_API_KEY=your_groq_key`
3. Restart backend

### "Graph not found"
**Cause:** Repository not parsed yet
**Solution:**
1. Go to Dashboard
2. Parse the repository/organization first
3. Wait for completion
4. Select from dropdown and try again

### Slow Response Times
**Cause:** Large amount of context being processed
**Solution:**
1. Reduce `max_context_elements` to 5
2. Ask more specific questions
3. Break down large organizations into queries

## Performance Tips

1. **For Large Organizations (10+ repos)**
   - The LLM will summarize key repos
   - Ask specific questions about 1-2 services at a time
   - Use What-If for architectural changes

2. **For Complex Queries**
   - Break into multiple simpler questions
   - Reference specific services/modules
   - Ask about one dependency type at a time

3. **For Better Answers**
   - Provide context: "In the order service..."
   - Be specific: "What's the relationship between..."
   - Ask about patterns: "Where are REST APIs used?"

## Data Flow - Complete Example

### Organization Parsing Flow:
```
1. User enters: https://github.com/my-company
2. Backend discovers all repos
3. Each repo is parsed:
   - Code structure extracted
   - Services identified
   - API endpoints found
   - Database access tracked
4. Organization-level analysis:
   - Dependencies between repos identified
   - Circular dependencies detected
   - Statistics calculated
5. Save to MongoDB:
   - parsed_data collection: All repo JSONs
   - graphs collection: Dependency graph with violations
6. Frontend updates dropdown with "Organization: my-company"
```

### Q&A Flow for Organization:
```
1. User selects: "Organization: my-company"
2. User asks: "What's the architecture?"
3. Backend:
   - Fetches repos_data from parsed_data collection
   - Fetches dependency_graph from graphs collection
   - Builds context string for LLM
   - Includes: repo list, services, endpoints, dependencies, violations
4. LLM processes full organization context
5. Returns: Architecture overview with service relationships
```

## Future Enhancements

1. **Query-Specific Optimization**
   - Detect query type automatically
   - Load only relevant repositories for context

2. **Caching**
   - Cache common questions
   - Cache organization context summaries

3. **Multi-turn Conversations**
   - Ask follow-up questions about previous analysis
   - Maintain conversation context

4. **Custom Context**
   - User-defined context scope
   - Focus on specific services only

5. **Performance Metrics**
   - Track query types
   - Optimize based on patterns
   - Suggest more specific queries

