var async   = require('async'),
    https   = require('follow-redirects').https,
    http    = require('http'),
    fs      = require('fs'),
    chalk   = require('chalk'),
    Serverless = require('serverless'),
    opn     = require('opn');

function welcomeToCommunityGraph(callback) {
  console.log("Hello and welcome to the community graph!")
  return callback(null);
}

function deployLambdas(callback) {
  const serverless = new Serverless({});
  const CLI = require('serverless/lib/classes/CLI');

  CLI.prototype.processInput = function() {
    return { commands: ['deploy'], options: { help: false } };
  };
  //
  // CLI.prototype.consoleLog = function(message) {
  //   (this._internal = this._internal || []).push(message);
  // };
  //
  // CLI.prototype.outputLog = function(message) {
  //   console.log(this._internal);
  // };

  serverless.cli = CLI;

  return serverless.init()
  .then(() => serverless.run())
  // .then(() => serverless.cli.outputLog())
  .catch((ex) => { console.error(ex); });
}


// MAIN
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
