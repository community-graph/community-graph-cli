const prereqs = require("../prereqs");
const Serverless = require('serverless');
const program = require('commander');

program.parse(process.argv);

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
    return encryptKey(data, "meetupApiKey", communityGraphParams.credentials);
}).then(data => {
    return encryptKey(data, "stackOverflowApiKey", communityGraphParams.credentials);
}).then(data => {
    return encryptKey(data, "githubToken", communityGraphParams.credentials);
}).then(data => {
    return encryptKey(data, "twitterBearer", communityGraphParams.credentials);
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
}).catch(err => {
    console.error("Error while creating community graph:", err);
    process.exit(1);
})