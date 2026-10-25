# Backup and recovery

Backups include original documents, extracted evidence, scenarios, citations and review decisions. They contain sensitive information. Keep the directory outside this checkout, restrict its access and use an encrypted disk or approved encrypted storage. The checksum detects accidental changes; it is not a signature or encryption. This tool does not schedule backups, upload them or enforce retention.

## Windows Command Prompt

Keep Docker Desktop running. From the project directory, create a dedicated folder and set its absolute path (change this example to your own user directory):

```cmd
mkdir C:\Users\aayus\CorpLexBackups
set "CORPLEX_BACKUP_DIR=C:\Users\aayus\CorpLexBackups"
docker compose -p corplex-app -f compose.app.yaml -f compose.backup.yaml run --rm recovery backup
```

For PowerShell, use `$env:CORPLEX_BACKUP_DIR = "C:\Users\aayus\CorpLexBackups"`. On Linux/macOS use `export CORPLEX_BACKUP_DIR=/absolute/private/backup-directory` and create that directory first. The directory must be writable by the PostgreSQL client container; on Linux configure appropriate ownership/ACLs for your Docker user namespace rather than making a real backup directory world-readable. Docker Desktop must have permission to share the selected directory.

The command prints a unique `.dump` filename and saves its `.sha256` alongside it. Partial failures retain a `.partial` file that is not a verified backup. No application database or volume is deleted. PostgreSQL takes a transactionally consistent snapshot; subsequent uploads are not part of that snapshot.

## Verify before relying on a backup

Replace `BACKUP.dump` with the exact filename printed by the backup command:

```cmd
docker compose -p corplex-app -f compose.app.yaml -f compose.backup.yaml run --rm recovery verify BACKUP.dump
```

Verification checks the checksum before creating a new temporary database. It restores the dump, applies constraints and runs integrity checks, prints record counts, then drops only its own temporary database. Even on failure, it never targets the application database for cleanup. The database user must have permission to create databases (the local Compose user does). The tools use the configured `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`; values are never printed. Do not pass passwords on command lines.

Only restore backups from a trusted source: a database archive can contain executable SQL. A matching checksum does not make an unknown archive safe. A successful verification confirms the recovered database passes these checks; it does not compare against later changes in the live database or prove all application semantics.

## Recover after data loss

Do not restore over the only existing copy or delete the application volume. Preserve a fresh backup of any recoverable current state first. Restore the trusted verified dump with PostgreSQL 17 `pg_restore --no-owner --no-acl --exit-on-error` into a newly created, separate database under reviewed database administration. Set the backend database connection to that recovered database, start the app, check readiness and inspect representative contracts, citations and approved reports before switching users to it. This tool intentionally does not automate overwriting or switching the live database.

The isolated verification also exercises restore mechanics without that switch. Trained ML artifacts, provider credentials and runtime configuration are not stored in the database backup; preserve trusted artifacts and secure settings separately. Keep multiple dated backups according to your retention needs; deleting a `.dump` permanently removes that recovery copy.
