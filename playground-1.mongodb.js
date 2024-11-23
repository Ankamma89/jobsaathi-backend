/* global use, db */
// MongoDB Playground
// Use Ctrl+Space inside a snippet or a string literal to trigger completions.

const database = 'jobsaathinew-prod';
const collection = 'plan_details';

// The current database to use.
use(database);

// Create a new collection.
db.createCollection(collection)

db.getCollection(collection).insertMany([
    {
      "_id": "basic", 
      "name": "Basic Plan",
      "price": 0,
      "job_limit": 5,
      "features": ["Post up to 5 jobs"]
    },
    {
      "_id": "premium",
      "name": "Premium Plan",
      "price": 50,
      "job_limit": 20,
      "features": ["Post up to 20 jobs", "Priority support"]
    },
    {
      "_id": "enterprise",
      "name": "Enterprise Plan",
      "price": 100,
      "job_limit": 50,
      "features": ["Post up to 50 jobs", "Dedicated account manager", "Custom support"]
    }
  ]);

// The prototype form to create a collection:
/* db.createCollection( <name>,
  {
    capped: <boolean>,
    autoIndexId: <boolean>,
    size: <number>,
    max: <number>,
    storageEngine: <document>,
    validator: <document>,
    validationLevel: <string>,
    validationAction: <string>,
    indexOptionDefaults: <document>,
    viewOn: <string>,
    pipeline: <pipeline>,
    collation: <document>,
    writeConcern: <document>,
    timeseries: { // Added in MongoDB 5.0
      timeField: <string>, // required for time series collections
      metaField: <string>,
      granularity: <string>,
      bucketMaxSpanSeconds: <number>, // Added in MongoDB 6.3
      bucketRoundingSeconds: <number>, // Added in MongoDB 6.3
    },
    expireAfterSeconds: <number>,
    clusteredIndex: <document>, // Added in MongoDB 5.3
  }
)*/

// More information on the `createCollection` command can be found at:
// https://www.mongodb.com/docs/manual/reference/method/db.createCollection/
