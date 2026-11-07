/* Makes a phone database from a .voidsync file (used for screenshots): node seed_from_sync.js file.voidsync > db.json */
const path = require('path'), fs = require('fs');
global.Core = require(path.join(__dirname, '../app/src/main/assets/www/js/core.js'));
const db = Core.ensure(Core.newDb()); db.sync.device_name = 'Pixel';
const plan = Core.prepare(db, fs.readFileSync(process.argv[2], 'utf8')); Core.commit(db, plan);
db.settings.welcomed = true; db.settings.lang = process.argv[3] || 'fa';
process.stdout.write(JSON.stringify(db));
