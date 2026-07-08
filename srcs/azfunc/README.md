# Media Studio Workers - Azure Durable Functions

Background job processing functions for the Media Studio application.

## Features

- **Crawler**: Parallel processing for multiple items
- **Translator**: Parallel translation for multiple texts

## Quick Run (Using Central Infrastructure)

This is the **recommended approach** - uses shared infrastructure from `deploy/dockercompose.local.infra.yml`

### Step 1: Setup Workers

```bash
cd ../../srcs/workers
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Run Functions

```bash
func start --slient
```

API available at `http://localhost:7071/api`

## API Endpoints

### Health Check
```bash
curl http://localhost:7071/api/health
```

### Crawler
```bash
curl -X POST http://localhost:7071/api/crawler/start \
  -H "Content-Type: application/json" \
  -d '{"items": ["item1", "item2", "item3"]}'
```

### Translator
```bash
curl -X POST http://localhost:7071/api/translator/start \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Hello", "World"]}'
```

### Check Status
```bash
curl http://localhost:7071/api/status/{instance_id}
```

## Docker Compose for Workers

If using centralized infrastructure, you can also run workers in a container:

```bash
cd srcs/workers
docker-compose up -d
```

This requires the central infrastructure running first (Option 1).

Stop:
```bash
docker-compose down
```

## Project Structure

```
srcs/workers/
├── function_app.py           # Main entry point
├── crawler.py                # Crawler functions
├── translator.py             # Translator functions
├── Dockerfile                # Function app image
├── docker-compose.yml        # Workers compose (uses shared network)
├── requirements.txt          # Minimal dependencies
├── host.json                 # Function configuration
├── local.settings.json       # Local settings
└── README.md                 # This file
```

## Cleanup

### Stop Central Infrastructure
```bash
cd deploy
docker-compose -f dockercompose.local.infra.yml down
```

### Clean Volumes
```bash
docker-compose -f dockercompose.local.infra.yml down -v
```

## Integration Notes

- **Shared Network**: Workers docker-compose uses external network `shared-net` from central infrastructure
- **Storage Connection**: Connects to `toolbox-azurite` from central infrastructure
- **Port 7071**: Functions app runs on default port
- **Durable Task Scheduler**: Dashboard at http://localhost:8082 when using central infrastructure

## Learn More

- [Azure Durable Functions](https://learn.microsoft.com/azure/azure-functions/durable/)
- [Durable Task Scheduler](https://aka.ms/dts-documentation)
- [Azure Functions Python Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
