function checkPythonVersion(data)  {
    return new Promise((resolve, reject) => {
        exec('python --version', function (err, stdout, stderr) {
            let systemPython = (stdout.toString() || stderr.toString()).replace("\n", "");
            if (systemPython.includes("3.6")) {
                resolve("Python 3.6 installed");
            } else {
                reject("The community graph runs on Python 3.6. Your system python is: " + systemPython);
            }
        });
    })
}

module.exports = {
    checkPythonVersion: checkPythonVersion
}