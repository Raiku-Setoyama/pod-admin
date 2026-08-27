# syntax=docker/dockerfile:1

FROM node:22-alpine AS base

WORKDIR /app

# Development stage
FROM base AS development

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev"]

# Builder stage
FROM base AS builder

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# API の向き先はビルド時にクライアントバンドルへ焼き込まれる（NEXT_PUBLIC_* の仕様）。
# 実行時の環境変数では変えられないため、環境ごとに別のイメージをビルドする。
# 未指定なら空になり、アプリ側の既定値（http://localhost:8000/api/v1）にフォールバックする。
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Build the application
RUN npm run build

# Production stage
FROM base AS production

ENV NODE_ENV=production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
