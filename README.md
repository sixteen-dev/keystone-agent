# Keystone Agent

**AI Board of Directors** - Your synthetic advisory board for solo builders.

A multi-agent CLI tool that evaluates your ideas, decisions, and direction through 7 specialist lenses, then delivers a structured verdict with actionable next steps.

## Architecture

The orchestrator (Keystone) coordinates 7 specialist agents in parallel, aggregates their verdicts, applies consensus rules, and produces a structured final output.

## The Board

| Codename | Role | Lens |
|----------|------|------|
| **Lynx** | Product Operator | User pain, UX, adoption, retention |
| **Wildfire** | Growth & Distribution | Acquisition loops, channels, spread |
| **Bedrock** | Systems & Architecture | Simplicity, stability, cost |
| **Leverage** | Capital Allocator | ROI of time, compounding decisions |
| **Sentinel** | Risk & Reality Check | Blind spots, over-optimism |
| **Prism** | Creative Director | Positioning, narrative, differentiation |
| **Razor** | Product Purist | Focus, simplicity, ruthless cuts |

## Installation

```bash
# Clone the repo
git clone https://github.com/your-org/keystone-agent.git
cd keystone-agent

# Install with uv
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your OpenAI API key
```

## Setup DynamoDB

The agent stores sessions in DynamoDB. Create the table before running:

```bash
# For local development (DynamoDB Local or LocalStack)
docker run -d -p 8000:8000 amazon/dynamodb-local
uv run python scripts/create_dynamodb_tables.py --local

# For AWS (uses your configured credentials)
uv run python scripts/create_dynamodb_tables.py --region us-east-2

# With custom prefix
uv run python scripts/create_dynamodb_tables.py --prefix myapp_
```

## Quick Start

```bash
# Review an idea
uv run board review "I'm building an AI-powered code review tool for small teams"

# Compare two options
uv run board decide --a "Build mobile first" --b "Build web first" --context "Weekend builder, limited time"

# Audit recent work
uv run board audit "Spent last 2 weeks on redesign" --since 14 --project my-saas

# Get creative directions
uv run board creative "How should I position my AI writing tool?"

# View project history
uv run board history --project my-saas

# Rate a past decision
uv run board rate <session-id> --rating correct --notes "Followed advice, got 50 users"
```

## Commands

### `board review`
Validate an idea and find the smallest viable wedge.

```bash
uv run board review "Your idea or question"
uv run board review "Your idea" --project my-project --stage mvp
cat idea.txt | uv run board review  # Pipe from file
```

### `board decide`
Compare two options and get a clear winner.

```bash
uv run board decide --a "Option A" --b "Option B" --context "Decision context"
```

### `board audit`
Detect drift and stop low-leverage work.

```bash
uv run board audit "What I've been working on" --since 14
```

### `board creative`
Generate divergent positioning directions.

```bash
uv run board creative "How should I position my product?"
```

## Output

Every board decision includes:

1. **Final Verdict**: GO / NO_GO / PIVOT / UNCLEAR
2. **Why This Verdict**: Top 3 reasons
3. **Top Risks**: What could go wrong
4. **Key Tradeoffs**: What you're trading off
5. **Next 3 Actions**: Concrete next steps
6. **One Week Plan**: Day-by-day breakdown
7. **Experiment**: Hypothesis + test + success metric
8. **Board Votes**: How each specialist voted
9. **Confidence**: 0-100% confidence level

## Configuration

Environment variables (or `.env` file):

```bash
# Required
KEYSTONE_OPENAI_API_KEY=sk-your-key

# Optional
KEYSTONE_ORCHESTRATOR_MODEL=gpt-5-mini    # Model for orchestrator
KEYSTONE_SPECIALIST_MODEL=gpt-5-nano      # Model for specialists
KEYSTONE_AWS_REGION=us-east-2             # AWS region
KEYSTONE_DYNAMODB_TABLE_PREFIX=keystone_  # Table name prefix
KEYSTONE_DYNAMODB_ENDPOINT_URL=           # Local DynamoDB endpoint (dev only)
KEYSTONE_MAX_RETRIES=1                    # Retries per specialist
KEYSTONE_HISTORY_LIMIT=5                  # Past decisions for context
```

## Storage

Single-table DynamoDB design backing the OpenAI Agents SDK session management.

**Table**: `{prefix}sessions`
- **PK**: `session_id` (UUID)
- **GSI**: `project_id-created_at-index` for history queries

**Attributes**:
- `items` - SDK conversation history
- `mode`, `request_text`, `option_a`, `option_b` - Request metadata
- `final_output` - Board result (nested JSON)
- `rating`, `rating_notes`, `rated_at` - User feedback

## Consensus Rules

The orchestrator applies these rules when synthesizing the final verdict:

1. **No-Go Threshold**: If 2+ specialists vote NO_GO, final cannot be GO
2. **Razor Veto**: If Razor (Product Purist) says CUT/REFRAME, final cannot be GO unless Lynx AND Wildfire both vote GO with 75%+ confidence
3. **Bedrock Pivot**: If Bedrock (Architecture) votes PIVOT, confidence is downgraded unless they provide an MVP path
4. **Creative Feasibility**: In creative mode, Prism's proposals must be validated by Lynx and Wildfire

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=keystone_agent

# Type check
uv run mypy src/keystone_agent

# Lint
uv run ruff check src/keystone_agent
```

## Project Structure

```
keystone-agent/
├── src/keystone_agent/
│   ├── agents/          # Specialist & orchestrator agents
│   ├── core/            # Runner using OpenAI Agents SDK
│   ├── prompts/         # Agent prompt files (*.md)
│   ├── schemas/         # Pydantic models for structured output
│   ├── storage/         # DynamoDB session backend (SessionABC)
│   ├── utils/           # Formatters, background tasks
│   └── cli.py           # Typer CLI
├── scripts/
│   └── create_dynamodb_tables.py  # Table setup script
├── tests/
├── docs/
│   └── PHILOSOPHY.md    # Your company philosophy
├── LICENSE
└── pyproject.toml
```

## Customization

### Company Philosophy
Edit `docs/PHILOSOPHY.md` with your own principles. This gets injected into every agent prompt.

### Adding Specialists
1. Create a new prompt in `src/keystone_agent/prompts/`
2. Add config to `agents/specialists.py`
3. Update the orchestrator prompt

## License

[MIT](LICENSE)
