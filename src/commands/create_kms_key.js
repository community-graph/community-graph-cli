const program = require('commander');
const fs = require('fs');
const aws = require("../aws")

program
    .option('-c, --config [configFile]', 'Config file')
    .parse(process.argv);

let configFile = program.config || "communitygraph.json";

let config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
let communityName = config["communityName"];

aws.createKMSKey().then(data => {
    console.log("Created KMS key: " + data.KeyMetadata.Arn);
    return aws.createKMSKeyAlias(communityName, data.KeyMetadata.Arn );
}).then(data => {
    console.log("Assigned alias to KMS key");
}).catch(err => {
    console.error(err, err.stack);
});