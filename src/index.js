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
    exec = require('child_process').exec;

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

function welcomeToCommunityGraph(callback) {
    console.log("Hello and welcome to the community graph!")
    return callback(null);
}

function getParameters(callback) {
    console.log("Provide us some parameters so we can get this show on the road:")
    prompt.start();
    
    prompt.get(cli.schema, function (err, result) {
        console.log('Command-line input received:');
        console.log(result);
        rawParams = result;
        return callback(null);
    });

}

function createKMSKey(callback) {
    _createKMSKey()
        .then(data => {
            rawParams.kmsKeyArn = data.KeyMetadata.Arn
            callback(null);
        }).catch(err => {
            console.log(err, err.stack); // an error occurred
            callback(null);
        });    
};

function createKMSKeyAlias(callback) {
    let kmsKeyArn = rawParams.kmsKeyArn;
    let communityName = rawParams.communityName;

    _createKMSKeyAlias(communityName, kmsKeyArn)
        .then(data => {
            callback(null);
        }).catch(err => {
            console.log(err, err.stack);
            callback(null);
        });
}

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

function createS3Bucket(callback) {
    let s3BucketName = "marks-test-" + rawParams.communityName.toLowerCase();    
    _createS3Bucket(s3BucketName)
        .then(data => {
            rawParams.s3Bucket = data.Location.replace("/", "");
            callback(null);
        })
        .catch(err => {
            console.log(err, err.stack);
            callback(null);
        });        
}

function _createS3Bucket(s3BucketName) {
    console.log("Creating bucket: " + s3BucketName);    
    var params = { Bucket: s3BucketName, ACL: "public-read" };    
    return s3.createBucket(params).promise()    
}

function encryptGitHubToken(callback) {
    let valueToEncrypt = rawParams.githubToken;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function (err, data) {
        if (err) {
            console.log(err, err.stack);
            callback(null);
        }
        else {
            communityGraphParams.credentials.githubToken = data.CiphertextBlob.toString('base64');
            callback(null);
        }
    });
}

function encryptMeetupApiKey(callback) {
    let valueToEncrypt = rawParams.meetupApiKey;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function (err, data) {
        if (err) {
            console.log(err, err.stack);
            callback(null);
        }
        else {
            communityGraphParams.credentials.meetupApiKey = data.CiphertextBlob.toString('base64');
            callback(null);
        }
    });
}

function encryptStackOverflowApiKey(callback) {
    let valueToEncrypt = rawParams.stackOverflowApiKey;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function (err, data) {
        if (err) {
            console.log(err, err.stack);
            callback(null);
        }
        else {
            communityGraphParams.credentials.stackOverflowApiKey = data.CiphertextBlob.toString('base64');
            callback(null);
        }
    });
}

function encryptTwitterBearer(callback) {
    let valueToEncrypt = rawParams.twitterBearer;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function (err, data) {
        if (err) {
            console.log(err, err.stack);
            callback(null);
        }
        else {
            communityGraphParams.credentials.twitterBearer = data.CiphertextBlob.toString('base64');
            callback(null);
        }
    });
}

function encryptWritePassword(callback) {
    let valueToEncrypt = rawParams.serverPassword;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function (err, data) {
        if (err) {
            console.log(err, err.stack);
            callback(null);
        }
        else {
            communityGraphParams.credentials.write.password = data.CiphertextBlob.toString('base64');
            callback(null);
        }
    });
}

function encryptReadOnlyPassword(callback) {
    let valueToEncrypt = rawParams.readOnlyServerPassword;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function (err, data) {
        if (err) {
            console.log(err, err.stack);
            callback(null);
        }
        else {
            communityGraphParams.credentials.readonly.password = data.CiphertextBlob.toString('base64');
            callback(null);
        }
    });
}

function writeCommunityGraphJson(callback) {
    communityGraphParams.communityName = rawParams.communityName;
    communityGraphParams.tag = rawParams.tag;
    communityGraphParams.serverUrl = rawParams.serverUrl;
    communityGraphParams.logo = rawParams.logo;
    communityGraphParams.s3Bucket = rawParams.s3Bucket;
    communityGraphParams.twitterSearch = rawParams.twitterSearch;

    communityGraphParams.credentials.keyArn = rawParams.kmsKeyArn;
    communityGraphParams.credentials.readonly.user = rawParams.readOnlyServerUsername || "neo4j";
    communityGraphParams.credentials.write.user = rawParams.serverUsername || "neo4j";

    try {
        fs.writeFileSync("communitygraph.json", JSON.stringify(communityGraphParams));
    } catch (e) {
        callback(null);
    }
}

