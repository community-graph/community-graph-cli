const program = require('commander');
const fs = require('fs');
const aws = require("../aws")

program
    .option('-c, --config [configFile]', 'Config file')
    .parse(process.argv);

let configFile = program.config || "communitygraph.json";

let config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
let communityName = config["communityName"];
let s3BucketName = "community-graph-" + communityName.toLowerCase();

aws.createS3Bucket(s3BucketName).then(data => {
    console.log("Created bucket: " + data.Location.replace("/", ""));
}).catch(err => {
    console.error("Failed to create bucket: " + err);
});