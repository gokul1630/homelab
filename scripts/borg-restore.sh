#!/bin/bash

set -e

log () {
	echo "#------------- $1 -------------#"
}

export BORG_PASSCOMMAND="cat /opt/.borg.pass"
REPO="borg@100.70.220.44:/mnt/sdb/immich"
RESTORE_DIR="/tank/restore"

log "Available backups:"
borg list "$REPO"

read -rp "Enter the archive name to restore: " ARCHIVE

mkdir -p "$RESTORE_DIR" && cd "$RESTORE_DIR"

log "Restoring $ARCHIVE to $RESTORE_DIR..."

borg extract --list \
    "$REPO::$ARCHIVE"

log "Restore completed."