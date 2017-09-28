var async = require('async'),
    https = require('follow-redirects').https,
    http = require('http'),
    fs = require('fs'),
    chalk = require('chalk'),
    Serverless = require('serverless'),
    prompt = require('prompt'),
    AWS = require("aws-sdk"),
    opn = require('opn'),
    commandLineCommands = require('command-line-commands'),
    parseArgs = require('minimist'),
    cli = require("./cli"),
    prereqs = require("./prereqs"),
    exec = require('child_process').exec,
    uuidv4 = require('uuid/v4');

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
var sns = new AWS.SNS(regionParams);

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
    communityGraphParams.serverUrl = data.serverUrl;
    communityGraphParams.logo = data.logo;
    communityGraphParams.s3Bucket = data.s3Bucket;
    communityGraphParams.twitterSearch = data.twitterSearch;

    communityGraphParams.credentials.keyArn = data.kmsKeyArn;

    communityGraphParams.credentials.readonly.user = data.readOnlyServerUsername || "neo4j";
    communityGraphParams.credentials.readonly.password = communityGraphParams.credentials.readonly.readOnlyServerPassword;
    communityGraphParams.credentials.write.user = data.serverUsername || "neo4j";
    communityGraphParams.credentials.write.password = communityGraphParams.credentials.write.serverPassword;

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

const validCommands = [null, 'create', "dump-config", "deploy", "encrypt", "create-neo4j-server", "create-s3-bucket", "create-kms-key", "init", "status"]
const { command, argv } = commandLineCommands(validCommands)

// MAIN
if (command == null) {
    console.log("Usage: community-graph [create|update|dump-config|encrypt]");
} else {
    if (command == "create") {
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
    } else if (command == "deploy") {
        let welcome = new Promise((resolve, reject) => {
            console.log("Deploying the community graph's lambdas to AWS");
            resolve();
        });

        welcome
        .then(prereqs.checkPythonVersion)
        .then(prereqs.removePyCache).then(data => {
            const serverless = new Serverless({});
            const CLI = require('serverless/lib/classes/CLI');

            CLI.prototype.processInput = function () {
                return { commands: ['deploy'], options: { help: false } };
            };

            serverless.cli = CLI;
            return serverless.init().then(() => serverless.run());
        }).then(data => {
            console.log("Lambdas deployed");
        }).catch(err => {
            console.error("Error updating community graph:", err);
            process.exit(1);
        });
    } else if (command == "dump-config") {
        var config = JSON.parse(fs.readFileSync('communitygraph.json', 'utf8'));
        console.log(JSON.stringify(config, null, 4));
    } else if (command == "encrypt") {
        var config = JSON.parse(fs.readFileSync('communitygraph.json', 'utf8'));
        let kmsKey = config["credentials"]["keyArn"]
        console.log("Encrypting with KMS Key: " + kmsKey);

        let args = parseArgs(argv);
        if (!args["value"]) {
            console.log("Usage: community-graph encrypt --value [Unencrypted Value]")
        } else {
            let valueToEncrypt = args["value"];
            let params = { KeyId: kmsKey, Plaintext: valueToEncrypt };

            kms.encrypt(params).promise()
                .then(data => console.log(data.CiphertextBlob.toString('base64')))
                .catch(err => console.log(err, err.stack));
        }
    } else if(command == "init") {
        let welcome = new Promise((resolve, reject) => {
            console.log("Initialising the community graph");
            resolve();
        });

        welcome
        .then(prereqs.checkPythonVersion)
        .then(prereqs.removePyCache).then(data => {
            const serverless = new Serverless({});
            const CLI = require('serverless/lib/classes/CLI');

            CLI.prototype.processInput = function () {
                return { commands: ['invoke'], options: { help: false, function: "constraints" } };
            };

            serverless.cli = CLI;
            return serverless.init().then(() => serverless.run());
        }).then(data => {
            console.log("Community graph initialised.");
        }).catch(err => {
            console.error("Error updating community graph:", err);
            process.exit(1);
        });
    } else if(command == "status") {
        let welcome = new Promise((resolve, reject) => {
            console.log("Checking the status of the community graph");
            resolve();
        });

        welcome.then(data => {
            let config = JSON.parse(fs.readFileSync('communitygraph.json', 'utf8'));

            console.log("Neo4j browser URI: http://" + config["serverUrl"] + ":7474");
            let s3Bucket = config["s3Bucket"];
            console.log(`Summary page: https://s3.amazonaws.com/${s3Bucket}/${s3Bucket}.html`);
        }).catch(err => {
            console.error("Error retrieving the status of the community graph:", err);
            process.exit(1);
        });
    }  else if (command == "create-neo4j-server") {
        console.log("Creating a Neo4j server");

        let args = parseArgs(argv);
        let dryRun = "dry-run" in args;
        console.log("Dry run?:" + dryRun);

        let serverParams = {};
        serverParams.keyName = "community-graph-golang-" + uuidv4();
        serverParams.groupName = "community-graph-security-golang-" + uuidv4();

        ec2.createKeyPair({ KeyName: serverParams.keyName, DryRun: dryRun }).promise().then(data => {
            console.log(data);
            return ec2.createSecurityGroup({ Description: "Community Graph Security Group", GroupName: serverParams.groupName, DryRun: dryRun }).promise()
        }).then(data => {
            console.log("Created Group Id:" + data.GroupId);
            serverParams["groupId"] = data.GroupId;
            var ports = [22, 7474, 7473, 7687];
            return Promise.all(ports.map(function (port) {
                let params = {
                    GroupId: data.GroupId,
                    IpProtocol: "tcp",
                    FromPort: port,
                    ToPort: port,
                    CidrIp: "0.0.0.0/0",
                    DryRun: dryRun
                };
                return ec2.authorizeSecurityGroupIngress(params).promise();
            }));
        }).then(data => {
            console.log(data);
            let params = {
                ImageId: "ami-f03c4fe6",
                MinCount: 1,
                MaxCount: 1,
                InstanceType: "m3.medium",
                KeyName: serverParams.keyName,
                SecurityGroupIds: [serverParams.groupId],
                DryRun: dryRun
            };
            return ec2.runInstances(params).promise();
        }).then(data => {
            let ourInstance = data.Instances[0];
            console.log("Instance Id: " + ourInstance.InstanceId);

            let params = {
                InstanceIds: [ourInstance.InstanceId]
            };
            return ec2.waitFor("instanceRunning", params).promise();
        }).then(data => {
            let reservations = data.Reservations;
            let instances = reservations[0].Instances;
            console.log("Public DNS Name: " + instances[0].PublicDnsName)
        }).catch(err => console.log(err, err.stack));
    } else if (command == "create-s3-bucket") {
        let config = JSON.parse(fs.readFileSync('communitygraph.json', 'utf8'));
        let communityName = config["communityName"];
        let s3BucketName = "community-graph-" + communityName.toLowerCase();

        _createS3Bucket(s3BucketName)
            .then(data => {
                console.log("Created bucket: " + data.Location.replace("/", ""));
            }).catch(err => {
                console.log(err);
            });
    } else if(command == "create-kms-key") {
        let args = parseArgs(argv);
        let config = JSON.parse(fs.readFileSync('communitygraph.json', 'utf8'));
        let communityName = config["communityName"];

        _createKMSKey()
            .then(data => {
                console.log("Created KMS key: " + data.KeyMetadata.Arn);
                return _createKMSKeyAlias(communityName, data.KeyMetadata.Arn );
            }).then(data => {
                console.log("Assigned alias to KMS key");
            }).catch(err => {
                console.log(err, err.stack);
            });
    }
}