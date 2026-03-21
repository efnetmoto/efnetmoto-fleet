FROM eggdrop:1.10

# Remap eggdrop user to UID 100 to match existing file structure.
# Required for shared volume permissions.
# GID is intentionally left as-is; shared volume access is UID-based only.
RUN apk add --no-cache shadow \
    && usermod -u 100 eggdrop \
    && chown -R eggdrop:eggdrop /home/eggdrop \
    && apk del shadow
