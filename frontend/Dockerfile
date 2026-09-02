FROM node:22-alpine AS deps
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /src
COPY --from=deps /src/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN addgroup -S -g 65532 app && adduser -S -u 65532 -G app app \
    && mkdir -p /app/.next \
    && chown -R 65532:65532 /app

COPY --from=build --chown=65532:65532 /src/public ./public
COPY --from=build --chown=65532:65532 /src/.next/standalone ./
COPY --from=build --chown=65532:65532 /src/.next/static ./.next/static

USER 65532:65532
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=3s --start-period=25s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
