# Local vs Remote MongoDB Topology

Use this reference before audits, migrations, seed checks, cleanup scripts, or
document counts when a project can point at more than one MongoDB database.

## Declare the authoritative database first

Before reading or writing data, state which database is authoritative for the
task and how the connection string is resolved.

Required checks:

- Identify the connection string key or environment variable used by the ABP
  app, for example `ConnectionStrings:Default` or
  `<PROJECT>_MONGO_CONNECTION_STRING`.
- Fail loudly if the required environment variable is absent. Do not silently
  fall back to a local database for an audit or migration.
- Run `db.getName()` against the connected shell and record the returned
  database name before trusting counts.
- Treat remote databases, including Atlas, as read-only unless the user
  explicitly authorizes a write for this task.

False-high pattern to avoid: an audit counted documents in a stale local
database while the current data lived in Atlas. The counts looked precise, but
every high-severity finding was false because the target database was wrong.

## Connection proof template

Resolve placeholders from the live ABP project with `abp_context` and the
project's configuration. Keep database and collection names parameterized.

```javascript
// mongosh --eval "..." or paste into an authenticated shell
const expectedDb = "{{DATABASE_NAME}}";
const actualDb = db.getName();

if (actualDb !== expectedDb) {
  throw new Error(`Wrong database: expected ${expectedDb}, got ${actualDb}`);
}

print(`Connected database: ${actualDb}`);
print(`Authority: {{LOCAL_OR_REMOTE_AUTHORITY}}`);
print(`Collection: {{COLLECTION_NAME}}`);
```

## Read-only parity check

Use this shape to compare local and remote counts without mutating either side.
Run it separately against each target and compare the printed JSON.

```javascript
const collection = "{{COLLECTION_NAME}}";
const query = {{FILTER_JSON}};

const result = {
  database: db.getName(),
  collection,
  count: db.getCollection(collection).countDocuments(query),
  sampleIds: db.getCollection(collection)
    .find(query, { _id: 1 })
    .sort({ _id: 1 })
    .limit(5)
    .toArray()
    .map(doc => doc._id)
};

printjson(result);
```

For field-level parity, project only the fields involved in the migration or
audit:

```javascript
const collection = "{{COLLECTION_NAME}}";
const projection = {{PROJECTION_JSON}};

db.getCollection(collection)
  .find({{FILTER_JSON}}, projection)
  .sort({ _id: 1 })
  .limit({{LIMIT}})
  .forEach(doc => printjson(doc));
```

## Authorized seed or cleanup template

Only run write templates after the user confirms the target and authorizes the
write. Keep the guard at the top so a copied script fails on the wrong database.

```javascript
const expectedDb = "{{DATABASE_NAME}}";
const actualDb = db.getName();
if (actualDb !== expectedDb) {
  throw new Error(`Wrong database: expected ${expectedDb}, got ${actualDb}`);
}

if ("{{REMOTE_READ_ONLY}}" === "true") {
  throw new Error("Remote database is read-only for this task; ask before writing.");
}

const collection = db.getCollection("{{COLLECTION_NAME}}");

// Idempotent seed example. Replace placeholders with project values.
collection.updateOne(
  { "{{UNIQUE_FIELD}}": "{{UNIQUE_VALUE}}" },
  {
    $setOnInsert: {{INSERT_DOCUMENT_JSON}},
    $set: {{UPDATE_DOCUMENT_JSON}}
  },
  { upsert: true }
);

printjson({
  database: actualDb,
  collection: "{{COLLECTION_NAME}}",
  matched: collection.countDocuments({ "{{UNIQUE_FIELD}}": "{{UNIQUE_VALUE}}" })
});
```

Cleanup uses the same guard and an exact filter:

```javascript
const expectedDb = "{{DATABASE_NAME}}";
if (db.getName() !== expectedDb) {
  throw new Error(`Wrong database: expected ${expectedDb}, got ${db.getName()}`);
}

const filter = {{EXACT_CLEANUP_FILTER_JSON}};
printjson({
  database: db.getName(),
  collection: "{{COLLECTION_NAME}}",
  wouldDelete: db.getCollection("{{COLLECTION_NAME}}").countDocuments(filter)
});

// Uncomment only after user approval for this exact target/filter.
// db.getCollection("{{COLLECTION_NAME}}").deleteMany(filter);
```

## Reporting rule

When reporting audit or migration evidence, include:

- connection source: config key or env var name, never the secret value
- `db.getName()` result
- collection name
- read/write authority: local, remote read-only, or remote write-authorized
- exact command or script template used
