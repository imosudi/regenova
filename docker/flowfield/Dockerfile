# REGENOVA FlowField — Dockerfile
FROM node:22-alpine

RUN apk add --no-cache curl wget bash

WORKDIR /usr/src/node-red

# Install production dependencies
COPY flowfield/package.json flowfield/package-lock.json ./
RUN npm ci --omit=dev

# Copy configuration, flows and scripts
COPY flowfield/settings.js flowfield/flows.json ./
COPY flowfield/scripts ./scripts
COPY flowfield/public ./public

# Setup runtime user and directories
RUN mkdir -p /usr/src/node-red/context && chown -R node:node /usr/src/node-red

USER node

EXPOSE 1880

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:1880/health || exit 1

CMD ["npm", "start"]
