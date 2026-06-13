#!/bin/bash

set -euo pipefail

DEVICE="/dev/nvme0n1p2"

MOUNTPOINT="/mnt"

REMOTE_USER=""
REMOTE_HOST=""
REMOTE_DIR="~/btrfs"

RETENTION_DAYS=7

DATE=$(date +%F_%H:%M:%S)
SNAPSHOT_NAME="root-${DATE}"

# Mount top-level BTRFS

mkdir -p "$MOUNTPOINT"

sudo mount -o subvolid=5 "$DEVICE" "$MOUNTPOINT"

mkdir -p "$MOUNTPOINT/.snapshots"

# Create read-only snapshot

echo "Creating snapshot..."

sudo btrfs subvolume snapshot -r \
    "$MOUNTPOINT/@rootfs" \
    "$MOUNTPOINT/.snapshots/$SNAPSHOT_NAME"

# Send to remote server

echo "Sending backup..."

sudo btrfs send \
    "$MOUNTPOINT/.snapshots/$SNAPSHOT_NAME" | \
    zstd -19 | \
    ssh "${REMOTE_USER}@${REMOTE_HOST}" \
    "mkdir -p ${REMOTE_DIR} && cat > ${REMOTE_DIR}/${SNAPSHOT_NAME}.btrfs.zst"

# Local snapshot retention

echo "Cleaning old snapshots..."

find "$MOUNTPOINT/.snapshots" \
    -maxdepth 1 \
    -mindepth 1 \
    -type d \
    -mtime +${RETENTION_DAYS} \
    -exec sudo btrfs subvolume delete {} \;

# Remote backup retention

echo "Cleaning remote backups..."

ssh "${REMOTE_USER}@${REMOTE_HOST}" "
find ${REMOTE_DIR} \
    -name '*.btrfs.zst' \
    -mtime +${RETENTION_DAYS} \
    -delete
"

# Unmount
sudo umount "$MOUNTPOINT"

echo "Backup completed successfully."