function deployLambdas(callback) {
    const serverless = new Serverless({});
    const CLI = require('serverless/lib/classes/CLI');

    CLI.prototype.processInput = function () {
        return { commands: ['deploy'], options: { help: false } };
    };

    serverless.cli = CLI;

    return serverless.init()
        .then(() => serverless.run())
        .catch((ex) => { console.error(ex); });
}


const validCommands = [null, 'create', "dump-config", "update", "encrypt", "create-neo4j-server", "create-s3-bucket", "create-kms-key"]
const { command, argv } = commandLineCommands(validCommands)

// MAIN
if (command == null) {
    console.log("Usage: community-graph [create|update|dump-config|encrypt]");
} else {
    if (command == "create") {
        async.waterfall([
            welcomeToCommunityGraph,
            getParameters,
            function (callback) {
                if (!rawParams.kmsKeyArn) {
                    async.waterfall([
                        createKMSKey,
                        createKMSKeyAlias
                    ], callback);
                } else {
                    callback(null)
                }
            },
            function (callback) {
                if (!rawParams.s3Bucket) {
                    async.waterfall([
                        createS3Bucket,
                    ], callback);
                } else {
                    callback(null)
                }
            },
            encryptMeetupApiKey,
            encryptTwitterBearer,
            encryptGitHubToken,
            encryptStackOverflowApiKey,
            function (callback) {
                if(!rawParams.serverUrl) {
                    console.log("No server URL provided so no password encryption for now");
                    callback(null);
                } else {
                    async.waterfall([
                        encryptWritePassword,
                        encryptReadOnlyPassword
                    ], callback)
                }
            },            
            writeCommunityGraphJson
        ], function (err, result) {
            if (err) {
                console.log("ERROR - exiting");
                console.log(err);
                process.exit(1);
            } else {
                if (result) {
                    var name = result.name || "";
                    console.log("\nThanks " + name + "! Please email " + chalk.underline("devrel@neo4j.com") + " with any questions or feedback.");
                    process.exit(0);
                }
            }
        });
    } else if (command == "update") {
        let welcome = new Promise((resolve, reject) => {
            console.log("Deploying the community graph's lambdas to AWS");
            resolve();
        });

        welcome.then(data => {
            return prereqs.checkPythonVersion(data);
        }).then(data => {
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
            console.error("Error while deploying lambdas:", err);
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
    } else if (command == "create-neo4j-server") {
        console.log("Creating a Neo4j server");

        // let params = { KeyName: "community-graph-nahi", DryRun: true }
        // ec2.createKeyPair(params).promise()
        //     .then(data => console.log(data))
        //     .catch(err => console.log(err, err.stack));

        let args = parseArgs(argv);
        let dryRun = "dry-run" in args;
        console.log("Dry run?:" + dryRun)

        let serverParams = {};

        let params = { Description: "Community Graph Security Group", GroupName: "community-graph-security-group2", DryRun: dryRun }
        ec2.createSecurityGroup(params).promise()
            .then(data => {
                console.log("Created Group Id:" + data.GroupId);
                serverParams["groupId"] = data.GroupId;
                var ports = [7474, 7473, 7687];
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
            })
            .then(data => {
                console.log(data);
                let params = {
                    ImageId: "ami-f03c4fe6",
                    MinCount: 1,
                    MaxCount: 1,
                    InstanceType: "m3.medium",
                    SecurityGroupIds: [serverParams.groupId],
                    DryRun: dryRun
                };
                return ec2.runInstances(params).promise();
            })
            .then(data => {
                let ourInstance = data.Instances[0];
                console.log("Instance Id:" + ourInstance.InstanceId);

                let params = {
                    InstanceIds: [ourInstance.InstanceId]
                };
                return ec2.waitFor("instanceRunning", params).promise();
            })
            .then(data => {
                let reservations = data.Reservations;
                let instances = reservations[0].Instances;
                console.log(instances[0].PublicDnsName)
            })
            .catch(err => console.log(err, err.stack));
    } else if (command == "create-s3-bucket") {
        let config = JSON.parse(fs.readFileSync('communitygraph.json', 'utf8'));
        let communityName = config["communityName"];        
        let s3BucketName = "marks-test-" + communityName.toLowerCase();

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