# Knowledge Graph Features Guide

## Where to See the Enhanced Graph Features

### 1. **Visual Graph Display** (`/knowledge-graph` page)

The main graph visualization shows:

#### **Node Types with Visual Styling:**
- **🤖 Agents** - Red star shape (`#e74c3c`)
  - Click to see: Agent type, LLM provider, capabilities
- **⚙️ Workflows** - Green round-diamond shape (`#16a085`)
  - Click to see: Workflow type, steps count
- **🗄️ Database Schemas** - Orange round-octagon shape (`#d35400`)
  - Click to see: Database language, ORM framework, table count
- **📊 Database Tables** - Red round-hexagon shape (`#c0392b`)
  - Click to see: Schema name, column count
- **Classes** - Purple rectangle
- **Functions/Methods** - Blue ellipse
- **API Endpoints** - Orange round-rectangle

#### **Edge Relations (Visible on Edges):**
- **Relation labels** appear on each edge showing the relationship type
- **Color-coded edges:**
  - `inheritance` - Red
  - `call` - Blue
  - `import` - Gray dashed
  - `uses_agent` - Red dotted
  - `triggers_workflow` - Green dashed
  - `queries_database` - Orange
  - `reads_from_database` - Blue dashed
  - `writes_to_database` - Red solid

**To see edge relations:**
- Hover over edges to see relation type
- Click on edges to see detailed relation info (relation type and strength)

### 2. **Metadata Dashboard** (Top of graph page)

The info cards show:
- **Total Nodes & Edges**
- **🤖 Agents Count** - Number of agents detected
- **⚙️ Workflows Count** - Number of workflows detected
- **🗄️ DB Schemas Count** - Number of database schemas
- **📊 DB Tables Count** - Number of database tables
- **💾 DB Languages** - List of database languages used (SQL, MongoDB, Redis, etc.)

### 3. **Subgraph Extraction** (New Feature!)

**Location:** "Subgraph Extraction" section on the Knowledge Graph page

**How to use:**
1. Enter an element name (e.g., "UserService", "OrderService")
2. Click "Extract Subgraph"
3. See structured context showing:
   - Direct dependents
   - Transitive dependents
   - Affected APIs
   - Database tables touched
   - Database operations (read/write)
   - Agents involved
   - Workflows involved
   - Related files
   - Impact summary

**Example:**
```
Input: "UserService"
Output:
- Direct Dependents: OrderService, PaymentService
- Affected APIs: /api/users/create, /api/users/update
- Database Tables: users, user_profiles
- Agents Involved: UserAgent
- Workflows Involved: UserOnboardingWorkflow
```

### 4. **API Endpoints**

#### **Get Graph Visualization:**
```
GET /api/graph/{repo_key}/visualize
```
Returns graph with all nodes, edges, and metadata including:
- Entity counts (agents, workflows, database schemas)
- Database languages
- All node categories

#### **Get Subgraph Context:**
```
GET /api/graph/{repo_key}/subgraph/{element_id}?max_depth=3
```
Returns structured `SubgraphContext` object with:
- `target_service` - Name of the target element
- `direct_dependents` - Elements directly depending on target
- `transitive_dependents` - Elements indirectly affected
- `affected_apis` - API endpoints that would be affected
- `database_tables` - Database tables touched
- `database_operations` - Types of DB operations (read/write/query)
- `agents_involved` - Agents that use this element
- `workflows_involved` - Workflows that include this element
- `related_files` - Files that would be affected
- `impact_summary` - Human-readable summary

### 5. **Node Click Details**

Click any node in the graph to see:
- **For Agents:**
  - Agent Type (LLM, RAG, Tool-using)
  - LLM Provider (OpenAI, Groq, etc.)
  - Capabilities list

- **For Workflows:**
  - Workflow Type (sequential, parallel, conditional)
  - Number of steps

- **For Database Schemas:**
  - Database Language (SQL, MongoDB, etc.)
  - ORM Framework (SQLAlchemy, Django ORM, etc.)
  - Table count

- **For Database Tables:**
  - Schema name
  - Column count

### 6. **Edge Click Details**

Click any edge to see:
- Relation type (e.g., "calls", "uses_agent", "queries_database")
- Dependency strength (0.0 to 1.0)

## Visual Legend

### Node Colors:
- 🔴 **Red** - Agents, Database Tables
- 🟢 **Green** - Workflows
- 🟠 **Orange** - Database Schemas, API Endpoints
- 🟣 **Purple** - Classes, Modules
- 🔵 **Blue** - Functions, Methods

### Edge Colors:
- 🔴 **Red** - Inheritance, Uses Agent, Writes to Database
- 🔵 **Blue** - Calls, Reads from Database
- 🟢 **Green** - Triggers Workflow
- 🟠 **Orange** - Queries Database
- ⚪ **Gray** - Imports

## Example Use Cases

### 1. "What happens if I modify UserService?"
1. Go to Subgraph Extraction section
2. Enter "UserService"
3. Click "Extract Subgraph"
4. See all affected components, APIs, databases, agents, and workflows

### 2. "What database languages are used?"
1. Look at the metadata cards at the top
2. See "💾 DB Languages" card showing all detected database technologies

### 3. "How many agents and workflows are in this project?"
1. Look at the metadata cards
2. See "🤖 Agents" and "⚙️ Workflows" counts

### 4. "What does this agent do?"
1. Find the agent node in the graph (red star)
2. Click on it
3. See agent type, LLM provider, and capabilities

### 5. "What are the relations between components?"
1. Look at the edges between nodes
2. Each edge shows a relation label (e.g., "calls", "uses_agent")
3. Click edges to see detailed relation information
