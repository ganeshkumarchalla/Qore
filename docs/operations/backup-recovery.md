# Backup and recovery

Mount durable storage for SQLite and snapshot it with a method that produces a consistent database copy. Retain multiple generations according to operational risk, encrypt backups, restrict access, and test restoration into a separate QORE instance. A backup that has never been restored is unverified.

Explorer source also exists in browser storage. Database recovery does not restore cleared browser files, and browser source does not recreate missing immutable run evidence. Export important source before browser migration. Keep the public origin stable because cookies and browser storage are origin-scoped.

Trash provides 48-hour application recovery for deleted workspace entries. It is not a disaster-recovery system and makes no promise about backup erasure schedules. Document which layer is being recovered before taking action.
