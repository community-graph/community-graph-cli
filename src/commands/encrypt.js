const program = require('commander');
const fs = require('fs');
const aws = require("../aws")

program
    .option('-c, --config [configFile]', 'Config file')
    .parse(process.argv);

let configFile = program.config || "communitygraph.json";

var config = JSON.parse(fs.readFileSync(configFile, 'utf8'));
let kmsKey = config["credentials"]["keyArn"]
console.log("Encrypting with KMS Key: " + kmsKey);

var values = program.args;

if (!values.length) {
  console.error('You must provide a value to encrypt');
  process.exit(1);
}

if (values.length > 1) {
    console.error('You can only encrypt one value at a time. Try calling the command one time per value.');
    process.exit(1);
  }

let valueToEncrypt = values[0];
let params = { KeyId: kmsKey, Plaintext: valueToEncrypt };

console.log("Value to encrypt: " + valueToEncrypt);

aws.kms.encrypt(params).promise()
    .then(data => console.log("Encrypted value: " + data.CiphertextBlob.toString('base64')))
    .catch(err => console.error(err, err.stack));
