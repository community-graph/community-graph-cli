const program = require('commander');
const fs = require('fs');

program
    .option('-c, --config [configFile]', 'Config file')
    .parse(process.argv);

let configFile = program.config || "communitygraph.json";

console.log(`Dumping community graph config: ${configFile}`);

var config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
console.log(JSON.stringify(config, null, 4));