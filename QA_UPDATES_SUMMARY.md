# Q&A System Updates - Summary

## Changes Made

### 1. **Backend - LLM Service** (`backend/app/core/llm.py`)

Added 3 new methods to support organization-level Q&A:

#### `_build_org_context(org_data, max_repos=5)`
- Builds context string from organization data
- Includes: repos overview, services, endpoints, databases, all dependencies
- Highlights violations with ⚠️ markers
- Returns formatted context for LLM

#### `answer_org_query(org_data, request)`
- Handles Q&A for entire organization
- Processes all repos + dependency graph as context
- Returns QueryResponse with answer + relevant services
- Confidence: 0.85

#### `analyze_org_what_if(org_data, request)`
- Handles what-if analysis for organization
- Analyzes impact across all services
- Determines risk level (low/medium/high)
- Returns detailed recommendations

### 2. **Backend - Query API** (`backend/app/api/query.py`)

Updated endpoints to support both single repositories and organizations:

#### `/api/query/ask` (POST)
**Before:** Only supported single repositories (graph=None caused failure)  
**After:** 
- Detects if repo_key starts with `org:`
- For organizations: Fetches from MongoDB and calls `llm_service.answer_org_query()`
- For single repos: Uses existing `llm_service.answer_query()`
- Better error messages with available keys

#### `/api/query/what-if` (POST)
**Before:** Only supported single repositories  
**After:**
- Detects organization vs single repository
- For organizations: Calls `llm_service.analyze_org_what_if()`
- For single repos: Uses existing `llm_service.analyze_what_if()`
- Same comprehensive analysis as single repos

#### New Helper Function: `get_organization_data(org_key)`
- Fetches organization data from MongoDB
- Retrieves both:
  - `parsed_data`: Individual repository JSONs
  - `graphs`: Dependency graph with edges, nodes, violations, stats
- Returns combined org_data dict

### 3. **Frontend** (No changes needed)
The frontend already supports organization graphs because:
- Dashboard already accepts organization URLs
- Parse endpoint already stores with `org:` prefix
- Graph list endpoint already retrieves them
- Q&A components work with the updated backend

---

## What Q&A Now Receives

### Single Repository Q&A
**Input:**
```
CodebaseGraph object {
  elements: [classes, functions, modules],
  dependencies: [code-level dependencies],
  metadata: {name, language, stats}
}
```

### Organization Q&A (NEW!)
**Input:**
```
{
  repos_data: {
    repo_name_1: {
      services: [...],
      api_endpoints: [...],
      database_access: [...]
    },
    repo_name_2: {...},
    ...
  },
  dependency_graph: {
    nodes: [all services],
    edges: [all dependencies: REST/EVENT/IMPORT],
    violations: [circular deps, missing contracts],
    statistics: {total_deps, total_services, ...}
  }
}
```

---

## How to Test

### Test 1: Organization Q&A
```
1. Go to Dashboard
2. Enter: https://github.com/your-org-name
3. Wait for parsing
4. Go to Graph tab
5. Select: "Organization: your-org-name"
6. Ask: "What's the architecture?"
7. Should receive comprehensive answer about all services + dependencies
```

### Test 2: What-If on Organization
```
1. Select organization from dropdown
2. Click "What If" tab
3. Enter: "What if we split the user service?"
4. Should see impact analysis across all affected services
```

### Test 3: Single Repo Still Works
```
1. Parse single repository: https://github.com/user/repo.git
2. Ask a question in Q&A
3. Should work as before (no changes to single repo logic)
```

---

## Files Modified

1. **backend/app/core/llm.py**
   - Added: `_build_org_context()` method
   - Added: `answer_org_query()` method  
   - Added: `analyze_org_what_if()` method

2. **backend/app/api/query.py**
   - Updated: `ask_question()` endpoint
   - Updated: `what_if_analysis()` endpoint
   - Added: `get_organization_data()` helper function
   - Added: MongoDB imports and unquote

3. **backend/app/api/parse.py** (Previously fixed)
   - Updated: `list_parsed_graphs()` to skip None graphs and include org graphs

---

## Database Requirements

### MongoDB Collections Used:
1. **graphs** collection
   - Key: `graph_name` (format: `org:org_name`)
   - Contains: `graph_data` with nodes, edges, violations, statistics

2. **parsed_data** collection
   - Key: `graph_name` (format: `org:org_name`)
   - Contains: `parsed_data` with all individual repo JSONs

Both are already created by `organization.py` when analyzing an organization.

---

## Environment Requirements

Must have in `.env`:
```
GROQ_API_KEY=your_groq_api_key_here
MONGO_URI=mongodb://...
```

---

## Example Usage

### Ask About Organization Architecture
```bash
curl -X POST "http://localhost:8000/api/query/ask?repo_key=org:my-org" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What services communicate with the API gateway?",
    "include_code": true,
    "max_context_elements": 10
  }'
```

### What-If Analysis for Organization
```bash
curl -X POST "http://localhost:8000/api/query/what-if?repo_key=org:my-org" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "What if we add caching to the API gateway?",
    "include_impact_chain": true,
    "max_depth": 5
  }'
```

---

## Key Improvements

✅ **Organizations now fully supported** - Can ask questions about entire architectures  
✅ **Complete context** - LLM sees all repos + all dependencies at once  
✅ **Better insights** - Identifies cross-service impacts, violations, patterns  
✅ **What-If analysis** - Analyze impact of changes across all services  
✅ **Better error handling** - Clear messages if data not found  
✅ **Backward compatible** - Single repo Q&A still works exactly the same  

---

## Next Steps (Optional Enhancements)

1. **Query-specific context loading** - Only include relevant services
2. **Caching** - Cache common organization analyses
3. **Custom prompts** - Different prompts for different query types
4. **Conversation history** - Multi-turn Q&A
5. **Performance optimization** - Async context building
