FROM nginx:alpine

# Change nginx user to UID 100 to match eggdrop and pisg containers
# Using same adduser flags as upstream nginx:alpine but with different UID
RUN set -eux \
    && apk add --no-cache shadow \
    && usermod -u 100 nginx \
    && chown -R nginx:nginx \
        /var/cache/nginx \
        /var/log/nginx \
        /etc/nginx/conf.d \
        /var/run \
    && apk del shadow

