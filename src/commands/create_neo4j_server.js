const program = require('commander');
const fs = require('fs');
const aws = require("../aws")

program
    .option('-c, --config [configFile]', 'Config file')
    .parse(process.argv);