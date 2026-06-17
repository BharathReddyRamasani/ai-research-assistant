# Stage 1: Build the React application
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration to handle React Router and API proxying
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 7860

CMD ["nginx", "-g", "daemon off;"]
