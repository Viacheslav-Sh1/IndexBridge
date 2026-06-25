[English](README.md) | [Russian](README.ru.md)

# IndexBridge

A universal torrent indexer aggregator that acts as a middleware layer for Jackett, Prowlarr, and Jacred.

It combines results from Jackett, Prowlarr, and Jacred, providing a single API with filtering, deduplication, and metadata normalization.

> [!NOTE]
> IndexBridge does not replace Jackett, Prowlarr, or Jacred.
>
> It acts as a middleware layer, combining multiple sources, filtering, deduplicating, and normalizing results before serving them through a single API.

```text
Jackett ─┐
Prowlarr ├──► IndexBridge ───► Client
Jacred ──┘
```
## Why use IndexBridge?

If you use multiple indexers, they may return results in different formats, duplicate releases, and provide inconsistent metadata. IndexBridge normalizes everything, removes duplicates, and delivers clean, filtered results in a single request using the Jacred format.

Additionally, instead of exposing multiple services externally, you can keep them accessible only within your local network and provide external access through a single IndexBridge instance.

```text
                Internet
                    │
                    ▼
          ┌──────────────────┐
          │   IndexBridge    │
          │ (single API key) │
          └──────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │Local Area Network│
          ├──────────────────┤
          │ Jackett #1       │
          │ Jackett #2       │
          │ Prowlarr #1      │
          │ Prowlarr #2      │
          │ Jacred #1        │
          │ Jacred #2        │
          └──────────────────┘
```
**What this gives:**

- **One open port** instead of several
- **One external API key** — Jackett, Prowlarr, and Jacred API keys never leave the local network.
- **Hidden infrastructure** — internal addresses and keys are not visible to external clients.
- **Centralized filtering** — uniform rules for all sources.
- **Deduplication between providers** — eliminates duplicates before they reach the client.
- **Change providers without reconfiguring clients** — you can add or remove a source, but the external URL remains the same.

**To the client, IndexBridge appears as a regular Jackett-compatible server:**

**Performance:** All providers are queried in parallel. Response time is typically determined by the slowest provider that successfully responded and the PROVIDER_TIMEOUT setting.

## Examples

### Jackett via IndexBridge

Same client (Lampa), same torrents, and the same source.
IndexBridge supplements Jackett results with metadata extracted from release titles and returns them in Jacred format.

Additional metadata becomes available:

- Audio languages
- Subtitle languages
- Video resolution
- Audio information
- Extra metadata for the client

IndexBridge does not replace Jackett and does not modify the releases themselves. It only supplements the results with metadata extracted from the release title.  
The screenshots below were taken in the Lampa client and show the actual results of IndexBridge.  


![Jackett via IndexBridge](docs/images/jackett-vs-indexbridge.webp)

---

### Combined results from multiple sources

IndexBridge can simultaneously aggregate Jackett, Prowlarr, and Jacred.

- Results are combined;
- Filtering is performed;
- Most duplicates are removed automatically;
- Jacred metadata is preserved unchanged;
- For Jackett and Prowlarr results, missing data is extracted from the headers.  


![Combined output from multiple sources](docs/images/multi-provider.webp)

> Deduplication does not guarantee the complete removal of all duplicates. If different sources return inconsistent or incomplete identifiers, identical releases may appear in the final output.
>
> This is a deliberate tradeoff: it's better to have multiple working versions of a single release than to accidentally lose the only available release.

## Features

- **Multiple-source aggregation** — Jackett, Prowlarr, Jacred (unlimited number)
- **Parallel queries** — all providers are queried simultaneously via `asyncio.gather()`
- **Configurable timeout** — slow providers are dropped due to a timeout, while fast ones continue to work
- **Circuit breaker** — after several consecutive errors, a provider is temporarily excluded from polling
- **RSS cache** — empty queries (without a search query) are cached to avoid pinging providers every 30 seconds
- **Provider priority** — when duplicates are found, results from higher-priority providers are preferred
- **No cascading failures** — one failed provider does not affect the others
- **Flexible access to providers** — you can get either a combined result (`/all`) or a result from a specific provider (`/name`)
- **Title parsing** — For Jackett and Prowlarr, metadata is extracted from the release title (languages, audio, quality, codecs, seasons, episodes)
- **Format auto-detection** — if the source already returns data in Jacred format (`ffprobe`, `languages`, `info`), metadata is used as-is without re-parsing.
- **Deduplication** — by BTIH hash, details link, or name+size
- **Advanced filtering** — seeders, peers, quality, languages, audio, keywords
- **Combined endpoint** — `/all` returns deduplicated results from all sources
- **Jacred output** — all results are returned in Jacred format (with `ffprobe`, `languages`, `info` fields)
- **Rate limiting** — per-IP request limits with automatic cleanup
- **Security** — API key, hidden service endpoints, security headers
- **Docker** — single container, easy installation

