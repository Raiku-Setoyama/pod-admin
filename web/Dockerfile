# syntax=docker/dockerfile:1

FROM node:22-slim AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Development stage
FROM base AS development
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "run", "dev"]

# Build stage
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build application
RUN npm run build

# Production stage
FROM base AS production
WORKDIR /app

ENV NODE_ENV=production

# Copy built application
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
