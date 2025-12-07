# PISG Cache Directory

This directory contains cache files used by pisg for faster processing of IRC logs.

## Purpose

PISG caches parsed log data to speed up subsequent statistics generation.
Without the cache, pisg would need to reprocess all historical logs on every run.

## Cache Files

Files in this directory are named based on the channel and time period processed.
They are binary data files managed by pisg.

## Important Notes

- All files in this directory are gitignored except this README
- Cache files are automatically generated and maintained by pisg
- You can safely delete cache files to force a full reprocessing
- Cache is owned by UID 100 / GID 65533 (matches eggdrop container)
