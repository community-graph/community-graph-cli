const fs = require("fs");

const { execFile } = require('child_process');

function checkPythonVersion(data) {
    return new Promise((resolve, reject) => {
        execFile('python', ['--version'], function (err, stdout, stderr) {
            let systemPython = (stdout.toString() || stderr.toString()).replace("\n", "");
            if (systemPython.includes("3.6")) {
                resolve("Python 3.6 installed");
            } else {
                reject("The community graph runs on Python 3.6. Your system python is: " + systemPython);
            }
        });
    })
}

function checkCommunityGraphExists(data) {
    return new Promise((resolve, reject) => {
        fs.stat("communitygraph.json", function (err, stat) {
            if (err) { 
                resolve(data);
            } else {
                reject("communitygraph.json already exists. If you want to run this command move that file and try again.")
            }
        });
    });
}

var deleteFolderRecursive = function(path) {
    if( fs.existsSync(path) ) {
      fs.readdirSync(path).forEach(function(file,index){
        var curPath = path + "/" + file;
        if(fs.lstatSync(curPath).isDirectory()) { // recurse
          deleteFolderRecursive(curPath);
        } else { // delete file
          fs.unlinkSync(curPath);
        }
      });
      fs.rmdirSync(path);
    }
  };

function removePyCache(data) { 
    return new Promise((resolve, reject) => {
        deleteFolderRecursive("__pycache__");
        resolve(data);
    });
}

module.exports = {
    checkPythonVersion: checkPythonVersion,
    checkCommunityGraphExists: checkCommunityGraphExists,
    removePyCache: removePyCache
}