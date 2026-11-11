# AWS backend with the existing Render frontend domain

The requested public address remains `https://qore-bmh1.onrender.com/`. Render can build `Dockerfile.render-gateway`, serve only the React assets, and forward same-origin `/api/*` calls to a fixed **HTTPS** AWS endpoint. All simulation, Forge, Ledger, workspace, and QI processing runs on AWS. The gateway preserves the browser's host-only `qore_workspace` cookie, so files and evidence remain in the same browser workspace. Render still handles static delivery and lightweight proxy traffic.

This is a prepared design, **not a completed deployment**. The currently observed EC2 container listens on HTTP port 80, has no persistent Docker mount, and stores its SQLite file inside the container. Route 53 has no hosted zones in this AWS account. Do not point the Render gateway at `http://` EC2 or switch its Dockerfile until an AWS HTTPS endpoint, persistent database mount, and tested migration are ready. The gateway refuses an HTTP backend origin at startup.

For the AWS backend, retain `QORE_PUBLIC_URL=https://qore-bmh1.onrender.com`, set `QORE_ALLOWED_HOSTS` to the exact HTTPS endpoint hostname, and serve the backend through the private integration behind that endpoint. For Render, set `QORE_AWS_API_ORIGIN` to that endpoint's HTTPS origin and select `Dockerfile.render-gateway`. Neither setting belongs in a `VITE_*` variable. The gateway forwards the browser Origin; the backend allows only its configured public origin for writes. Test cookie continuity, a saved run, Explorer refresh, and QI from the public Render hostname after cutover.

An AWS-managed API Gateway HTTPS endpoint with a **private VPC integration** to the existing EC2 service is one possible ingress. Its required network components and ongoing charges must be reviewed before provisioning. A public HTTP integration would expose source and workspace cookies on the API Gateway-to-EC2 hop and is unsuitable. Keep the existing Render service untouched until both ingress and storage are ready. Prepare a rollback that restores the prior Render Dockerfile and the original EC2 container image without discarding its database.

## Existing single-instance runtime

QORE currently uses one FastAPI container, a built React frontend, and a local SQLite database. A single EC2 instance with an attached, persistent EBS volume is the smallest AWS compute profile that preserves these contracts. Run one QORE container, mount the volume at `/data`, and set `QORE_DB_PATH=/data/qore.sqlite3`. The browser continues to call same-origin `/api` through the Render gateway. The EC2 instance handles backend requests, while the AWS ingress supplies a stable HTTPS origin.

This profile is **single instance**, with a two-job quantum worker limit. More EC2 CPU or RAM can improve capacity, but it does not change QORE's worker admission limit or the browser's download size. Do not start multiple replicas against the same SQLite file. Moving to horizontally scaled workers requires a reviewed shared job queue, distributed admission/rate limits, and a database migration. Do not treat a network file system as a drop-in SQLite scaling solution.

## Before creating resources

1. Use a dedicated AWS account or project boundary with a budget and alerts. Choose a region near the intended users.
2. Provision EC2 and a separate encrypted EBS data volume. Restrict SSH or use Systems Manager Session Manager. Allow public HTTPS only through the chosen ingress; keep database files off the public web root.
3. Build the repository Dockerfile from the tested release commit. Mount the EBS filesystem at `/data` in the container and set `QORE_ENV=production`, `QORE_STORAGE=sqlite`, `QORE_DB_PATH=/data/qore.sqlite3`, `QORE_PUBLIC_URL=https://qore-bmh1.onrender.com`, and `QORE_ALLOWED_HOSTS=<exact AWS ingress host>`. Set `GEMINI_API_KEY` only through a server-side secret source if QI is enabled. Never send it to Vite or commit it.
4. Route the AWS ingress privately to container port 8080 and perform a health check on `/api/health`. Configure EBS snapshots and test a restore into a separate instance.
5. Run the release checks in `docs/PRODUCTION.md`, then verify an Explorer edit survives refresh and container replacement, a local Aer result and Ledger record persist, and the public page loads at laptop and mobile widths.

QORE currently has browser-scoped anonymous workspaces, not verified human accounts. Limit access to a controlled audience until identity and abuse controls are reviewed. A public AWS hostname alone does not provide user authentication.

The [AWS ECS storage guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_data_volumes.html) distinguishes persistent from ephemeral task volumes. [App Runner storage](https://docs.aws.amazon.com/apprunner/latest/dg/develop.html) is ephemeral, so moving the existing SQLite file there would lose the persistence guarantee. These references explain the storage choice; no AWS resource has been created or billed by this document.

## Migrating an existing unmounted container

An existing `qore` container may have its SQLite database inside `/app/data` with no Docker mount. Replacing that container would discard the database even if the EC2 instance itself remains running. Inspect `docker inspect qore --format '{{json .Mounts}}'` and the database path before changing it. Do not print container environment variables: they can contain secrets.

Prepare the migration in this order:

1. Capture the running image ID, container creation time, restart policy, port mapping, and database file size. Identify the exact release commit and run its quality gates. Do not build an unverified worktree on the production host.
2. Provision a **separate encrypted EBS volume in the instance's Availability Zone** and mount it at a stable host path such as `/srv/qore/data`. Confirm it is listed in `/etc/fstab` by UUID and that the intended container user can write there. Do not format or overwrite an existing volume.
3. Make an EBS snapshot and a consistent SQLite backup before cutover. Use Python's `sqlite3.Connection.backup` API from the running container; copying only a live `.sqlite3` file can omit uncheckpointed WAL data. Store the backup on the new volume with restricted permissions, run `PRAGMA integrity_check` on the copy, and compare record counts without printing private rows.
4. Stage the new image under a distinct tag. Supply environment settings through a root-readable secret source, not Docker build arguments or a public repository. Start a staging container on a loopback-only alternate port with a **copy** of the backup. Verify `/api/health`, a small Aer run, Ledger restore, Explorer refresh, and QI's unavailable behavior without making live provider calls.
5. In a maintenance window, stop writes, make a final consistent backup, and replace the old container with one bind-mounting `/srv/qore/data` to `/data` and setting `QORE_DB_PATH=/data/qore.sqlite3`. Preserve the prior image and backup for rollback. Verify the new container's mount, API health, saved record counts, and browser workflow before reopening traffic.
6. Add HTTPS and a stable DNS name before treating the service as public. Keep port 8080 private to the host, limit SSH to a trusted source or use Session Manager, and enable volume snapshots and disk-space alerts. The anonymous workspace model still requires controlled access.

The production cutover, new EBS volume, DNS, and security-group changes are separate infrastructure actions. This guide does not execute them. A root EBS volume configured for deletion on instance termination is not an adequate sole copy of Ledger evidence.