## Supported sources

- Jackett
- Prowlarr
- Jacred
- Multiple instances of the same type
- Mixed configurations

## Architecture
```text
Jackett #1 ─┐
Jackett #2 ─┤
Prowlarr ───┼──► IndexBridge ──► /name
Jacred #1 ──┤                 └► /all
Jacred #2 ──┘
```
All providers are queried in parallel, the results are merged, filtered, and deduplicated.

### Source Processing

- Jackett / Prowlarr — metadata is extracted from release titles.
- Jacred — existing metadata is used without re-parsing.

## Deduplication

Results from all providers are combined and checked for duplicates at three levels (in order of priority):

1. **BTIH hash** — the torrent hash is extracted from the Magnet link. This is the most reliable method.
2. **Details** — the release page URL. Used when no magnet link is available.
3. **Title + Size** — a fallback option if neither the hash nor the link are available.

If a duplicate is found, the selection is based on one of two rules:

- **With provider priority** — if `PROVIDER_PRIORITY` is set, the result from the provider with the highest priority (first in the list) is retained
- **Without priority** — the release with the largest number of seeders is retained (default behavior)

### Deduplication Limitations

If different providers return incomplete or inconsistent identifiers, some duplicate releases may still remain in the results.  
This is expected behavior. Preference is given to preserving available releases rather than aggressively removing potential duplicates.  
If there are too many duplicates, you can:  
- Disable `PROVIDER_PRIORITY`;
- use only one source for a specific tracker;
- create an issue with examples.

## Fault Tolerance and Performance

### RSS Cache

Empty queries (without the `Query` parameter) are cached for a specified time.

This is standard behavior for Jackett/Prowlarr—an RSS feed of updates that clients poll every 30 seconds.

Without the cache, IndexBridge would trigger all providers with each such request.
```env
RSS_CACHE_TTL=300 # cache timeout in seconds (default 300 = 5 minutes)
```
During this time, all empty queries receive a cached response. Search queries (with `Query`) are not cached.

### Circuit Breaker
After several consecutive errors or timeouts, the provider is temporarily excluded from polling.

This prevents freezing: the problematic provider does not slow down queries to other providers.

```env
CB_MAX_FAILS=3 # number of consecutive errors to disconnect (default 3)
CB_TIMEOUT=300 # disconnection time in seconds (default 300 = 5 minutes)
```
How it works:  
The provider responds with an error or fails to meet the PROVIDER_TIMEOUT limit.  
After CB_MAX_FAILS consecutive errors, the provider is temporarily excluded from polling for CB_TIMEOUT seconds.  

The following entry appears in the logs:  
WARNING: [jac] circuit breaker OPEN for 300s  
After the time expires, the provider is queried again.  

### Provider Priority  
The order in which providers are preferred during deduplication.  
The first in the list has the highest priority.  

```env
PROVIDER_PRIORITY=jac,jred,pr # jac > jred > pr
```

If a duplicate is found, the result from the provider with the highest priority is retained.  
If no priority is specified, the priority is based on the number of seeders.  

Example:  
The same release was found on two providers:  

| Provider | Seeders |
|-----|----|
| jred | 25 |
| jac | 5 |

No priority: jred will remain (25 seeders > 5)

