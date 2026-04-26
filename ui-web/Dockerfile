FROM node:24-alpine AS build

WORKDIR /app
COPY ui-web/package.json ui-web/package-lock.json* ./
RUN npm install
COPY ui-web ./
RUN npm run build

FROM nginx:1.27-alpine
COPY ui-web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

