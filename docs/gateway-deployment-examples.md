# Gateway Deployment Examples

These examples are generic starting points for the customer-hosted PolicyStrata Agent Trust Gateway.
They keep runtime manifests and gateway tokens in caller-owned infrastructure. They do not assume
Clearance auth, private networking, or a specific cloud account.

## Docker

```dockerfile
FROM node:24-bookworm-slim

WORKDIR /app
RUN npm install -g @policystrata/agent-trust-gateway@0.1.1

COPY runtime-manifest.json /app/runtime-manifest.json

EXPOSE 8787
CMD ["agent-trust-gateway", "serve", "--manifest", "/app/runtime-manifest.json", "--host", "0.0.0.0", "--port", "8787"]
```

Run it with an external token:

```bash
docker run --rm -p 8787:8787 \
  -e POLICYSTRATA_GATEWAY_TOKEN="$POLICYSTRATA_GATEWAY_TOKEN" \
  policystrata-gateway:local
```

## Terraform

This sketch shows the configuration shape for any container service. Adapt the resource type to
your platform:

```hcl
variable "gateway_token" {
  type      = string
  sensitive = true
}

locals {
  gateway_env = {
    POLICYSTRATA_GATEWAY_TOKEN = var.gateway_token
    POLICYSTRATA_GATEWAY_MODE  = "enforce"
  }
}
```

Store `runtime-manifest.json` in the same deployment mechanism you use for application config, and
mount it read-only into the gateway container.

## Helm

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: policystrata-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      app: policystrata-gateway
  template:
    metadata:
      labels:
        app: policystrata-gateway
    spec:
      containers:
        - name: gateway
          image: policystrata-gateway:local
          args:
            - agent-trust-gateway
            - serve
            - --manifest
            - /config/runtime-manifest.json
            - --host
            - 0.0.0.0
            - --port
            - "8787"
          env:
            - name: POLICYSTRATA_GATEWAY_TOKEN
              valueFrom:
                secretKeyRef:
                  name: policystrata-gateway
                  key: token
          ports:
            - containerPort: 8787
          volumeMounts:
            - name: runtime-manifest
              mountPath: /config
              readOnly: true
      volumes:
        - name: runtime-manifest
          configMap:
            name: policystrata-runtime-manifest
```

For production, terminate TLS and rate-limit at your ingress, bind only to trusted networks, and
keep event payloads metadata-only.
