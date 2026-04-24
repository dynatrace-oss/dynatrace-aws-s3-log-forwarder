# JSON Streaming Library Migration: ijson → json-stream

## What Changed and Why

The Lambda function previously used `ijson` with the `yajl2_c` C backend to stream large JSON log files from S3 without loading them fully into memory. This required bundling `libyajl.so.2` — a native C shared library — into every deployment artifact and setting `LD_LIBRARY_PATH=/var/task/lib` at runtime so the Lambda process could find it.

`ijson` has been replaced with [`json-stream`](https://github.com/daggaz/json-stream) using the `json-stream-rs-tokenizer` Rust backend. The Rust extension ships as a self-contained manylinux wheel; no system library needs to be installed or manually bundled.

The streaming guarantee is unchanged: both libraries iterate entries one at a time without loading the full file into memory.

---

## Performance

Benchmarks were run on the development host (macOS, Python 3.14) comparing `ijson yajl2_c` (old) against the new implementation for each log format. Results on the Lambda runtime (Amazon Linux 2023, x86\_64) may differ, but are expected to follow the same relative trend because both the yajl C library and the Rust tokenizer wheel are compiled for x86\_64.

### Nested JSON array (`log_format: json`, e.g. CloudTrail, WAF, Network Firewall)

Entries are streamed from a single large JSON document with an array nested under a key (e.g. `Records`).

| Entries | File size | ijson yajl2\_c — time | json-stream Rust — time | Relative | ijson peak mem | json-stream peak mem |
|--------:|----------:|----------------------:|------------------------:|---------:|---------------:|---------------------:|
| 1,000 | 341 KB | 5.9 ms | 16.8 ms | ×0.35 | 274 KB | 6 KB |
| 10,000 | 3.4 MB | 42.7 ms | 168.3 ms | ×0.25 | 274 KB | 6 KB |
| 50,000 | 17.2 MB | 213.5 ms | 870.3 ms | ×0.25 | 274 KB | 6 KB |

**Throughput**: json-stream Rust processes nested JSON arrays at roughly **25–35% of ijson yajl2\_c's throughput** — approximately 4× slower. For a typical CloudTrail delivery file (10,000 records, ~3.4 MB) the wall-clock difference is ~125 ms per file.

**Memory**: json-stream Rust holds a **constant ~6 KB** regardless of file size. ijson yajl2\_c holds a constant ~274 KB (internal yajl parse buffers), also independent of file size. Both are well within Lambda's memory budget; neither grows with file size.

### NDJSON stream (`log_format: json_stream`, e.g. WAF, VPC DNS, AppFabric)

Each line is a self-contained JSON object. The new implementation uses stdlib `json.loads()` per line instead of ijson's streaming `multiple_values` mode.

| Entries | File size | ijson yajl2\_c — time | json.loads per line — time | Relative |
|--------:|----------:|----------------------:|---------------------------:|---------:|
| 1,000 | 276 KB | 2.6 ms | 3.3 ms | ×0.79 |
| 10,000 | 2.8 MB | 26.0 ms | 34.2 ms | ×0.76 |
| 50,000 | 14.0 MB | 130.1 ms | 161.4 ms | ×0.81 |

**Throughput**: ~20–25% slower than ijson yajl2\_c. The difference is small in absolute terms (e.g. ~31 ms for 10,000 entries).

### Practical Lambda impact

The Lambda function is configured with a maximum execution time (default 5 minutes) and processes SQS message batches. Each SQS message corresponds to one S3 object. Worst-case realistic log files are in the low-MB range for most AWS services.

At 4× slower throughput for the `json` format, a file that previously took 200 ms to parse will now take ~800 ms. Given typical batch sizes and the Lambda timeout, this is within budget for all but the most extreme file sizes. If extremely large files (hundreds of MB) are expected, the throughput regression warrants load testing before rollout.

The NDJSON regression (~25%) is unlikely to be observable in practice.

### Rust tokenizer availability guarantee

`json-stream` silently falls back to a pure-Python tokenizer if the Rust extension is unavailable, emitting only an `ImportWarning` that Python ignores by default. Running on the Python fallback would make the `json` format ~16× slower than ijson yajl2\_c (based on benchmarks) with no visible error.

To prevent silent degradation, `processing.py` performs a fail-fast check at module import time (Lambda cold start):

```python
try:
    rust_tokenizer_or_raise()
except ExtensionException as exc:
    raise RuntimeError(
        "json-stream Rust tokenizer (json-stream-rs-tokenizer) is not available. ..."
    ) from exc
```

If the Rust wheel is missing or incompatible, the Lambda function will fail on every invocation from cold start, surfacing the problem immediately rather than processing logs slowly and silently.

### Summary

| | Throughput vs ijson yajl2\_c | Peak memory |
|-|------------------------------|-------------|
| `json` format (json-stream Rust) | **~4× slower** | **45× lower** (274 KB → 6 KB) |
| `json_stream` format (json.loads) | **~25% slower** | **144× lower** (288 KB → 2 KB) |

The trade-off is a meaningful throughput reduction in exchange for near-zero parser memory overhead and elimination of a bundled native C library from the deployment artifact.

---

## Is This a Breaking Change?

**No, from an operator or integrator perspective.** The change is internal to the Lambda function. Log output, configuration format, AWS infrastructure, and deployment procedures are all unchanged.

### Detailed Assessment

| Concern | Verdict | Detail |
|---------|---------|--------|
| Log processing output | **No change** | All JSON formats (`json`, `json_stream`) produce identical parsed entries. Streaming is preserved for nested paths (e.g. CloudTrail `Records`, Network Firewall events). |
| Configuration files | **No change** | `log-forwarding-rules.yaml` and `log-processing-rules.yaml` formats are untouched. |
| Dynatrace environment variables | **No change** | `DYNATRACE_N_ENV_URL`, `DYNATRACE_N_API_KEY_PARAM`, etc. are unaffected. |
| `IJSON_BACKEND` env var | **Silently ignored** | Operators who manually set this variable on the Lambda function will find it has no effect after the update. It will not cause an error. It can be removed from the function configuration. |
| `LD_LIBRARY_PATH` env var | **Removed from template** | The SAM template no longer injects this variable for ZIP deployments. Any stack update will drop it. If an operator had set it manually it becomes a harmless no-op, since `lib/` in the deployment package is now empty. |
| AWS infrastructure | **No change** | Same Lambda, SQS queue, EventBridge rules, AppConfig, SSM. No CloudFormation resource additions or deletions. |
| Lambda runtime / architecture | **No change** | Python 3.14, x86\_64. |

---

## Deployment Update Path

Both deployment modes are fully supported and updated in the same way as before.

### Layer mode (default)

1. Build the new layer artifact:

   ```bash
   ./scripts/build_docker.sh layer build/lambda-layer.zip
   ```

2. Publish the layer to AWS and obtain the new Layer Version ARN.
3. Update the CloudFormation/SAM stack, passing the new ARN as `DynatraceS3LogForwarderLayerArn`.

The stack update replaces the layer reference on the Lambda function and performs a zero-downtime configuration update (Lambda continues serving in-flight events from the previous version until the update completes).

### ZIP mode

1. Build the new ZIP artifact:

   ```bash
   ./scripts/build_docker.sh zip build/lambda.zip
   ```

2. Upload the ZIP to the Lambda function (via `aws lambda update-function-code` or your CI/CD pipeline).
3. If doing a full stack update, the CloudFormation template no longer sets `LD_LIBRARY_PATH` — this is applied atomically during the stack update with no downtime impact.

### Rollback

Rolling back to the previous version follows the same path: redeploy the previous Layer ARN (layer mode) or re-upload the previous ZIP (ZIP mode). There are no database migrations, schema changes, or persistent state involved.

---

## Build Pipeline Changes

The Docker build no longer installs `yajl` via `dnf` and no longer copies `libyajl.so.2` into the artifact. `json-stream-rs-tokenizer` ships a pre-built `manylinux_2_28_x86_64` wheel for Python 3.14, so `pip install` inside the Amazon Linux 2023 container resolves it from PyPI without requiring a Rust toolchain at build time.

This simplifies the build: fewer OS-level dependencies, no manual native library handling, and the artifact is slightly smaller (no `lib/libyajl.so.2`).
