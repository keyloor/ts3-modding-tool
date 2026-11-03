// Developer/CI check only. The application has no Node.js or validator dependency.
// npm.cmd install --prefix build/gltf-validator --no-save --ignore-scripts gltf-validator@2.0.0-dev.3.10
// node tests/validate_gltf.cjs build/gltf-checks [ANOTHER_DIRECTORY ...]
const fs = require('fs');
const path = require('path');
const validator = require('../build/gltf-validator/node_modules/gltf-validator');

(async () => {
    let count = 0, errors = 0;
    for (const dir of process.argv.slice(2)) {
        for (const name of fs.readdirSync(dir).filter(n => n.endsWith('.glb'))) {
            const file = path.join(dir, name);
            const report = await validator.validateBytes(new Uint8Array(fs.readFileSync(file)), {uri: name, maxIssues: 200});
            fs.writeFileSync(file + '.validation.json', JSON.stringify(report, null, 2));
            console.log(file, report.issues.numErrors, 'errors,', report.issues.numWarnings, 'warnings');
            if (report.issues.numErrors) console.error(JSON.stringify(report.issues.messages));
            errors += report.issues.numErrors; count++;
        }
    }
    if (!count) throw new Error('No GLB artifacts were checked.');
    process.exitCode = errors ? 1 : 0;
})().catch(error => { console.error(error); process.exitCode = 1; });
