# SDKs

This repo ships minimal JS and Python SDKs alongside API docs.

- JavaScript/TypeScript: `sdk/js`
- Python: `sdk/python`

Each SDK is typed, has a small surface area, and exposes the same endpoints.

## JavaScript

```bash
npm install @portpulse/client
# or
pnpm add @portpulse/client
```

```ts
import { PortPulse } from "@portpulse/client";

const client = new PortPulse({ apiKey: process.env.PORTPULSE_API_KEY });
const trend = await client.getTrend("USLAX", { window: 30 });
console.log(trend.points.length);
```

## Python

```bash
pip install portpulse
```

```python
from portpulse import PortPulse

client = PortPulse(api_key=os.environ["PORTPULSE_API_KEY"])
snap = client.get_snapshot("USLAX")
print(snap["waiting_vessels"])
```
