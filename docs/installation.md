# Windows installation

The `GrowMaster-Setup-<version>.exe` artifact installs the application files under the current user's local application directory, creates Start-menu and optional desktop shortcuts, generates a private random database password, starts the Docker Compose stack and opens GrowMaster.

Docker Desktop is the only prerequisite. If it is missing, the launcher opens the official Docker installation page and can be run again after Docker starts. Updates preserve the private environment file under `%APPDATA%\GrowMaster` and preserve both Docker volumes. Uninstalling stops GrowMaster but deliberately does not delete the database or backups.

GitHub Actions builds the installer from `installer/GrowMaster.iss`. The repository `.env` is excluded from the installer, so one farm can never receive another farm's credentials or data.
