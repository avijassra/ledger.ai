# Stage 1: Build
FROM node:20-alpine AS build
WORKDIR /app

COPY src/client/package*.json ./
RUN npm install

COPY src/client/ .

RUN npx nx build ledger-ai-client --configuration=production

# Stage 2: Serve
FROM nginx:alpine

COPY --from=build /app/dist/ledger-ai-client/browser /usr/share/nginx/html

COPY deploy/docker/files/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
