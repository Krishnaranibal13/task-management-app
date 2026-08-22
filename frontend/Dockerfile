# Task Management MVP — frontend image (local development)
FROM node:24-alpine

WORKDIR /app

# Install dependencies first for better layer caching.
COPY package.json package-lock.json ./
RUN npm ci

# Application source.
COPY . .

EXPOSE 3000

# Development server (hot reload). Production image/build comes later.
CMD ["npm", "run", "dev"]
