var AWS = require("aws-sdk")

let regionParams = { 'region': 'us-east-1' }
let s3 = new AWS.S3(regionParams);

function createS3Bucket(s3BucketName) {
    console.log("Creating bucket: " + s3BucketName);
    var params = { Bucket: s3BucketName, ACL: "public-read" };
    return s3.createBucket(params).promise()
}

module.exports = {
    createS3Bucket: createS3Bucket
}