With jac,jred priority: jac will remain (it's first in the list, and we trust it more)

Priority is useful when:
- You want to prefer a trusted source.
- Jacred reports outdated seeder counts, so you can place it lower in the list and keep fresher data from Jackett or Prowlarr.

**How many providers can be configured?**  
Technically, there is no limit imposed by `NAMES`.  

Performance characteristics:

| Providers | Status | Recommendation |
|-------------|-----------|---------------|
| 1-5 | ✅ Ideal | Default settings are sufficient |
| 5-15 | ✅ Good | Increase `PROVIDER_TIMEOUT` to 20-30 sec |
| 15-30 | ⚠️ Possible delays | Increase timeout (not yet tested) |
| 30+ | ⚠️ Experimental | CPU and memory requirements have not been tested |

Response time is approximately equal to the response time of the slowest provider plus processing overhead (~100-200ms).  
Response time is not equal to the sum of the response times of all sources.  

Example with 5 providers (each ~1 second):  
Sequential requests: ~5 seconds  
IndexBridge (parallel): ~1 second  

## Quick Start

### 1. Copy the configuration template
```bash
cp .env.example .env
```
### 2. Edit the settings
```bash
nano .env
```
**Important**:
- Replace all values ​​with your own  
- Remove lines for providers you don't have  
- Provider names in NAMES must match the names in the `JACKETT_{name}_URL` / `PROWLARR_{name}_URL` variables  
- If NAMES specifies a provider for which there is no URL and API_KEY, IndexBridge will start, but that provider will be skipped.  

`PROXY_API_KEY=your-secret-key`  
`NAMES=jred,jac,pr`  
`JACKETT_jred_URL=https://remote.example.com`  
`JACKETT_jred_API_KEY=jred-key`  
`JACKETT_jac_URL=http://jackett:9117`  
`JACKETT_jac_API_KEY=abc123`  
`PROWLARR_pr_URL=http://prowlarr:9696`  
`PROWLARR_pr_API_KEY=def456`  

### 3. Build and run the container
**Option 1 - Docker**
```bash
docker build -t indexbridge .
docker run -d --name indexbridge --env-file .env -p 8000:8000 indexbridge
```
**Option 2 - Docker Compose**
```bash
docker-compose up -d --build
```
### docker-compose.yml
```yaml
version: '3.8'

services:
  indexbridge:
    build: .
    image: indexbridge:latest
    container_name: indexbridge
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - LOG_LEVEL=INFO
      - PROXY_API_KEY=${PROXY_API_KEY}
      - TZ=Europe/Kyiv
      - PORT=8000
      - COMBINED_NAME=all
      - NAMES=${NAMES}
      # Specify your providers, remove unused ones 
      # - PROVIDER_PRIORITY=jac,pr
      - JACKETT_jac_URL=${JACKETT_jac_URL}
      - JACKETT_jac_API_KEY=${JACKETT_jac_API_KEY}
      - PROWLARR_pr_URL=${PROWLARR_pr_URL}
      - PROWLARR_pr_API_KEY=${PROWLARR_pr_API_KEY}
      - RATE_LIMIT_ENABLED=true
      - RATE_LIMIT_REQUESTS=60
      - RATE_LIMIT_WINDOW=60
      - FILTER_MIN_SEEDERS=1
      - PROVIDER_TIMEOUT=15
      - RSS_CACHE_TTL=300
      - CB_MAX_FAILS=3
      - CB_TIMEOUT=300
```

**Important**: Remove the provider lines you don't use from the environment variable. `JACKETT_{name}_URL` and `JACKETT_{name}_API_KEY` (or `PROWLARR_{name}_URL` and `PROWLARR_{name}_API_KEY`) must be defined for each provider in NAMES.

### 4. Verification

**Individual Provider**
```bash
curl "http://localhost:8000/jac?apikey=your-secret-key&Query=Foundation"
```

**All Providers Together**
```bash
curl "http://localhost:8000/all?apikey=your-secret-key&Query=Foundation"
```

**Torznab-compatible path (without provider name)**  
```bash
curl "http://localhost:8000/api/v2.0/indexers/all/results?apikey=your-secret-key&Query=Foundation"
```

API Endpoints:

| Endpoint | Description |
|------------|-------------|
| /{name} | Results from a single provider |
| /{name}/api/v2.0/indexers/all/results | Jackett-compatible path |
|/api/v2.0/indexers/all/results | Torznab without a name (combined) |
| /{COMBINED_NAME} | Combined results from all providers (default: /all) |

## Authorization

All requests require an API key:  
**Query parameter**  
?apikey=your-key  

**Header**  
X-API-Key: your-key  
An invalid or missing key returns a 404 Not Found.  

## Configuration

### Required Variables

| Variable | Description |
|----|----|
| PROXY_API_KEY | API key for authorization |
| NAMES | Provider names separated by commas |

### Configuring Providers

**Jackett (including Jacred as a Jackett-compatible server)**  
`JACKETT_{name}_URL=http://host:9117`  
`JACKETT_{name}_API_KEY=key`  

**Prowlarr**  
`PROWLARR_{name}_URL=http://host:9696`  
`PROWLARR_{name}_API_KEY=key`  

**Important**: Jacred connects as a regular Jackett provider.  
IndexBridge will automatically detect that the response is already in Jacred format and will not re-parse the headers.  

You can add as many providers as you like. All are queried in parallel.  

Example with 6 Providers:  

```env
NAMES=jac1,jac2,jac3,pr1,pr2,jred1

JACKETT_jac1_URL=http://10.0.0.1:9117
JACKETT_jac1_API_KEY=key-jac1

JACKETT_jac2_URL=http://10.0.0.2:9117
JACKETT_jac2_API_KEY=key-jac2

JACKETT_jac3_URL=http://10.0.0.3:9117
JACKETT_jac3_API_KEY=jac3-key

PROWLARR_pr1_URL=http://10.0.0.3:9696
PROWLARR_pr1_API_KEY=pr1-key

PROWLARR_pr2_URL=http://10.0.0.4:9696
PROWLARR_pr2_API_KEY=pr2-key

JACKETT_jred1_URL=https://remote.example.com
JACKETT_jred1_API_KEY=jred1-key
```

### Performance

| Variable | Default | Description |
|------------|-------------|-----------|
| PROVIDER_TIMEOUT | 15 | Maximum provider timeout (sec) |
| RSS_CACHE_TTL | 300 | Empty Request Cache TTL (sec) |
| CB_MAX_FAILS | 3 | Errors in a row before provider disconnection |
| CB_TIMEOUT | 300 | Provider disconnection time (sec) |
| PROVIDER_PRIORITY | — | Provider priority for deduplication: jac, jred, pr |

How to change:  
In .env:  
```env
PROVIDER_TIMEOUT=30
RSS_CACHE_TTL=600
CB_MAX_FAILS=5
CB_TIMEOUT=600
PROVIDER_PRIORITY=jac,jred,pr
```
Or in docker-compose.yml:  
```yml
environment:
- PROVIDER_TIMEOUT=30
- RSS_CACHE_TTL=600
- CB_MAX_FAILS=5
- CB_TIMEOUT=600
- PROVIDER_PRIORITY=jac,jred,pr
```
After changing the settings, restart the container.  

**Recommendations:**  
Local providers: PROVIDER_TIMEOUT=10-15, remote: 15-30  
RSS_CACHE_TTL no less than the RSS client polling interval (usually 300)  
CB_MAX_FAILS=3 and CB_TIMEOUT=300 — good default values  
PROVIDER_PRIORITY — list the most trusted source first  
Reduce PROVIDER_TIMEOUT if you prefer fast partial results instead of waiting for everything  

### Additional Options

| Variable | Default | Description |
|------------|-------------|-----------|
| COMBINED_NAME | all | Combined endpoint name (e.g., combined → /combined) |
| PORT | 8000 | Server port |
| LOG_LEVEL | INFO | Log level: DEBUG, INFO, WARNING, ERROR |

### Filtering

| Variable | Default | Description |
|------------|--------------|------------|
| FILTER_MIN_SEEDERS | 1 | Minimum number of seeders |
| FILTER_MAX_SEEDERS | 0 | Maximum number of seeders (0 = unlimited) |
| FILTER_MIN_PEERS | 0 | Minimum number of peers |
| FILTER_LANGUAGES | — | Prohibited languages: rus, ukr, eng (empty = all allowed) |
| FILTER_VOICES | — | Prohibited voiceover studios (empty = all allowed) |
| FILTER_BLACKLIST_TITLES | — | Prohibited words in title |
| FILTER_QUALITY_MIN | 0 | Minimum quality |
| FILTER_QUALITY_MAX | 9999 | Maximum quality |

### Rate Limiting

| Variable | Default | Description |
|------------|-------------|-----------|
| RATE_LIMIT_ENABLED | true | Enable rate limiting |
| RATE_LIMIT_REQUESTS | 60 | Requests per window |
| RATE_LIMIT_WINDOW | 60 | Window in seconds |

### Security

- API key required for all requests  
- Per-IP rate limiting  
- Swagger/OpenAPI disabled  
- Server header hidden  
- Security headers: X-Content-Type-Options, X-Frame-Options, Cache-Control: no-store  
- `hmac.compare_digest` for secure key comparison  

## Integration with other applications  
As a Jackett indexer  
Add as Torznab:  
URL: http://indexbridge:8000/all — for aggregated results  
URL: http://indexbridge:8000/name — for a specific provider  
API Key: your PROXY_API_KEY  

As a Prowlarr indexer  
Add as a Custom Torznab:  
URL: http://indexbridge:8000/all — for aggregated results  
URL: http://indexbridge:8000/name — for a specific provider  
API Key: your PROXY_API_KEY  

As a Torznab indexer (for Sonarr, Radarr, Lidarr):  
URL: http://indexbridge:8000/api/v2.0/indexers/all/results — for aggregated results  
API Key: your PROXY_API_KEY  

### Typical Scenarios  
- Multiple Jackett instances → one IndexBridge → client  
- Multiple Prowlarr instances → one IndexBridge → client  
- Multiple Jacred instances → one IndexBridge → client  
- Mixed sources via a single API  
- A single external entry point instead of exposing multiple services  
- Unified filtering and deduplication  
- A single API endpoint for multiple indexers  

> [!IMPORTANT]
> IndexBridge does not replace Jackett, Prowlarr, or Jacred.  
>
> It does not perform indexing and does not search for releases on its own.  
>
> IndexBridge acts as a middleware layer between indexers and clients, providing aggregation, filtering, deduplication, and metadata normalization.

## License

MIT License (c) 2026 Viacheslav-Sh1
