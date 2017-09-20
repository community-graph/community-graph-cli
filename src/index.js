var async   = require('async'),
    https   = require('follow-redirects').https,
    http    = require('http'),
    fs      = require('fs'),
    chalk   = require('chalk'),
    Serverless = require('serverless'),
    prompt = require('prompt'),
    AWS = require("aws-sdk"),
    opn     = require('opn');

let communityGraphParams = {}

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
        description: 'Search term for finding projects on GitHub',
        required: true
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
    communityGraphParams = result;
    return callback(null);
  });

//    communityGraphParams.kmsKeyArn = "foo"

//    return callback(null)

}

function createKMSKey(callback) {
    let kms = new AWS.KMS({'region': 'us-east-1'});
    kms.createKey({}, function (err, data) {
        if (err) {
            console.log(err, err.stack); // an error occurred
            callback(null);
        }
        else {
            communityGraphParams.kmsKeyArn = data.KeyMetadata.Arn
            callback(null);
        }
    });
};

function createKMSKeyAlias(callback) {
    let kmsKeyArn = communityGraphParams.kmsKeyArn;
    let communityName = communityGraphParams.communityName;

    let kms = new AWS.KMS({'region': 'us-east-1'});
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


function after(callback) {
    console.log('after everything');
    console.log(communityGraphParams);
    return callback(null);
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


// MAIN
async.waterfall([
  welcomeToCommunityGraph,
  getParameters,
  function(callback) {
    if(!communityGraphParams.kmsKeyArn) {
        async.waterfall([
            createKMSKey,
            createKMSKeyAlias
        ], callback);
    } else {
        callback(null)
    }
  },
//  deployLambdas
  after
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
