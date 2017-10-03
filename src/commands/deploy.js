const prereqs = require("../prereqs");
const Serverless = require('serverless');
const program = require('commander');

program.parse(process.argv);

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