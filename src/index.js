var async   = require('async'),
    https   = require('follow-redirects').https,
    http    = require('http'),
    fs      = require('fs'),
    chalk   = require('chalk'),
    Serverless = require('serverless'),
    prompt = require('prompt'),
    AWS = require("aws-sdk"),
    opn     = require('opn'),
    commandLineCommands = require('command-line-commands');

let rawParams = {};
let communityGraphParams = {
    credentials: {
        write: { },
        readonly: { }
    }
};

let kms = new AWS.KMS({'region': 'us-east-1'});
let s3 = new AWS.S3({'region': 'us-east-1'});

function welcomeToCommunityGraph(callback) {
  console.log("Hello and welcome to the community graph!")
  return callback(null);
}

function getParameters(callback)  {
    console.log("Provide us some parameters so we can get this show on the road:")
    prompt.start();

    var schema = {
    properties: {
      communityName: {
        description: 'Name of your community',
        required: true
      },
      serverUrl: {
        description: "URL of your Neo4j server (leave blank if you don't have one, and one will be created)",
      },
      serverUsername: {
        description: 'Neo4j server username',
        ask: function() {
          return prompt.history('serverUrl').value != "";
        }
      },
      serverPassword: {
        description: 'Neo4j server password',
        ask: function() {
          return prompt.history('serverUrl').value != "";
        }
      },
      readOnlyServerUsername: {
        description: 'Neo4j read only server username',
        ask: function() {
          return prompt.history('serverUrl').value != "";
        }
      },
      readOnlyServerPassword: {
        description: 'Neo4j read only server password',
        ask: function() {
          return prompt.history('serverUrl').value != "";
        }
      },
      tag: {
        description: 'Search term for use on GitHub/SO/Meetup (Ctrl + C when all tags added)',
        required: true,
        type: 'array',
        minItems: 1
      },
      twitterSearch: {
        description: 'Search term for finding links on Twitter',
        required: true
      },
      twitterBearer: {
        description: 'Twitter Bearer',
        required: true
      },
      githubToken: {
        description: 'GitHub Token',
        required: true
      },
      meetupApiKey: {
        description: 'Meetup API key',
        required: true
      },
      s3Bucket: {
        description: "Name of S3 bucket where the dashboard should be generated (leave blank if you don't have one, and one will be created)",
      },
      logo: {
        description: 'Link to a logo to use for your community graph',
      },
      kmsKeyArn: {
        description: "KMS Key Arn (leave blank if you don't have one, and one will be created)",
      },
    }
  };

  prompt.get(schema, function (err, result) {
    //
    // Log the results.
    //
    console.log('Command-line input received:');
    console.log('  community name: ' + result.communityName);
    console.log('  serverUrl: ' + result.serverUrl);
    console.log('  serverUsername: ' + result.serverUsername);
    console.log('  serverPassword: ' + result.serverPassword);
    rawParams = result;
    return callback(null);
  });

}

function createKMSKey(callback) {
    kms.createKey({}, function (err, data) {
        if (err) {
            console.log(err, err.stack); // an error occurred
            callback(null);
        }
        else {
            rawParams.kmsKeyArn = data.KeyMetadata.Arn
            callback(null);
        }
    });
};

function createKMSKeyAlias(callback) {
    let kmsKeyArn = rawParams.kmsKeyArn;
    let communityName = rawParams.communityName;

    let createAliasParams = {
        AliasName: "alias/CommunityGraphCLI-" + communityName,
        TargetKeyId: kmsKeyArn
    };
    kms.createAlias(createAliasParams, function (err, data) {
        if (err) {
            console.log(err, err.stack); // an error occurred
            callback(null);
        }
        else {
            callback(null);
        }
    });
}

function createS3Bucket(callback) {
    let s3BucketName = "marks-test-" + rawParams.communityName.toLowerCase();
    var params = {
        Bucket: s3BucketName,
        ACL: "public-read",
        GrantRead: "*"
    };

    s3.createBucket(params, function(err, data) {
        if(err) {
            console.log(err, err.stack);
            callback(null);
        } else {
            console.log(data);
            rawParams.s3Bucket = data.Location.replace("/", "");
            callback(null);
        }
    });
}

function encryptGitHubToken(callback) {
    let valueToEncrypt = rawParams.githubToken;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function(err, data) {
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

    kms.encrypt(params, function(err, data) {
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

function encryptTwitterBearer(callback) {
    let valueToEncrypt = rawParams.twitterBearer;
    var params = {
        KeyId: rawParams.kmsKeyArn,
        Plaintext: valueToEncrypt
    };

    kms.encrypt(params, function(err, data) {
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

    kms.encrypt(params, function(err, data) {
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

    kms.encrypt(params, function(err, data) {
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
    communityGraphParams.credentials.readonly.user = rawParams.readOnlyServerUsername;
    communityGraphParams.credentials.write.user = rawParams.serverUsername;

    try {
        fs.writeFileSync("communitygraph.json", JSON.stringify(communityGraphParams));
    } catch (e) {
        callback(null);
    }
}

function deployLambdas(callback) {
  const serverless = new Serverless({});
  const CLI = require('serverless/lib/classes/CLI');

  CLI.prototype.processInput = function() {
    return { commands: ['deploy'], options: { help: false } };
  };

  serverless.cli = CLI;

  return serverless.init()
  .then(() => serverless.run())
  .catch((ex) => { console.error(ex); });
}


const validCommands = [ null, 'create', "dump-config", "update" ]
const { command, argv } = commandLineCommands(validCommands)

// MAIN
if(command == null) {
    console.log("Usage: community-graph [create|update]");
} else {
    if(command == "create") {
        async.waterfall([
          welcomeToCommunityGraph,
          getParameters,
          function(callback) {
            if(!rawParams.kmsKeyArn) {
                async.waterfall([
                    createKMSKey,
                    createKMSKeyAlias
                ], callback);
            } else {
                callback(null)
            }
          },
          function(callback) {
            if(!rawParams.s3Bucket) {
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
          encryptWritePassword,
          encryptReadOnlyPassword,
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
    } else if(command == "update") {
        async.waterfall([
          welcomeToCommunityGraph,
          deployLambdas
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
    } else if(command == "dump-config") {
        var config = JSON.parse(fs.readFileSync('communitygraph.json', 'utf8'));
        console.log(JSON.stringify(config, null, 4));
    }
}