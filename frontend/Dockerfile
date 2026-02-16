FROM node:20-alpine AS base

# --- Build stage ---
FROM base AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
# Ensure /app/public always exists so COPY in runtime stage never fails.
RUN mkdir -p /app/public
RUN npm run build

# --- Production stage ---
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8080

RUN addgroup --system --gid 1001 labsight && \
    adduser --system --uid 1001 labsight

# Copy standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER labsight

EXPOSE 8080

CMD ["node", "server.js"]
