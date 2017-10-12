const prereqs = require("../prereqs");
const Serverless = require('serverless');
const program = require('commander');
const cli = require("../cli");
const AWS = require("aws-sdk");
const fs = require('fs');

program.parse(process.argv);

let rawParams = {};
let communityGraphParams = {
    credentials: {
        write: {},
        readonly: {}
    }
};

let regionParams = { 'region': 'us-east-1' }
let kms = new AWS.KMS(regionParams);
let s3 = new AWS.S3(regionParams);
var ec2 = new AWS.EC2(regionParams);

function _createKMSKeyAlias(communityName, kmsKeyArn) {
    let createAliasParams = {
        AliasName: "alias/CommunityGraphCLI-" + communityName,
        TargetKeyId: kmsKeyArn
    };

    return kms.createAlias(createAliasParams).promise();
}

function _createKMSKey() {
    return kms.createKey({}).promise();
}

function _createS3Bucket(s3BucketName) {
    console.log("Creating bucket: " + s3BucketName);
    var params = { Bucket: s3BucketName, ACL: "public-read" };
    return s3.createBucket(params).promise()
}

function encryptKey(data, keyName, mapToUpdate) {
    let kmsKey = data.kmsKeyArn;
    let valueToEncrypt = data[keyName];

    console.log("Encrypting " + keyName + ":" + valueToEncrypt);

    return new Promise((resolve, reject) => {
        if (!valueToEncrypt) {
            console.log(keyName + " not provided - skipping");
            resolve(data);
        } else {
            let params = { KeyId: kmsKey, Plaintext: valueToEncrypt };

            kms.encrypt(params).promise().then(result => {
                mapToUpdate[keyName] = result.CiphertextBlob.toString('base64');
                resolve(data);
            }).catch(reject);
        }
    });
}

function writeCommunityGraphJson(data) {
    communityGraphParams.communityName = data.communityName;
    communityGraphParams.tag = data.tag;
    communityGraphParams.serverUrl = data.serverUrl || "<neo4j-server-url>";
    communityGraphParams.logo = data.logo;
    communityGraphParams.s3Bucket = data.s3Bucket;
    communityGraphParams.twitterSearch = data.twitterSearch;

    communityGraphParams.credentials.keyArn = data.kmsKeyArn;

    communityGraphParams.credentials.readonly.user = data.readOnlyServerUsername || "<read-only-username>";
    communityGraphParams.credentials.readonly.password = communityGraphParams.credentials.readonly.readOnlyServerPassword ||  "<read-only-password>";
    communityGraphParams.credentials.write.user = data.serverUsername || "neo4j";
    communityGraphParams.credentials.write.password = communityGraphParams.credentials.write.serverPassword || "<server-password>";

    delete communityGraphParams.credentials.readonly.readOnlyServerPassword;
    delete communityGraphParams.credentials.write.serverPassword;

    return new Promise((resolve, reject) => {
        try {
            fs.writeFileSync("communitygraph.json", JSON.stringify(communityGraphParams, null, 4));
            resolve(data);
        } catch (e) {
            reject(e);
        }
    });
}

let welcome = new Promise((resolve, reject) => {
    console.log("Welcome to the community graph - it's time to find out what's happening in your community!");
    resolve();
});

welcome
.then(prereqs.checkCommunityGraphExists)
.then(prereqs.checkPythonVersion).then(data => {
    console.log("Provide us some parameters so we can get this show on the road:");
    return cli.getParameters(data);
}).then(data => {
    console.log('Parameters provided:');
    console.log(data);
    return Promise.resolve(data);
}).then(data => {
    return new Promise((resolve, reject) => {
        if (!data.kmsKeyArn) {
            _createKMSKey().then(result => {
                console.log("Created KMS key: " + result.KeyMetadata.Arn);
                data.kmsKeyArn = result.KeyMetadata.Arn;

                let kmsKeyArn = data.kmsKeyArn;
                let communityName = data.communityName;
                return _createKMSKeyAlias(communityName, kmsKeyArn);
            }).then(result => {
                console.log("Assigned KMS Key alias");
                resolve(data);
            }).catch(reject);
        } else {
            resolve(data);
        }
    });
}).then(data => {
    let communityName = data.communityName;
    let s3BucketName = "community-graph-" + communityName.toLowerCase();
    return new Promise((resolve, reject) => {
        if (!data.s3Bucket) {
            console.log("Creating S3 bucket: " + s3BucketName)
            _createS3Bucket(s3BucketName).then(result => {
                data.s3Bucket = result.Location.replace("/", "");
                resolve(data);
            }).catch(reject);
        } else {
            console.log("Using S3 bucket: " + data.s3Bucket)
            resolve(data);
        }
    });
}).then(data => {
    return Promise.all([
        encryptKey(data, "meetupApiKey", communityGraphParams.credentials),
        encryptKey(data, "stackOverflowApiKey", communityGraphParams.credentials),
        encryptKey(data, "githubToken", communityGraphParams.credentials),
        encryptKey(data, "twitterBearer", communityGraphParams.credentials)
    ]);
}).then(data => {
    if (!data.serverUrl) {
        return Promise.resolve(data);
    } else {
        return encryptKey(data, "readOnlyServerPassword", communityGraphParams.credentials.readonly);
    }
}).then(data => {
    if (!data.serverUrl) {
        return Promise.resolve(data);
    } else {
        return encryptKey(data, "serverPassword", communityGraphParams.credentials.write);
    }
}).then(data => {
    return writeCommunityGraphJson(data);
}).then(data => {
    console.log(`Community Graph created! If you want to update any of the parameters you'll need to edit communitygraph.json`)
}).catch(err => {
    console.error("Error while creating community graph:", err);
    process.exit(1);
})