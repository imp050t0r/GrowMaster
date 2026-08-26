# Windows installation

The `GrowMaster-Setup-<version>.exe` artifact installs the application files under the current user's local application directory, creates Start-menu and optional desktop shortcuts, generates a private random database password, starts the Docker Compose stack and opens GrowMaster.

On a new installation, the wizard asks where GrowMaster should store its data. The selected directory contains separate `database` and `backups` subdirectories, so the database can live on another local drive. The default is `%LOCALAPPDATA%\GrowMasterData`. Use a local drive that remains connected while GrowMaster is running.

After installation, an administrator can open **Podatki** and choose **Izberi novo mapo**. The installed Windows helper opens the native folder picker, stops the Compose stack, copies and verifies both PostgreSQL data and backups, switches the private environment file atomically, restarts GrowMaster and waits for its health check. If startup fails, it restores the previous environment. A successful move deliberately retains the old database as a recovery copy; remove it only after the new location has been checked. The same helper is also available in the Start menu as **GrowMaster - prestavi podatke**.

Docker Desktop is the only prerequisite. If it is missing, the launcher opens the official Docker installation page and can be run again after Docker starts. Updates preserve the private environment file under `%APPDATA%\GrowMaster` and mount the configured application-data directory at `/data`, so the installation ID, signed license, Plant DB, database and backups survive container rebuilds. Legacy installations that use Docker-managed volumes continue using those volumes; an update never silently moves or replaces an existing database. Uninstalling stops GrowMaster but deliberately does not delete the database or backups.

GitHub Actions builds the installer from `installer/GrowMaster.iss`. The repository `.env` is excluded from the installer, so one farm can never receive another farm's credentials or data.
