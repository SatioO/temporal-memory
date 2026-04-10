from typing import Dict, List, Set

from query.stemmer import stem


SYNONYM_GROUPS: List[List[str]] = [
    # --- Auth & Identity ---
    ["auth", "authentication", "authn", "authenticating"],
    ["authz", "authorization", "authorizing", "rbac", "permissions", "acl"],
    ["jwt", "token", "access-token", "bearer", "session-token"],
    ["oauth", "oauth2", "oidc", "sso", "saml", "identity-provider", "idp"],
    ["password", "credential", "credentials", "secret", "passphrase"],
    ["api-key", "apikey", "service-account", "service-token"],
    ["signup", "register", "registration", "onboarding"],
    ["login", "signin", "sign-in", "log-in"],

    # --- Database & Storage ---
    ["db", "database", "datastore", "data-store"],
    ["pg", "postgres", "postgresql"],
    ["mysql", "mariadb"],
    ["mongo", "mongodb", "document-store", "document-db"],
    ["redis", "memcached", "keyvalue", "key-value-store"],
    ["sqlite", "embedded-db"],
    ["dynamo", "dynamodb", "nosql", "no-sql"],
    ["elastic", "elasticsearch", "opensearch", "search-engine"],
    ["cassandra", "scylladb", "wide-column"],
    ["orm", "object-relational-mapper", "prisma", "sqlalchemy",
        "typeorm", "sequelize", "drizzle", "mongoose"],
    ["query", "sql", "cypher", "gql"],
    ["schema", "model", "entity", "table", "collection"],
    ["index", "indices", "indexes"],
    ["transaction", "tx", "atomic", "acid"],
    ["migration", "migrations", "migrate", "schema-change"],
    ["seed", "seeding", "fixture", "fixtures"],
    ["replication", "replica", "read-replica", "failover"],
    ["sharding", "shard", "partition", "partitioning"],
    ["backup", "snapshot", "restore", "point-in-time-recovery"],
    ["connection-pool", "pool", "pooling", "pgpool", "pgbouncer"],
    ["s3", "blob", "object-storage", "gcs", "azure-blob", "bucket"],

    # --- Messaging & Queues ---
    ["msg", "message", "messaging"],
    ["queue", "job-queue", "task-queue", "worker-queue"],
    ["kafka", "kinesis", "pubsub", "pub-sub", "event-stream", "message-bus"],
    ["rabbitmq", "sqs", "amqp", "broker", "message-broker"],
    ["worker", "consumer", "job", "background-job", "task"],
    ["producer", "publisher", "emitter"],
    ["event", "events", "event-driven", "event-sourcing"],
    ["webhook", "webhooks", "callback"],
    ["sse", "server-sent-events", "streaming"],
    ["websocket", "ws", "realtime", "real-time", "socket"],
    ["grpc", "protobuf", "proto", "rpc", "thrift"],

    # --- API & Networking ---
    ["api", "endpoint", "endpoints", "route", "routes"],
    ["rest", "restful", "http-api"],
    ["graphql", "gql"],
    ["req", "request", "http-request"],
    ["res", "response", "http-response"],
    ["middleware", "mw", "interceptor", "handler"],
    ["router", "routing", "routes"],
    ["cors", "cross-origin"],
    ["proxy", "reverse-proxy", "gateway",
        "api-gateway", "nginx", "traefik", "envoy"],
    ["rate-limit", "throttle", "throttling", "backpressure", "ratelimit"],
    ["dns", "domain", "hostname", "subdomain"],
    ["tls", "ssl", "https", "mtls", "certificate", "cert"],
    ["http", "http2", "http3"],
    ["cdn", "edge", "cloudfront", "fastly"],
    ["timeout", "deadline", "ttl"],
    ["retry", "backoff", "exponential-backoff", "circuit-breaker"],
    ["pagination", "paginate", "cursor", "offset", "page"],

    # --- Frontend & UI ---
    ["react", "reactjs", "jsx", "tsx"],
    ["vue", "vuejs", "nuxt"],
    ["angular", "angularjs", "ng"],
    ["next", "nextjs", "next.js"],
    ["svelte", "sveltekit"],
    ["component", "widget", "ui-component"],
    ["state", "state-management", "store", "redux", "zustand", "pinia", "recoil"],
    ["hook", "hooks", "use-effect", "use-state", "lifecycle"],
    ["hydration", "ssr", "ssg", "csr",
        "server-side-rendering", "static-site-generation"],
    ["bundle", "bundler", "webpack", "vite",
        "esbuild", "rollup", "parcel", "turbopack"],
    ["css", "styles", "styling", "sass", "scss", "tailwind"],
    ["dom", "virtual-dom", "shadow-dom"],

    # --- Languages & Runtimes ---
    ["ts", "typescript"],
    ["js", "javascript"],
    ["py", "python"],
    ["go", "golang"],
    ["rs", "rust"],
    ["rb", "ruby"],
    ["java", "jvm", "kotlin"],
    ["cs", "csharp", "dotnet", ".net"],
    ["node", "nodejs", "node.js", "deno", "bun"],
    ["wasm", "webassembly"],

    # --- Infrastructure & Cloud ---
    ["k8s", "kubernetes", "kube"],
    ["docker", "container", "containerization",
        "dockerfile", "compose", "docker-compose"],
    ["helm", "chart", "helm-chart"],
    ["terraform", "tf", "iac", "infrastructure-as-code", "pulumi", "cdk"],
    ["ansible", "chef", "puppet", "salt"],
    ["aws", "amazon", "ec2", "ecs", "eks", "fargate"],
    ["gcp", "gke", "google-cloud", "cloud-run"],
    ["azure", "aks"],
    ["serverless", "lambda", "cloud-function", "faas", "function-as-a-service"],
    ["vm", "virtual-machine", "vps"],
    ["infra", "infrastructure"],
    ["deploy", "deployment", "deploying", "release", "rollout", "ship"],
    ["ci", "continuous-integration"],
    ["cd", "continuous-deployment", "continuous-delivery"],
    ["pipeline", "workflow", "action", "github-actions", "jenkins", "gitlab-ci"],
    ["registry", "artifact", "ecr", "docker-hub", "ghcr"],
    ["namespace", "env", "environment"],
    ["secret", "secrets-manager", "vault", "parameter-store", "ssm"],
    ["ingress", "load-balancer", "alb", "nlb", "elb"],
    ["autoscaling", "hpa", "scaling", "scale-out", "scale-in"],

    # --- Observability ---
    ["log", "logging", "logs"],
    ["monitor", "monitoring"],
    ["observe", "observability"],
    ["trace", "tracing", "distributed-tracing",
        "jaeger", "zipkin", "opentelemetry", "otel"],
    ["metric", "metrics", "prometheus", "statsd", "cloudwatch", "datadog"],
    ["alert", "alerting", "pagerduty", "oncall", "on-call", "incident"],
    ["dashboard", "grafana", "kibana"],
    ["slo", "sla", "sli", "uptime", "availability", "error-budget"],
    ["profil", "profiling", "flamegraph", "pprof"],

    # --- Performance ---
    ["perf", "performance", "latency", "throughput", "slow", "bottleneck"],
    ["optim", "optimization", "optimizing", "optimise", "query-optimization"],
    ["cache", "caching", "cached", "memoize", "memoization"],
    ["bench", "benchmark", "benchmarking", "load-test", "stress-test"],
    ["gc", "garbage-collection", "memory-leak", "oom", "out-of-memory"],
    ["cpu", "compute", "cpu-bound"],
    ["io", "i/o", "io-bound", "disk", "network-io"],

    # --- Security ---
    ["sec", "security", "secure"],
    ["xss", "cross-site-scripting"],
    ["csrf", "cross-site-request-forgery"],
    ["sqli", "sql-injection", "injection"],
    ["vuln", "vulnerability", "cve", "patch", "advisory"],
    ["encrypt", "encryption", "aes", "rsa"],
    ["hash", "hashing", "bcrypt", "argon2", "sha"],
    ["sanitize", "sanitization", "escape", "encode"],
    ["firewall", "waf", "network-policy"],
    ["audit", "audit-log", "compliance", "gdpr", "pci", "hipaa", "soc2"],

    # --- Dev Workflow ---
    ["repo", "repository"],
    ["pr", "pull-request", "code-review", "review", "merge-request", "mr"],
    ["branch", "git-branch", "feature-branch"],
    ["merge", "rebase", "cherry-pick"],
    ["commit", "patch", "diff", "changeset"],
    ["tag", "semver", "version", "release-tag", "changelog"],
    ["lint", "linting", "linter", "eslint", "ruff", "flake8", "golangci"],
    ["format", "formatter", "prettier", "black", "gofmt", "rustfmt"],
    ["deps", "dependencies", "dependency", "packages", "modules"],
    ["lock", "lockfile", "package-lock", "yarn-lock", "uv-lock", "cargo-lock"],
    ["monorepo", "workspace", "turborepo", "nx"],

    # --- Testing ---
    ["test", "testing", "tests"],
    ["unit", "unit-test", "unit-tests"],
    ["integration", "integration-test", "integration-tests"],
    ["e2e", "end-to-end", "playwright", "cypress", "selenium"],
    ["mock", "mocking", "stub", "fake", "spy"],
    ["fixture", "test-data", "factory"],
    ["coverage", "code-coverage", "lcov"],
    ["regression", "regression-test"],
    ["tdd", "bdd", "test-driven"],

    # --- Architecture & Patterns ---
    ["microservice", "microservices", "service", "soa"],
    ["monolith", "modular-monolith"],
    ["cqrs", "event-sourcing", "saga"],
    ["singleton", "factory", "observer", "decorator",
        "strategy", "repository-pattern"],
    ["di", "dependency-injection", "ioc", "inversion-of-control"],
    ["config", "configuration", "configuring", "setup", "settings"],
    ["fn", "function"],
    ["impl", "implementation", "implementing"],
    ["interface", "contract", "protocol", "trait", "abstract"],
    ["type", "types", "generics", "template"],
    ["async", "asynchronous", "concurrent", "concurrency", "parallel"],
    ["sync", "synchronous", "blocking"],
    ["thread", "goroutine", "coroutine", "fiber", "green-thread"],
    ["mutex", "lock", "semaphore", "race-condition", "deadlock"],
    ["queue", "stack", "buffer", "channel", "pipe"],
    ["stream", "iterator", "generator", "lazy"],
    ["immutable", "immutability", "readonly", "frozen"],
    ["nullable", "optional", "maybe", "nil", "null", "none"],

    # --- Data Formats & Serialization ---
    ["json", "jsonl", "ndjson"],
    ["yaml", "yml"],
    ["toml", "ini", "dotenv"],
    ["xml", "html", "xhtml"],
    ["csv", "tsv", "spreadsheet"],
    ["proto", "protobuf", "flatbuffers", "msgpack", "avro"],
    ["serialize", "serialization", "marshal", "encode"],
    ["deserialize", "deserialization", "unmarshal", "decode", "parse"],
    ["validate", "validation", "validating",
        "schema-validation", "zod", "pydantic", "joi"],

    # --- Errors & Reliability ---
    ["err", "error", "errors", "exception", "fault"],
    ["crash", "crashloop", "crashloopbackoff", "panic"],
    ["debug", "debugging", "breakpoint", "trace"],
    ["rollback", "revert", "undo"],
    ["fallback", "failover", "degraded", "graceful-degradation"],
    ["health", "healthcheck", "liveness", "readiness", "probe"],

    # --- Documentation ---
    ["doc", "documentation", "docs"],
    ["readme", "wiki", "runbook", "playbook"],
    ["comment", "annotation", "docstring", "jsdoc"],
    ["spec", "specification", "rfc", "adr"],

    # --- AI / ML (relevant for this codebase) ---
    ["llm", "language-model", "ai", "gpt",
        "claude", "gemini", "openai", "anthropic"],
    ["embed", "embedding", "embeddings", "vector"],
    ["rag", "retrieval-augmented-generation", "retrieval"],
    ["prompt", "prompting", "system-prompt", "instruction"],
    ["token", "tokens", "context-window"],
    ["inference", "completion", "generation"],
    ["fine-tune", "finetune", "finetuning", "lora"],
    ["agent", "agents", "tool-use", "function-calling"],
    ["chunk", "chunking", "split", "splitting"],
    ["semantic", "semantic-search", "similarity"],
]

# term -> set of synonyms (all values are stemmed)
synonym_map: Dict[str, Set[str]] = {}

for group in SYNONYM_GROUPS:
    stemmed = [stem(t.lower()) for t in group]

    for s in stemmed:
        if s not in synonym_map:
            synonym_map[s] = set()

        for other in stemmed:
            if other != s:
                synonym_map[s].add(other)


def get_synonyms(stemmed_term: str) -> List[str]:
    return list(synonym_map.get(stemmed_term, []))
