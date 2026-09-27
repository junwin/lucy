# Switching Lucy's episodic SQLite store

Lucy defaults to the existing `SqliteEpisodicMemory` and `chat2.sqlite`.
A migrated database can be selected explicitly once a galet-memory release
containing `RelationalSqliteEpisodicMemory` is installed.

1. Stop Lucy before making the final copy so no new events are written to the
   old database after the snapshot.
2. Run the galet-memory migration against the live database path:

   ```bash
   python -m galet_memory.migrations.migrate_episodic_sqlite \
     /path/to/chat2.sqlite /path/to/chat2-relational.sqlite
   ```

3. Check reported counts, representative sessions, and correlated events.
   The migration refuses dangling links, including links left by deleted
   legacy sessions. The old database is preserved.
4. Set in Lucy's configuration:

   ```json
   {
     "episodic_memory_backend": "relational_sqlite",
     "episodic_memory_db_path": "/path/to/chat2-relational.sqlite"
   }
   ```

5. Restart Lucy and check session listing, an existing conversation, and a
   new message. To roll back, restore `episodic_memory_backend` to
   `legacy_sqlite` and the old path. Messages written only to the new
   database would need copying back separately.

Without an explicit path, the relational backend defaults to
`<storage_root>/<storage_namespace>/chat2-relational.sqlite`. The
`chat2_store_db_path` fallback applies only to the legacy backend so Lucy
cannot accidentally open the old database as a new one. This change does not
alter any separate embedding store that may still use the old file.
