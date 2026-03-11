# Stage 1: Build
FROM node:18-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build-time env vars (baked into JS bundle)
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_AGENT_ENDPOINT
ARG VITE_ENABLE_STREAMING=true
ARG VITE_LANGFUSE_HOST_WITH_PROJECT

ENV VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
ENV VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
ENV VITE_AGENT_ENDPOINT=${VITE_AGENT_ENDPOINT}
ENV VITE_ENABLE_STREAMING=${VITE_ENABLE_STREAMING}
ENV VITE_LANGFUSE_HOST_WITH_PROJECT=${VITE_LANGFUSE_HOST_WITH_PROJECT}

RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

RUN apk add --no-cache dumb-init

RUN addgroup -g 1001 -S appuser && \
    adduser -S appuser -u 1001

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html

RUN mkdir -p /var/cache/nginx /var/run/nginx && \
    chown -R appuser:appuser /var/cache/nginx /var/run/nginx /usr/share/nginx/html

EXPOSE 8080

USER appuser

ENTRYPOINT ["dumb-init", "--"]
CMD ["nginx", "-g", "daemon off;"]
