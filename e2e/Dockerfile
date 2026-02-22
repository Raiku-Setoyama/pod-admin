# syntax=docker/dockerfile:1

FROM mcr.microsoft.com/playwright:v1.51.0-noble

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy test files
COPY . .

# Run tests
CMD ["npm", "test"]
