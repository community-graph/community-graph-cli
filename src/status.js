const program = require('commander');
const fs = require('fs');

program
    .option('-c, --config [configFile]', 'Config file')
    .parse(process.argv);

let configFile = program.config || "communitygraph.json";

let welcome = new Promise((resolve, reject) => {
    console.log(`Checking the status of the community graph: ${configFile}`);
    resolve();
});

welcome.then(data => {
    let config = JSON.parse(fs.readFileSync(configFile, 'utf8'));

    console.log("Neo4j browser URI: http://" + config["serverUrl"] + ":7474");
    let s3Bucket = config["s3Bucket"];
    console.log(`Summary page: https://s3.amazonaws.com/${s3Bucket}/${s3Bucket}.html`);
}).catch(err => {
    console.error("Error retrieving the status of the community graph:", err);
    process.exit(1);
});