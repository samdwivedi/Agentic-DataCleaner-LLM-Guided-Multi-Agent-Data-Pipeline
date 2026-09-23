FROM node:18-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Build Next.js application
COPY . .
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app
ENV NODE_ENV=production

# Copy only the necessary files for production
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

# Expose port
EXPOSE 3000

# Start server
CMD ["npm", "start"]
