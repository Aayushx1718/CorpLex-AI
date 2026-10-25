#!/bin/sh
# Run via compose.backup.yaml; all binary data stays inside the container/mount.
set -eu
umask 077
mode=${1:-}
case "$mode" in
  backup)
    name="corplex-$(date -u +%Y%m%dT%H%M%SZ)-$(od -An -N6 -tx1 /dev/urandom | tr -d ' \n').dump"
    pg_dump --format=custom --no-owner --no-acl --file="/backups/$name.partial"
    mv "/backups/$name.partial" "/backups/$name"
    cd /backups
    sha256sum "$name" > "$name.sha256"
    echo "Backup saved: $name (and .sha256). Run verify before relying on it."
    ;;
  verify)
    name=${2:-}
    case "$name" in ''|*[!a-zA-Z0-9_.-]*|.*|-*) echo 'Use a backup basename, not a path.' >&2; exit 2;; esac
    cd /backups
    # Compare against our own fixed filename, never paths supplied by a checksum file.
    expected=$(cut -d ' ' -f 1 "./$name.sha256")
    actual=$(sha256sum "./$name" | cut -d ' ' -f 1)
    [ "$expected" = "$actual" ] || { echo 'Backup checksum mismatch; refusing restore.' >&2; exit 1; }
    scratch="corplex_recovery_$(od -An -N12 -tx1 /dev/urandom | tr -d ' \n')"
    createdb --maintenance-db="$PGDATABASE" --template=template0 "$scratch"
    # Never clean/drop the application DB. Only this newly created scratch DB is removed.
    trap 'dropdb --maintenance-db="$PGDATABASE" --if-exists "$scratch"' EXIT HUP INT TERM
    pg_restore --dbname="$scratch" --no-owner --no-acl --exit-on-error "./$name"
    psql --dbname="$scratch" -X --set=ON_ERROR_STOP=1 --file=/opt/verify_recovery.sql
    echo 'Recovery verified in an isolated temporary database; application data unchanged.'
    ;;
  *) echo 'Usage: recovery backup | recovery verify BACKUP.dump' >&2; exit 2;;
esac
